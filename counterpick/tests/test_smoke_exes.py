import os
import time
import subprocess
from pathlib import Path
import pytest

pytestmark = pytest.mark.smoke

# Список возможных имён exe — если какого-то нет в release_stub, тест его просто пропустит.
EXE_CANDIDATES = [
    "screenshot_capture.exe",
    "detector.exe",
    "overlay_window.exe",
    "screenshot_detector.exe",  # если используешь совмещённый бинарь
]

START_WAIT_SEC = 1.5   # ждём, чтобы убедиться, что процесс не упал сразу
RUN_WINDOW_SEC = 1.0   # короткое «окно жизни» процесса
TERMINATE_WAIT_SEC = 5.0

@pytest.mark.parametrize("exe_name", EXE_CANDIDATES)
def test_smoke_exes_start_and_exit_clean(release_dir: Path, exe_name: str):
    exe = release_dir / exe_name
    if not exe.exists():
        pytest.skip(f"{exe_name} отсутствует в {release_dir}")

    # окружение: мягкий флаг для «лёгкого» старта, если поддерживается
    env = os.environ.copy()
    env.setdefault("CP_SMOKE", "1")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(release_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        env=env,
    )

    try:
        # 1) убедимся, что не упал сразу
        time.sleep(START_WAIT_SEC)
        assert proc.poll() is None, f"{exe_name} завершился слишком рано"

        # 2) даём чуть поработать
        time.sleep(RUN_WINDOW_SEC)
        assert proc.poll() is None, f"{exe_name} неожиданно завершился"

    finally:
        # 3) корректно завершаем
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=TERMINATE_WAIT_SEC)
            except Exception:
                proc.kill()

        # 4) финальная гарантия — процесса нет
        assert proc.poll() is not None, f"{exe_name} завис и не завершился"
