import os  # Работа с файловой системой / File system operations
import cv2  # OpenCV для чтения изображений / OpenCV for image handling
import time  # Паузы и таймеры / Delays and timing
import json  # Работа с JSON-файлами / JSON file handling
from ultralytics import YOLO  # Модель YOLO от Ultralytics / Ultralytics YOLO model
import sys  # Системные функции / System-specific parameters
import signal  # Обработка системных сигналов / OS signal handling
from typing import Tuple, List, Dict  # Типы для аннотаций / Type hints
import torch  # PyTorch для CUDA-проверок и режима инференса / PyTorch for CUDA checks & inference mode
import stat      # Манипуляция атрибутами файла (снять read-only)
# === WinAPI named mutex (single instance) / Именованный мьютекс (единственный экземпляр) ===
import atexit  # Финализатор для закрытия дескриптора / Finalizer to close handle
import ctypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)  # kernel32.dll для мьютекса / kernel32 for mutex
CreateMutexW = kernel32.CreateMutexW                      # Создание/открытие мьютекса / Create/Open mutex
CloseHandle = kernel32.CloseHandle                        # Закрытие дескриптора / Close handle
ERROR_ALREADY_EXISTS = 183                                # Код: мьютекс уже существует / Mutex already exists

# === Single-instance guard (detector) / Защита от второго экземпляра (детектор) ===
MUTEX_NAME = r"Global\COUNTERPICK_DETECTOR_MUTEX"  # Уникальное имя для детектора / Unique name for detector
hMutex = CreateMutexW(None, False, ctypes.c_wchar_p(MUTEX_NAME))
if not hMutex:
    sys.exit(1)  # Не получили дескриптор — выходим / Failed to get handle -> exit

if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    # Экземпляр уже запущен — тихо завершаемся / Already running — exit quietly
    CloseHandle(hMutex)
    sys.exit(0)

atexit.register(lambda: CloseHandle(hMutex))  # Закрыть мьютекс при выходе / Release on exit
# === END single-instance guard ===


# === GPU required check / Проверка обязательной доступности CUDA ===
try:
    # Базовая проверка доступности CUDA / Basic CUDA availability
    if not torch.cuda.is_available() or torch.cuda.device_count() == 0:
        raise RuntimeError("CUDA not available (no device)")

    # Доп. проверка аллокации на GPU / Extra safety: try to allocate on GPU
    torch.zeros(1, device="cuda")

except Exception as e:
    # Показать системное окно с ошибкой и завершиться кодом 2 / Show MessageBox and exit(2)
    try:
        from ctypes import windll, c_wchar_p
        msg = (
            "CUDA недоступна или драйвер не разрешает доступ.\n"
            "Установите драйверы NVIDIA и разрешите приложению доступ в Защитнике Windows.\n"
            f"(error: {e})"
        )
        windll.user32.MessageBoxW(
            0, c_wchar_p(msg), c_wchar_p("Counterpick — GPU required"), 0x10  # MB_ICONERROR
        )
    except Exception:
        pass
    sys.exit(2)
# === END GPU check ===

# === Обработка сигналов завершения / Termination signal handling ===
def handle_exit(signum, frame):
    sys.exit(0)  # Корректно завершить процесс / Exit process cleanly

signal.signal(signal.SIGINT, handle_exit)   # Обработчик Ctrl+C / Handle Ctrl+C (SIGINT)
signal.signal(signal.SIGTERM, handle_exit)  # Обработчик SIGTERM / Handle SIGTERM

# === Пути / Paths ===
# Для .exe: опираемся на папку рядом с исполняемым файлом / For .exe: base on folder near executable
BASE_DIR = os.path.dirname(sys.executable)

SAVE_DIR = os.path.join(BASE_DIR, 'tmp_screenshots')          # Папка со скриншотами / Screenshots folder
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')                # Путь к весам YOLO / YOLO weights path
COUNTERS_PATH = os.path.join(BASE_DIR, 'counters.json')       # Контрпики / Counters DB path
OVERLAY_JSON_PATH = os.path.join(BASE_DIR, 'overlay_data.json')  # Данные для оверлея / Overlay data
STATE_PATH = os.path.join(BASE_DIR, 'overlay_state.json')        # Состояние оверлея / Overlay state

# === Параметры модели / Model params ===
imgsz = 640    # Размер входа модели / Model input size
conf = 0.25    # Порог уверенности / Confidence threshold
iou = 0.6      # Порог NMS IOU / NMS IoU threshold
MIN_HEIGHT = 30  # Минимальная высота бокса — меньшие отбрасываем / Min bbox height filter

# === Подготовка папки / Ensure folder exists ===
os.makedirs(SAVE_DIR, exist_ok=True)  # Создать папку при отсутствии / Create if not exists

# === overlay_data.json — очистка на старте (пустая строка = «нет данных») /
# === Clear overlay_data.json at start (empty string = "no data") ===
with open(OVERLAY_JSON_PATH, "w", encoding="utf-8") as f:
    f.write("")  # Сброс содержимого / Reset file contents

# === Утилиты для overlay_state.json / Helpers for overlay_state.json ===
def _read_state() -> Tuple[bool, bool]:
    """Возвращает (enabled, detected). Если файла нет/битый — (True, False).
    Returns (enabled, detected). If missing/corrupt — (True, False)."""
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            st = json.load(f)  # Парсим JSON / Parse JSON
        enabled = bool(st.get("enabled", True))    # Флаг включения / Enabled flag
        detected = bool(st.get("detected", False)) # Флаг наличия детектов / Detected flag
        return enabled, detected
    except Exception:
        return True, False  # Значения по умолчанию / Defaults on error

def _robust_replace(src: str, dst: str, retries: int = 5, delay: float = 0.1) -> None:
    """
    Надёжная замена файла с коротким ретраем.
    Пытается os.replace(src, dst) несколько раз, снимая read-only и выдерживая паузу.
    :param src: временный файл (.tmp), который хотим переименовать
    :param dst: целевой файл, который нужно атомарно заменить
    :param retries: кол-во дополнительных попыток после первой
    :param delay: задержка между попытками в секундах
    """
    last_err = None  # <- инициализация переменной заранее
    # Первая попытка — самая быстрая
    try:
        os.replace(src, dst)  # Атомарная замена на Windows / Atomic replace
        return                # Успех — выходим
    except PermissionError:
        # Падать не спешим — пойдём в цикл ретраев
        pass
    except OSError as e:
        # Иногда это может быть sharing violation как OSError — тоже ретраим
        last_err = e

    # Ретраи: короткие и безопасные
    for _ in range(retries):
        # Снимаем возможный read-only с целевого файла (если он существует)
        try:
            if os.path.exists(dst):
                os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)  # rw- для owner
        except Exception:
            # Игнорируем сбои chmod — всё равно попробуем replace
            pass

        try:
            os.replace(src, dst)  # Повторная попытка замены
            return                # Успех
        except PermissionError as e:
            last_err = e          # Сохраняем последнюю ошибку
        except OSError as e:
            last_err = e          # Любая OSError — тоже пробуем ещё
        time.sleep(delay)         # Короткая пауза, чтобы читатель отпустил файл

    # Если все попытки исчерпаны — аккуратно удалить src, чтобы не висел .tmp, и пробросить ошибку
    try:
        if os.path.exists(src):
            os.remove(src)  # Чистим временный файл, чтобы не накапливались .tmp
    except Exception:
        pass
    # Финально пробрасываем последнюю ошибку — пусть упадёт явно, если совсем плохо
    if last_err:
        raise last_err
    else:
        # Теоретически сюда не попадём, но на всякий случай
        raise PermissionError("Failed to replace file after retries")

def _write_state_detected(detected: bool) -> None:
    """Атомарно перезаписывает overlay_state.json, сохраняя текущее 'enabled'.
    Atomically rewrites overlay_state.json, preserving current 'enabled'."""
    enabled, _ = _read_state()  # Читаем текущее enabled / Read current enabled
    data = {"enabled": enabled, "detected": bool(detected)}  # Собираем состояние / Build state dict

    tmp = STATE_PATH + ".tmp"  # Временный файл для атомарной записи / Temp file for atomic write
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)  # Пишем JSON / Write JSON
        f.flush()
        os.fsync(f.fileno())

    # Надёжная замена с коротким ретраем (фикс WinError 5)
    _robust_replace(tmp, STATE_PATH)


# === Инициализация overlay_state.json / Initialize overlay_state.json ===
if not os.path.exists(STATE_PATH):
    _write_state_detected(False)  # Создать файл с detected=False / Create with detected=False
else:
    _write_state_detected(_read_state()[1])  # Сохранить текущее detected / Preserve detected

# === Загрузка модели и контрпиков / Load model and counters ===
model = YOLO(MODEL_PATH)  # Загрузить YOLO веса / Load YOLO weights
model.to('cuda')          # Принудительно на GPU / Force model to GPU

print("CUDA device index:", torch.cuda.current_device())
print("CUDA device name:", torch.cuda.get_device_name(0))

torch.set_grad_enabled(False)  # Отключаем градиенты / Disable gradients for speed & memory

print("CUDA available:", torch.cuda.is_available())
print("Model device:", model.device)
print("Torch version:", torch.__version__)

with open(COUNTERS_PATH, 'r', encoding='utf-8') as f:
    counters_data = json.load(f)  # Загрузить базу контрпиков / Load counters DB

def get_counter_names(hero_short: str) -> List[str]:
    """Возвращает список имён контрпиков для героя.
    Returns list of counter names for a hero."""
    for entry in counters_data:  # Проходим по записям / Iterate entries
        if entry.get("hero") == hero_short:  # Совпадение героя / Match hero
            # Вернуть список имён контрпиков / Return list of counters
            return [c.get("counter") for c in entry.get("counters", []) if isinstance(c, dict)]
    return []  # Пусто, если герой не найден / Empty if not found

# === Утилиты снапшота / Snapshot helpers ===
def read_existing_overlay_list() -> List[Dict]:
    """Читает overlay_data.json как список [{hero,counters,box}], иначе возвращает пустой список.
    Reads overlay_data.json as list, else returns empty list."""
    try:
        if not os.path.exists(OVERLAY_JSON_PATH) or os.path.getsize(OVERLAY_JSON_PATH) == 0:
            return []  # Нет файла/пустой файл / Missing or empty
        with open(OVERLAY_JSON_PATH, "r", encoding="utf-8") as f:
            txt = f.read().strip()  # Читаем текст / Read text
        if txt == "":
            return []  # Пустая строка = нет данных / Empty string = no data
        obj = json.loads(txt)  # Парсим JSON / Parse JSON
        return obj if isinstance(obj, list) else []  # Только список / Ensure list
    except Exception:
        return []  # Любая ошибка — вернуть пусто / On error, empty list

def write_overlay_atomic(data_list: List[Dict]) -> None:
    """Атомарная запись снапшота (список элементов) в overlay_data.json.
    Atomic write of snapshot list into overlay_data.json."""
    tmp = OVERLAY_JSON_PATH + ".tmp"  # Временный файл / Temp file
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=2) # Запись JSON / Write JSON
        f.flush()
        os.fsync(f.fileno())

    _robust_replace(tmp, OVERLAY_JSON_PATH)  # Атомарная замена / Atomic replace

# === Основной цикл / Main loop ===
try:
    while True:
        # Берём самый ранний PNG / Pick the oldest PNG
        entries = [e for e in os.scandir(SAVE_DIR) if e.is_file() and e.name.lower().endswith('.png')]
        entries.sort(key=lambda e: e.stat().st_ctime)  # Сортировка по времени создания / Sort by ctime

        if not entries:
            time.sleep(0.5)  # Если нет файлов — подождать / Sleep when no files
            #_write_state_detected(False)  # На всякий — погасить индикатор / Ensure overlay hidden
            continue

        filepath = entries[0].path  # Путь к первому файлу / Path to the first file

        # === Безопасное чтение скрина / Safe image read ===
        # Проверяем размер файла ретраями, чтобы не ловить «сырой» PNG
        for _ in range(10):  # до ~1 сек ожидания
            try:
                size = os.path.getsize(filepath)
            except FileNotFoundError:
                size = 0
            if size >= 5000:
                break
            time.sleep(0.1)
        else:
            # Если после всех попыток файл всё ещё маленький — удаляем и пропускаем
            try:
                os.remove(filepath)
            except Exception:
                pass
            continue

        # Читаем изображение ОДИН раз
        img = cv2.imread(filepath)
        if img is None or img.size == 0:
            try:
                os.remove(filepath)  # удалить битый
            except Exception:
                pass
            continue

        # === Предикт с принудительным устройством и FP16 / Inference with forced device & FP16 ===
        try:
            with torch.inference_mode():  # Без построения графа / No graph building
                results = model.predict(
                    source=img,     # Кадр как numpy-массив / Frame as numpy array
                    imgsz=imgsz,    # Размер входа / Input size
                    conf=conf,      # Порог уверенности / Confidence threshold
                    iou=iou,        # Порог NMS IoU / NMS IoU
                    device=0,       # Только GPU:0 / Force GPU:0
                    half=True,      # FP16 на поддерживаемых картах / Use FP16 if supported
                    verbose=False   # Без лишнего лога / No console logs
                )
        except Exception as e:
            # Критическая ошибка CUDA — сообщить и завершить / CUDA runtime error — notify & exit
            try:
                from ctypes import windll, c_wchar_p
                windll.user32.MessageBoxW(
                    0,
                    c_wchar_p(f"Критическая ошибка CUDA во время инференса:\n{e}"),
                    c_wchar_p("Counterpick — GPU runtime error"),
                    0x10  # MB_ICONERROR
                )
            except Exception:
                pass
            sys.exit(3)

        r = results[0]      # Первый результат батча / First result
        boxes = r.boxes     # Детектированные боксы / Detected boxes

        if boxes is not None and len(boxes) > 0:
            _write_state_detected(True)  # Есть детекты — включить показ / Detected => show overlay

            # Внутрикадровая дедупликация по имени героя: берём бокс с макс. уверенностью
            # Per-frame dedup by hero: keep box with max confidence
            by_hero: Dict[str, Dict] = {}

            for b in boxes:
                cls_id = int(b.cls[0])  # Индекс класса / Class index
                x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int)  # Координаты бокса / BBox coords
                hero_name = model.names[cls_id]  # Короткое имя героя / Hero short name
                conf_val = float(b.conf[0]) if hasattr(b, "conf") else 1.0  # Уверенность / Confidence

                # --- фильтр по высоте бокса --- / bbox height filter
                if (y2 - y1) < MIN_HEIGHT:
                    continue  # Пропустить слишком маленький бокс / Skip small box

                if (hero_name not in by_hero) or (conf_val > by_hero[hero_name]["conf"]):
                    # Обновляем лучшую версию бокса по герою / Keep best box per hero
                    counters = get_counter_names(hero_name)  # Получить контрпики / Fetch counters
                    if counters:
                        by_hero[hero_name] = {
                            "hero": hero_name,                    # Имя героя / Hero name
                            "counters": counters[:4],             # Топ-4 контрпика / Top-4 counters
                            "box": [int(x1), int(y1), int(x2), int(y2)],  # Бокс / BBox
                            "conf": conf_val,                     # Уверенность / Confidence
                        }

            # Текущий снапшот как список без поля conf / Snapshot list without 'conf'
            current_snapshot = [
                {"hero": v["hero"], "counters": v["counters"], "box": v["box"]}
                for v in by_hero.values()
            ]

            # === добавляем только новых героев === / append only new heroes
            prev_list = read_existing_overlay_list()  # Предыдущие данные / Previous overlay list
            existing_names = {h["hero"] for h in prev_list if isinstance(h, dict)}  # Уже есть / Existing set

            new_snapshot = []  # Новые записи / Newly found heroes
            for hero_entry in current_snapshot:
                if hero_entry["hero"] not in existing_names:  # Если герой новый / If hero is new
                    new_snapshot.append(hero_entry)           # Добавить / Append

            # Если появились новые герои — обновляем файл / Update file if new heroes appeared
            if new_snapshot:
                merged = prev_list + new_snapshot  # Объединить с прошлыми / Merge with previous
                write_overlay_atomic(merged)       # Атомарно записать / Atomic write

        else:
            # Детекций нет — только погасить показ; данные не трогаем
            # No detections — only hide overlay; keep data intact
            _write_state_detected(False)

        # Удаляем обработанный скрин / Remove processed screenshot
        try:
            os.remove(filepath)
        except Exception:
            pass

finally:
    # При выходе гасим детект / On exit, hide overlay
    try:
        _write_state_detected(False)  # detected=False на выходе / Set detected=False on exit
    except Exception:
        pass
    cv2.destroyAllWindows()  # Закрыть все окна OpenCV (если были) / Close any OpenCV windows
