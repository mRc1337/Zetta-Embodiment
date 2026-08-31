# Zetta × LIBERO-Pro 评测实验日志

> 单一人工可读日志；原始机器可读 episode 与 latency 事件保存在各次运行的 artifact 目录。本文件不记录密钥、私有 API 地址或认证信息。

## 目标与验收

- [x] 将 `/home/pai/zxw/LIBERO-PRO` 的 benchmark 注册接入当前 `liberopro` 包。
- [x] 验证 `libero_goal_task`、`libero_goal_swap`、`libero_10_task`、`libero_10_swap` 均为 10 个任务，且每个任务加载后的 init-state 集合非空。
- [x] 使用冻结的 Pi0.5 基座运行真实 LIBERO-Pro episode，记录官方终止信号与成功率。
- [x] 提供可配置的分组件延迟事件与 count/mean/p50/p95/max 汇总，并运行若干真实任务。
- [x] 按论文 §4.1 冻结 4 setting × 10 task 的正式 campaign matrix，并验证 development/test seed 隔离、官方 horizon 与逐 episode latency 配置。

## 固定环境

| 项目 | 值 |
|---|---|
| 记录开始（UTC） | 2026-08-31T10:06:13Z |
| Zetta commit | `3512e7ccb9ed416f30d92fafb3ba5e037436544d` |
| Python | 3.11.15 |
| PyTorch | 2.7.1+cu126 |
| MuJoCo / robosuite | 3.3.1 / 1.4.1 |
| GPU | 4 × NVIDIA A800-SXM4-80GB（81920 MiB） |
| checkpoint | `/home/pai/zxw/openpi_data/pi05_libero/checkpoints/RLinf-Pi05-LIBERO-SFT` |
| runtime venv | `/home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311` |
| benchmark source | `/home/pai/zxw/LIBERO-PRO/libero/libero` |
| Ray 临时目录 | `/tmp/zr2`（规避 Linux AF_UNIX 107 字节路径限制） |
| EGL vendor 描述 | `scripts/evolution/nvidia-egl-vendor.json` |

## 实验时间线

### 2026-08-31T10:04:21Z — LoopX 控制面初始化

- 将当前 Codex SSH thread 绑定到 agent `zetta-liberopro-eval-codex-01`。
- 创建 4 个 P0/P1/P2 Todo，覆盖注册、评测、延迟和证据汇总。
- 问题：目标注册表初始 `write_scope=[]`，quota guard 判定 `boundary_projection_repair`，禁止交付写入。
- 根因：LoopX bootstrap 默认只读，尚未投影用户在本目标中明确授予的代码与实验输出写权限。
- 解决：使用 `loopx configure-goal` 将权限限制到本任务涉及的 repo 路径、当前 `liberopro` 安装和结果目录，并记录 authority source 为 `explicit_user_request`。
- 验证：全局注册表读回成功；quota guard 从 `self_repair` 变为 `run`，`normal_delivery_allowed=true`。
- 次要问题：`heartbeat-prompt --host-surface codex-app-ssh` 不接受连字符 token；改用 runtime profile `codex_app_ssh_goal` 后成功生成心跳契约。

### 2026-08-31T10:06:13Z — benchmark 接入前审计

- 本地源中四个目标 suite 均有 10 个 BDDL 和 10 个 init 文件；文件计数合计分别为 40 和 40。
- 当前安装包已有四套件数据目录，但 `benchmark/__init__.py` 未注册四个类，`libero_suite_task_map.py` 也缺少四个映射，因此运行时 `get_benchmark(...)` 无法解析它们。
- namespace 差异：源使用 `libero.libero`，当前包使用 `liberopro.liberopro`。
- PyTorch 差异：当前环境需保留 `torch.load(..., weights_only=False)` 才能读取受信任的 LIBERO init-state 文件。
- 实现决策：新增可重复执行的 `scripts/evolution/integrate_liberopro_benchmark.py`，同步本地注册代码和四套件数据、仅做上述 namespace/PyTorch 兼容转换，并在覆盖前保存备份。

## Benchmark 注册验证

### 2026-08-31T10:07:43Z — 安装与全量 init-state 验证

执行：

```bash
python3 scripts/evolution/integrate_liberopro_benchmark.py \
  --source-package /home/pai/zxw/LIBERO-PRO/libero/libero \
  --target-package /home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311/lib/python3.11/site-packages/liberopro/liberopro \
  --backup-root /home/pai/zxw/openpi_data/pi05_libero/results/registration-backups \
  --execute
```

- 安装前备份：`/home/pai/zxw/openpi_data/pi05_libero/results/registration-backups/20260831T100743Z`。
- 更新注册代码 2 个文件，源数据同步时新增或修正 11 个文件。
- 安装后代码 SHA-256：`benchmark/__init__.py` = `bd2938bd241a9378dd550412b13bf10a76d032ab390ce4ae12d3a00a8c31dbdc`；`libero_suite_task_map.py` = `0feec8499da91e25a134273b6624ffa7adb9c6dc7da23f8cb5e3cd8998d1c80f`。
- 验证方法：在目标 venv 和目标 `LIBERO_CONFIG_PATH` 下，通过 `get_benchmark(name)()` 创建 suite，逐任务检查 BDDL 路径，并调用 `get_task_init_states(task_id)` 实际反序列化，而非只检查文件大小。

| suite | 注册 | 任务数 | BDDL 全存在 | 每任务 init 数 | init 非空 |
|---|---:|---:|---:|---|---:|
| `libero_goal_task` | 是 | 10 | 是 | 10 × 50 | 是 |
| `libero_goal_swap` | 是 | 10 | 是 | 10 × 50 | 是 |
| `libero_10_task` | 是 | 10 | 是 | 10 × 50 | 是 |
| `libero_10_swap` | 是 | 10 | 是 | 10 × 50 | 是 |

结论：四个目标套件已从当前 `liberopro` 安装包 API 可见，40/40 个任务均有可加载且长度为 50 的 init-state 集合。

## 实际评测结果

成功仅采用环境官方 termination；基础设施失败单列，不计为策略失败。

### 2026-08-31T10:15:34Z — Goal-T task0 seed21，首次尝试（基础设施无效）

| suite/task | seed | mode | status | success | elapsed |
|---|---:|---|---|---:|---:|
| `libero_goal_task/task0` | 21 | strict pure Pi0.5 | `infra_invalid` | N/A | 11.33 s |

- 服务健康：4/4 env rank healthy，12/12 heartbeat 正常；4 张卡各加载约 7593 MiB。
- 问题：冻结 task contract 期望 `open the middle drawer of the cabinet`，环境 reset 返回 `open the bottom drawer of the cabinet`，fail-closed 校验终止。
- 根因：LIBERO-Pro Task perturbation 保留基准任务文件名，但 BDDL 内 `(:language ...)` 与 `(:goal ...)` 已改变。`prepare_libero_campaign.py` 原探针读取由文件名生成的 `Task.language`；真实环境正确读取 BDDL language。
- 解决：预注册探针改为从安装包解析目标 BDDL 的 `(:language ...)`，仅在字段不存在时回退 `Task.language`。本任务真实 prompt 为 `open the bottom drawer of the cabinet`。
- 计分：这是任务身份冻结错误，尚未执行 policy action，按协议不计成功或失败。

### 2026-08-31T10:22:47Z–10:49:13Z — 两个完整 horizon episode

两次运行均使用冻结的 `RLinf-Pi05-LIBERO-SFT`、`strict_pure_vla`、`role1-planner=none` 和 5-action receding horizon。Goal suite 的官方 contract 是 10 个 reset/warm-up step 加 300 个 policy action，共 310 个环境 step。

| suite/task | seed | prompt | status | success | env actions | policy chunks | elapsed | failure |
|---|---:|---|---|---:|---:|---:|---:|---|
| `libero_goal_task/task0` | 21 | `open the bottom drawer of the cabinet` | `valid` | false | 310 | 60 | 43.271 s | `horizon_incomplete` |
| `libero_goal_swap/task0` | 35 | `Open the middle layer of the drawer` | `valid` | false | 310 | 60 | 46.932 s | `horizon_incomplete` |

- 小样本实际成功率：0/2（0%）。它只证明评测链路能够完成官方 horizon 并消费环境官方 termination，不能外推为四套件正式成功率。
- `horizon_incomplete` 表示在权威 horizon 内未收到成功 termination，不是基础设施错误。
- 原始结果：`/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_eval/goal_task_t0_seed21-r1-result.json` 和 `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_eval/goal-swap-t0-seed35-full-result.json`。

### Runtime 启动与单 episode 复现

当前镜像缺少系统级 NVIDIA GLVND vendor JSON；仓库中的等价描述避免依赖易失的 `/tmp/zetta-nvidia-egl-vendor.json`。先从单 rank PRO preset 生成本机配置，仅替换 checkpoint 占位路径：

```bash
cd /home/pai/zxw/Zetta-Embodiment
cp rollout_runtime/config/presets/a100_libero_pi05_pro_dynamic.yaml /tmp/zetta-liberopro-runtime.yaml
sed -i 's#/path/to/checkpoints/RLinf-Pi05-LIBERO-SFT#/home/pai/zxw/openpi_data/pi05_libero/checkpoints/RLinf-Pi05-LIBERO-SFT#' /tmp/zetta-liberopro-runtime.yaml
mkdir -p /tmp/zr2

MUJOCO_GL=egl \
PYOPENGL_PLATFORM=egl \
__EGL_VENDOR_LIBRARY_FILENAMES=/home/pai/zxw/Zetta-Embodiment/scripts/evolution/nvidia-egl-vendor.json \
LIBERO_CONFIG_PATH=/home/pai/zxw/openpi_data/pi05_libero/libero-pro-config \
TMPDIR=/tmp/zr2 \
RAY_TMPDIR=/tmp/zr2 \
/home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311/bin/python \
  -m rollout_runtime.cli serve \
  --config /tmp/zetta-liberopro-runtime.yaml \
  --launch ray --host 127.0.0.1 --port 18730
```

另一个终端执行完整 Goal-S task0；其余 suite/task/seed 只需替换对应参数与 BDDL language：

```bash
cd /home/pai/zxw/Zetta-Embodiment
LIBERO_CONFIG_PATH=/home/pai/zxw/openpi_data/pi05_libero/libero-pro-config \
/home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311/bin/python \
  robots/libero/run_evolution_rollout.py \
  --suite libero_goal_swap --task-id 0 \
  --task libero_goal_swap/task0 \
  --seed 35 --policy-rng 35001 \
  --logical-id goal-swap-t0-seed35-full --attempt-index 0 --generation 0 \
  --baseline-mode strict_pure_vla \
  --output-dir /home/pai/zxw/openpi_data/pi05_libero/results/liberopro_eval/goal-swap-t0-seed35-full \
  --result-file /home/pai/zxw/openpi_data/pi05_libero/results/liberopro_eval/goal-swap-t0-seed35-full-result.json \
  --expected-task-language 'Open the middle layer of the drawer' \
  --runtime-url http://127.0.0.1:18730 --policy-id pi05 \
  --max-actions 300 --wait-steps 10 --actions-per-chunk 5 \
  --role1-planner none --record-latency
```

这里没有启用 Role1，因此该复现不需要 LLM API 或密钥。

## 延迟结果

### 实现与配置

直接 episode runner 的 `--record-latency` 总开关默认关闭；正式 campaign prepare 默认开启并冻结该开关。打开后可用 `--latency-events`、`--latency-summary` 指定输出，用 `--latency-components` 提供逗号分隔的组件 allowlist。默认输出为 episode 目录下的 `latency/events.jsonl` 和 `latency/summary.json`。

可记录组件：observation preprocess、policy queue wait、model inference、action decode/postprocess、policy request end-to-end、environment execution、critic evaluation、Role1 LLM request、recovery execution、chunk end-to-end 和 episode end-to-end。每条事件写 JSONL；汇总提供 count、mean、p50、p95、max。纯 Pi0.5 实测未触发 Role1/recovery，二者路径由单测覆盖。

### 2026-08-31T10:37:13Z — EGL reset 基础设施失败

- 四次初始尝试在 reset 阶段返回 `ENV_FAILURE: [Errno 104] Connection reset by peer`，均记为 `infra_invalid`，不计为策略失败。
- Ray actor 日志显示 MuJoCo EGL 初始化时 `eglQueryDevicesEXT()` 返回 0。系统存在 `/lib/x86_64-linux-gnu/libEGL_nvidia.so.0`，但 `/usr/share/glvnd/egl_vendor.d` 没有 NVIDIA vendor 描述。
- 修复：设置 `MUJOCO_GL=egl`、`PYOPENGL_PLATFORM=egl`，并令 `__EGL_VENDOR_LIBRARY_FILENAMES` 指向仓库内 `scripts/evolution/nvidia-egl-vendor.json`；重启 Runtime 后 reset 和四套件运行均通过。

### 2026-08-31T10:46:43Z — 四套件部分任务

每套件运行 task0、50 个 policy action 加 10 个 warm-up step，共 60 env actions / 10 次模型推理。它们是延迟诊断运行，不是官方完整 horizon，因此 `success=false` 不进入正式成功率。

| suite | seed | run | status | env actions | inference calls | latency events | elapsed |
|---|---:|---|---|---:|---:|---:|---:|
| `libero_goal_task` | 31 | `goal-task-t0-seed31-r2` | `valid` | 60 | 10 | 101 | 22.681 s |
| `libero_goal_swap` | 32 | `goal-swap-t0-seed32-r1` | `valid` | 60 | 10 | 101 | 19.931 s |
| `libero_10_task` | 33 | `libero10-task-t0-seed33-r1` | `valid` | 60 | 10 | 101 | 26.194 s |
| `libero_10_swap` | 34 | `libero10-swap-t0-seed34` | `valid` | 60 | 10 | 101 | 26.188 s |

四套件聚合（40 次模型推理；environment/critic 各 80 个 timing）：

| component | count | mean ms | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|---:|---:|
| model inference | 40 | 300.878 | 233.814 | 822.421 | 933.090 |
| policy queue wait | 40 | 20.999 | 20.793 | 21.291 | 26.779 |
| observation preprocess | 40 | 5.570 | 2.869 | 5.637 | 72.877 |
| action decode/postprocess | 40 | 0.172 | 0.166 | 0.212 | 0.230 |
| policy request end-to-end | 40 | 348.886 | 299.755 | 865.660 | 981.851 |
| environment execution | 80 | 91.394 | 73.806 | 209.244 | 250.682 |
| critic evaluation（Critic 未配置，no-op） | 80 | 0.006 | 0.007 | 0.009 | 0.013 |
| chunk end-to-end | 40 | 653.029 | 616.920 | 1177.002 | 1227.323 |

Goal-S 完整 horizon 另外记录 501 条事件：60 次 model inference 平均 201.460 ms、p95 230.152 ms；queue wait 平均 20.750 ms；chunk end-to-end 平均 528.649 ms。四套件部分运行中的首次模型加载/热身抬高了聚合 p95，完整运行更接近稳态。

原始 summary：

- `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_latency/goal-task-t0-seed31-r2/latency/summary.json`
- `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_latency/goal-swap-t0-seed32-r1/latency/summary.json`
- `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_latency/libero10-task-t0-seed33-r1/latency/summary.json`
- `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_latency/libero10-swap-t0-seed34/latency/summary.json`
- `/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_eval/goal-swap-t0-seed35-full/latency/summary.json`

## 论文 §4.1 正式评测矩阵

### 2026-08-31T15:22:31Z–15:28:00Z — 40-task campaign dry-run

新增 `scripts/evolution/prepare_liberopro_paper_campaigns.py`，将 Goal-T、Goal-S、LIBERO-10-T、LIBERO-10-S 映射到 `libero_goal_task`、`libero_goal_swap`、`libero_10_task`、`libero_10_swap`。每个 task 生成独立、不可变、可通过 `--resume` 审计后续跑的 campaign；中断后只跳过 manifest 与矩阵完全一致的 task，部分目录或协议漂移会 fail closed。

协议冻结如下：

| 项目 | 冻结值 |
|---|---:|
| setting / tasks | 4 / 40 |
| development seeds | 每 task 随机确定 50 个，强制排除 1–20 |
| development rollout slots / round | 2000 |
| diagnosis target | 最大 failure cluster 的 deterministic medoid |
| held-out seeds | 每 task 固定 1–20 |
| held-out episodes / method | 800 |
| development success gate | ≥ 50% |
| originating-cluster historical regression | 100%（不跳过 regression gate） |
| held-out 用途 | `test`，仅最终报告，不参与 candidate promotion |
| horizon | Goal 300+10；LIBERO-10 520+10，均为 OpenPI official contract |
| latency | 每 episode 开启，11 个组件全部冻结进 manifest 和 rollout command |

实现时发现并修复两个协议缺口：

- 单 task campaign 虽支持 episode latency，但原 `prepare_libero_campaign.py` 没有把 `--record-latency` 和组件集合写进冻结 rollout command。现已把开关、组件、事件/汇总 artifact 约定同时写入 runtime manifest 和 preregistration。
- 原 CLI 默认把 held-out 当 validation gate，可能让 seeds 1–20 反向影响 patch 选择。正式矩阵强制 `heldout_mode=test`，并显式启用 regression gate，保持最终测试隔离。

真实安装包 dry-run 结果：四个 suite 各 10 个 task，每 task 最少 50 个可加载 init states；40 个 campaign、2000 个 development slots、800 个 held-out episodes/method；所有 seed partition 无重叠，40/40 horizon 为 official，latency 全开启。

代码提交并推送为 `cac81c398a741c670e1f0ba8e5fcc89faa204787` 后，已在本地结果目录 materialize 全部 40 个 campaign manifest：`/home/pai/zxw/openpi_data/pi05_libero/results/liberopro_paper_v1/cac81c398a741c670e1f0ba8e5fcc89faa204787`。`campaign-plan.json` 的文件 SHA-256 为 `9ad682ef0755ea1b43a1b165cf0d9fd2b485d99f3aa30b90ff2a07f925d013e8`；再次用 `--resume` 执行得到 40/40 `prepared`，证明恢复路径会校验并复用相同 manifest。

复现 dry-run（不写 campaign artifact）：

```bash
/home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311/bin/python \
  scripts/evolution/prepare_liberopro_paper_campaigns.py \
  --output-root /tmp/zetta-liberopro-paper-dry-run \
  --runtime-python /home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311/bin/python \
  --dry-run
```

本节只证明正式矩阵与 40 个 manifest 已冻结、可恢复；尚未产生 40-task development 或 seeds 1–20 的正式成功率，不得作为论文复现实验结果。正式运行应从干净的 `cac81c3` source worktree 启动，以匹配 manifest 的 source revision。

### 2026-08-31T15:44:43Z–15:51:00Z — development 首批次与共享 session 竞争

启动前重新读取 LoopX experiment board，并对四条运行逐一执行 source revision fence。固定 source worktree 为 `cac81c398a741c670e1f0ba8e5fcc89faa204787`，结果均为 `admitted=true`、`source_clean=true`。manifest 中的绝对 runner 路径仍指向主 worktree；主 worktree 此时只比固定提交多本日志，`robots/libero`、`rollout_runtime`、`zetta`、`scripts/evolution` 与 `tests` 的树 diff 为空，且 `run_evolution_rollout.py` 两侧 SHA-256 同为 `b6f182146a46c2ab62702161accd1d95f6231ca427b37c297e2f4c35c0c4997c`。

四个 task0 campaign 均已初始化可恢复的 `state` 与 `queue`，每个 queue 预登记 50 个 development jobs；本批只消费第一个固定 seed。seeds `66655`、`59451`、`85862`、`63675` 均不属于 held-out `1–20`。运行前在 LoopX board 写入四条 `status=running` 记录，终止后按真实结果更新；当前均为 `score_countable=false`，不可作为完整套件成绩。

| setting | suite | seed | official horizon | 结果 | attempts | 说明 |
|---|---|---:|---:|---|---:|---|
| Goal-T | `libero_goal_task` | 66655 | 300+10 | `infra_invalid` | 2 | reset 返回 `SESSION_NOT_READY`，重试返回 `UNKNOWN_SESSION` |
| Goal-S | `libero_goal_swap` | 59451 | 300+10 | `infra_invalid` | 2 | reset 返回 `SESSION_NOT_READY`，重试返回 `UNKNOWN_SESSION` |
| LIBERO-10-T | `libero_10_task` | 85862 | 520+10 | `infra_invalid` | 2 | reset 返回 `SESSION_NOT_READY`，重试返回 `QUOTA_EXCEEDED` |
| LIBERO-10-S | `libero_10_swap` | 63675 | 520+10 | `valid`, success=false | 1 | 完成 530 env actions，策略失败计入该 development episode |

前三个任务的四路并发 reset 命中了同一共享 session 的创建窗口；campaign supervisor 将其归类为基础设施失败、没有污染策略分母，并为可重试项维护 append-only queue/state。首 seed 已达到 manifest 冻结的两次 infrastructure attempt 上限，继续它们前需要先修复 runtime session 建立/并发 admission，或通过显式恢复授权提高预算；不得直接把这三条记作失败样本。

LIBERO-10-S 的有效 episode 记录 853 条 latency events。关键汇总：episode end-to-end 80.256 s；104 次 model inference 平均 235.485 ms、p95 278.559 ms；104 次 policy request end-to-end 平均 277.608 ms、p95 323.740 ms；104 个 chunk end-to-end 平均 572.229 ms、p95 627.018 ms；114 次 environment execution 平均 144.219 ms；114 次 Critic evaluation 平均 0.006 ms。Gen0 为 strict pure-VLA，Critic 是 no-op，Role1/recovery 未触发，因此没有这两类真实 API 延迟。

本批暴露的后继动作是先消除共享 session reset 竞争，再对 Goal-T、Goal-S、LIBERO-10-T 做同 seed 可审计恢复；在此之前不运行 held-out seeds。

## 最终验证

2026-08-31 再次从安装后的 `liberopro` API 创建四个 suite，并对每个 task 调用 `get_task_init_states`：40/40 BDDL 存在，四套件各 10 个任务，每个任务均反序列化得到 50 个非空 init states。

```text
56 targeted tests passed in 9.81s
40 campaigns / 2000 development slots / 800 held-out episodes per method: dry-run pass
git diff --check: pass
Python py_compile: pass
```

本轮目标测试覆盖 `tests/test_liberopro_paper_campaign_matrix.py`、`tests/test_libero_latency.py`、`tests/test_libero_evolution_runtime.py` 和 `tests/test_evolution_protocol.py`；此前 runtime policy/batch 测试仍保留在上一轮 95 项验证中。

LoopX experiment board 已写入 2 个 terminal、`diagnostic_only` 行（完整 Goal pilot 与四套件 latency profile）；二者 `score_countable=false`，没有伪装成官方结果或 matched comparison。对本日志单文件执行 `loopx check` 为 clean；全仓扫描只命中仓库既有源码/测试中的通用 `credential`、`private_ip` 字样，并未在本日志发现密钥或私有 API 地址。

## 已知限制与下一步

- 已完成两个完整 Goal horizon episode，但 0/2 只是链路验证样本，不代表 40-task benchmark 成绩；要报告套件成功率仍需按固定 seed 覆盖全部任务并给出分母。
- 四套件的 60-step 运行只用于比较延迟，不得计入正式成功率。
- 本轮 pure Pi0.5 未触发 Role1/recovery；这两个组件的真实 LLM/恢复延迟需要在启用 Critic 与 Role1 的独立实验中测量。
- 正式矩阵已在 `cac81c3` 上 materialize；下一步须从该 SHA 的干净 source worktree 执行 development baseline/故障聚类与 patch 流程，最后才可触碰 held-out 1–20。
- 不得引用项目 README 的 90.8% 作为本机结果。
