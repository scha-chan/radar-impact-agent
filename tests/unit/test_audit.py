import json

from src.observability.audit import AuditRecord, read_audit_trail, record_audit


def test_record_audit_appends_a_json_line(tmp_path):
    path = tmp_path / "trail.jsonl"
    record = AuditRecord(
        session_id="s1",
        decision="ESCALATED",
        actor="system",
        risk_level="HIGH",
        confidence=63,
        threshold=70,
    )

    record_audit(record, path=str(path))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["session_id"] == "s1"
    assert entry["decision"] == "ESCALATED"
    assert entry["actor"] == "system"
    assert entry["risk_level"] == "HIGH"
    assert entry["confidence"] == 63
    assert entry["threshold"] == 70
    assert entry["tool_authorized"] is None
    assert "timestamp" in entry


def test_record_audit_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "trail.jsonl"

    record_audit(AuditRecord(session_id="s1", decision="ESCALATED", actor="system"), path=str(path))

    assert path.exists()


def test_record_audit_appends_without_truncating(tmp_path):
    path = tmp_path / "trail.jsonl"
    record_audit(AuditRecord(session_id="s1", decision="ESCALATED", actor="system"), path=str(path))
    record_audit(AuditRecord(session_id="s1", decision="AUTO_PUBLISHED", actor="system"), path=str(path))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_record_audit_includes_reason_only_when_present(tmp_path):
    path = tmp_path / "trail.jsonl"
    record_audit(
        AuditRecord(session_id="s1", decision="BLOCKED_ADVERSARIAL", actor="system", reason="x"),
        path=str(path),
    )
    record_audit(
        AuditRecord(session_id="s1", decision="ESCALATED", actor="system"),
        path=str(path),
    )

    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]
    assert entries[0]["reason"] == "x"
    assert "reason" not in entries[1]


def test_read_audit_trail_filters_by_session_id_and_preserves_order(tmp_path):
    path = tmp_path / "trail.jsonl"
    record_audit(AuditRecord(session_id="s1", decision="ESCALATED", actor="system"), path=str(path))
    record_audit(AuditRecord(session_id="s2", decision="BLOCKED_ADVERSARIAL", actor="system"), path=str(path))
    record_audit(AuditRecord(session_id="s1", decision="APPROVED_PUBLISHED", actor="human"), path=str(path))

    entries = read_audit_trail("s1", path=str(path))

    assert [e["decision"] for e in entries] == ["ESCALATED", "APPROVED_PUBLISHED"]


def test_read_audit_trail_returns_empty_list_when_file_does_not_exist(tmp_path):
    assert read_audit_trail("s1", path=str(tmp_path / "does-not-exist.jsonl")) == []


def test_read_audit_trail_returns_empty_list_for_unknown_session(tmp_path):
    path = tmp_path / "trail.jsonl"
    record_audit(AuditRecord(session_id="s1", decision="ESCALATED", actor="system"), path=str(path))

    assert read_audit_trail("s-desconhecida", path=str(path)) == []


def test_read_audit_trail_skips_blank_lines(tmp_path):
    path = tmp_path / "trail.jsonl"
    record_audit(AuditRecord(session_id="s1", decision="ESCALATED", actor="system"), path=str(path))
    with path.open("a", encoding="utf-8") as f:
        f.write("\n")
    record_audit(AuditRecord(session_id="s1", decision="AUTO_PUBLISHED", actor="system"), path=str(path))

    entries = read_audit_trail("s1", path=str(path))

    assert [e["decision"] for e in entries] == ["ESCALATED", "AUTO_PUBLISHED"]
