import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request

from .config import ConfigError, Dataset, Settings, load_settings, validate_parameters
from .upstream import UpstreamClient, UpstreamError


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _catalog_item(dataset: Dataset) -> Dict:
    return {"id": dataset.id, "name": dataset.name, "parameters": dataset.parameters}


def create_app(settings: Settings, client: UpstreamClient) -> FastAPI:
    app = FastAPI(
        title="Local Market Data Platform",
        version="0.1.0",
        description="A local, allowlist-based market data proxy.",
    )

    @app.get("/health")
    def health() -> Dict:
        return {"ok": True, "service": "local-data-platform"}

    @app.get("/v1/datasets")
    def list_datasets() -> Dict:
        return {"data": [_catalog_item(item) for item in settings.datasets.values() if item.enabled]}

    @app.get("/v1/datasets/{dataset_id}")
    def get_dataset(
        dataset_id: str,
        request: Request,
        refresh: bool = Query(False, description="绕过本机内存缓存"),
    ) -> Dict:
        dataset = settings.datasets.get(dataset_id)
        if not dataset or not dataset.enabled:
            raise HTTPException(status_code=404, detail="dataset_not_found")
        supplied = {
            name: value
            for name, value in request.query_params.items()
            if name != "refresh"
        }
        try:
            params = validate_parameters(dataset, supplied)
            payload, cached, fetched_at = client.fetch_pool(dataset.pool_id, params, refresh)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except UpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return {
            "meta": {
                "dataset": dataset.id,
                "pool_id": dataset.pool_id,
                "parameters": params,
                "fetched_at": _iso(fetched_at),
                "cached": cached,
            },
            "data": payload.get("data"),
            "upstream": {"success": payload.get("success", True), "source": payload.get("source")},
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal local market data platform")
    parser.add_argument("--config", default="config/datasets.json", help="本地 JSON 配置文件")
    args = parser.parse_args()
    settings = load_settings(Path(args.config))
    app = create_app(settings, UpstreamClient(settings))
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
