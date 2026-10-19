# 本机 CPU KV 卸载配置入口

这是可选专项的运行契约。完整原理、源码、正确性证据和局限见[项目二教材第38—39章](../../../投递档案/字节跳动_DataAML_机器学习系统调度编排工程师/项目二_从零到工程实战教材.md#p38)。主线请求治理不依赖重做这个实验；LMCache 已退出，不恢复已清理的旧模板。

## 固定组合

2026-10-18 留存验收组合：RTX4070 Laptop 8GB、Qwen2.5-3B-AWQ、vLLM 0.27.1 固定镜像摘要。配置文件 `local-cpu-offload-patch.json`：CPU KV 512MiB、GPU KV 256MiB、内存型 `/dev/shm` 上限 1GiB、context 5000、旧执行器、FlashInfer、关闭异步调度。预算不是最优容量；GPU KV 不包括权重和其他工作区。

`wsl_offload_compat.py` 只替换私有块搬运函数，以同一 CUDA stream 逐块 cudaMemcpyAsync 明确 D2H/H2D；缓存管理与事件仍由原引擎负责。接口、库名和参数绑定当前版本，升级或换硬件需重新验证；逐块提交可能降低吞吐。

## 重新应用前

下面操作会修改现有模型 Deployment。先确认显式 context/server/namespace、当前模型实例、镜像 digest、驱动挂载、Recreate 策略与可恢复的原 Deployment。这里只保留操作入口，不在读教材时自动执行；地址是本机快照。

从 inference-platform 根目录执行配置生成和应用：

```bash
kubectl --context k3d-ai-cluster --server=https://127.0.0.1:46121 -n ai-platform \
  create configmap fei-wsl-offload-compat --from-file=packaging/vllm/wsl_offload_compat.py --dry-run=client -o yaml > /tmp/fei-offload-compat.yaml
kubectl --context k3d-ai-cluster --server=https://127.0.0.1:46121 apply -f /tmp/fei-offload-compat.yaml
kubectl --context k3d-ai-cluster --server=https://127.0.0.1:46121 -n ai-platform \
  patch deployment vllm-3b --type strategic --patch-file packaging/vllm/local-cpu-offload-patch.json
```

引擎 Ready 后另验证可达地址；转发工具只管理自己登记的进程，不修改 Windows/Tailscale。`scripts/validate_native_offload.py` 可在明确端点上验证冷请求、GPU 热命中、挤出与 CPU 回读，报告选独立输出路径，不覆盖保留证据。

原始结果在 `artifacts/native-offload/`：每轮外部恢复 1280 Token、GPU 原生命中增量 0、约 45MiB CPU→GPU、回答一致。它们证明当前专项的功能正确性线索，不证明所有 KV 逐位一致、长期稳定或 TTFT/吞吐收益。当前 Pod、端口转发和显存状态使用前重新核实。
