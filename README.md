# LLM 推理服务平台

从原有 API、Router、Web、DB 四仓整理出的个人实践项目。React 控制台、FastAPI 控制面、请求路由、PostgreSQL 与健康探测组成单机平台，复用 vLLM/Ollama 执行模型。

## 学习入口

[项目二：从零到工程实战教材](../投递档案/字节跳动_DataAML_机器学习系统调度编排工程师/项目二_从零到工程实战教材.md) 是统一教材，覆盖基础、源码、隔离实验、排障、取舍、证据与面试。阶段 Markdown 已合并清理；不必按历史报告时间线阅读。

- 第 1—10 章：基础；第 11—26 章：请求、数据与前端。
- 第 27—36 章：发布恢复与隔离实验；第 37—44 章：GPU、联调、排障与重建。
- 第 45—48 章及附录：48 道练习答案、JD 对应、参数账本和原始证据入口。

## 链路与目录

```text
浏览器 → Web → API → PostgreSQL
              → Router → 外部推理引擎
                  ↓
                 API → 请求与决策记录
Monitor → 后端探测 → API健康历史
```

| 目录 | 职责 |
|---|---|
| services/api/ | 模型、后端、Key、候选评分、请求审计 |
| services/router/ | 选路、单进程准入、有界执行与审计、TTFT/Prometheus |
| web/ | React/Vite 控制台与 Nginx 入口 |
| db/ | 8 表契约、初始化迁移、种子 |
| ops/ | 健康状态机、发布账本 |
| scripts/ | 初始化、检查、冒烟、发布、专项验证 |
| packaging/ | 本机镜像与可选 vLLM 兼容配置 |
| artifacts/ | 已有原始 JSON/CSV/日志及测试报告 |
| docs/source-provenance.json | 原四仓路径、commit 与已有未提交改动 |

原四仓保留在 `D:/projects/platform/`。新项目不依赖 Gitea/Jenkins；旧环境没有因整合而卸载。Windows Go 网关与制品台账没有接入当前请求链路。

## 使用与验证

日常部署的历史入口是 `http://127.0.0.1:18080`，API/Router 为 18000/18001，数据库为 55433；当前运行状态使用前核实。管理员 Key 在本根目录 `.state/admin-key`，不入 Git，不打印或分享。容器内 `127.0.0.1` 指容器本身，后端地址必须从 Router 所在网络可达。

第一次学习先执行教材第 32—36 章：独立源码根、临时数据库、端口、Key、状态和产物一起隔离。测试会重建专用数据库 public schema；`_test` 后缀只是一道校验，不能替代确认所有权。不要在日常源码根随手执行 bootstrap、smoke 或测试。

已有环境的发布入口为 `scripts/release.py <新且不复用的tag> --build`，恢复入口为同脚本的 `--recover-only`。它们会真实修改服务，先读教材第 27—28 章并核对 `.env`、项目名和目标。回退只恢复应用镜像，不恢复数据库、配置、Key 或模型；首次发布没有已知前版。Compose 固定项目名和端口，复制目录不等于隔离部署。

依赖以各服务 requirements 文件和 Web 锁文件为准。GitHub Actions 配置检查及三个镜像构建，`push:false`，不自动部署；没有远端执行成功的证据。

## 已有证据与范围

2026-10-18 保留产物记录 API 87、Router 45、Web 20、运维 7，共 159 项核心模块测试；另有 21 项协议桩冒烟、真实引擎冒烟和 24 项跨项目联调。统计单位不同，不合并成端到端总数；这次教材编写没有重跑实现测试或服务。

Router 支持 weighted_random、least_latency、least_inflight；准入只覆盖本进程入口，数据库 max_concurrency 与 Key RPS 字段并未接入执行。内部 OpenAI SSE 可采 TTFT，浏览器仍收到完整 JSON；Ollama 非流式不进入当前 TTFT 窗口。

健康探测有 3 坏/2 好防抖、状态文件恢复和 Compose 下 60 秒 TTL；发布有单机互斥、事务标识和中断恢复。它们不等于生产高可用、全局 GPU Quota 或数据库灾备。

联调伸缩 CPU 转发副本，仍共享单 GPU，训练侧是占位；没有多 GPU 迁移或无损缩容结论。LMCache 已退出；原生 CPU KV 卸载作为正确性专项保留，见 [运行配置说明](packaging/vllm/README.md) 和教材第 38—39 章，无性能收益结论。
