# LIBERO-Pro Table 3 单任务复现：当前服务器阶段性报告

更新时间：2026-09-22

## 目标

复现论文 Table 3（LIBERO-Pro，Success rates (%)）的评测方式，但只运行一个 task，不运行完整 4 settings × 10 tasks 矩阵。运行约束为只使用 GPU3，并把可复核的命令、结果和问题推送到远端仓库。

## 当前服务器审计结论

此前服务器实际可见的 LIBERO 资产是标准 LIBERO。本轮已按用户提供的官方仓库和 Hugging Face 数据集补齐 Pro 资产：

```text
LIBERO root: /usr1/home/s125mdg56_02/LIBERO
config:      /usr1/home/s125mdg56_02/.libero/config.yaml
benchmark_root: .../LIBERO/libero/libero
```

配置只指向标准 `bddl_files` / `init_files`，没有 `libero-pro-config`、`libero_goal_task`、`libero_goal_swap`、`libero_10_task` 或 `libero_10_swap` 的 Pro BDDL 和 init-state 目录。在 `/usr1/home/s125mdg56_02` 下也没有找到对应的 `LIBERO-PRO` 或 `libero-pro-config` 目录。

Pro 代码现位于 `/usr1/home/s125mdg56_02/LIBERO-PRO`，数据下载到其 `libero_data/` 后已复制到 Pro 代码的 `libero/libero/{bddl_files,init_files}`。因此可以继续进行真实 LIBERO-Pro 单 task 运行；运行时必须优先使用 `PYTHONPATH=/usr1/home/s125mdg56_02/LIBERO-PRO`，避免误加载标准 LIBERO 包。

### 资产与注册验证

官方仓库：`https://github.com/Zxy-MLlab/LIBERO-PRO`，浅克隆 revision：`eafdb80`。

官方数据集：`zhouxueyang/LIBERO-Pro`，下载 676 个文件到 `/usr1/home/s125mdg56_02/LIBERO-PRO/libero_data`，并复制到代码树。四个目标 suite 均实际加载成功：

| suite | tasks | task0 init states |
|---|---:|---:|
| `libero_goal_task` | 10 | 50 |
| `libero_goal_swap` | 10 | 50 |
| `libero_10_task` | 10 | 50 |
| `libero_10_swap` | 10 | 50 |

Zetta 环境导入名是 `liberopro.liberopro`，而官方仓库导入名是 `libero.libero`。直接运行第一次得到 `ModuleNotFoundError: No module named 'liberopro'`。解决方式是在 `/tmp/zetta-liberopro-pkg/liberopro/liberopro` 建立运行时副本，并将内部导入统一改写为 `liberopro.liberopro`；未修改仓库源代码或标准 LIBERO 安装。

## 首个真实单 task 结果

运行约束：GPU3、Pro Goal-T、task0、seed21、policy RNG 21001、Pi0.5 PyTorch checkpoint、官方 300 action horizon、5-action chunks、无 Role1。

结果：

| suite/task | prompt | status | success | env steps | elapsed |
|---|---|---|---:|---:|---:|
| `libero_goal_task/task0` | `open the middle drawer of the cabinet` | `valid` | **false (0%)** | 311 | 75.55 s |

这是一个真实 LIBERO-Pro episode：环境 reset、policy inference、官方 horizon 和视频生成均完成；在该 task/seed 上 Pi0.5 未在 horizon 内完成目标。因此这里的单 task success rate 是 0%，不是基础设施失败，也不代表 10-task macro-average。

原始结果目录（服务器本地、未提交大文件）：

```text
.local-repro/liberopro-goal-task0-seed21-v2/
```

视频：

```text
.local-repro/liberopro-goal-task0-seed21-v2/videos/episode_agentview.mp4
.local-repro/liberopro-goal-task0-seed21-v2/videos/episode_agentview_wrist.mp4
.local-repro/liberopro-goal-task0-seed21-v2/videos/episode_agentview_multiview.mp4
```

动作 artifact SHA-256：`147b951a95ffac1b2a9c6c7fee01e94d01ba4d4403e3d33df434be35b950db5b`。

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

## 资产到位后的单 task 命令模板

下面模板只启动 GPU3，并在运行前对 Pro 配置路径做 fail-fast 检查；将 `LIBERO_PRO_CONFIG`、suite、task prompt 和 checkpoint 改成实际值即可：

```bash
export LIBERO_PRO_CONFIG=/path/to/libero-pro-config
test -d "$LIBERO_PRO_CONFIG" || { echo "missing LIBERO_PRO_CONFIG"; exit 2; }

CUDA_VISIBLE_DEVICES=3 \
LIBERO_TYPE=pro \
LIBERO_CONFIG_PATH="$LIBERO_PRO_CONFIG" \
TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 \
MUJOCO_GL=egl PYOPENGL_PLATFORM=egl EGL_PLATFORM=egl \
python -m rollout_runtime.cli serve \
  --config /path/to/pro-runtime.yaml --host 127.0.0.1 --port 18740 \
  --launch local

# 另一终端：只跑一个 task，成功率就是该 task 的 0% 或 100%
CUDA_VISIBLE_DEVICES=3 LIBERO_CONFIG_PATH="$LIBERO_PRO_CONFIG" \
python robots/libero/run_evolution_rollout.py \
  --suite libero_goal_task --task-id 0 \
  --task libero_goal_task/task0 --seed 21 --policy-rng 21001 \
  --logical-id liberopro-one-task0-seed21 --attempt-index 0 --generation 0 \
  --baseline-mode strict_pure_vla \
  --output-dir .local-repro/liberopro-one-task0-seed21 \
  --result-file .local-repro/liberopro-one-task0-seed21-result.json \
  --runtime-url http://127.0.0.1:18740 --policy-id pi05 \
  --max-actions 300 --wait-steps 10 --actions-per-chunk 5 \
  --role1-planner none --record-latency
```

若该 task 的官方 termination 成功，则该单 task 的 success rate 为 100%；否则为 0%。这不是 10-task macro-average，符合本阶段“只复现一个 task”的范围。

## 当前阶段结论

本提交完成了“单 task Pro 复现前的服务器审计和阻塞定位”，但**没有把标准 LIBERO 结果冒充 LIBERO-Pro Table 3 结果**。阻塞根因是 Pro benchmark 资产缺失，而不是 GPU3、runtime 或 rollout 入口故障。
