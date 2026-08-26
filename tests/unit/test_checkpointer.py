from langgraph.checkpoint.sqlite import SqliteSaver

from src.graph.checkpointer import build_checkpointer


def test_build_checkpointer_returns_a_usable_sqlite_saver(tmp_path):
    db_path = tmp_path / "checkpoints.db"

    checkpointer = build_checkpointer(str(db_path))

    assert isinstance(checkpointer, SqliteSaver)
    assert db_path.exists()


def test_build_checkpointer_allows_access_from_a_different_thread(tmp_path):
    # check_same_thread=False (docstring): a submissao do requisito e a
    # decisao de aprovacao chegam em threads diferentes do servidor.
    import threading

    db_path = tmp_path / "checkpoints.db"
    checkpointer = build_checkpointer(str(db_path))
    errors: list[Exception] = []

    def _use_from_another_thread():
        try:
            config = {"configurable": {"thread_id": "t1"}}
            list(checkpointer.list(config))
        except Exception as exc:  # noqa: BLE001 - queremos ver qualquer falha de thread
            errors.append(exc)

    thread = threading.Thread(target=_use_from_another_thread)
    thread.start()
    thread.join()

    assert errors == []
