# LIBERO-Pro Table 3 单任务复现：当前服务器阶段性报告

更新时间：2026-09-22

## 目标

复现论文 Table 3（LIBERO-Pro，Success rates (%)）的评测方式，但只运行一个 task，不运行完整 4 settings × 10 tasks 矩阵。运行约束为只使用 GPU3，并把可复核的命令、结果和问题推送到远端仓库。

## 当前服务器审计结论

当前服务器实际可见的 LIBERO 资产是标准 LIBERO：

```text
LIBERO root: /usr1/home/s125mdg56_02/LIBERO
config:      /usr1/home/s125mdg56_02/.libero/config.yaml
benchmark_root: .../LIBERO/libero/libero
```

配置只指向标准 `bddl_files` / `init_files`，没有 `libero-pro-config`、`libero_goal_task`、`libero_goal_swap`、`libero_10_task` 或 `libero_10_swap` 的 Pro BDDL 和 init-state 目录。在 `/usr1/home/s125mdg56_02` 下也没有找到对应的 `LIBERO-PRO` 或 `libero-pro-config` 目录。

因此，当前机器不能合法地产生 Table 3 的 LIBERO-Pro 单 task 分数；用标准 LIBERO task 替代会改变 benchmark，不能作为论文 Table 3 结果。

审计还直接验证了仓库提供的 Pro 安装工具入口存在，但其历史源路径不存在：

```text
python scripts/evolution/integrate_liberopro_benchmark.py --help  # 可执行
/home/pai/zxw/LIBERO-PRO/libero/libero                    # 不存在
```

所以阻塞发生在 benchmark 数据输入层，而不是注册脚本缺失或 rollout 入口不可用。

## 已完成的可复现基础

- Zetta runtime 已配置为单卡 `CUDA_VISIBLE_DEVICES=3`。
- Pi0.5 PyTorch checkpoint 已转换并可在 GPU3 上运行。
- 标准 LIBERO 端到端 rollout 已成功，视频与轨迹保存在 `.local-repro/`（该目录按设计被 gitignore）。
- `robots/libero/run_evolution_rollout.py` 已支持通过 `LIBERO_TYPE` 选择 benchmark，不再强制写死 `pro`。
- 已记录 EGL、PyTorch `weights_only`、checkpoint 格式和 runtime 启动问题及解决方式，见 [current-server-reproduction-progress.md](current-server-reproduction-progress.md)。

## 需要的外部输入

要继续完成真正的单 task LIBERO-Pro 复现，需要把论文对应的 Pro 资产提供到服务器，并确认其路径，至少包括：

1. 一个目标 suite 的 10 个 BDDL（任选一个 task，例如 `libero_goal_task/task0`）；
2. 对应 task 的 50 个 init states；
3. Pro 配置文件中的 `assets`、`bddl_files`、`init_states` 路径；
4. 论文 Table 3 所用 checkpoint（当前 Pi0.5 checkpoint 可用于链路验证，但不应默认等同论文模型）。

拿到资产后，单 task 验收应同时保存：

- `status=valid`，并使用环境官方 termination 判定 `success`；
- task、seed、policy RNG、horizon、checkpoint SHA-256；
- GPU 约束和 runtime 配置；
- rollout 视频、trajectory/action JSONL、latency summary；
- 一份 Markdown，明确区分真实 Pro 结果、基础设施失败和未完成项。

## 当前阶段结论

本提交完成了“单 task Pro 复现前的服务器审计和阻塞定位”，但**没有把标准 LIBERO 结果冒充 LIBERO-Pro Table 3 结果**。阻塞根因是 Pro benchmark 资产缺失，而不是 GPU3、runtime 或 rollout 入口故障。
