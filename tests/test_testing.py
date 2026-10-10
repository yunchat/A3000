from data_platform.config import load_settings
from data_platform.testing import run_config_checks, run_live_checks


class FakeUpstreamClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def fetch_pool(self, pool_id, params, refresh):
        self.calls.append((pool_id, params, refresh))
        return self.payload, False, 1728000000.0


def test_config_checks_pass_for_registered_dataset():
    settings = load_settings("config/datasets.json")

    report = run_config_checks(settings)

    assert report["mode"] == "config"
    assert report["summary"] == {"passed": 1, "failed": 0, "error": 0, "skipped": 0}


def test_live_check_validates_response_shape():
    settings = load_settings("config/datasets.json")
    upstream = FakeUpstreamClient({"success": True, "data": []})

    report = run_live_checks(settings, client=upstream)

    assert report["summary"]["passed"] == 1
    assert upstream.calls == [(2, {}, True)]


def test_live_check_reports_contract_mismatch():
    settings = load_settings("config/datasets.json")
    upstream = FakeUpstreamClient({"success": True, "data": {}})

    report = run_live_checks(settings, client=upstream)

    assert report["summary"]["failed"] == 1
    assert "期望 list" in report["results"][0]["message"]
