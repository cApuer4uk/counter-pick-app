import os      # Работа с файловой системой / File system operations
import time    # Задержки и работа со временем / Time handling and delays
from mss import mss  # Библиотека для скриншотов экрана / Library for taking screenshots
from datetime import datetime  # Работа с датой и временем / Work with date and time
import sys     # Доступ к системным переменным / Access to system-related variables
# === WinAPI named mutex (single instance) / Именованный мьютекс (единственный экземпляр) ===
import ctypes, atexit  # Импорты для работы с WinAPI и финализации / WinAPI + finalizer

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)  # Загрузка kernel32.dll / Load kernel32.dll
CreateMutexW = kernel32.CreateMutexW                      # Функция создания мьютекса / Create/Open mutex
CloseHandle = kernel32.CloseHandle                        # Закрытие дескриптора / Close handle
ERROR_ALREADY_EXISTS = 183                                # Код ошибки "уже существует" / "Already exists" code

MUTEX_NAME = r"Global\COUNTERPICK_SCREENSHOT_MUTEX"  # Уникальное имя мьютекса / Unique mutex name
hMutex = CreateMutexW(None, False, ctypes.c_wchar_p(MUTEX_NAME))  # Создаём мьютекс / Create mutex
if not hMutex:
    sys.exit(1)  # Не удалось создать — выходим / Failed to create — exit

if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    CloseHandle(hMutex)  # Освобождаем хэндл / Release handle
    sys.exit(0)          # Уже запущен — выходим / Already running — exit

atexit.register(lambda: CloseHandle(hMutex))  # Гарантированно освободить при завершении / Release on exit
# === END single-instance guard ===

# === Настройки / Settings ===
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
# Определяем базовую директорию / Define the base directory
# Если программа собрана в .exe, берём путь к исполняемому файлу / If frozen (.exe), use executable path
# Иначе — путь к текущему .py файлу / Otherwise, use current script path

SAVE_DIR = os.path.join(BASE_DIR, 'tmp_screenshots')
# Папка для временных скриншотов / Folder for temporary screenshots

DELAY = 2
# Задержка между созданием скриншотов (в секундах) / Delay between screenshots in seconds

# === Проверка папки / Check folder ===
os.makedirs(SAVE_DIR, exist_ok=True)
# Создаём папку, если её нет / Create folder if it doesn't exist

# === Инициализация скриншотов / Screenshot initialization ===
sct = mss()
# Создаём объект для захвата экрана / Create an MSS object for screen capturing

try:
    while True:
        # Бесконечный цикл для постоянных скриншотов / Infinite loop for continuous screenshots

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Получаем текущую дату и время как строку / Get current date and time as string

        filename = f"{timestamp}.png"
        # Формируем имя файла на основе времени / Create filename based on timestamp

        filepath = os.path.join(SAVE_DIR, filename)
        # Полный путь до файла / Full path to the file

        sct.shot(output=filepath)
        # Делаем скриншот и сохраняем / Take screenshot and save it to file

        time.sleep(DELAY)
        # Ждём заданное количество секунд / Wait for the specified delay

except KeyboardInterrupt:
    # Если пользователь нажал Ctrl+C — выходим корректно / Handle manual stop (Ctrl+C)
    pass

finally:
    sct.close()
    # Закрываем MSS и освобождаем ресурсы / Close MSS and release resources
