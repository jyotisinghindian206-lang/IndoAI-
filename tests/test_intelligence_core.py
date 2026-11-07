from indo_intelligence_core import IndoIntelligenceCore


class FakeResearch:
    def status(self):
        return {"enabled": True, "active_background_jobs": 1, "cached_findings": 4, "prepared_followups": 2}


def test_core_reports_feature_readiness_without_sensitive_data():
    core = IndoIntelligenceCore(
        anticipatory=FakeResearch(), persona_sync=object(), project_threads=object(),
        devil_advocate=object(), autonomous=object(), hyperlocal=object(), dlm=object(),
    )
    status = core.status()
    assert status["state"] == "ready"
    assert status["features_ready"] == 7
    assert status["background_research"]["active_jobs"] == 1
    assert "secret" not in str(status).lower()
    assert "no device geolocation" in status["location_policy"]
