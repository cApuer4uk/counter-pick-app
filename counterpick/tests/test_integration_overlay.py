import json
import subprocess
import sys
import time
from pathlib import Path
import shutil

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

def test_overlay_smoke_start(release_dir, proc_guard):
    exe = release_dir / "overlay_window.exe"
    assert exe.exists(), f"{exe} not found"

    icons_dir = release_dir / "hero_icons"
    icons = sorted([p for p in icons_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTS])
    assert icons, f"No hero icons with {SUPPORTED_EXTS} in {icons_dir}"

    # Берём имя героя из первого файла (stem = имя без расширения)
    hero_name = icons[0].stem

    test_overlay = [
        {
            "hero": hero_name,
            "counters": ["huskar", "juggernaut", "ember_spirit"],
            "box": [1573, 334, 1665, 385]
        }
    ]

    overlay_json = release_dir / "overlay_data.json"
    backup = release_dir / "overlay_data.bak"

    # Подмена overlay_data.json на время теста
    if overlay_json.exists():
        shutil.move(str(overlay_json), str(backup))
    overlay_json.write_text(json.dumps(test_overlay, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = proc_guard(subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    ))

    try:
        time.sleep(3)
        assert proc.poll() is None, "overlay_window.exe exited prematurely"
    finally:
        # Восстановление overlay_data.json
        try:
            overlay_json.unlink(missing_ok=True)
        except TypeError:
            # если Python <3.8, делаем безопасно
            if overlay_json.exists():
                overlay_json.unlink()
        if backup.exists():
            shutil.move(str(backup), str(overlay_json))
