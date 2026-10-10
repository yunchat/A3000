import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    pool_id: int
    enabled: bool
    parameters: Dict[str, Dict[str, Any]]
    test_cases: List[Dict[str, Any]]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    api_base: str
    username: str
    timeout_seconds: int
    cache_ttl_seconds: int
    datasets: Dict[str, Dataset]


def load_settings(path: Union[str, Path]) -> Settings:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"无法读取配置 {source}: {exc}") from exc

    try:
        server = raw["server"]
        upstream = raw["upstream"]
        entries = raw["datasets"]
        datasets = {
            item["id"]: Dataset(
                id=item["id"],
                name=item["name"],
                pool_id=int(item["pool_id"]),
                enabled=bool(item.get("enabled", True)),
                parameters=dict(item.get("parameters", {})),
                test_cases=list(item.get("test_cases", [])),
            )
            for item in entries
        }
        if not datasets:
            raise ConfigError("datasets 不能为空")
        return Settings(
            host=str(server.get("host", "127.0.0.1")),
            port=int(server.get("port", 8765)),
            api_base=str(upstream["api_base"]).rstrip("/"),
            username=str(upstream["username"]),
            timeout_seconds=int(upstream.get("timeout_seconds", 20)),
            cache_ttl_seconds=int(upstream.get("cache_ttl_seconds", 60)),
            datasets=datasets,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"配置字段不完整或非法: {exc}") from exc

    for dataset in datasets.values():
        _validate_test_cases(dataset)


def validate_parameters(dataset: Dataset, params: Dict[str, str]) -> Dict[str, str]:
    unknown = set(params) - set(dataset.parameters)
    if unknown:
        raise ConfigError(f"不支持的参数: {', '.join(sorted(unknown))}")

    validated = {}  # type: Dict[str, str]
    for name, spec in dataset.parameters.items():
        value = params.get(name)
        if not value:
            if spec.get("required"):
                raise ConfigError(f"缺少必填参数: {name}")
            continue
        if spec.get("type") == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                raise ConfigError(f"参数 {name} 必须为 YYYY-MM-DD") from exc
        validated[name] = value
    return validated


def _validate_test_cases(dataset: Dataset) -> None:
    case_ids = set()
    for case in dataset.test_cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ConfigError(f"数据集 {dataset.id} 的 test_cases 必须包含字符串 id")
        if case["id"] in case_ids:
            raise ConfigError(f"数据集 {dataset.id} 的测试用例 id 重复: {case['id']}")
        case_ids.add(case["id"])
        params = case.get("params", {})
        if not isinstance(params, dict):
            raise ConfigError(f"测试用例 {dataset.id}/{case['id']} 的 params 必须是对象")
        validate_parameters(dataset, {str(k): str(v) for k, v in params.items()})
        expect = case.get("expect", {})
        if not isinstance(expect, dict):
            raise ConfigError(f"测试用例 {dataset.id}/{case['id']} 的 expect 必须是对象")
        data_type = expect.get("data_type", "any")
        if data_type not in ("any", "list", "object", "null"):
            raise ConfigError(f"测试用例 {dataset.id}/{case['id']} 的 data_type 不支持: {data_type}")
        min_items = expect.get("min_items")
        if min_items is not None and (not isinstance(min_items, int) or min_items < 0):
            raise ConfigError(f"测试用例 {dataset.id}/{case['id']} 的 min_items 必须是非负整数")
