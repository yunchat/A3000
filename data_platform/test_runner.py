import argparse
import json
import sys

from .config import ConfigError, load_settings
from .testing import run_config_checks, run_live_checks, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="数据接口配置校验和联机探测")
    parser.add_argument("--config", default="config/datasets.json", help="数据集配置文件")
    parser.add_argument("--mode", choices=("config", "live"), default="config", help="config 不访问上游；live 访问真实上游")
    parser.add_argument("--dataset", action="append", dest="dataset_ids", help="仅测试指定数据集；可重复传入")
    parser.add_argument("--output", help="将 JSON 报告写入文件")
    args = parser.parse_args()
    try:
        settings = load_settings(args.config)
        report = run_config_checks(settings, args.dataset_ids) if args.mode == "config" else run_live_checks(settings, dataset_ids=args.dataset_ids)
    except (ConfigError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
    if args.output:
        write_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["summary"]["failed"] or report["summary"]["error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
