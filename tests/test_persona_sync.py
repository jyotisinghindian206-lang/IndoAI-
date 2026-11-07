from indo_persona_sync import explicit_preference, current_turn_style, sync_profile


class FakeDLM:
    def __init__(self):
        self.items = []
    def save(self, identity, text, **kwargs):
        self.items.insert(0, {"id": str(len(self.items) + 1), "identity": identity, "text": text, "source": kwargs.get("source"), "category": kwargs.get("category")})
        return {"saved": True}
    def list_all(self, identity, limit=500):
        return [item for item in self.items if item["identity"] == identity][:limit]


def test_explicit_preferences_only():
    assert explicit_preference("Please keep it short from now") == "Prefer concise answers unless the user asks for detail."
    assert explicit_preference("I like short videos") is None


def test_current_turn_style_is_not_persisted():
    assert "briefly" in current_turn_style("Just tell me briefly")
    assert explicit_preference("Just tell me briefly") is None


def test_sync_saves_account_preference_and_returns_profile():
    dlm = FakeDLM()
    result = sync_profile(dlm, "account-1", "Please explain in detail from now")
    assert "Prefer thorough explanations" in result
    assert len(dlm.items) == 1
    assert dlm.items[0]["source"] == "persona_sync"
    assert dlm.items[0]["category"] == "preference"


def test_sync_does_not_share_between_accounts():
    dlm = FakeDLM()
    sync_profile(dlm, "account-1", "Please keep it short")
    assert sync_profile(dlm, "account-2", "hello") == ""


def test_new_explicit_preference_replaces_old_preference_set():
    class ReplaceableDLM(FakeDLM):
        def delete(self, identity, memory_id=None, category=None, **kwargs):
            before = len(self.items)
            self.items = [x for x in self.items if not (x["identity"] == identity and
                ((memory_id and x.get("id") == memory_id) or (category and x["category"] == category)))]
            return before - len(self.items)
    dlm = ReplaceableDLM()
    sync_profile(dlm, "account-1", "Please keep it short from now")
    result = sync_profile(dlm, "account-1", "Please explain in detail from now")
    assert "Prefer thorough explanations" in result
    assert "Prefer concise answers" not in result
    assert len(dlm.items) == 1
