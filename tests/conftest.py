import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Isola o diretório de trabalho de todo teste. A partir do card 20,
    `decide_autonomy`/`block`/`publish_comment`/`archive` gravam a trilha
    de auditoria (`audit/trail.jsonl`, caminho relativo por padrão) a cada
    execução — sem isolar o cwd, qualquer teste que rode o grafo real
    passaria a escrever no próprio repositório. `tmp_path` é o mesmo
    diretório descartável que um teste recebe se também pedir o fixture
    `tmp_path` diretamente (ambos são o mesmo fixture, `function`-scoped).
    """
    monkeypatch.chdir(tmp_path)
