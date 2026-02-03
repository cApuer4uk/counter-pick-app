import json
import subprocess
import sys
import time
from pathlib import Path
import shutil
from datetime import datetime

def _dump_logs(proc: subprocess.Popen, logs_dir: Path, tag: str):
    try:
        stdout, stderr = proc.communicate(timeout=0)
    except Exception:
        stdout, stderr = (b"", b"")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (logs_dir / f"{tag}_{ts}_stdout.log").write_bytes(stdout or b"")
    (logs_dir / f"{tag}_{ts}_stderr.log").write_bytes(stderr or b"")

def test_overlay_survives_broken_then_valid_json(release_dir, proc_guard):
    exe = release_dir / "overlay_window.exe"
    assert exe.exists(), f"{exe} not found"

    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    overlay_json = release_dir / "overlay_data.json"
    backup = release_dir / "overlay_data.bak"

    if overlay_json.exists():
        shutil.move(str(overlay_json), str(backup))

    # запускаем через proc_guard
    proc = proc_guard(subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    ))

    try:
        time.sleep(0.8)
        assert proc.poll() is None, "overlay_window.exe exited too early at startup"

        # битый JSON
        overlay_json.write_text("{ bad json", encoding="utf-8")
        time.sleep(0.4)
        assert proc.poll() is None, "overlay_window.exe crashed on broken JSON write"

        # валидный JSON
        valid_payload = [
            {
                "hero": "any_hero_name",
                "counters": ["huskar", "juggernaut", "ember_spirit", "lifestealer"],
                "box": [1573, 334, 1665, 385]
            }
        ]
        overlay_json.write_text(json.dumps(valid_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.6)
        assert proc.poll() is None, "overlay_window.exe crashed after recovering to valid JSON"

        # пустой -> снова валидный
        overlay_json.write_text("", encoding="utf-8")
        time.sleep(0.3)
        assert proc.poll() is None, "overlay_window.exe crashed on empty JSON"

        overlay_json.write_text(json.dumps(valid_payload, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.5)
        assert proc.poll() is None, "overlay_window.exe crashed after second recovery"

    except AssertionError:
        try:
            _dump_logs(proc, logs_dir, "overlay_invalid_json_fail")
        finally:
            raise
    finally:
        # восстановление overlay_data.json
        try:
            overlay_json.unlink(missing_ok=True)
        except TypeError:
            if overlay_json.exists():
                overlay_json.unlink()
        if backup.exists():
            shutil.move(str(backup), str(overlay_json))

        # ЖЁСТКАЯ зачистка на Windows по имени процесса (на случай отрыва дочернего PID)
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/IM", "overlay_window.exe", "/F", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
