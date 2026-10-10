from fastapi.testclient import TestClient

from data_platform.config import load_settings
from data_platform.server import create_app


class FakeUpstreamClient:
    def fetch_pool(self, pool_id, params, refresh):
        return {"success": True, "source": "fixture", "data": []}, False, 1728000000.0


def test_registered_dataset_is_available():
    app = create_app(load_settings("config/datasets.json"), FakeUpstreamClient())
    client = TestClient(app)

    response = client.get("/v1/datasets/market.limit-up?date=2026-10-09")

    assert response.status_code == 200
    assert response.json()["meta"]["parameters"] == {"date": "2026-10-09"}


def test_unregistered_parameter_is_rejected():
    app = create_app(load_settings("config/datasets.json"), FakeUpstreamClient())
    client = TestClient(app)

    response = client.get("/v1/datasets/market.limit-up?code=1.600000")

    assert response.status_code == 400
    assert "不支持的参数" in response.json()["detail"]


