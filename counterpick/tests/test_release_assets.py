from pathlib import Path
import json

def test_release_has_core_files(release_dir: Path):
    must_exist = [
        "overlay_window.exe",
        "screenshot_detector.exe",
        "counters.json",
        "overlay_data.json",      # может быть пустой, но файл должен лежать
        "overlay_state.json",
        "hero_icons",
    ]
    for name in must_exist:
        p = release_dir / name
        assert p.exists(), f"Missing in release_stub: {p}"

def test_hero_icons_nonempty(release_dir: Path):
    icons = list((release_dir / "hero_icons").glob("*.*"))
    assert icons, "hero_icons is empty"

def test_counters_json_minimal_schema(release_dir: Path):
    data = json.loads((release_dir / "counters.json").read_text(encoding="utf-8"))
    assert isinstance(data, list), "counters.json must be a list"
    # проверим несколько первых элементов
    for item in data[:3]:
        assert isinstance(item.get("hero"), str) and item["hero"], "hero must be non-empty string"
        assert isinstance(item.get("counters"), list), "counters must be list"
        for c in item["counters"]:
            if isinstance(c, str):
                assert c
            elif isinstance(c, dict):
                assert isinstance(c.get("counter"), str) and c["counter"]
                if "score" in c:  # опционально
                    assert isinstance(c["score"], (int, float))
            else:
                raise AssertionError("counter must be str or {counter, score}")
