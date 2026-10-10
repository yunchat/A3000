# Local Market Data Platform

首版是单进程、本机部署的数据代理。它使用 FastAPI、本地 JSON 配置、服务端 token 管理和进程内 TTL 缓存。

## 启动

```bash
/opt/miniconda3/bin/python3 -m data_platform.server
```

默认只绑定 `127.0.0.1:8765`。本项目要求 Python 3.10+；当前开发环境使用 Conda 的 `/opt/miniconda3/bin/python3`（3.10.16）。配置位于 `config/datasets.json`；新增可用接口时，在 `datasets` 中增加一个白名单条目，而不是开放任意 `pool_id`。

## API

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/v1/datasets
curl http://127.0.0.1:8765/v1/datasets/market.limit-up
curl 'http://127.0.0.1:8765/v1/datasets/market.limit-up?date=2026-10-09'
curl 'http://127.0.0.1:8765/v1/datasets/market.limit-up?refresh=true'
```

`refresh=true` 会绕过本机内存缓存。token 仅存在于进程内，永不返回给 API 调用者。

启动后可通过 [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs) 使用 FastAPI 自动生成的交互式接口文档。

## 首版范围

- 本地文件配置数据集、参数白名单、上游地址和缓存 TTL。
- `GET /health`、数据目录和受控数据读取 API。
- 内存 token 缓存与内存响应缓存。

后续再加入 Redis、持久化快照、定时调度、用户权限、前端管理页和 MCP 服务。

## 数据接口测试

每个数据集可在 `config/datasets.json` 的 `test_cases` 中定义测试参数和响应契约。新增接口后，先增加至少一个测试用例，再运行：

```bash
# 不访问上游：检查数据集、参数和测试配置
/opt/miniconda3/bin/python3 -m data_platform.test_runner --mode config

# 访问上游：验证真实接口是否可访问、响应是否符合配置约束
/opt/miniconda3/bin/python3 -m data_platform.test_runner --mode live

# 仅探测一个数据集，并保存 JSON 报告
/opt/miniconda3/bin/python3 -m data_platform.test_runner --mode live --dataset market.limit-up --output reports/live.json

# 运行离线回归测试
/opt/miniconda3/bin/python3 -m pytest
```

联机测试不会输出上游 token 或完整响应内容。若上游不可达、返回业务失败或响应类型不符合声明，命令会以非零状态退出，便于后续接入 CI 或定时巡检。
