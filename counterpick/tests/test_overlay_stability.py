import json
import random
import subprocess
import sys
import time
from pathlib import Path
import shutil

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

def _pick_any_hero(icons_dir: Path) -> str:
    icons = [p for p in icons_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTS]
    assert icons, f"No hero icons found in {icons_dir}"
    return random.choice(icons).stem  # имя файла без расширения

def test_overlay_survives_frequent_overlay_data_writes(release_dir, proc_guard):
    """Оверлей не должен падать, если overlay_data.json часто перезаписывается."""
    exe = release_dir / "overlay_window.exe"
    assert exe.exists(), f"{exe} not found"

    icons_dir = release_dir / "hero_icons"
    assert icons_dir.is_dir(), f"hero_icons dir missing: {icons_dir}"

    overlay_json = release_dir / "overlay_data.json"
    backup = release_dir / "overlay_data.bak"

    # Бэкапим оригинал
    if overlay_json.exists():
        shutil.move(str(overlay_json), str(backup))

    # Стартуем оверлей с защитой proc_guard
    proc = proc_guard(subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    ))

    # Дадим подняться окну
    time.sleep(0.8)
    assert proc.poll() is None, "overlay_window.exe exited too early at startup"

    # 15 быстрых обновлений overlay_data.json
    for i in range(15):
        hero = _pick_any_hero(icons_dir)
        # Немного "шевелим" box, имитируя разные позиции
        x1 = random.randint(1560, 1585)
        y1 = random.randint(320, 450)
        x2 = x1 + random.randint(80, 110)
        y2 = y1 + random.randint(45, 65)

        payload = [
            {
                "hero": hero,
                "counters": ["huskar", "juggernaut", "ember_spirit", "lifestealer"],
                "box": [x1, y1, x2, y2]
            }
        ]
        overlay_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        time.sleep(0.2)
        assert proc.poll() is None, f"overlay_window.exe crashed during write #{i+1}"

    # финальная проверка через маленькую задержку
    time.sleep(0.5)
    assert proc.poll() is None, "overlay_window.exe exited after rapid writes"

    # Восстановление overlay_data.json
    overlay_json.unlink(missing_ok=True)
    if backup.exists():
        shutil.move(str(backup), str(overlay_json))
