import subprocess
import sys
import time
from pathlib import Path
import pytest

def test_screenshot_creates_new_image(release_dir: Path):
    """
    Проверяем, что screenshot_windows.exe создаёт новый файл в tmp_screenshots/.
    """
    exe = release_dir / "screenshot_windows.exe"
    if not exe.exists():
        pytest.skip(f"{exe} not found (skipping)")

    tmp_dir = release_dir / "tmp_screenshots"
    tmp_dir.mkdir(exist_ok=True)
    before = {p.name for p in tmp_dir.iterdir() if p.is_file()}

    proc = subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    )

    try:
        # даём время на создание хотя бы одного файла
        time.sleep(4)
        after = {p.name for p in tmp_dir.iterdir() if p.is_file()}
        new_files = after - before
        assert new_files, "screenshot_windows.exe did not produce any new files"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
