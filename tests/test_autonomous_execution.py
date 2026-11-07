from indo_autonomous_execution import AutonomousExecution
import pytest


def test_workflow_requires_approval_and_tracks_steps(tmp_path):
    engine = AutonomousExecution(tmp_path)
    item = engine.create('google:a@example.com', 'Build a Python app with tests')
    assert item['status'] == 'awaiting_approval'
    with pytest.raises(PermissionError):
        engine.advance('google:a@example.com', item['id'], 'step_1', 'in_progress')
    item = engine.approve('google:a@example.com', item['id'])
    assert item['approved'] is True
    item = engine.advance('google:a@example.com', item['id'], 'step_1', 'in_progress')
    assert item['status'] == 'in_progress'
    item = engine.advance('google:a@example.com', item['id'], 'step_1', 'completed', 'Inspected source')
    assert item['steps'][0]['result'] == 'Inspected source'


def test_workflows_are_account_isolated(tmp_path):
    engine = AutonomousExecution(tmp_path)
    item = engine.create('google:a@example.com', 'Research renewable energy options')
    assert engine.get('google:b@example.com', item['id']) is None
    assert engine.list('google:b@example.com') == []


def test_consequential_step_is_not_executable_by_tracker(tmp_path):
    engine = AutonomousExecution(tmp_path)
    item = engine.create('google:a@example.com', 'Deploy the production app')
    engine.approve('google:a@example.com', item['id'])
    with pytest.raises(PermissionError):
        engine.advance('google:a@example.com', item['id'], 'step_3', 'in_progress')


def test_secret_like_goal_is_rejected(tmp_path):
    engine = AutonomousExecution(tmp_path)
    with pytest.raises(ValueError):
        engine.create('google:a@example.com', 'Deploy using my API key abc123')


def test_cancel_and_delete_workflow_are_account_scoped(tmp_path):
    engine = AutonomousExecution(tmp_path)
    item = engine.create("acct-a", "Research a better database architecture")
    assert engine.cancel("acct-b", item["id"]) is None
    cancelled = engine.cancel("acct-a", item["id"])
    assert cancelled["status"] == "cancelled"
    assert engine.delete("acct-b", item["id"]) is False
    assert engine.delete("acct-a", item["id"]) is True


def test_workflow_snapshot_round_trip_is_account_scoped_and_merges_newer(tmp_path):
    source = AutonomousExecution(tmp_path / "source")
    target = AutonomousExecution(tmp_path / "target")
    created = source.create("acct-a", "Research a durable workflow store")
    source.approve("acct-a", created["id"])
    snapshot = source.export_account("acct-a")
    assert target.import_account("acct-a", snapshot) == 1
    restored = target.get("acct-a", created["id"])
    assert restored and restored["approved"] is True
    assert target.get("acct-b", created["id"]) is None
    with pytest.raises(ValueError):
        target.import_account("acct-b", snapshot)


def test_workflow_snapshot_does_not_overwrite_newer_local_record(tmp_path):
    source = AutonomousExecution(tmp_path / "source")
    target = AutonomousExecution(tmp_path / "target")
    created = source.create("acct-a", "Research a durable workflow store")
    target.import_account("acct-a", source.export_account("acct-a"))
    target.approve("acct-a", created["id"])
    newer = target.get("acct-a", created["id"])
    stale = source.export_account("acct-a")
    stale["records"][0]["updated_at"] = newer["updated_at"] - 1
    assert target.import_account("acct-a", stale) == 0
    assert target.get("acct-a", created["id"])["approved"] is True
