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
| Zetta formal-run source | `d0463d0c249164a5490a4c5cf36bf43a32abc153`（日志提交位于后续 `main`） |
| Python | 3.11.15 |
| PyTorch | 2.7.1+cu126 |
| MuJoCo / robosuite | 3.3.1 / 1.4.1 |
| GPU | 4 × NVIDIA A800-SXM4-80GB（81920 MiB） |
| checkpoint | `/home/pai/zxw/openpi_data/pi05_libero/checkpoints/RLinf-Pi05-LIBERO-SFT` |
| runtime venv | `/home/pai/zxw/openpi_data/pi05_libero/venvs/zetta_libero_py311` |
| benchmark source | `/home/pai/zxw/LIBERO-PRO/libero/libero` |
| Ray 临时目录 | `/tmp/zr4`（规避 Linux AF_UNIX 107 字节路径限制） |
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

### 2026-08-31T15:54:28Z–16:02:00Z — session 隔离修复与四路并发恢复

根因是 `client_session_key` 原先只包含 campaign 内局部唯一的 `logical_id + attempt_index`。四个 task0 campaign 都从 `g0000-rollout-000/attempt-0` 开始，因此 Gateway 按设计执行幂等合并，把四个不同 suite 的请求错误复用为同一 session。修复提交 `d0463d0c249164a5490a4c5cf36bf43a32abc153` 将 key 绑定到 suite、task、seed、generation、logical id、attempt，并加入 attempt 输出目录的不可逆摘要；相同 attempt 仍稳定，独立 campaign 不再冲突，本地绝对路径不会出现在 key 中。

修复通过 124 项定向测试。随后从 `d0463d0` 建立干净 detached source worktree，source revision fence 返回 `admitted=true`、`source_clean=true`，重新物化并用 `--resume` 审计 40 个 campaign。新 `campaign-plan.json` SHA-256 为 `a705f054f1a6d1374442a77bf0c30ab9c11c7d4713e2fd08bbb5e4978a187414`；协议规模保持 40 tasks、2000 development slots/round、800 held-out episodes/method，seed partition 与 official horizon 检查全部通过。

用与上轮相同的四个 development seeds 并发执行后，4/4 均被 campaign supervisor 接受为 `valid`，`infra_invalid=0`；每个 campaign 保留 49 个 pending jobs，可从现有 state/queue 恢复。四条 episode 均未成功，所以当前首批样本是 0/4；它只证明修复后的正式执行链和冻结延迟记录有效，不能外推为套件成功率。

| setting | seed | env actions | success | latency events | elapsed |
|---|---:|---:|---|---:|---:|
| Goal-T | 66655 | 311 | false | 501 | 52.155 s |
| Goal-S | 59451 | 311 | false | 501 | 54.059 s |
| LIBERO-10-T | 85862 | 531 | false | 853 | 84.372 s |
| LIBERO-10-S | 63675 | 531 | false | 853 | 69.883 s |

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting | model inference | policy request e2e | chunk e2e | environment execution | episode e2e |
|---|---:|---:|---:|---:|---:|
| Goal-T | 220.534 / 264.985 | 265.366 / 316.292 | 564.284 / 616.511 | 139.649 / 178.183 | 52156.060 |
| Goal-S | 218.212 / 247.808 | 262.184 / 294.303 | 580.923 / 659.882 | 147.807 / 212.301 | 54060.935 |
| LIBERO-10-T | 216.790 / 252.910 | 261.060 / 303.139 | 573.775 / 626.746 | 155.697 / 192.872 | 84372.937 |
| LIBERO-10-S | 214.474 / 250.299 | 260.211 / 296.705 | 565.116 / 615.014 | 153.260 / 196.781 | 69883.895 |

四条 episode 共 2708 条 latency events；按所有事件聚合：model inference 328 次，平均 217.001 ms、p95 252.298 ms；policy request end-to-end 平均 261.784 ms、p95 298.994 ms；chunk end-to-end 平均 570.601 ms、p95 626.716 ms；environment execution 368 次，平均 150.389 ms、p95 194.262 ms；observation preprocess 平均 2.852 ms；policy queue wait 平均 20.906 ms；action decode/postprocess 平均 0.168 ms。Critic evaluation 368 次、平均 0.008 ms，仍是未配置 Critic 的 no-op；Role1/recovery 均未触发。

LoopX experiment board 为修复后四条运行保留独立 terminal `inventory_only` 行：`official_result_present=true`。用当前 episode record 与 runtime device assignment 执行 integrity reducer，返回 `runtime_isolation_not_attested`（现有 artifact schema 不包含 benchmark-toolkit 要求的 runner 隔离声明），故 `integrity_qualified=false`、`score_countable=false`；没有把缺少 attestation 误报成可计数成绩。held-out seeds `1–20` 仍未使用。

### 2026-08-31T16:12:36Z–16:14:57Z — development 第二批四路并发

启动前再次读取 LoopX experiment board，并对固定的 `d0463d0c249164a5490a4c5cf36bf43a32abc153` clean source worktree 执行 source revision fence；结果为 `admitted=true`、`source_clean=true`。Gateway `/healthz` 返回 4/4 EnvWorker 健康，且主仓 `origin/main` 与本地均为日志提交 `07bb6146c32d8116d97b9147caa6f45c8e1281eb`。本批继续四个 task0 的 `g0000-rollout-001`，未触碰 held-out seeds `1–20`。

四路 worker 均以 exit 0 结束，supervisor 分别 ingest 1 条记录；4/4 为 `valid`、`infra_invalid=0`。每个 task0 campaign 的状态现为 2 completed、48 pending、0 running。本批仍为 0/4 success；累计两个批次为 8 条有效 development episode、0/8 success，仅代表 task0 当前样本，不是四套件成绩。

| setting | seed | env actions | success | latency events | elapsed |
|---|---:|---:|---|---:|---:|
| Goal-T | 41720 | 311 | false | 501 | 48.718 s |
| Goal-S | 16804 | 311 | false | 501 | 42.500 s |
| LIBERO-10-T | 94683 | 531 | false | 853 | 76.366 s |
| LIBERO-10-S | 62712 | 531 | false | 853 | 79.766 s |

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting | model inference | policy request e2e | chunk e2e | environment execution | episode e2e |
|---|---:|---:|---:|---:|---:|
| Goal-T | 216.895 / 258.403 | 260.444 / 305.550 | 551.621 / 617.450 | 135.653 / 181.597 | 48719.574 |
| Goal-S | 210.939 / 240.358 | 254.925 / 287.556 | 573.333 / 666.131 | 151.813 / 212.709 | 42501.184 |
| LIBERO-10-T | 206.100 / 251.808 | 249.123 / 296.050 | 556.766 / 615.785 | 152.583 / 190.584 | 76367.494 |
| LIBERO-10-S | 208.475 / 247.569 | 250.937 / 297.121 | 548.528 / 615.923 | 146.398 / 180.861 | 79767.141 |

本批共 2708 条 latency events；按组件事件数加权的均值为：model inference 209.713 ms、policy request end-to-end 252.830 ms、chunk end-to-end 556.243 ms、environment execution 147.300 ms、observation preprocess 2.742 ms、policy queue wait 20.791 ms、action decode/postprocess 0.160 ms。Critic evaluation 368 次、平均 0.007 ms，仍是 strict pure-VLA 下的 no-op；Role1/recovery 均未触发。

累计两个修复后批次共 5416 条 latency events；model inference 656 次、平均 213.357 ms，policy request end-to-end 平均 257.307 ms，chunk end-to-end 平均 563.422 ms，environment execution 736 次、平均 148.844 ms，Critic evaluation 平均 0.008 ms。四条新运行已从 `running` 更新为 terminal `inventory_only`；完整性 reducer 仍返回 `runtime_isolation_not_attested`，因此 `official_result_present=true` 但 `integrity_qualified=false`、`score_countable=false`。

### 2026-08-31T16:30Z–16:38Z — development 第三批批量编排与 16 条实跑

为消除每轮手工编排四条 episode 的吞吐瓶颈，新增 `scripts/evolution/run_liberopro_development_batch.py`。该入口在默认 dry-run 下依次读取 experiment board、执行固定 runner revision fence、检查 Gateway 健康状态、按 queue 实际 claim 顺序选择任务并预览 running 行；仅显式 `--execute` 时才预登记全部 run、按 suite 建立四条并发 lane、每条 lane 串行消费指定数量的 development jobs、调用 supervisor `resume` ingest，并将同一批 run_id 更新为 terminal。它只输出 compact episode/latency 聚合，不输出轨迹、视频或本地 artifact 路径。

本批先以 `--episodes-per-campaign 4` 运行四个 task0，共 16 条 episode。启动前 experiment board 为 14 条 terminal；固定 `d0463d0c249164a5490a4c5cf36bf43a32abc153` source revision fence 为 `admitted=true`、`source_clean=true`，Gateway 为 4/4 EnvWorker healthy。一次错误的预检曾把仅含后续日志/编排提交的当前 `main` 当作 observed runner revision，fence 按设计返回 `observed_reference_revision_mismatch`；修正为从冻结 campaign manifest 读取 `code_commit=d0463d0...` 后通过，实际 runner 未切换到主分支。

16 条 run 在 worker 启动前全部登记为 `running`。四路 worker 均完成 4 条，supervisor 各 ingest 4 条，合计 16/16 `valid`、0 `infra_invalid`、0 success。四个 task0 queue 均达到 6 completed、44 pending、0 running、0 failed；所有已执行 seed 与 held-out `1–20` 的交集为空。

| setting | logical id | seed | success | latency events | elapsed (s) |
|---|---|---:|---|---:|---:|
| Goal-T | `g0000-rollout-002` | 67983 | false | 501 | 39.072 |
| Goal-T | `g0000-rollout-003` | 98170 | false | 501 | 39.810 |
| Goal-T | `g0000-rollout-005` | 28209 | false | 501 | 39.941 |
| Goal-T | `g0000-rollout-004` | 23414 | false | 501 | 39.518 |
| Goal-S | `g0000-rollout-003` | 53128 | false | 501 | 47.981 |
| Goal-S | `g0000-rollout-002` | 81868 | false | 501 | 41.618 |
| Goal-S | `g0000-rollout-004` | 359 | false | 501 | 40.482 |
| Goal-S | `g0000-rollout-006` | 51440 | false | 501 | 40.105 |
| LIBERO-10-T | `g0000-rollout-002` | 43554 | false | 853 | 76.659 |
| LIBERO-10-T | `g0000-rollout-003` | 38059 | false | 853 | 68.910 |
| LIBERO-10-T | `g0000-rollout-004` | 91107 | false | 853 | 67.396 |
| LIBERO-10-T | `g0000-rollout-006` | 54036 | false | 853 | 67.219 |
| LIBERO-10-S | `g0000-rollout-002` | 41480 | false | 853 | 69.340 |
| LIBERO-10-S | `g0000-rollout-003` | 14065 | false | 853 | 68.387 |
| LIBERO-10-S | `g0000-rollout-004` | 756 | false | 853 | 66.494 |
| LIBERO-10-S | `g0000-rollout-005` | 20238 | false | 853 | 65.553 |

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting / seed | model inference | policy request e2e | chunk e2e | environment execution | Critic |
|---|---:|---:|---:|---:|---:|
| Goal-T / 67983 | 204.842 / 250.615 | 246.773 / 290.683 | 526.295 / 603.079 | 129.212 / 179.913 | 0.006 / 0.008 |
| Goal-T / 98170 | 206.640 / 270.621 | 252.264 / 319.909 | 535.860 / 618.915 | 131.301 / 167.924 | 0.007 / 0.009 |
| Goal-T / 28209 | 202.970 / 237.937 | 244.297 / 277.322 | 531.397 / 596.810 | 134.402 / 175.016 | 0.007 / 0.008 |
| Goal-T / 23414 | 203.009 / 269.684 | 246.199 / 313.984 | 526.615 / 607.787 | 126.394 / 178.311 | 0.006 / 0.008 |
| Goal-S / 53128 | 204.141 / 264.599 | 248.226 / 309.846 | 532.403 / 599.273 | 126.109 / 168.699 | 0.006 / 0.008 |
| Goal-S / 81868 | 216.195 / 280.215 | 260.029 / 324.214 | 557.610 / 657.501 | 136.406 / 187.407 | 0.007 / 0.008 |
| Goal-S / 359 | 211.064 / 260.702 | 253.408 / 302.779 | 538.536 / 606.543 | 127.586 / 170.124 | 0.006 / 0.008 |
| Goal-S / 51440 | 202.858 / 245.832 | 246.295 / 287.783 | 536.645 / 608.416 | 132.599 / 179.358 | 0.006 / 0.008 |
| LIBERO-10-T / 43554 | 203.780 / 247.559 | 249.084 / 304.945 | 557.254 / 639.529 | 149.841 / 196.414 | 0.009 / 0.009 |
| LIBERO-10-T / 38059 | 209.470 / 263.522 | 252.646 / 311.370 | 557.908 / 641.919 | 150.310 / 190.259 | 0.007 / 0.009 |
| LIBERO-10-T / 91107 | 204.185 / 248.228 | 248.827 / 306.022 | 547.694 / 624.452 | 148.378 / 184.839 | 0.006 / 0.008 |
| LIBERO-10-T / 54036 | 206.392 / 272.276 | 247.947 / 313.338 | 546.861 / 650.911 | 150.745 / 208.561 | 0.006 / 0.008 |
| LIBERO-10-S / 41480 | 207.458 / 259.678 | 251.387 / 304.832 | 563.501 / 665.576 | 156.563 / 203.303 | 0.006 / 0.008 |
| LIBERO-10-S / 14065 | 211.312 / 257.389 | 253.656 / 298.813 | 551.669 / 639.557 | 140.083 / 167.750 | 0.007 / 0.008 |
| LIBERO-10-S / 756 | 203.975 / 246.511 | 246.478 / 299.643 | 538.346 / 597.822 | 146.361 / 193.400 | 0.006 / 0.008 |
| LIBERO-10-S / 20238 | 199.332 / 234.903 | 240.729 / 275.123 | 530.798 / 600.117 | 144.212 / 184.836 | 0.006 / 0.008 |

本批共 10832 条 latency events；按组件事件数加权：model inference 1312 次、平均 206.004 ms，policy request end-to-end 1312 次、平均 249.152 ms，chunk end-to-end 1312 次、平均 544.284 ms，environment execution 1472 次、平均 141.536 ms，Critic evaluation 1472 次、平均 0.007 ms。Critic 仍为 strict pure-VLA 下的 no-op，Role1/recovery 未触发。

修复后累计为 24 条有效 development episode、0/24 success、16248 条 latency events；model inference 1968 次、加权平均 208.455 ms，policy request end-to-end 平均 251.870 ms，chunk end-to-end 平均 550.663 ms，environment execution 2208 次、平均 143.972 ms。LoopX board 当前 30/30 terminal，其中本批 16 条均为 `official_result_present=true`；integrity reducer 仍统一返回 `runtime_isolation_not_attested`，所以 0 条 score-countable。该结果仍仅覆盖四个 task0，不是套件最终成绩。

### 2026-08-31T16:44Z–16:57Z — development 第四批 32 条实跑

继续使用固定 runner `d0463d0c249164a5490a4c5cf36bf43a32abc153` 和 plan SHA-256 `a705f054f1a6d1374442a77bf0c30ab9c11c7d4713e2fd08bbb5e4978a187414`，以每个 task0 八条、四条 suite lane 并发的方式执行 32 条 development episode。启动顺序仍为读取 LoopX experiment board、source revision fence、Gateway health check、全部 running 行预登记；fence 为 clean/admitted，Gateway 为 4/4 EnvWorker healthy。所有 seed 均不在 held-out `1–20`。

四条 worker lane 均完成 8 条，supervisor 接受 32/32，`infra_invalid=0`、success 0/32。四个 task0 queue 均达到 14 completed、36 pending、0 running、0 failed。与上一批相比没有出现新的共享 session 冲突或 heartbeat 故障，说明 campaign-scoped session key 与批量编排在本轮 32 条负载下保持稳定。

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting / seed | logical id | model inference | policy request e2e | chunk e2e | environment execution | Critic | elapsed (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| Goal-T / 31404 | `g0000-rollout-006` | 206.299 / 267.746 | 248.887 / 313.406 | 527.807 / 617.714 | 127.253 / 165.809 | 0.008 / 0.009 | 39.616 |
| Goal-T / 15862 | `g0000-rollout-007` | 204.992 / 249.098 | 250.323 / 297.418 | 531.293 / 594.579 | 124.773 / 167.581 | 0.006 / 0.008 | 39.826 |
| Goal-T / 98768 | `g0000-rollout-008` | 190.460 / 245.406 | 234.291 / 309.443 | 503.473 / 594.814 | 124.326 / 170.422 | 0.007 / 0.008 | 44.950 |
| Goal-T / 90038 | `g0000-rollout-009` | 199.040 / 241.803 | 242.365 / 289.610 | 524.484 / 576.543 | 131.858 / 179.105 | 0.008 / 0.008 | 39.452 |
| Goal-T / 64059 | `g0000-rollout-010` | 204.216 / 257.315 | 248.223 / 304.120 | 531.714 / 609.193 | 131.076 / 175.263 | 0.007 / 0.008 | 39.678 |
| Goal-T / 72666 | `g0000-rollout-011` | 203.929 / 248.530 | 246.546 / 291.251 | 524.860 / 568.073 | 126.469 / 163.183 | 0.006 / 0.008 | 39.407 |
| Goal-T / 15754 | `g0000-rollout-012` | 205.883 / 269.844 | 249.238 / 312.949 | 522.341 / 591.627 | 123.173 / 164.545 | 0.006 / 0.008 | 39.002 |
| Goal-T / 63735 | `g0000-rollout-014` | 194.115 / 228.335 | 236.050 / 271.211 | 515.792 / 586.731 | 129.207 / 164.023 | 0.007 / 0.012 | 38.717 |
| Goal-S / 34316 | `g0000-rollout-005` | 204.728 / 249.445 | 246.666 / 292.029 | 535.829 / 594.243 | 129.349 / 178.098 | 0.006 / 0.008 | 40.295 |
| Goal-S / 68479 | `g0000-rollout-007` | 196.864 / 249.686 | 239.288 / 297.921 | 522.680 / 589.976 | 124.762 / 163.109 | 0.006 / 0.008 | 39.489 |
| Goal-S / 46059 | `g0000-rollout-008` | 198.780 / 269.153 | 239.675 / 313.423 | 510.867 / 577.990 | 119.487 / 154.897 | 0.006 / 0.008 | 38.469 |
| Goal-S / 85508 | `g0000-rollout-009` | 204.753 / 251.871 | 251.364 / 301.640 | 560.006 / 625.867 | 144.722 / 204.983 | 0.006 / 0.008 | 41.576 |
| Goal-S / 61670 | `g0000-rollout-010` | 202.301 / 268.816 | 246.601 / 311.309 | 544.188 / 633.270 | 140.369 / 201.205 | 0.007 / 0.008 | 40.713 |
| Goal-S / 7887 | `g0000-rollout-011` | 202.150 / 246.898 | 244.338 / 290.095 | 525.624 / 604.220 | 125.623 / 167.314 | 0.006 / 0.008 | 39.770 |
| Goal-S / 41753 | `g0000-rollout-012` | 199.767 / 249.380 | 243.372 / 295.135 | 533.884 / 600.894 | 131.784 / 176.454 | 0.006 / 0.008 | 39.729 |
| Goal-S / 98490 | `g0000-rollout-013` | 203.564 / 242.915 | 245.345 / 285.690 | 528.839 / 607.005 | 126.936 / 166.267 | 0.006 / 0.008 | 40.466 |
| LIBERO-10-T / 83968 | `g0000-rollout-005` | 204.054 / 255.373 | 248.322 / 305.359 | 542.127 / 612.101 | 144.200 / 182.568 | 0.006 / 0.008 | 67.096 |
| LIBERO-10-T / 47207 | `g0000-rollout-007` | 197.877 / 247.162 | 240.758 / 293.203 | 542.259 / 626.747 | 148.906 / 205.722 | 0.006 / 0.008 | 66.832 |
| LIBERO-10-T / 72608 | `g0000-rollout-008` | 202.434 / 250.461 | 245.734 / 311.201 | 544.195 / 628.339 | 146.206 / 192.571 | 0.007 / 0.009 | 67.445 |
| LIBERO-10-T / 44863 | `g0000-rollout-009` | 199.338 / 242.840 | 242.656 / 290.720 | 540.415 / 607.133 | 145.981 / 193.479 | 0.006 / 0.008 | 66.852 |
| LIBERO-10-T / 15839 | `g0000-rollout-010` | 202.803 / 253.686 | 246.486 / 303.041 | 545.128 / 624.644 | 145.558 / 193.190 | 0.006 / 0.008 | 67.590 |
| LIBERO-10-T / 81743 | `g0000-rollout-011` | 195.873 / 218.622 | 236.686 / 260.154 | 524.975 / 580.472 | 142.969 / 185.285 | 0.006 / 0.007 | 64.803 |
| LIBERO-10-T / 90835 | `g0000-rollout-012` | 194.476 / 223.412 | 234.612 / 263.731 | 518.654 / 570.309 | 140.736 / 178.687 | 0.006 / 0.008 | 63.982 |
| LIBERO-10-T / 40069 | `g0000-rollout-013` | 191.599 / 214.000 | 232.528 / 257.553 | 527.619 / 573.180 | 149.261 / 194.397 | 0.006 / 0.007 | 64.768 |
| LIBERO-10-S / 18929 | `g0000-rollout-006` | 198.556 / 244.432 | 241.385 / 285.257 | 537.649 / 601.093 | 148.699 / 196.709 | 0.007 / 0.008 | 66.967 |
| LIBERO-10-S / 4064 | `g0000-rollout-007` | 209.617 / 274.133 | 252.782 / 330.857 | 551.901 / 645.255 | 149.319 / 186.965 | 0.007 / 0.008 | 77.811 |
| LIBERO-10-S / 41137 | `g0000-rollout-008` | 203.238 / 264.087 | 247.120 / 309.884 | 550.219 / 656.837 | 156.786 / 211.005 | 0.007 / 0.008 | 68.035 |
| LIBERO-10-S / 53023 | `g0000-rollout-009` | 206.777 / 266.505 | 249.758 / 308.468 | 545.240 / 632.388 | 146.478 / 195.643 | 0.007 / 0.008 | 67.215 |
| LIBERO-10-S / 54187 | `g0000-rollout-010` | 205.984 / 258.237 | 249.408 / 300.406 | 544.769 / 636.806 | 141.453 / 184.223 | 0.006 / 0.008 | 67.523 |
| LIBERO-10-S / 60292 | `g0000-rollout-011` | 196.868 / 226.412 | 237.317 / 266.077 | 511.731 / 567.108 | 133.092 / 167.302 | 0.006 / 0.007 | 70.849 |
| LIBERO-10-S / 32965 | `g0000-rollout-012` | 196.322 / 232.201 | 236.451 / 273.691 | 512.078 / 570.158 | 126.397 / 166.045 | 0.006 / 0.007 | 63.521 |
| LIBERO-10-S / 56430 | `g0000-rollout-013` | 197.141 / 241.417 | 239.145 / 295.614 | 528.971 / 602.393 | 140.787 / 196.756 | 0.007 / 0.008 | 65.024 |

本批共 21664 条 latency events；按组件事件数加权：model inference 2624 次、平均 200.617 ms，policy request end-to-end 2624 次、平均 243.290 ms，chunk end-to-end 2624 次、平均 532.655 ms，environment execution 2944 次、平均 138.336 ms，Critic evaluation 2944 次、平均 0.006 ms。Critic 仍为 strict pure-VLA 下的 no-op，Role1/recovery 未触发。

固定 runner 的四批累计为 56 条有效 development episode、0/56 success、37912 条 latency events；model inference 4592 次、加权平均 203.976 ms，policy request end-to-end 平均 246.967 ms，chunk end-to-end 平均 540.373 ms，environment execution 5152 次、平均 140.751 ms，Critic evaluation 平均约 0.006 ms。LoopX board 为 62/62 terminal，其中本批 32 条均 `official_result_present=true`；所有 62 条仍为 0 score-countable，完整性分类继续是 `runtime_isolation_not_attested`。这仍只覆盖四个 task0，不能作为四套件最终成功率。

### 2026-08-31T17:04Z–17:16Z — development 第五批 32 条实跑

本批继续固定 runner `d0463d0c249164a5490a4c5cf36bf43a32abc153` 和相同 campaign plan。启动前 LoopX board 为 62/62 terminal，source revision fence 为 clean/admitted，Gateway 4/4 EnvWorker healthy、`heartbeat_failed=0`；dry-run 对 32 个候选逐一预览 running 行并确认均为 development seed，和 held-out `1–20` 无交集。

四条 worker lane 各完成 8 条，supervisor 接受 32/32，`infra_invalid=0`、success 0/32；四个 task0 queue 均达到 22 completed、28 pending、0 running、0 failed。运行期间 Goal 两条 lane 先完成，两个 LIBERO-10 lane 的 worker PID 随 episode 正常变化，Gateway 心跳持续增长且无失败，未发现静默卡死或 session 冲突。

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting / seed | logical id | model inference | policy request e2e | chunk e2e | environment execution | Critic | elapsed (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| Goal-T / 66670 | `g0000-rollout-015` | 188.567 / 218.038 | 227.959 / 259.526 | 479.114 / 528.922 | 114.449 / 152.419 | 0.006 / 0.008 | 36.164 |
| Goal-T / 66556 | `g0000-rollout-013` | 201.247 / 235.105 | 245.538 / 292.286 | 524.235 / 598.659 | 125.966 / 170.365 | 0.006 / 0.007 | 38.729 |
| Goal-T / 1480 | `g0000-rollout-016` | 192.820 / 264.332 | 232.910 / 302.389 | 495.955 / 558.812 | 118.486 / 154.975 | 0.006 / 0.007 | 37.153 |
| Goal-T / 57247 | `g0000-rollout-017` | 203.514 / 257.410 | 247.967 / 299.867 | 522.915 / 599.594 | 123.234 / 169.631 | 0.006 / 0.008 | 38.924 |
| Goal-T / 66321 | `g0000-rollout-020` | 188.563 / 225.791 | 228.178 / 264.695 | 491.961 / 555.351 | 119.723 / 166.747 | 0.009 / 0.008 | 36.698 |
| Goal-T / 43478 | `g0000-rollout-018` | 196.302 / 232.549 | 237.057 / 272.097 | 502.042 / 578.306 | 122.271 / 158.295 | 0.006 / 0.008 | 37.459 |
| Goal-T / 65248 | `g0000-rollout-019` | 207.143 / 275.290 | 248.394 / 321.446 | 527.242 / 629.018 | 128.826 / 183.685 | 0.006 / 0.008 | 39.220 |
| Goal-T / 28927 | `g0000-rollout-022` | 196.301 / 218.253 | 237.470 / 265.006 | 512.191 / 604.963 | 128.164 / 167.742 | 0.006 / 0.012 | 39.165 |
| Goal-S / 68914 | `g0000-rollout-015` | 193.544 / 239.572 | 233.895 / 279.659 | 520.619 / 595.490 | 133.338 / 194.522 | 0.006 / 0.008 | 39.117 |
| Goal-S / 92767 | `g0000-rollout-014` | 196.873 / 229.926 | 240.109 / 279.449 | 545.609 / 613.498 | 145.494 / 216.603 | 0.006 / 0.009 | 40.485 |
| Goal-S / 8655 | `g0000-rollout-016` | 190.770 / 218.767 | 232.184 / 270.673 | 513.587 / 582.379 | 128.749 / 190.497 | 0.006 / 0.007 | 38.429 |
| Goal-S / 31853 | `g0000-rollout-017` | 192.888 / 238.203 | 236.522 / 287.000 | 532.372 / 603.126 | 136.769 / 188.476 | 0.006 / 0.007 | 39.700 |
| Goal-S / 78225 | `g0000-rollout-019` | 192.074 / 240.075 | 233.341 / 279.178 | 512.125 / 583.363 | 127.602 / 174.402 | 0.006 / 0.007 | 38.453 |
| Goal-S / 7476 | `g0000-rollout-018` | 202.438 / 268.689 | 241.731 / 314.678 | 531.070 / 600.111 | 136.290 / 192.322 | 0.006 / 0.008 | 45.911 |
| Goal-S / 11480 | `g0000-rollout-022` | 201.417 / 245.560 | 247.101 / 297.737 | 569.013 / 662.407 | 150.374 / 224.832 | 0.006 / 0.008 | 42.104 |
| Goal-S / 44644 | `g0000-rollout-021` | 201.772 / 256.584 | 243.882 / 297.468 | 537.469 / 603.703 | 131.326 / 184.915 | 0.007 / 0.009 | 40.349 |
| LIBERO-10-T / 58861 | `g0000-rollout-014` | 191.572 / 235.185 | 233.777 / 283.283 | 521.261 / 591.448 | 138.293 / 176.764 | 0.007 / 0.008 | 65.678 |
| LIBERO-10-T / 47963 | `g0000-rollout-016` | 194.965 / 228.518 | 237.021 / 287.303 | 531.495 / 617.118 | 145.773 / 192.310 | 0.007 / 0.009 | 76.148 |
| LIBERO-10-T / 32609 | `g0000-rollout-015` | 193.297 / 239.773 | 234.161 / 278.625 | 520.435 / 617.543 | 141.697 / 195.588 | 0.017 / 0.008 | 64.911 |
| LIBERO-10-T / 69794 | `g0000-rollout-017` | 201.731 / 272.966 | 242.989 / 320.164 | 539.111 / 630.062 | 145.868 / 175.322 | 0.008 / 0.009 | 67.037 |
| LIBERO-10-T / 98633 | `g0000-rollout-018` | 206.885 / 275.710 | 250.821 / 320.495 | 548.734 / 623.013 | 145.642 / 184.165 | 0.007 / 0.009 | 68.838 |
| LIBERO-10-T / 39888 | `g0000-rollout-019` | 204.109 / 232.953 | 246.756 / 293.133 | 546.538 / 624.954 | 149.572 / 187.648 | 0.007 / 0.008 | 67.460 |
| LIBERO-10-T / 79928 | `g0000-rollout-020` | 197.866 / 236.827 | 238.076 / 281.327 | 527.391 / 615.560 | 144.515 / 191.070 | 0.006 / 0.007 | 65.600 |
| LIBERO-10-T / 89438 | `g0000-rollout-021` | 194.338 / 223.419 | 235.112 / 271.760 | 518.669 / 572.246 | 137.819 / 176.296 | 0.006 / 0.008 | 64.133 |
| LIBERO-10-S / 50286 | `g0000-rollout-014` | 198.057 / 232.123 | 240.068 / 279.876 | 527.613 / 595.709 | 139.735 / 186.687 | 0.007 / 0.008 | 66.245 |
| LIBERO-10-S / 32971 | `g0000-rollout-015` | 198.493 / 244.326 | 241.302 / 301.340 | 527.173 / 600.677 | 135.962 / 183.864 | 0.007 / 0.008 | 65.207 |
| LIBERO-10-S / 52868 | `g0000-rollout-017` | 192.646 / 248.139 | 235.423 / 293.503 | 529.377 / 614.936 | 150.302 / 207.110 | 0.006 / 0.008 | 66.069 |
| LIBERO-10-S / 53071 | `g0000-rollout-016` | 204.250 / 270.250 | 244.800 / 309.522 | 532.417 / 620.969 | 134.292 / 172.486 | 0.006 / 0.008 | 65.586 |
| LIBERO-10-S / 86121 | `g0000-rollout-019` | 202.865 / 251.978 | 247.019 / 296.510 | 538.993 / 619.482 | 138.404 / 174.034 | 0.006 / 0.008 | 66.994 |
| LIBERO-10-S / 56617 | `g0000-rollout-018` | 211.863 / 264.201 | 254.424 / 305.681 | 555.087 / 645.662 | 148.715 / 196.476 | 0.006 / 0.008 | 68.262 |
| LIBERO-10-S / 98709 | `g0000-rollout-020` | 203.269 / 261.371 | 243.394 / 302.712 | 521.032 / 598.545 | 137.399 / 163.544 | 0.007 / 0.008 | 64.623 |
| LIBERO-10-S / 43402 | `g0000-rollout-021` | 197.727 / 228.071 | 237.875 / 273.660 | 525.417 / 579.449 | 139.458 / 183.434 | 0.006 / 0.007 | 64.914 |

本批共 21664 条 latency events；按组件事件数加权：model inference 2624 次、平均 198.530 ms，policy request end-to-end 2624 次、平均 240.323 ms，chunk end-to-end 2624 次、平均 527.503 ms，environment execution 2944 次、平均 137.278 ms，Critic evaluation 2944 次、平均 0.007 ms。Critic 仍为 strict pure-VLA 下的 no-op，Role1/recovery 未触发。

固定 runner 的五批累计为 88 条有效 development episode、0/88 success、59576 条 latency events；model inference 7216 次、加权平均 201.996 ms，policy request end-to-end 平均 244.551 ms，chunk end-to-end 平均 535.693 ms，environment execution 8096 次、平均 139.488 ms，Critic evaluation 平均约 0.006 ms。LoopX board 为 94/94 terminal，本批 32 条均 `official_result_present=true`，0 条 score-countable；完整性分类仍是 `runtime_isolation_not_attested`。

本轮唯一记录处理问题是编排器终态 JSON 超过交互输出上限而被截断。解决方式是先通过 LoopX artifact classifier 将 `summary.json` 显式限定为 compact/public artifact，再只读取 32 个 latency summary 的聚合字段重建表格；没有读取轨迹、视频、privileged state 或 worker 日志，也未把本地绝对路径写入公开日志。

## 最终验证

2026-08-31 再次从安装后的 `liberopro` API 创建四个 suite，并对每个 task 调用 `get_task_init_states`：40/40 BDDL 存在，四套件各 10 个任务，每个任务均反序列化得到 50 个非空 init states。

```text
56 targeted tests passed in 9.81s
76 current targeted tests passed in 11.61s
60 post-fifth-batch targeted tests passed in 10.32s
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
- 正式矩阵已在 `d0463d0` clean source worktree 上恢复运行；四个 task0 各完成 22/50 个 development seeds，下一步继续其余 28 seeds，再扩展其余 36 个任务并进入故障聚类与 patch 流程，最后才可触碰 held-out 1–20。
- 不得引用项目 README 的 90.8% 作为本机结果。
