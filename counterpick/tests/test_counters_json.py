def test_counters_json_contract(release_dir, load_json):
    # В release_stub всё лежит рядом, без подпапки db
    p = release_dir / "counters.json"
    data = load_json(p)

    assert isinstance(data, list), "В корне должен быть список объектов-героев"
    assert data, "Файл пуст — ожидались герои"

    seen = set()
    for i, item in enumerate(data):
        assert isinstance(item, dict), f"[{i}] ожидался объект героя"

        hero = item.get("hero")
        assert isinstance(hero, str) and hero.strip(), f"[{i}] пустое поле 'hero'"
        key = hero.lower().strip()
        assert key not in seen, f"Дубликат героя: {hero}"
        seen.add(key)

        counters = item.get("counters")
        assert isinstance(counters, list), f"[{hero}] 'counters' должен быть списком"

        for c in counters:
            # допускаем две формы: строка или объект {counter, score?}
            if isinstance(c, str):
                assert c.strip(), f"[{hero}] пустой элемент в 'counters'"
            elif isinstance(c, dict):
                name = c.get("counter")
                assert isinstance(name, str) and name.strip(), f"[{hero}] некорректное поле 'counter'"
                score = c.get("score", None)
                if score is not None:
                    assert isinstance(score, int), f"[{hero}] 'score' должен быть int"
            else:
                raise AssertionError(f"[{hero}] неподдерживаемый тип элемента в 'counters': {type(c)}")
