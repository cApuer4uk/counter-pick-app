import subprocess
import sys
import time
from pathlib import Path
import pytest

def test_screenshot_exe_smoke_start(release_dir: Path):
    """
    Проверяем, что screenshot_windows.exe запускается и не падает сразу.
    """
    exe = release_dir / "screenshot_windows.exe"
    if not exe.exists():
        pytest.skip(f"{exe} not found (skipping)")

    proc = subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    )

    try:
        time.sleep(3)
        assert proc.poll() is None, "screenshot_windows.exe exited prematurely"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
