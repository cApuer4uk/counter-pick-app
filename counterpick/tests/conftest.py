from pathlib import Path
import json
import pytest
import os, sys, subprocess, signal, time

@pytest.fixture(scope="session")
def app_root() -> Path:
    # .../counterpick (папка, где лежат release_stub, db, weights, tests)
    return Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session")
def release_dir(app_root: Path) -> Path:
    return app_root / "release_stub"

@pytest.fixture(scope="session")
def weights_dir(app_root: Path) -> Path:
    return app_root / "weights"

@pytest.fixture
def load_json():
    def _load(p: Path):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            return None  # пустой файл трактуем как "пусто" без ошибки
        return json.loads(text)
    return _load

def kill_process_tree(proc: subprocess.Popen, timeout: float = 2.0):
    """
    Аккуратно пытаемся завершить процесс, затем гарантированно убиваем всё дерево.
    Работает и если .exe успел расплодить дочерние процессы.
    """
    if proc.poll() is not None:
        return  # уже умер

    # 1) Мягкая попытка
    try:
        proc.terminate()
    except Exception:
        pass

    try:
        proc.wait(timeout=timeout)
        return
    except Exception:
        pass

    # 2) Жёстко, с деревом
    try:
        if sys.platform.startswith("win"):
            # /T - дерево, /F - принудительно
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            # *nix: посылаем всей группе процессов
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
    except Exception:
        # Последняя страховка
        try:
            proc.kill()
        except Exception:
            pass

@pytest.fixture
def proc_guard():
    """
    Фикстура-контекст: регистрируем процессы и убиваем их деревья в конце теста.
    Использование:
        proc = subprocess.Popen(...); proc_guard(proc)
    """
    spawned = []
    def _reg(p: subprocess.Popen):
        spawned.append(p)
        return p
    yield _reg
    # teardown: гарантированно прибьём всё, что зарегистрировано
    for p in spawned:
        kill_process_tree(p, timeout=2.0)