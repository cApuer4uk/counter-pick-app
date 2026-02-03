import sys  # системные параметры и путь к exe / system parameters and path to exe
import os  # работа с файлами и путями / file and path operations
import subprocess  # запуск внешних процессов / run external processes
import psutil  # контроль и завершение процессов / control and terminate processes
import ctypes  # доступ к WinAPI / access to WinAPI
from ctypes import wintypes  # типы данных WinAPI / WinAPI data types
import shutil  # копирование и удаление папок / copy and remove directories
import stat  # изменение прав доступа к файлам / change file permissions
import tempfile  # временные файлы и папки / temporary files and folders
from PyQt5.QtWidgets import (  # элементы интерфейса Qt / Qt interface elements
    QApplication, QMainWindow, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt5.QtGui import (  # графические классы Qt / Qt graphic classes
    QMouseEvent, QFont, QIcon, QPainter, QColor, QPen
)
from PyQt5.QtCore import Qt  # базовые константы Qt / basic Qt constants

# Функции WinAPI для фокусировки уже запущенного процесса / WinAPI functions to focus an already running process
user32 = ctypes.WinDLL('user32', use_last_error=True)  # загрузка user32.dll с прокидыванием последней ошибки / load user32.dll with last-error propagation
FindWindowW = user32.FindWindowW  # получить HWND окна по имени класса/заголовка (Unicode) / get window handle by class/title (Unicode)
AllowSetForegroundWindow = user32.AllowSetForegroundWindow  # разрешить процессу захватить фокус окна / allow a process to set a foreground window
SetForegroundWindow = user32.SetForegroundWindow  # перевести указанное окно на передний план / bring specified window to foreground
ShowWindow = user32.ShowWindow  # изменить состояние окна (показать/свернуть/восстановить) / change window state (show/minimize/restore)
SW_RESTORE = 9  # флаг для ShowWindow: восстановить из свернутого/макс. в нормальное / ShowWindow flag: restore from minimized/maximized


# === Пути === / Paths
if getattr(sys, 'frozen', False):  # если приложение собрано в exe через PyInstaller / if app is frozen into exe by PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)  # берем путь к папке, где лежит exe / use folder where exe is located
else:  # если запущено из исходников / if running from source
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # путь к текущему файлу .py / path to current .py file

overlay_json = os.path.join(BASE_DIR, 'overlay_data.json')  # файл для данных о детекциях / json file with detection data
screenshot_exe = os.path.join(BASE_DIR, 'screenshot_windows.exe')  # exe для скриншотов / exe for taking screenshots
detector_exe = os.path.join(BASE_DIR, 'screenshot_detector.exe')  # exe для распознавания героев / exe for hero detection
overlay_exe = os.path.join(BASE_DIR, 'overlay_window.exe')  # exe для оверлея контрпиков / exe for overlay display
icon_path = os.path.join(BASE_DIR, 'launcher_icon.ico')  # иконка лаунчера / launcher window icon


def _on_rm_error(func, path, exc_info):  # обработчик ошибок при удалении / error handler for deletion
    """
    RU: Обработчик ошибок для shutil.rmtree: пытается снять read-only и повторить удаление.
    EN: Error handler for shutil.rmtree: tries to clear read-only and retry removal.
    """
    try:
        os.chmod(path, stat.S_IWRITE)  # делаем файл или папку доступной на запись / make file or folder writable
        func(path)  # повторяем попытку удаления / retry the remove operation
    except Exception:
        # игнорируем ошибку, остатки удалятся при следующем запуске / ignore error, leftovers will be removed next run
        pass


def safe_cleanup_mei():  # очистка временных папок _MEI / cleanup of _MEI temp folders
    """
    RU: Удаляет все папки вида _MEI* в системной TEMP-директории.
        - Чистим только %TEMP%
        - Удаляем только директории с префиксом '_MEI'
        - Тихо пропускаем занятые/проблемные папки
    EN: Removes all _MEI* folders in system TEMP.
        - Touch TEMP only
        - Remove directories starting with '_MEI' prefix
        - Silently skip locked/problematic folders
    """
    try:
        temp_dir = os.environ.get('TEMP') or tempfile.gettempdir()  # получаем путь к TEMP / get TEMP directory path
        if not temp_dir or not os.path.isdir(temp_dir):  # если нет TEMP — выходим / if no TEMP found — exit
            return  # ничего не делаем / do nothing

        # перебираем содержимое TEMP, удаляем только папки с префиксом '_MEI' / iterate TEMP, remove only '_MEI' dirs
        for name in os.listdir(temp_dir):
            if not name.startswith('_MEI'):  # пропускаем всё, что не _MEI / skip non-_MEI items
                continue
            full_path = os.path.join(temp_dir, name)  # формируем полный путь / build full path
            if not os.path.isdir(full_path):  # если не папка — пропускаем / skip non-directory
                continue
            try:
                shutil.rmtree(full_path, onerror=_on_rm_error)  # удаляем папку, снимаем readonly при ошибке / remove dir, handle readonly errors
            except PermissionError:
                # папка занята процессом — пропускаем / folder locked by process — skip
                pass
            except Exception:
                # другие ошибки не прерывают запуск / ignore other errors to not block startup
                pass
    except Exception:
        # глобально игнорируем сбой очистки TEMP / globally ignore TEMP cleanup failure
        pass


class PatternWidget(QWidget):  # виджет с фоновыми диагональными полосами / widget with diagonal stripe background
    """Контейнер с диагональными полосами на тёмном фоне / Container with diagonal stripes on dark background"""

    def paintEvent(self, e):  # событие перерисовки виджета / widget paint event
        qp = QPainter(self)  # создаём объект рисования / create painter object
        qp.setRenderHint(QPainter.Antialiasing)  # включаем сглаживание / enable antialiasing
        r = self.rect()  # получаем прямоугольник области виджета / get widget rectangle

        qp.setBrush(QColor("#2d2e34"))  # устанавливаем тёмный фон / set dark background
        qp.setPen(Qt.NoPen)  # убираем обводку / disable border
        qp.drawRoundedRect(r, 12, 12)  # рисуем скруглённый прямоугольник / draw rounded rectangle

        pen = QPen(QColor(80, 90, 110, 60), 2)  # создаём полупрозрачную серую линию / create semi-transparent gray line
        qp.setPen(pen)  # применяем перо / apply pen
        step = 20  # расстояние между линиями / distance between lines
        h, w = r.height(), r.width()  # размеры области / widget height and width
        for x in range(-h, w, step):  # рисуем диагональные линии по всей области / draw diagonal lines across area
            start_x = w - x  # начальная координата X / starting X coordinate
            end_x = start_x - h  # конечная координата X / ending X coordinate
            qp.drawLine(start_x, 0, end_x, h)  # рисуем линию от верха до низа / draw line top to bottom

class DragTitle(QFrame):  # кастомная шапка окна с кнопками управления / custom window title bar with control buttons
    def __init__(self):  # конструктор / constructor
        super().__init__()  # инициализация базового QFrame / init base QFrame
        self.setFixedHeight(40)  # фиксированная высота заголовка / fixed title height
        self.setStyleSheet("""  # стили шапки: жёлтая полоса со скруглениями / header styles: yellow bar with rounded corners
            background-color: #FFCC00;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
        """)
        self._drag_pos = None  # последняя позиция мыши для перетаскивания / last mouse pos for dragging

        layout = QHBoxLayout(self)  # горизонтальный лейаут для кнопок / horizontal layout for buttons
        layout.setContentsMargins(10, 0, 10, 0)  # внутренние отступы / inner margins
        layout.addStretch()  # отталкиваем кнопки вправо / push buttons to the right

        btn_specs = [  # описание трёх кнопок: свернуть, развернуть/восстановить, закрыть / three buttons: minimize, maximize/restore, close
            ("━", lambda: self.window().showMinimized(), 12, "rgba(0,0,0,0.25)"),
            ("▢", self.toggle_maximize_restore, 35, "rgba(0,0,0,0.25)"),
            ("✕", lambda: self.window().close(), 20, "#FF5C5C"),
        ]
        for sym, action, size, hover_color in btn_specs:  # создаём кнопки по спецификации / create buttons from spec
            btn = QPushButton(sym, self)  # кнопка с символом / button with symbol
            btn.setFixedSize(30, 30)  # размер кнопки / button size
            btn.setStyleSheet(f"""  # стили кнопки, включая hover/pressed / button styles incl. hover/pressed
                QPushButton {{
                    background-color: transparent;
                    color: #000;
                    border: none;
                    border-radius: 4px;
                    font-size: {size}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: rgba(0,0,0,0.35);
                }}
            """)
            btn.clicked.connect(action)  # привязываем действие к клику / connect action to click
            layout.addWidget(btn)  # добавляем кнопку в лейаут / add button to layout
            layout.addSpacing(5)  # небольшой отступ между кнопками / small spacing between buttons

    def toggle_maximize_restore(self):  # переключение между окном и фуллскрином / toggle maximize/restore
        wnd = self.window()  # ссылка на главное окно / reference to main window
        wnd.showNormal() if wnd.isMaximized() else wnd.showMaximized()  # инвертируем состояние / invert state

    def mousePressEvent(self, e: QMouseEvent):  # обработка нажатия мыши / mouse press handler
        if e.button() == Qt.LeftButton:  # реагируем только на левую кнопку / handle left button only
            self._drag_pos = e.globalPos()  # запоминаем позицию для начала перетаскивания / store pos to start dragging

    def mouseMoveEvent(self, e: QMouseEvent):  # обработка движения мыши / mouse move handler
        if self._drag_pos:  # если идёт перетаскивание / if dragging in progress
            delta = e.globalPos() - self._drag_pos  # вектор смещения / movement delta
            self.window().move(self.window().pos() + delta)  # двигаем окно / move the window
            self._drag_pos = e.globalPos()  # обновляем опорную точку / update reference point

class MainWindow(QMainWindow):  # главное окно лаунчера / main launcher window
    def __init__(self):  # конструктор / constructor
        super().__init__()  # инициализация базового QMainWindow / init base QMainWindow
        # Устанавливаем заголовок, чтобы потом найти окно в WinAPI / Set title so we can find the window via WinAPI later
        self.setWindowTitle("CounterPick Launcher")  # заголовок окна / window title
        self.setWindowFlags(Qt.FramelessWindowHint)  # убираем системную рамку / remove native window frame
        self.setAttribute(Qt.WA_TranslucentBackground)  # прозрачный фон окна / translucent window background
        self.setFixedSize(360, 240)  # фиксированный размер окна / fixed window size
        self.setWindowIcon(QIcon(icon_path))  # иконка окна из файла / window icon from file

        self.screenshot_proc = None  # процесс скриншотов / screenshot process handle
        self.detector_proc = None  # процесс детектора / detector process handle
        self.overlay_proc = None  # процесс оверлея / overlay process handle

        title = DragTitle()  # кастомная шапка с кнопками и перетаскиванием / custom title bar with buttons and drag

        # START button / кнопка START
        self.start_button = QPushButton("START")  # создаём кнопку START / create START button
        self.start_button.setFont(QFont("Segoe UI", 14, QFont.Bold))  # шрифт кнопки / button font
        self.start_button.setStyleSheet("""  # стили для норм/hover/pressed/disabled / styles for normal/hover/pressed/disabled
            QPushButton { background-color: #007BFF; color: white; padding:12px;
                          border-radius:8px; min-width:100px; }
            QPushButton:hover { background-color: #0056d2; }
            QPushButton:pressed { background-color: #0041a8; }
            QPushButton:disabled { background-color: #5a6f8a; color: white; }
        """)
        self.start_button.clicked.connect(self.start_processes)  # обработчик клика: запуск процессов / click handler: start processes

        # STOP button / кнопка STOP
        self.stop_button = QPushButton("STOP")  # создаём кнопку STOP / create STOP button
        self.stop_button.setFont(QFont("Segoe UI", 14, QFont.Bold))  # шрифт кнопки / button font
        self.stop_button.setStyleSheet("""  # стили для enabled/hover/pressed/disabled / styles for enabled/hover/pressed/disabled
            QPushButton {
                background-color: #DC3545;
                color: white;
                padding: 12px;
                border-radius: 8px;
                min-width: 100px;
            }
            QPushButton:enabled:hover {        /* ← только для enabled */  /* only when enabled */
                background-color: #A52A2A;     /* тёмно-красный при наведении */  /* dark red on hover */
            }
            QPushButton:enabled:pressed {
                background-color: #801920;     /* ещё темнее при нажатии */  /* darker on press */
            }
            QPushButton:disabled {
                background-color: #7f3f42;
                color: white;
            }
        """)
        self.stop_button.setEnabled(False)  # по умолчанию выключена / disabled by default
        self.stop_button.clicked.connect(self.stop_processes)  # обработчик клика: остановка процессов / click handler: stop processes

        hl = QHBoxLayout()  # горизонтальный лейаут для кнопок / horizontal layout for buttons
        hl.addStretch()  # растяжка слева / left stretch
        hl.addWidget(self.start_button)  # добавляем START / add START
        hl.addSpacing(20)  # промежуток между кнопками / spacing between buttons
        hl.addWidget(self.stop_button)  # добавляем STOP / add STOP
        hl.addStretch()  # растяжка справа / right stretch

        vl = QVBoxLayout()  # вертикальный лейаут контента / vertical layout for content
        vl.setContentsMargins(0, 0, 0, 20)  # нижний отступ для «воздуха» / bottom margin for spacing
        vl.addWidget(title)  # шапка сверху / add title bar
        vl.addStretch()  # отталкиваем панель кнопок вниз / push buttons area down
        vl.addLayout(hl)  # добавляем панель кнопок / add buttons layout
        vl.addStretch()  # балансируем вертикально / balance vertically

        content = PatternWidget()  # фон с диагональными полосами / patterned background widget
        content.setLayout(vl)  # вкладываем вертикальный лейаут внутрь / set vertical layout inside
        wrapper = QFrame()  # обёртка для тени и прозрачности / wrapper frame for shadow and transparency
        wrapper.setStyleSheet("background: transparent;")  # делаем бэкграунд обёртки прозрачным / transparent wrapper background
        wlay = QVBoxLayout(wrapper)  # лейаут обёртки / wrapper layout
        wlay.setContentsMargins(10, 10, 10, 10)  # внешние поля для скруглений/тени / outer margins for rounding/shadow
        wlay.addWidget(content)  # помещаем контент внутрь обёртки / add content into wrapper
        self.setCentralWidget(wrapper)  # ставим обёртку как центральный виджет / set wrapper as central widget

        shadow = QGraphicsDropShadowEffect(self)  # создаём эффект тени / create drop shadow effect
        shadow.setBlurRadius(25)  # радиус размытия тени / shadow blur radius
        shadow.setXOffset(0)  # смещение по X / X offset
        shadow.setYOffset(5)  # смещение по Y / Y offset
        shadow.setColor(QColor(0, 0, 0, 180))  # полупрозрачная чёрная тень / semi-transparent black shadow
        wrapper.setGraphicsEffect(shadow)  # применяем тень к обёртке / apply shadow to wrapper

        self.logo = QLabel("C", self)  # маленький логотип «C» в левом верхнем углу / small "C" logo near top-left
        self.logo.setFixedSize(50, 50)  # размер логотипа / logo size
        self.logo.setAlignment(Qt.AlignCenter)  # центрирование текста / center text
        self.logo.setStyleSheet("""  # стиль логотипа: жёлтый фон, чёрная рамка, крупный шрифт / logo style: yellow bg, black border, large font
            background-color:#FFCC00; color:#000; border:3px solid #000;
            border-radius:6px; font-size:35px; font-weight:bold;
        """)
        self.logo.move(20, 40 - self.logo.height() // 2 + 12)  # позиция логотипа относительно шапки / logo position relative to title bar

    def closeEvent(self, event):  # событие закрытия окна / window close event
        # Останавливаем процессы перед закрытием / Stop processes before closing
        self.stop_processes()  # остановка трёх дочерних процессов / stop three child processes
        super().closeEvent(event)  # стандартная обработка закрытия окна / call base closeEvent

    def clear_tmp_screenshots(self):  # очистка временной папки со скриншотами / clear temp screenshots folder
        tmp_dir = os.path.join(BASE_DIR,
                               'tmp_screenshots')  # путь к tmp_screenshots рядом с exe / path to tmp_screenshots next to exe
        if not os.path.isdir(tmp_dir):  # если папки нет — выходим / if folder absent — exit
            return  # ничего не чистим / nothing to clean
        for name in os.listdir(tmp_dir):  # перебираем файлы в папке / iterate files in folder
            path = os.path.join(tmp_dir, name)  # полный путь к элементу / full path to item
            try:
                if os.path.isfile(path):  # чистим только файлы / only remove files
                    os.remove(path)  # удаляем файл / delete file
                # если там могут появляться подпапки — можно добавить: / if subfolders may appear — enable this:
                # elif os.path.isdir(path):
                #     shutil.rmtree(path)
            except Exception as e:
                QMessageBox.warning(self, "Внимание",  # предупреждение при ошибке удаления / warn if deletion fails
                                    f"Не удалось удалить {path}:\n{e}")  # текст ошибки / error text

    def start_processes(self):  # запуск всех процессов и подготовка состояния / start all processes and prepare state
        state_path = os.path.join(BASE_DIR,
                                  'overlay_state.json')  # путь к overlay_state.json / path to overlay_state.json
        try:
            # Очистить overlay_data.json / Clear overlay_data.json
            with open(overlay_json, "w", encoding="utf-8") as f:  # открываем на перезапись / open for overwrite
                f.write("")  # пишем пустую строку (сигнал «нет данных») / write empty string (means "no data")
            # Включить оверлей и сбросить флаг детекции / Enable overlay and reset detection flag
            with open(state_path, "w", encoding="utf-8") as f:  # открываем state файл / open state file
                f.write(
                    '{"enabled": true, "detected": false}')  # включаем overlay, детекта пока нет / enable overlay, no detection yet
        except Exception as e:
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось подготовить JSON:\n{e}")  # сообщение об ошибке I/O / I/O error message
            return  # прерываем запуск / abort start

        # Очистить временные скриншоты / Clear temporary screenshots
        self.clear_tmp_screenshots()  # удаляем остатки из прошлых запусков / remove leftovers from previous runs

        # Запустить процессы / Start processes
        try:
            self.screenshot_proc = subprocess.Popen(  # запускаем сборщик скриншотов / start screenshot collector
                [screenshot_exe], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                # отдельная группа процессов / separate process group
            )
            self.detector_proc = subprocess.Popen(  # запускаем детектор / start detector
                [detector_exe], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                # отдельная группа процессов / separate process group
            )
            self.overlay_proc = subprocess.Popen(  # запускаем оверлей / start overlay
                [overlay_exe], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                # отдельная группа процессов / separate process group
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", str(e))  # критическая ошибка старта / critical start error
            return  # останавливаемся / stop

        self.start_button.setEnabled(
            False)  # блокируем START, чтобы не дублировать процессы / disable START to avoid duplicates
        self.stop_button.setEnabled(True)  # разрешаем STOP / enable STOP

    def stop_processes(self):  # остановить все процессы и сбросить состояние / stop all processes and reset state
        # Остановить процессы (+дети) / Terminate processes (+children)
        for proc in (self.screenshot_proc, self.detector_proc,
                     self.overlay_proc):  # обходим три процесса / iterate three processes
            if proc and proc.poll() is None:  # жив ли процесс / is process alive
                try:
                    p = psutil.Process(proc.pid)  # получаем объект процесса / get process object
                    for c in p.children(recursive=True):  # все дочерние процессы / all child processes
                        c.kill()  # убиваем детей / kill children
                    p.kill()  # убиваем сам процесс / kill parent process
                except Exception:
                    pass  # игнорируем ошибки завершения / ignore termination errors

        # Сбросить JSON / Reset JSON
        state_path = os.path.join(BASE_DIR, 'overlay_state.json')  # путь к state / path to state
        try:
            with open(overlay_json, "w", encoding="utf-8") as f:  # очищаем overlay_data / clear overlay_data
                f.write("")  # пустая строка = нет данных / empty string = no data
            with open(state_path, "w", encoding="utf-8") as f:  # перезаписываем overlay_state / overwrite overlay_state
                f.write(
                    '{"enabled": false, "detected": false}')  # выключаем overlay и детект / disable overlay and detection
        except Exception as e:
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось сбросить JSON:\n{e}")  # предупреждение при ошибке / warn on error

        # Почистить скриншоты / Clean screenshots
        self.clear_tmp_screenshots()  # удаляем временные файлы / delete temp files

        # Сброс ссылок на процессы / Reset process handles
        self.screenshot_proc = None  # очистка дескриптора / clear handle
        self.detector_proc = None  # очистка дескриптора / clear handle
        self.overlay_proc = None  # очистка дескриптора / clear handle
        self.start_button.setEnabled(True)  # снова разрешаем START / enable START again
        self.stop_button.setEnabled(False)  # отключаем STOP / disable STOP
        safe_cleanup_mei()  # финальная уборка _MEI в TEMP / final _MEI cleanup in TEMP


if __name__ == "__main__":  # точка входа при прямом запуске / entry point when run directly
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket  # локальный IPC-сервер и сокет / local IPC server and socket

    SERVER_NAME = "counterpick_single_instance"  # имя одноэкземплярного сервера / single-instance server name

    # Попытка «стучаться» к уже запущенному экземпляру / Try to connect to an already running instance
    socket = QLocalSocket()  # клиентский сокет / client socket
    socket.connectToServer(SERVER_NAME)  # подключаемся к имени сервера / connect to server name
    if socket.waitForConnected(100):  # если подключились за 100 мс — экземпляр уже работает / if connected within 100 ms — instance exists
        # SECONDARY PROCESS: мы в фокусе, можем разбудить primary / we are secondary, can wake the primary
        # находим главное окно по заголовку / find main window by title
        hwnd = FindWindowW(None, "CounterPick Launcher")  # получаем HWND по титулу / get HWND by window title
        if hwnd:  # если окно найдено / if window found
            AllowSetForegroundWindow(wintypes.DWORD(-1))  # разрешаем поднять окно на передний план / allow bringing to foreground
            ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)  # восстанавливаем из свернутого / restore if minimized
            SetForegroundWindow(wintypes.HWND(hwnd))  # даём фокус окну / give focus to the window
        sys.exit(0)  # завершаем вторичный процесс / exit secondary process

    # Удаляем «зависший» сервер после крэша / Remove stale server after a crash
    try:
        QLocalServer.removeServer(SERVER_NAME)  # попытка очистить имя сервера / try to clear server name
    except:
        pass  # игнорируем сбой очистки / ignore cleanup failure

    # PRIMARY PROCESS: создаём сервер и запускаем GUI / create server and start GUI
    server = QLocalServer()  # локальный сервер одноэкземплярности / local single-instance server
    if not server.listen(SERVER_NAME):  # не удалось занять имя — ошибка / failed to bind name — error
        sys.exit(1)  # выходим с кодом 1 / exit with code 1

    app = QApplication(sys.argv)  # создаём приложение Qt / create Qt application
    app.setWindowIcon(QIcon(icon_path))  # иконка по умолчанию для окон / default app window icon
    win = MainWindow()  # создаём главное окно / create main window
    win.show()  # показываем его / show it

    # Обработчик нового подключения (тим, кто не в фокусе, просто сбросит сокет) / New-connection handler (secondary will just drop the socket)
    def handle_new_connection():  # вызывается при подключении вторичного процесса / called when a secondary connects
        client = server.nextPendingConnection()  # берём сокет клиента / get client socket
        client.waitForReadyRead(100)  # ждём чуть-чуть данных (необязательно) / wait briefly for data (optional)
        client.disconnectFromServer()  # сразу закрываем / disconnect immediately
        # Развернуть windowState, но foreground мы уже сделали в secondary / Restore window state; foreground was done by secondary
        if win.isMinimized():  # если окно свёрнуто / if window minimized
            win.showNormal()  # разворачиваем / restore

    server.newConnection.connect(handle_new_connection)  # подписка на новые подключения / connect new-connection signal

    sys.exit(app.exec_())  # запускаем цикл обработки событий / start Qt event loop
