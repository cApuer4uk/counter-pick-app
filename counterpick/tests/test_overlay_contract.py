def _is_number(x):
    return isinstance(x, (int, float))

def test_overlay_data_contract(release_dir, load_json):
    p = release_dir / "overlay_data.json"
    data = load_json(p)

    # Пустой файл допустим для smoke-теста (между запусками сервисов)
    if data is None:
        return

    assert isinstance(data, list), "overlay_data.json: корень должен быть списком"

    for i, row in enumerate(data):
        assert isinstance(row, dict), f"[{i}] ожидался объект"
        hero = row.get("hero")
        counters = row.get("counters")
        box = row.get("box")

        assert isinstance(hero, str) and hero.strip(), f"[{i}] поле 'hero' некорректно"
        assert isinstance(counters, list), f"[{hero}] 'counters' должен быть списком"
        assert isinstance(box, (list, tuple)) and len(box) == 4, f"[{hero}] 'box' должен быть из 4 чисел"
        assert all(_is_number(v) for v in box), f"[{hero}] 'box' должен содержать числа"

        for c in counters:
            if isinstance(c, str):
                assert c.strip(), f"[{hero}] пустой элемент в 'counters'"
            elif isinstance(c, dict):
                name = c.get("counter")
                assert isinstance(name, str) and name.strip(), f"[{hero}] некорректное поле 'counter'"
            else:
                raise AssertionError(f"[{hero}] неподдерживаемый тип в 'counters': {type(c)}")
