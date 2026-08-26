import pytest

from tests.helpers import close_all_sqlite_connections


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


@pytest.fixture(autouse=True)
def _close_sqlite_connections():
    """Achado do card 26 (análise do log do job "test" da CI): conexões
    sqlite abertas via `tests.helpers.sqlite_checkpointer` ficavam sem
    fechar, gerando `ResourceWarning: unclosed database` no relatório do
    pytest. Fecha qualquer conexão registrada ao fim de cada teste."""
    yield
    close_all_sqlite_connections()
