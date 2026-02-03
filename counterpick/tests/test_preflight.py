from pathlib import Path

def test_release_folder_exists(release_dir):
    assert release_dir.exists(), "❌ Нет папки release_stub"

def test_executables_present(release_dir):
    for name in ["overlay_window.exe", "screenshot_detector.exe", "screenshot_windows.exe"]:
        p = release_dir / name
        assert p.exists(), f"❌ Нет {name} в release_stub"

def test_core_json_present(release_dir):
    for name in ["overlay_data.json", "overlay_state.json", "counters.json"]:
        p = release_dir / name
        assert p.exists(), f"❌ Нет {name} в release_stub"

def test_weights_present(weights_dir):
    p = weights_dir / "best.pt"
    assert p.exists(), "❌ Нет weights/best.pt"
    assert p.stat().st_size >= 1_000_000, "⚠️ best.pt подозрительно маленький (<1 МБ)"

def test_hero_icons_present(release_dir):
    icons_dir = release_dir / "hero_icons"
    pngs = list(icons_dir.glob("*.png"))
    jpgs = list(icons_dir.glob("*.jpg")) + list(icons_dir.glob("*.jpeg"))
    icons = pngs + jpgs
    assert icons, "❌ Папка release_stub/hero_icons пуста или отсутствует (ожидались .png или .jpg)"


def test_tmp_screenshots_folder(release_dir):
    assert (release_dir / "tmp_screenshots").exists(), "❌ Нет папки release_stub/tmp_screenshots"
