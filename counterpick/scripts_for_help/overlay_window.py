import sys   # Доступ к системным параметрам / Access to system parameters
import os    # Работа с путями и файлами / Path and file operations
import json  # Чтение/запись JSON / Read/write JSON
from PyQt5.QtWidgets import QApplication, QWidget  # Приложение и окно / App and window
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPixmap  # Шрифт, цвета, рисование / Font, colors, drawing
from PyQt5.QtCore import Qt, QTimer, QRect  # Флаги окна, таймеры, прямоугольник / Window flags, timers, rect
import signal  # Обработка сигналов ОС / OS signal handling
# === WinAPI named mutex (single instance) / Именованный мьютекс (единственный экземпляр) ===
import ctypes, atexit  # Импорты для работы с WinAPI и финализации / WinAPI + finalizer

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)  # Загрузка kernel32.dll / Load kernel32.dll
CreateMutexW = kernel32.CreateMutexW                      # Функция создания мьютекса / Create/Open mutex
CloseHandle = kernel32.CloseHandle                        # Закрытие дескриптора / Close handle
ERROR_ALREADY_EXISTS = 183                                # Код ошибки "уже существует" / "Already exists" code

MUTEX_NAME = r"Global\COUNTERPICK_OVERLAY_MUTEX"  # Уникальное имя мьютекса / Unique mutex name
hMutex = CreateMutexW(None, False, ctypes.c_wchar_p(MUTEX_NAME))  # Создаём мьютекс / Create mutex
if not hMutex:
    sys.exit(1)  # Не удалось создать — выходим / Failed to create — exit

if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    CloseHandle(hMutex)  # Освобождаем хэндл / Release handle
    sys.exit(0)          # Уже запущен — выходим / Already running — exit

atexit.register(lambda: CloseHandle(hMutex))  # Гарантированно освободить при завершении / Release on exit
# === END single-instance guard ===

# === Сигналы завершения / Termination signals ===
def handle_exit(signum, frame):
    sys.exit(0)  # Корректное завершение процесса / Clean process exit

signal.signal(signal.SIGINT, handle_exit)   # Обработчик Ctrl+C / Handle Ctrl+C (SIGINT)
signal.signal(signal.SIGTERM, handle_exit)  # Обработчик SIGTERM / Handle SIGTERM

# === Пути / Paths ===
BASE_DIR = os.path.dirname(sys.executable)   # Папка, где лежит скрипт / Folder of this script
OVERLAY_DATA_PATH = os.path.join(BASE_DIR, 'overlay_data.json')  # Данные о героях / Heroes overlay data
STATE_PATH = os.path.join(BASE_DIR, 'overlay_state.json')        # Состояние оверлея / Overlay state
ICON_FOLDER = os.path.join(BASE_DIR, 'hero_icons')         # Папка иконок героев / Hero icons folder

# === Зоны пиков / Pick zones ===
RADIANT_ZONE = (1465, 215, 1540, 715)  # Прямоугольник зоны Radiant / Radiant zone rect
DIRE_ZONE    = (1575, 215, 1650, 715)  # Прямоугольник зоны Dire / Dire zone rect

# === Настройки иконок / Icons settings ===
ICON_WIDTH = 46                 # Ширина иконки / Icon width
ICON_HEIGHT_RATIO = 0.45        # Высота иконки как доля высоты бокса героя / Icon height ratio of hero box
LEFT_COLUMN_X = 1343            # X-координата левой колонки / Left column X
RIGHT_COLUMN_X = 1720           # X-координата правой колонки / Right column X

# Минимальная высота бокса героя для перерисовки (иначе держим старое) /
# Minimal hero box height to redraw (otherwise keep the last one)
MIN_BOX_H_FOR_DRAW = 40  # Под твой UI / Tuned for your UI

# === IOU / Перекрытие прямоугольников ===
def intersection_over_union(boxA, boxB):
    # Расчёт пересечения / Compute intersection
    xA = max(boxA[0], boxB[0]); yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]); yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA); interH = max(0, yB - yA)
    interA = interW * interH  # Площадь пересечения / Intersection area
    if interA == 0: return 0.0  # Нет пересечения / No overlap
    boxAA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])  # Площадь boxA / boxA area
    return interA / float(boxAA)  # IOU относительно boxA / IOU w.r.t. boxA

# === Фокус окна: активно ли «Dota 2»? (без pywin32) /
# === Foreground check: is "Dota 2" active? (no pywin32) ===
user32 = ctypes.windll.user32                           # Доступ к User32 / Access User32
GetForegroundWindow = user32.GetForegroundWindow        # HWND активного окна / Foreground HWND
GetWindowTextW = user32.GetWindowTextW                  # Чтение заголовка окна / Read window title
GetWindowTextLengthW = user32.GetWindowTextLengthW      # Длина заголовка / Title length

def is_dota_foreground() -> bool:
    """Проверка: в фокусе ли окно с заголовком 'Dota 2' / Check if 'Dota 2' window is foreground."""
    try:
        hwnd = GetForegroundWindow()            # Получить активное окно / Get active window
        if not hwnd:
            return False                        # Нет окна в фокусе / No foreground window
        length = GetWindowTextLengthW(hwnd)     # Длина заголовка / Title length
        buff = ctypes.create_unicode_buffer(length + 1)  # Буфер под текст / Buffer for title
        GetWindowTextW(hwnd, buff, length + 1)  # Прочитать заголовок / Read title
        title = buff.value.lower().strip()      # Нормализовать строку / Normalize string
        return "dota 2" in title or title == "dota 2"  # Совпадение / Match
    except Exception:
        return False  # На любом исключении считаем, что не в фокусе / On error, assume not in focus

def read_state():
    """Чтение enabled/detected из overlay_state.json /
    Read enabled/detected from overlay_state.json."""
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            st = json.load(f)                          # Парсинг JSON / Parse JSON
        return bool(st.get("enabled", True)), bool(st.get("detected", False))  # Флаги / Flags
    except Exception:
        return True, False  # Значения по умолчанию / Defaults on error

class Overlay(QWidget):
    def __init__(self):
        super().__init__()  # Инициализация QWidget / QWidget init

        # Окно / Window
        self.setWindowTitle("Overlay")                                        # Заголовок окна / Window title
        self.setGeometry(0, 0, 1920, 1080)                                    # Размер во весь экран / Full HD geometry
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # Без рамки, поверх всех, как туловое окно / Frameless, always-on-top, tool window
        self.setAttribute(Qt.WA_TranslucentBackground)                        # Прозрачный фон / Transparent background
        self.setAttribute(Qt.WA_TransparentForMouseEvents)                    # Прозрачно для мыши / Mouse-click through

        # Рисование / Painting setup
        self.font = QFont("Arial", 12, QFont.Bold)                            # Шрифт / Font
        self.pen = QPen(QColor("yellow")); self.pen.setWidth(2)               # Жёлтая обводка / Yellow pen

        # Данные / Data
        self.data = []                 # list[{hero,counters,box}] — текущие данные / current overlay list
        self.icon_cache = {}           # Кэш QPixmap для иконок / QPixmap cache for icons
        self.last_mtime = None         # Последний mtime overlay_data.json / Last mtime of data file

        # Кэш последней удачной отрисовки: hero -> {"box":[...], "side":"L"/"R"} /
        # Cache of last successful draw per hero
        self.last_draw = {}

        # Таймеры / Timers
        self.timer_data = QTimer(self)                        # Таймер загрузки данных / Data poll timer
        self.timer_data.timeout.connect(self.load_data)       # Колбэк на таймер / Connect callback
        self.timer_data.start(500)                            # Период 500 мс / 500 ms period

        self.timer_vis  = QTimer(self)                        # Таймер видимости / Visibility timer
        self.timer_vis.timeout.connect(self.update_visibility)# Колбэк / Callback
        self.timer_vis.start(300)                             # Период 300 мс / 300 ms period

        self.update_visibility()  # Установить начальную видимость / Initial visibility
        self.show()               # Показать окно / Show window

    def update_visibility(self):
        """Показ/скрытие окна по флагам enabled/detected и фокусу Dota 2 /
        Show/hide window based on enabled/detected and Dota 2 focus."""
        enabled, detected = read_state()          # Прочитать флаги / Read flags
        in_focus = is_dota_foreground()           # Проверить фокус / Foreground check
        should_show = enabled and detected and in_focus  # Логика видимости / Visibility logic
        if should_show and not self.isVisible():
            self.show()                           # Показать, если нужно / Show if needed
        elif not should_show and self.isVisible():
            self.hide()                           # Спрятать, если не нужно / Hide if not needed

    def load_data(self):
        """Загрузка overlay_data.json при изменении mtime /
        Load overlay_data.json when mtime changes."""
        try:
            if not os.path.exists(OVERLAY_DATA_PATH):
                self.data = []    # Нет файла — нет данных / No file -> no data
                self.update()     # Перерисовка / Repaint
                return
            mtime = os.path.getmtime(OVERLAY_DATA_PATH)  # Время изменения / mtime
            if self.last_mtime is not None and mtime == self.last_mtime:
                return            # Не изменился — не перерисовывать / No change -> skip
            self.last_mtime = mtime
            with open(OVERLAY_DATA_PATH, "r", encoding="utf-8") as f:
                txt = f.read().strip()                    # Прочитать текст / Read text
            self.data = json.loads(txt) if txt else []    # Парсинг / Parse or empty
            if not isinstance(self.data, list):
                self.data = []                            # Гарантируем список / Ensure list
        except Exception:
            self.data = []                                # На ошибке — пусто / On error -> empty
        self.update()                                     # Запрос перерисовки / Request repaint

    def _draw_counters(self, painter, hero, box, counters):
        """Отрисовать 2×2 иконки контрпиков возле бокса героя /
        Draw 2×2 counter icons near hero box."""
        x1, y1, x2, y2 = map(int, box)    # Координаты бокса / Box coords
        w = x2 - x1; h = y2 - y1          # Размеры бокса / Box size
        if w <= 0 or h <= 0:
            return False                  # Некорректный бокс / Invalid box

        # Если бокс низкий — используем сохранённый, чтобы не мигало /
        # If box too short — use cached one to avoid flicker
        if h < MIN_BOX_H_FOR_DRAW and hero in self.last_draw:
            box = self.last_draw[hero]["box"]
            x1, y1, x2, y2 = map(int, box)
            w = x2 - x1; h = y2 - y1
            if w <= 0 or h <= 0:
                return False

        # Выбор стороны по IoU; при 0/равенстве — берем прошлую сторону /
        # Choose side via IoU; if 0/tie — use last side
        iou_r = intersection_over_union([x1, y1, x2, y2], RADIANT_ZONE)
        iou_d = intersection_over_union([x1, y1, x2, y2], DIRE_ZONE)
        if iou_r == 0 and iou_d == 0 and hero in self.last_draw:
            draw_left = (self.last_draw[hero]["side"] == "L")  # Предыдущая сторона / Last side
        else:
            draw_left = iou_r > iou_d                           # Влево, если ближе к Radiant / Left if nearer Radiant

        icon_h = max(1, int(h * ICON_HEIGHT_RATIO))  # Высота иконки / Icon height
        icon_w = ICON_WIDTH                           # Ширина иконки / Icon width
        pad = 5                                       # Отступ между иконками / Padding
        center_x = LEFT_COLUMN_X if draw_left else RIGHT_COLUMN_X  # Колонка / Column X
        base_y = y1                                   # Верхняя привязка / Top Y

        # Рисуем сетку 2×2 / Draw 2×2 grid
        for i, name in enumerate(counters[:4]):
            row, col = divmod(i, 2)                                     # Ряд и колонка / Row and column
            base_x = center_x - icon_w - pad // 2                       # Базовый X / Base X
            cx = base_x + col * (icon_w + pad)                          # X иконки / Icon X
            cy = base_y + row * (icon_h + pad)                          # Y иконки / Icon Y
            icon_path = os.path.join(ICON_FOLDER, f"{name}.jpg")        # Путь иконки / Icon path
            if os.path.exists(icon_path):
                key = (name, icon_w, icon_h)                            # Ключ кэша / Cache key
                pm = self.icon_cache.get(key)                           # Попытка из кэша / Try cache
                if pm is None:
                    pm = QPixmap(icon_path).scaled(
                        icon_w, icon_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                    )                                                   # Масштабирование / Scale
                    self.icon_cache[key] = pm                           # Сохранить в кэш / Store in cache
                painter.drawPixmap(QRect(cx, cy, icon_w, icon_h), pm)   # Рисуем иконку / Draw icon
            else:
                painter.drawText(cx, cy + 20, name)                     # Фолбэк: текст / Fallback: text

        # Сохранить успешную отрисовку (бокс и сторона) /
        # Remember last successful draw (box and side)
        self.last_draw[hero] = {"box": [x1, y1, x2, y2], "side": "L" if draw_left else "R"}
        return True

    def paintEvent(self, event):
        """Основная отрисовка на прозрачном окне / Main painting on transparent window."""
        if not self.data:
            return                            # Нет данных — ничего не рисуем / No data -> nothing to draw
        painter = QPainter(self)              # Создать рисовальщика / Create painter
        painter.setFont(self.font)            # Настроить шрифт / Set font
        painter.setPen(self.pen)              # Настроить перо / Set pen

        for item in self.data:                # Пройти по героям / Iterate heroes
            hero = item.get("hero")           # Имя героя / Hero name
            box = item.get("box", [0, 0, 0, 0])       # Бокс / Box
            counters = item.get("counters", [])       # Контрпики / Counters
            if not hero or not (isinstance(box, list) and len(box) == 4):
                continue                      # Пропустить некорректные записи / Skip invalid items

            ok = self._draw_counters(painter, hero, box, counters)  # Попытка отрисовки / Try draw
            if not ok and hero in self.last_draw:
                # Если не удалось — рисуем по кэшу, чтобы не мигало /
                # If failed — draw from cache to avoid flicker
                cached = self.last_draw[hero]
                self._draw_counters(painter, hero, cached["box"], counters)

if __name__ == "__main__":
    app = QApplication(sys.argv)  # Создать приложение Qt / Create Qt application
    overlay = Overlay()           # Создать и показать оверлей / Create and show overlay
    sys.exit(app.exec_())         # Запуск цикла событий / Run event loop
