"""Configuration-driven upstream test runner for registered datasets."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Dataset, Settings, validate_parameters
from .upstream import UpstreamClient, UpstreamError


def run_config_checks(settings: Settings, dataset_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    selected = _select_datasets(settings, dataset_ids)
    results = []
    for dataset in selected:
        if not dataset.test_cases:
            results.append(_result(dataset, "configuration", "skipped", "未定义 test_cases"))
            continue
        for case in dataset.test_cases:
            validate_parameters(dataset, {str(k): str(v) for k, v in case.get("params", {}).items()})
            results.append(_result(dataset, case["id"], "passed", "配置和参数有效"))
    return _report("config", results)


def run_live_checks(
    settings: Settings,
    client: Optional[UpstreamClient] = None,
    dataset_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = _select_datasets(settings, dataset_ids)
    client = client or UpstreamClient(settings)
    results = []
    for dataset in selected:
        if not dataset.test_cases:
            results.append(_result(dataset, "live", "skipped", "未定义 test_cases"))
            continue
        for case in dataset.test_cases:
            started_at = time.monotonic()
            try:
                params = validate_parameters(dataset, {str(k): str(v) for k, v in case.get("params", {}).items()})
                payload, cached, _ = client.fetch_pool(dataset.pool_id, params, refresh=True)
                errors = _validate_response(payload, case.get("expect", {}))
                status = "passed" if not errors else "failed"
                message = "响应符合预期" if not errors else "; ".join(errors)
                results.append(_result(dataset, case["id"], status, message, cached, started_at))
            except (ValueError, UpstreamError) as exc:
                results.append(_result(dataset, case["id"], "error", str(exc), False, started_at))
    return _report("live", results)


def write_report(report: Dict[str, Any], output: str) -> None:
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_datasets(settings: Settings, dataset_ids: Optional[List[str]]) -> List[Dataset]:
    if not dataset_ids:
        return [dataset for dataset in settings.datasets.values() if dataset.enabled]
    selected = []
    for dataset_id in dataset_ids:
        dataset = settings.datasets.get(dataset_id)
        if not dataset or not dataset.enabled:
            raise ValueError("未找到已启用数据集: " + dataset_id)
        selected.append(dataset)
    return selected


def _validate_response(payload: Dict[str, Any], expect: Dict[str, Any]) -> List[str]:
    errors = []
    if payload.get("success", True) is not True:
        errors.append("上游 success 不是 true")
    data = payload.get("data")
    expected_type = expect.get("data_type", "any")
    actual_type = _data_type(data)
    if expected_type != "any" and actual_type != expected_type:
        errors.append("data 类型为 %s，期望 %s" % (actual_type, expected_type))
    min_items = expect.get("min_items")
    if min_items is not None:
        if not isinstance(data, list):
            errors.append("min_items 仅适用于列表响应")
        elif len(data) < min_items:
            errors.append("data 条数 %d，小于期望 %d" % (len(data), min_items))
    return errors


def _data_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _result(
    dataset: Dataset,
    case_id: str,
    status: str,
    message: str,
    cached: bool = False,
    started_at: Optional[float] = None,
) -> Dict[str, Any]:
    result = {
        "dataset": dataset.id,
        "pool_id": dataset.pool_id,
        "case": case_id,
        "status": status,
        "message": message,
        "cached": cached,
    }
    if started_at is not None:
        result["duration_ms"] = round((time.monotonic() - started_at) * 1000, 1)
    return result


def _report(mode: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for result in results:
        counts[result["status"]] += 1
    return {"mode": mode, "summary": counts, "results": results}
