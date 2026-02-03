import shutil
import time
from pathlib import Path
import subprocess
import json
import pytest

pytestmark = pytest.mark.integration


def _read_json_safe(p: Path):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore").strip()
        if not txt:
            return None
        return json.loads(txt)
    except Exception:
        return None


def test_detector_updates_overlay_data(release_dir: Path):
    exe = release_dir / "screenshot_detector.exe"
    assert exe.exists(), "Нет screenshot_detector.exe в release_stub"

    overlay = release_dir / "overlay_data.json"
    tmp_dir = release_dir / "tmp_screenshots"
    tmp_dir.mkdir(exist_ok=True)

    # тестовый кадр
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample_pick.png"
    if not fixture.exists():
        pytest.skip("Нет fixtures/sample_pick.png — добавь кадр и перезапусти тест.")

    for f in tmp_dir.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass
    shutil.copy2(fixture, tmp_dir / fixture.name)

    # снимем до-знаки (mtime/size)
    before_mtime = overlay.stat().st_mtime if overlay.exists() else 0.0
    before_size = overlay.stat().st_size if overlay.exists() else -1

    # небольшой сдвиг, чтобы mtime точно отличался по секундам на Windows
    time.sleep(1.2)

    # запуск
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(release_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        time.sleep(8)
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

    # проверки
    assert overlay.exists(), "После запуска детектора overlay_data.json не появился"
    after_mtime = overlay.stat().st_mtime
    after_size = overlay.stat().st_size

    # Достаточно изменения времени ИЛИ размера (очистка даёт size=0 и новый mtime)
    assert (after_mtime > before_mtime) or (after_size != before_size), \
        "overlay_data.json не изменился ни по времени, ни по размеру"

    data = _read_json_safe(overlay)
    # файл может быть пустым — это допустимо
    assert (data is None) or isinstance(data, list), "overlay_data.json должен быть списком или пустым"

    if isinstance(data, list) and data:
        row = data[0]
        assert isinstance(row, dict), "элементы overlay_data.json должны быть объектами"
        assert "hero" in row and "counters" in row and "box" in row, "неполный объект в overlay_data.json"
