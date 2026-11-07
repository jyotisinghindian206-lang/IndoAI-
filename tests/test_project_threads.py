from indo_project_threads import CrossSessionProjectThreads


def test_project_decision_survives_sessions_and_is_account_scoped(tmp_path):
    engine = CrossSessionProjectThreads(tmp_path)
    saved = engine.record_turn("acct-a", "For Indo AI, we choose Supabase for persistent cloud storage.",
                               "That keeps account data in cloud storage.", session_id="s1", project_hint="indo ai")
    assert saved["saved"]
    context = engine.context("acct-a", "indo ai")
    assert "Supabase" in context
    assert engine.context("acct-b", "indo ai") == ""
    assert engine.list_projects("acct-a")[0]["project_name"] == "indo ai"


def test_no_project_or_secret_is_saved(tmp_path):
    engine = CrossSessionProjectThreads(tmp_path)
    assert not engine.record_turn("acct-a", "hello there, how are you?")["saved"]
    assert not engine.record_turn("acct-a", "For Indo AI, my API key is secret-value", project_hint="indo ai")["saved"]


def test_milestone_and_project_detail(tmp_path):
    engine = CrossSessionProjectThreads(tmp_path)
    engine.record_turn("acct-a", "Indo AI Level 1 is implemented and now works.", project_hint="indo ai")
    events = engine.events("acct-a", "indo ai")
    assert any(x["event_type"] == "milestone" for x in events)


def test_encrypted_cloud_snapshot_round_trip(tmp_path):
    from cryptography.fernet import Fernet
    cipher = Fernet(Fernet.generate_key())
    first = CrossSessionProjectThreads(tmp_path / "first")
    first.record_turn("acct-a", "For Indo AI, we choose Supabase for persistent cloud storage.", project_hint="indo ai")
    encrypted = first.cloud_export("acct-a", cipher)
    assert "Supabase" not in encrypted
    second = CrossSessionProjectThreads(tmp_path / "second")
    assert second.cloud_import("acct-a", encrypted, cipher) >= 1
    assert "Supabase" in second.context("acct-a", "indo ai")
    assert second.context("acct-b", "indo ai") == ""


def test_project_and_event_deletion_is_account_scoped(tmp_path):
    engine = CrossSessionProjectThreads(tmp_path)
    engine.record_turn("acct-a", "For Indo AI, we choose Supabase for persistent cloud storage.", project_hint="indo ai")
    events = engine.events("acct-a", "indo ai")
    assert events
    assert engine.delete_event("acct-b", events[0]["id"]) is False
    assert engine.delete_event("acct-a", events[0]["id"]) is True
    engine.record_turn("acct-a", "For Indo AI, we choose Supabase for persistent cloud storage.", project_hint="indo ai")
    assert engine.delete_project("acct-a", "indo ai") >= 1
    assert engine.context("acct-a", "indo ai") == ""
