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

### 2026-08-31T17:26Z–17:39Z — development 第六批 56 条实跑

上一批的完整终态 JSON 会超过交互输出上限。为让长批次结果可复核，本轮给批量器增加可选 `--summary-output`：只在 `--execute` 时启用，只允许写入 matrix root 内，且使用 create-only 语义拒绝覆盖已有证据。保存内容仍是原有 compact 终态摘要，不包含轨迹、视频、本地 artifact 路径或密钥；新增 2 项单测覆盖目录越界和重复写入。

本批继续固定 runner `d0463d0c249164a5490a4c5cf36bf43a32abc153`。启动前 LoopX board 为 94/94 terminal，source revision fence 为 clean/admitted，Gateway 4/4 EnvWorker healthy、`heartbeat_failed=0`。dry-run 预览 56 条候选并确认每套件 14 条、held-out `1–20` 交集为空；正式运行前完成 running 行预登记。

四条 worker lane 各完成 14 条，supervisor 接受 56/56，`infra_invalid=0`、success 0/56。四个 task0 queue 均达到 36 completed、14 pending、0 running、0 failed。运行中 Goal lane 先完成，两个 LIBERO-10 lane 持续更换 worker PID，Gateway 心跳持续增长且无失败。

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting / seed | logical id | model inference | policy request e2e | chunk e2e | environment execution | Critic | elapsed (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| Goal-T / 70659 | `g0000-rollout-021` | 201.380 / 239.053 | 242.860 / 293.304 | 520.500 / 596.069 | 129.228 / 170.745 | 0.006 / 0.008 | 45.904 |
| Goal-T / 98500 | `g0000-rollout-023` | 201.700 / 250.995 | 244.007 / 296.033 | 519.744 / 632.450 | 128.607 / 188.269 | 0.006 / 0.008 | 38.987 |
| Goal-T / 71916 | `g0000-rollout-024` | 204.375 / 248.255 | 245.442 / 293.316 | 517.644 / 588.799 | 124.385 / 163.705 | 0.006 / 0.008 | 38.838 |
| Goal-T / 24195 | `g0000-rollout-026` | 202.140 / 261.274 | 243.884 / 306.136 | 519.122 / 609.084 | 125.833 / 173.064 | 0.006 / 0.007 | 38.533 |
| Goal-T / 77233 | `g0000-rollout-025` | 208.009 / 261.552 | 251.020 / 307.299 | 527.915 / 606.048 | 126.361 / 164.012 | 0.006 / 0.008 | 39.050 |
| Goal-T / 25273 | `g0000-rollout-028` | 193.409 / 220.696 | 233.259 / 269.307 | 497.822 / 554.442 | 119.815 / 157.331 | 0.006 / 0.008 | 37.502 |
| Goal-T / 24307 | `g0000-rollout-027` | 184.089 / 218.811 | 223.208 / 265.935 | 482.559 / 544.195 | 117.187 / 156.957 | 0.006 / 0.008 | 35.955 |
| Goal-T / 28946 | `g0000-rollout-029` | 174.881 / 193.834 | 213.047 / 233.248 | 452.874 / 495.742 | 106.384 / 152.022 | 0.006 / 0.008 | 33.921 |
| Goal-T / 72405 | `g0000-rollout-030` | 186.561 / 214.596 | 224.982 / 253.557 | 473.131 / 509.257 | 112.209 / 142.663 | 0.007 / 0.008 | 35.069 |
| Goal-T / 77469 | `g0000-rollout-033` | 180.786 / 200.326 | 219.704 / 238.821 | 465.523 / 510.460 | 109.791 / 150.390 | 0.006 / 0.008 | 34.692 |
| Goal-T / 11237 | `g0000-rollout-031` | 174.994 / 193.878 | 213.150 / 234.201 | 451.501 / 486.827 | 105.615 / 144.713 | 0.006 / 0.007 | 33.787 |
| Goal-T / 50133 | `g0000-rollout-032` | 178.245 / 208.173 | 216.254 / 244.977 | 460.967 / 506.636 | 111.399 / 156.894 | 0.006 / 0.007 | 34.109 |
| Goal-T / 63998 | `g0000-rollout-034` | 176.077 / 205.773 | 214.325 / 244.668 | 456.132 / 502.398 | 105.747 / 150.347 | 0.006 / 0.008 | 33.870 |
| Goal-T / 28439 | `g0000-rollout-035` | 177.064 / 208.847 | 215.119 / 246.467 | 451.553 / 518.736 | 105.412 / 147.687 | 0.006 / 0.008 | 33.563 |
| Goal-S / 67803 | `g0000-rollout-020` | 199.308 / 259.243 | 239.932 / 298.250 | 524.669 / 600.303 | 128.172 / 172.070 | 0.006 / 0.008 | 39.396 |
| Goal-S / 59820 | `g0000-rollout-024` | 202.753 / 237.822 | 244.922 / 295.890 | 528.998 / 620.069 | 127.754 / 171.609 | 0.006 / 0.008 | 40.085 |
| Goal-S / 48247 | `g0000-rollout-023` | 204.980 / 266.030 | 245.965 / 305.797 | 554.029 / 662.167 | 146.598 / 217.963 | 0.006 / 0.008 | 40.656 |
| Goal-S / 87992 | `g0000-rollout-026` | 201.546 / 234.719 | 243.313 / 283.732 | 530.092 / 606.524 | 129.133 / 179.922 | 0.006 / 0.008 | 40.085 |
| Goal-S / 31650 | `g0000-rollout-025` | 197.105 / 231.709 | 238.825 / 279.035 | 522.397 / 606.084 | 127.308 / 172.917 | 0.006 / 0.008 | 39.558 |
| Goal-S / 72925 | `g0000-rollout-028` | 193.081 / 240.428 | 233.546 / 281.101 | 505.259 / 567.105 | 122.585 / 163.261 | 0.006 / 0.008 | 38.402 |
| Goal-S / 45571 | `g0000-rollout-027` | 187.766 / 223.205 | 229.510 / 275.645 | 512.056 / 585.708 | 135.579 / 193.354 | 0.006 / 0.008 | 38.004 |
| Goal-S / 40374 | `g0000-rollout-029` | 178.589 / 198.981 | 216.445 / 238.410 | 469.504 / 506.568 | 112.550 / 150.581 | 0.006 / 0.008 | 35.251 |
| Goal-S / 31779 | `g0000-rollout-030` | 182.115 / 213.262 | 220.985 / 251.843 | 476.852 / 522.431 | 112.238 / 164.122 | 0.006 / 0.008 | 35.875 |
| Goal-S / 36812 | `g0000-rollout-031` | 180.079 / 204.950 | 219.080 / 244.869 | 475.730 / 520.727 | 113.242 / 164.215 | 0.006 / 0.008 | 35.598 |
| Goal-S / 54991 | `g0000-rollout-032` | 176.279 / 204.513 | 214.407 / 243.922 | 458.098 / 507.783 | 107.260 / 153.028 | 0.006 / 0.007 | 34.273 |
| Goal-S / 16881 | `g0000-rollout-034` | 184.239 / 213.427 | 223.063 / 252.848 | 477.794 / 549.540 | 112.084 / 166.196 | 0.006 / 0.007 | 35.601 |
| Goal-S / 68058 | `g0000-rollout-035` | 175.349 / 200.506 | 213.967 / 239.852 | 467.888 / 529.849 | 111.962 / 166.345 | 0.006 / 0.007 | 34.801 |
| Goal-S / 10307 | `g0000-rollout-033` | 177.208 / 211.517 | 216.033 / 251.498 | 462.444 / 509.276 | 106.879 / 143.812 | 0.006 / 0.008 | 34.535 |
| LIBERO-10-T / 87574 | `g0000-rollout-023` | 197.789 / 245.173 | 238.945 / 289.465 | 531.439 / 612.004 | 143.276 / 177.931 | 0.007 / 0.008 | 66.100 |
| LIBERO-10-T / 77797 | `g0000-rollout-024` | 200.657 / 241.224 | 242.010 / 286.911 | 541.508 / 623.277 | 147.268 / 193.149 | 0.007 / 0.008 | 67.928 |
| LIBERO-10-T / 30770 | `g0000-rollout-022` | 200.420 / 240.175 | 242.970 / 293.007 | 532.433 / 613.303 | 142.545 / 180.330 | 0.006 / 0.008 | 67.208 |
| LIBERO-10-T / 53580 | `g0000-rollout-026` | 189.140 / 216.918 | 229.967 / 261.762 | 514.616 / 570.192 | 139.457 / 180.919 | 0.006 / 0.008 | 63.798 |
| LIBERO-10-T / 51873 | `g0000-rollout-025` | 181.091 / 210.524 | 220.251 / 251.356 | 491.593 / 550.437 | 131.993 / 166.573 | 0.006 / 0.007 | 60.510 |
| LIBERO-10-T / 90133 | `g0000-rollout-028` | 182.434 / 213.701 | 221.157 / 251.858 | 489.748 / 533.950 | 129.582 / 162.855 | 0.005 / 0.007 | 59.907 |
| LIBERO-10-T / 73545 | `g0000-rollout-027` | 176.336 / 204.030 | 214.470 / 241.910 | 477.547 / 528.585 | 128.764 / 180.316 | 0.005 / 0.007 | 58.970 |
| LIBERO-10-T / 5696 | `g0000-rollout-029` | 179.957 / 225.307 | 218.070 / 265.825 | 475.876 / 540.754 | 123.258 / 160.517 | 0.005 / 0.007 | 58.615 |
| LIBERO-10-T / 61029 | `g0000-rollout-030` | 176.754 / 200.012 | 214.931 / 237.958 | 473.820 / 520.542 | 125.866 / 168.218 | 0.005 / 0.007 | 58.079 |
| LIBERO-10-T / 31186 | `g0000-rollout-031` | 176.378 / 203.976 | 214.791 / 244.283 | 479.941 / 517.487 | 128.917 / 169.348 | 0.005 / 0.007 | 58.865 |
| LIBERO-10-T / 43027 | `g0000-rollout-032` | 176.863 / 194.980 | 215.007 / 232.569 | 486.932 / 524.959 | 136.866 / 170.865 | 0.006 / 0.007 | 59.701 |
| LIBERO-10-T / 17339 | `g0000-rollout-033` | 179.438 / 205.372 | 217.470 / 245.706 | 482.871 / 538.995 | 130.041 / 171.096 | 0.005 / 0.007 | 59.172 |
| LIBERO-10-T / 9342 | `g0000-rollout-034` | 177.005 / 196.055 | 215.335 / 238.517 | 469.887 / 513.545 | 122.854 / 152.587 | 0.005 / 0.007 | 58.568 |
| LIBERO-10-T / 34458 | `g0000-rollout-035` | 175.621 / 195.248 | 214.197 / 235.246 | 481.058 / 526.952 | 130.720 / 166.270 | 0.005 / 0.007 | 58.792 |
| LIBERO-10-S / 77780 | `g0000-rollout-022` | 199.866 / 241.289 | 241.452 / 288.504 | 538.548 / 600.763 | 146.452 / 185.924 | 0.007 / 0.008 | 67.421 |
| LIBERO-10-S / 38632 | `g0000-rollout-023` | 203.424 / 255.526 | 247.129 / 311.396 | 545.794 / 638.613 | 150.360 / 194.913 | 0.007 / 0.008 | 68.378 |
| LIBERO-10-S / 33054 | `g0000-rollout-024` | 196.890 / 230.019 | 239.029 / 278.069 | 541.278 / 647.986 | 153.511 / 220.775 | 0.006 / 0.008 | 68.145 |
| LIBERO-10-S / 74509 | `g0000-rollout-025` | 189.678 / 216.369 | 230.007 / 254.874 | 505.108 / 568.336 | 131.142 / 173.411 | 0.006 / 0.008 | 62.063 |
| LIBERO-10-S / 65726 | `g0000-rollout-027` | 183.474 / 227.265 | 222.196 / 265.585 | 482.085 / 534.365 | 124.662 / 167.650 | 0.006 / 0.007 | 59.437 |
| LIBERO-10-S / 19378 | `g0000-rollout-026` | 181.208 / 211.470 | 220.356 / 253.474 | 484.512 / 528.464 | 126.501 / 168.277 | 0.006 / 0.007 | 59.611 |
| LIBERO-10-S / 2645 | `g0000-rollout-028` | 179.321 / 211.106 | 217.801 / 254.896 | 478.316 / 543.706 | 128.778 / 173.803 | 0.006 / 0.008 | 59.392 |
| LIBERO-10-S / 41641 | `g0000-rollout-029` | 178.049 / 210.932 | 216.036 / 249.761 | 474.649 / 520.213 | 120.191 / 160.141 | 0.006 / 0.009 | 58.723 |
| LIBERO-10-S / 29960 | `g0000-rollout-031` | 174.717 / 200.461 | 212.928 / 239.888 | 462.716 / 510.445 | 120.375 / 152.150 | 0.006 / 0.008 | 57.716 |
| LIBERO-10-S / 91009 | `g0000-rollout-030` | 179.198 / 212.359 | 217.385 / 251.182 | 465.000 / 505.377 | 117.026 / 153.308 | 0.006 / 0.007 | 57.342 |
| LIBERO-10-S / 24377 | `g0000-rollout-032` | 178.867 / 211.102 | 217.019 / 249.111 | 465.374 / 508.590 | 113.383 / 150.608 | 0.006 / 0.007 | 57.239 |
| LIBERO-10-S / 90491 | `g0000-rollout-033` | 178.483 / 204.162 | 217.415 / 241.957 | 478.198 / 526.579 | 126.984 / 174.174 | 0.006 / 0.007 | 58.849 |
| LIBERO-10-S / 9698 | `g0000-rollout-034` | 177.036 / 193.887 | 215.065 / 232.916 | 467.928 / 507.738 | 121.043 / 156.656 | 0.006 / 0.007 | 57.754 |
| LIBERO-10-S / 17289 | `g0000-rollout-035` | 176.220 / 198.229 | 214.358 / 238.118 | 462.052 / 494.877 | 116.388 / 146.167 | 0.006 / 0.007 | 57.106 |

本批共 37912 条 latency events；按组件事件数加权：model inference 4592 次、平均 185.597 ms，policy request end-to-end 4592 次、平均 225.127 ms，chunk end-to-end 4592 次、平均 491.937 ms，environment execution 5152 次、平均 126.073 ms，Critic evaluation 5152 次、平均 0.006 ms。Critic 仍为 strict pure-VLA 下的 no-op，Role1/recovery 未触发。

固定 runner 的六批累计为 144 条有效 development episode、0/144 success、97488 条 latency events；model inference 11808 次、加权平均 195.619 ms，policy request end-to-end 平均 236.997 ms，chunk end-to-end 平均 518.677 ms，environment execution 13248 次、平均 134.271 ms，Critic evaluation 平均约 0.006 ms。LoopX board 为 150/150 terminal，本批 56 条均 `official_result_present=true`，0 条 score-countable；完整性分类仍是 `runtime_isolation_not_attested`。

### 2026-08-31T17:55Z–18:09Z — development 第七批 56 条实跑，四个 task0 完成

本批在 LoopX capability guard 首次发现宿主未声明 `benchmark_runner`；先用同一批量器完成一次真实 dry-run 能力验证，再用同一 turn id 声明已验证能力并重新申请配额，守卫从 `repair_bridge` 转为 `normal_run`。正式启动前再次读取 experiment board、通过固定 `d0463d0c249164a5490a4c5cf36bf43a32abc153` source revision fence，并确认 Gateway 4/4 EnvWorker healthy、`heartbeat_failed=0`。dry-run 选中四套件各 14 条、合计 56 条 development episode，与 held-out seeds `1–20` 的交集为空。

四条 worker lane 各完成 14 条，supervisor 接受 56/56，`infra_invalid=0`、success 0/56。四个 task0 queue 均达到 50 completed、0 pending、0 running、0 failed。compact summary 经 LoopX artifact classifier 判定为 `public_compact_candidate=true` 后才读取；未读取或公开轨迹、视频、privileged state、本地 artifact 路径或 worker 原始日志。

逐 episode 核心推理延迟（ms；`mean / p95`）：

| setting / seed | logical id | model inference | policy request e2e | chunk e2e | environment execution | Critic | elapsed (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| Goal-T / 79921 | `g0000-rollout-037` | 176.934 / 202.667 | 215.302 / 241.047 | 457.639 / 492.351 | 107.551 / 148.415 | 0.006 / 0.007 | 34.123 |
| Goal-T / 27999 | `g0000-rollout-036` | 179.783 / 200.054 | 218.415 / 240.103 | 465.315 / 518.536 | 109.051 / 154.074 | 0.006 / 0.007 | 34.669 |
| Goal-T / 61943 | `g0000-rollout-038` | 181.208 / 204.874 | 219.285 / 242.134 | 461.689 / 492.661 | 110.482 / 137.400 | 0.005 / 0.007 | 34.617 |
| Goal-T / 59218 | `g0000-rollout-040` | 180.366 / 221.825 | 219.377 / 265.947 | 459.640 / 513.139 | 107.317 / 151.628 | 0.006 / 0.007 | 34.275 |
| Goal-T / 63936 | `g0000-rollout-039` | 186.088 / 249.746 | 223.796 / 289.028 | 465.174 / 530.853 | 108.722 / 151.835 | 0.006 / 0.008 | 34.822 |
| Goal-T / 26238 | `g0000-rollout-042` | 185.663 / 228.550 | 224.334 / 266.889 | 470.226 / 539.033 | 109.102 / 145.249 | 0.006 / 0.007 | 34.880 |
| Goal-T / 13414 | `g0000-rollout-041` | 180.891 / 213.773 | 218.858 / 255.610 | 466.967 / 550.034 | 114.620 / 181.073 | 0.006 / 0.008 | 34.718 |
| Goal-T / 15331 | `g0000-rollout-044` | 183.122 / 228.792 | 221.814 / 265.797 | 472.987 / 525.320 | 113.850 / 165.309 | 0.006 / 0.008 | 35.137 |
| Goal-T / 51484 | `g0000-rollout-043` | 180.316 / 216.840 | 218.278 / 257.222 | 468.497 / 539.323 | 110.033 / 147.329 | 0.006 / 0.008 | 34.708 |
| Goal-T / 12134 | `g0000-rollout-046` | 176.471 / 222.763 | 213.669 / 258.967 | 449.891 / 497.590 | 107.125 / 151.689 | 0.005 / 0.007 | 33.505 |
| Goal-T / 23416 | `g0000-rollout-045` | 178.641 / 202.346 | 217.195 / 240.578 | 455.963 / 489.539 | 103.717 / 151.163 | 0.005 / 0.007 | 34.317 |
| Goal-T / 65880 | `g0000-rollout-047` | 182.833 / 210.892 | 221.209 / 250.370 | 471.588 / 538.954 | 111.372 / 147.746 | 0.006 / 0.008 | 35.018 |
| Goal-T / 10840 | `g0000-rollout-049` | 177.572 / 198.236 | 216.293 / 238.136 | 453.467 / 488.360 | 107.175 / 138.357 | 0.006 / 0.007 | 34.116 |
| Goal-T / 70195 | `g0000-rollout-048` | 182.693 / 206.475 | 221.526 / 247.208 | 472.377 / 534.715 | 112.859 / 162.203 | 0.006 / 0.007 | 35.010 |
| Goal-S / 67948 | `g0000-rollout-037` | 176.839 / 203.272 | 216.636 / 256.605 | 462.470 / 497.395 | 108.574 / 152.504 | 0.006 / 0.007 | 34.736 |
| Goal-S / 34009 | `g0000-rollout-036` | 182.094 / 222.895 | 220.957 / 261.020 | 476.414 / 531.539 | 113.164 / 159.055 | 0.006 / 0.008 | 35.700 |
| Goal-S / 65693 | `g0000-rollout-040` | 180.603 / 208.758 | 219.531 / 248.697 | 483.961 / 543.931 | 120.432 / 171.207 | 0.006 / 0.012 | 36.193 |
| Goal-S / 14274 | `g0000-rollout-039` | 180.955 / 213.753 | 219.782 / 253.358 | 475.866 / 515.665 | 113.122 / 152.801 | 0.006 / 0.008 | 35.813 |
| Goal-S / 66133 | `g0000-rollout-038` | 181.829 / 228.498 | 220.191 / 267.118 | 484.389 / 550.919 | 119.672 / 169.729 | 0.006 / 0.008 | 36.036 |
| Goal-S / 95988 | `g0000-rollout-042` | 180.419 / 207.605 | 219.153 / 246.125 | 467.541 / 501.840 | 108.479 / 144.254 | 0.006 / 0.008 | 35.044 |
| Goal-S / 55485 | `g0000-rollout-041` | 187.401 / 235.312 | 227.548 / 278.509 | 478.990 / 535.806 | 109.793 / 153.694 | 0.006 / 0.008 | 35.606 |
| Goal-S / 6017 | `g0000-rollout-044` | 183.967 / 237.797 | 222.696 / 276.009 | 479.602 / 534.092 | 111.419 / 157.466 | 0.007 / 0.011 | 35.788 |
| Goal-S / 78118 | `g0000-rollout-045` | 178.594 / 209.226 | 217.095 / 248.938 | 465.964 / 514.168 | 107.203 / 142.282 | 0.006 / 0.008 | 34.931 |
| Goal-S / 97713 | `g0000-rollout-043` | 173.926 / 206.889 | 212.609 / 246.293 | 457.404 / 499.062 | 106.563 / 148.934 | 0.006 / 0.008 | 34.279 |
| Goal-S / 34630 | `g0000-rollout-046` | 179.661 / 218.124 | 217.777 / 256.983 | 469.373 / 521.834 | 110.149 / 155.825 | 0.006 / 0.007 | 34.983 |
| Goal-S / 78995 | `g0000-rollout-047` | 183.552 / 211.199 | 221.977 / 253.599 | 480.804 / 564.995 | 114.801 / 169.605 | 0.006 / 0.008 | 35.967 |
| Goal-S / 43546 | `g0000-rollout-048` | 177.656 / 192.562 | 217.054 / 230.707 | 462.904 / 509.636 | 108.281 / 147.171 | 0.006 / 0.007 | 34.739 |
| Goal-S / 14401 | `g0000-rollout-049` | 182.656 / 210.567 | 222.283 / 255.704 | 480.766 / 514.201 | 115.295 / 157.094 | 0.006 / 0.007 | 35.762 |
| LIBERO-10-T / 99729 | `g0000-rollout-036` | 180.751 / 205.944 | 219.675 / 246.007 | 487.958 / 540.573 | 131.229 / 169.046 | 0.006 / 0.008 | 60.183 |
| LIBERO-10-T / 42095 | `g0000-rollout-037` | 182.882 / 219.683 | 221.806 / 257.623 | 485.253 / 541.770 | 126.267 / 162.338 | 0.006 / 0.007 | 60.426 |
| LIBERO-10-T / 21430 | `g0000-rollout-039` | 180.674 / 213.043 | 219.044 / 251.768 | 481.892 / 537.584 | 128.607 / 165.164 | 0.006 / 0.008 | 59.797 |
| LIBERO-10-T / 4171 | `g0000-rollout-038` | 180.373 / 216.204 | 218.585 / 253.413 | 482.206 / 532.300 | 127.119 / 170.598 | 0.007 / 0.008 | 60.106 |
| LIBERO-10-T / 31562 | `g0000-rollout-041` | 185.585 / 223.191 | 224.924 / 262.177 | 487.063 / 550.810 | 128.114 / 170.732 | 0.007 / 0.010 | 60.424 |
| LIBERO-10-T / 27821 | `g0000-rollout-040` | 177.098 / 205.233 | 214.743 / 245.579 | 477.020 / 519.521 | 126.041 / 161.826 | 0.006 / 0.008 | 59.087 |
| LIBERO-10-T / 53887 | `g0000-rollout-044` | 180.491 / 212.387 | 219.050 / 250.193 | 484.273 / 530.762 | 124.132 / 159.881 | 0.007 / 0.008 | 60.203 |
| LIBERO-10-T / 39919 | `g0000-rollout-042` | 183.024 / 209.080 | 221.479 / 247.664 | 488.436 / 562.280 | 130.173 / 167.961 | 0.006 / 0.008 | 60.409 |
| LIBERO-10-T / 75938 | `g0000-rollout-043` | 183.201 / 217.891 | 222.511 / 264.116 | 481.006 / 535.136 | 123.323 / 163.180 | 0.006 / 0.008 | 59.689 |
| LIBERO-10-T / 11413 | `g0000-rollout-046` | 177.307 / 197.544 | 215.657 / 235.409 | 481.032 / 527.478 | 128.558 / 178.499 | 0.006 / 0.007 | 59.377 |
| LIBERO-10-T / 86513 | `g0000-rollout-045` | 179.951 / 203.245 | 217.902 / 241.642 | 479.069 / 527.911 | 126.134 / 156.482 | 0.006 / 0.008 | 58.936 |
| LIBERO-10-T / 68960 | `g0000-rollout-048` | 179.130 / 208.558 | 217.014 / 255.025 | 471.096 / 540.007 | 121.044 / 150.384 | 0.005 / 0.007 | 58.154 |
| LIBERO-10-T / 76119 | `g0000-rollout-047` | 174.633 / 200.262 | 212.625 / 238.727 | 468.890 / 509.752 | 121.187 / 153.312 | 0.005 / 0.007 | 57.799 |
| LIBERO-10-T / 36147 | `g0000-rollout-049` | 176.643 / 200.802 | 214.820 / 240.034 | 473.172 / 510.699 | 124.009 / 158.357 | 0.006 / 0.007 | 58.116 |
| LIBERO-10-S / 6531 | `g0000-rollout-037` | 179.535 / 206.266 | 217.613 / 246.790 | 469.098 / 523.205 | 119.023 / 152.168 | 0.006 / 0.007 | 57.874 |
| LIBERO-10-S / 78416 | `g0000-rollout-036` | 179.887 / 204.471 | 219.316 / 245.640 | 478.464 / 526.915 | 123.392 / 160.278 | 0.006 / 0.007 | 59.226 |
| LIBERO-10-S / 79536 | `g0000-rollout-039` | 181.527 / 211.619 | 220.020 / 248.796 | 474.874 / 521.790 | 120.084 / 151.651 | 0.006 / 0.007 | 58.703 |
| LIBERO-10-S / 22631 | `g0000-rollout-038` | 178.300 / 205.719 | 217.185 / 244.312 | 476.089 / 538.124 | 123.323 / 159.106 | 0.006 / 0.008 | 59.040 |
| LIBERO-10-S / 47549 | `g0000-rollout-040` | 181.633 / 220.106 | 220.994 / 259.713 | 484.589 / 536.832 | 129.657 / 169.078 | 0.006 / 0.008 | 59.782 |
| LIBERO-10-S / 71838 | `g0000-rollout-041` | 176.653 / 203.407 | 214.756 / 242.135 | 471.408 / 525.839 | 122.161 / 165.645 | 0.005 / 0.007 | 57.963 |
| LIBERO-10-S / 23484 | `g0000-rollout-043` | 182.248 / 213.776 | 220.850 / 253.962 | 478.826 / 526.744 | 122.582 / 154.999 | 0.006 / 0.007 | 58.935 |
| LIBERO-10-S / 69621 | `g0000-rollout-042` | 179.761 / 207.232 | 218.322 / 245.278 | 475.775 / 518.450 | 123.371 / 158.575 | 0.006 / 0.008 | 59.088 |
| LIBERO-10-S / 86768 | `g0000-rollout-045` | 182.739 / 210.844 | 222.901 / 254.683 | 492.328 / 537.808 | 138.648 / 180.633 | 0.006 / 0.007 | 60.268 |
| LIBERO-10-S / 15610 | `g0000-rollout-044` | 176.669 / 202.368 | 215.543 / 250.101 | 463.920 / 511.488 | 117.275 / 150.815 | 0.006 / 0.007 | 57.192 |
| LIBERO-10-S / 97763 | `g0000-rollout-046` | 180.813 / 209.343 | 219.717 / 249.434 | 477.983 / 527.779 | 124.366 / 167.042 | 0.006 / 0.008 | 58.662 |
| LIBERO-10-S / 77641 | `g0000-rollout-047` | 176.243 / 205.754 | 213.913 / 243.729 | 461.944 / 493.856 | 113.564 / 144.643 | 0.005 / 0.007 | 56.872 |
| LIBERO-10-S / 28311 | `g0000-rollout-048` | 177.712 / 203.605 | 216.422 / 241.896 | 480.235 / 514.501 | 130.658 / 167.466 | 0.006 / 0.007 | 58.884 |
| LIBERO-10-S / 23764 | `g0000-rollout-049` | 179.554 / 208.190 | 218.903 / 263.286 | 479.814 / 547.043 | 127.685 / 177.964 | 0.005 / 0.007 | 58.782 |

本批共 37912 条 latency events；按组件事件数加权：model inference 4592 次、平均 180.184 ms，policy request end-to-end 4592 次、平均 218.809 ms，chunk end-to-end 4592 次、平均 474.743 ms，environment execution 5152 次、平均 119.602 ms，Critic evaluation 5152 次、平均 0.006 ms。Critic 仍是 strict pure-VLA 下的 no-op，Role1/recovery 未触发。

固定 runner 的七批累计为 200 条有效 development episode、0/200 success、135400 条 latency events；model inference 16400 次、加权平均 191.297 ms，policy request end-to-end 平均 231.904 ms，chunk end-to-end 平均 506.375 ms，environment execution 18400 次、平均 130.164 ms，Critic evaluation 平均约 0.006 ms。LoopX board 为 206/206 terminal，仍有 0 条 score-countable；完整性分类统一为 `runtime_isolation_not_attested`。这些结果只完成四个 task0 的 development 阶段，不能称为四套件最终成功率。

批量 ingest 只闭合 episode queue，不自动推进 evolution lifecycle：四个 task0 的 compact state 均仍为 `phase=rollout`，且尚未生成 failure-cluster/medoid artifact。后续必须显式运行 Cluster 阶段或先扩展其余 campaign，不能把 queue 50/50 误报为完整 development/patch 流程已完成。

## 最终验证

2026-08-31 再次从安装后的 `liberopro` API 创建四个 suite，并对每个 task 调用 `get_task_init_states`：40/40 BDDL 存在，四套件各 10 个任务，每个任务均反序列化得到 50 个非空 init states。

```text
56 targeted tests passed in 9.81s
76 current targeted tests passed in 11.61s
62 post-sixth-batch targeted tests passed in 7.13s
62 post-seventh-batch targeted tests passed in 6.62s
batch7 Markdown table identity check: 56/56 pass
four task0 queues: 50 completed / 0 pending / 0 running / 0 failed
LoopX board: 206/206 terminal / 0 score-countable
40 campaigns / 2000 development slots / 800 held-out episodes per method: dry-run pass
git diff --check: pass
Python py_compile: pass
```

本轮 62 项目标测试覆盖 `tests/test_liberopro_development_batch.py`、`tests/test_liberopro_paper_campaign_matrix.py`、`tests/test_libero_latency.py`、`tests/test_libero_evolution_runtime.py` 和 `tests/test_evolution_protocol.py`；此前 runtime policy 测试仍保留在上一轮 95 项验证中。

LoopX experiment board 当前有 206 个 terminal 行：200 条有效固定-runner development episode、4 条修复前 terminal 证据，以及 2 条 diagnostic pilot/latency profile；全部 `score_countable=false`，没有伪装成官方结果或 matched comparison。对本日志单文件执行 `loopx check` 为 clean（0 errors、0 warnings）；全仓扫描只命中仓库既有源码/测试中的通用 `credential`、`private_ip` 字样，并未在本日志发现密钥或私有 API 地址。

## 已知限制与下一步

- 固定 runner 已完成四个 task0 各 50 条 development episode，但 0/200 仍只覆盖 40 个 task-setting campaign 中的 4 个，不能代表四套件最终成绩；要报告套件成功率仍需覆盖其余 36 个任务并完成论文规定的后续阶段。
- 四套件的 60-step 运行只用于比较延迟，不得计入正式成功率。
- 本轮 pure Pi0.5 未触发 Role1/recovery；这两个组件的真实 LLM/恢复延迟需要在启用 Critic 与 Role1 的独立实验中测量。
- 正式矩阵继续固定在 `d0463d0` clean source worktree；四个 task0 已各完成 50/50 个 development seeds。下一步检查 failure-cluster/medoid 状态并扩展其余 36 个任务，完成开发与 patch 冻结流程后才可触碰 held-out 1–20。
- 不得引用项目 README 的 90.8% 作为本机结果。

## 2026-09-01 — 单条 Critic → Role1 → Recovery 闭环诊断

本节是 development-only wiring smoke，不是论文正式成绩，不进入前述 200 条
strict pure-VLA development episode 的分母。测试对象为 Goal-S task0、development
seed 21；合成 bundle 固定一条 `episode.step_index >= 12` Critic rule，并绑定一条
两步 `set_gripper` Recovery。LoopX 中所有尝试均登记为 `diagnostic_only` explore，
`score_countable=false`。

### 问题与修复

1. a0/a1 均在 reset 阶段失败，公开摘要分别为 connection reset 和 broken pipe；
   根因是启动 runtime 时遗漏 NVIDIA GLVND vendor manifest，MuJoCo 无法创建 headless
   EGL context。重新通过 `activate_zetta_libero.sh` 注入 `MUJOCO_GL=egl`、
   `PYOPENGL_PLATFORM=egl` 和 `__EGL_VENDOR_LIBRARY_FILENAMES` 后，预检得到完整的
   CUDA→EGL 0–3 映射，reset 恢复正常。两次失败均记为 `runner_invalid`。
2. a2 已触发 Critic 并发出 3 次真实 Role1 LLM 请求，但严格输出校验均拒绝
   `Role1 model must return exactly one bare JSON object`，Recovery 未执行。根因是
   `CodexPlanner` 将包含 transport/reasoning 标记的完整渲染流作为一条模型消息交给
   Role1，而非 SDK 的 final response。修复后完整渲染流仍留在本地审计 artifact，
   下游 `PlannerResult.messages` 只接收 final response；无 final event 时保留旧回退。
   修复提交为 `7341eec69ae60c91fb70b9dc44cadee934068341`，38 项
   Codex/Role1 定向测试通过，clean source fence 通过。

### a3 实际闭环结果

- episode：`valid`，任务官方 success=false；后者只表示 Pi0.5 未在 horizon 内完成
  抽屉任务，不影响本节的机制闭环判定。
- Critic：合成 rule 在 step 12 单次触发（cooldown 10000）。
- Role1：1 次真实 `gpt-5.6-sol` / `high` 请求，生成并持久化 1 个 decision。
- Recovery：Actor 取得唯一环境写权限，执行 1 次 `set_gripper` Recovery；
  `candidate_intervention=true`，随后控制权返回 Pi0.5 并跑完 episode。
- 闭环判定：`Critic=1 / Role1 decision=1 / Recovery execution=1`，通过。
- 总耗时 62.352 s，共 515 条 latency events；仅用于 wiring/latency diagnosis。

分组件延迟（ms）：

| component | count | mean | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| observation preprocess | 61 | 2.817 | 2.481 | 3.256 | 17.643 |
| policy queue wait | 61 | 20.737 | 20.672 | 21.035 | 22.914 |
| model inference | 61 | 229.051 | 186.626 | 320.552 | 890.110 |
| action decode/postprocess | 61 | 0.159 | 0.155 | 0.198 | 0.270 |
| policy request end-to-end | 61 | 272.639 | 231.365 | 367.060 | 934.101 |
| environment execution | 73 | 118.128 | 130.459 | 178.179 | 214.270 |
| Critic evaluation | 73 | 38.125 | 40.483 | 52.487 | 125.076 |
| Role1 LLM request | 1 | 18095.800 | 18095.800 | 18095.800 | 18095.800 |
| Recovery execution | 1 | 236.967 | 236.967 | 236.967 | 236.967 |
| chunk end-to-end | 61 | 597.650 | 572.952 | 699.822 | 1207.564 |
| episode end-to-end | 1 | 62351.816 | 62351.816 | 62351.816 | 62351.816 |

本地保存三份非空视频 artifact：agentview 110678 bytes、wrist 198952 bytes、
multiview 303432 bytes。它们位于本次 a3 的 `episode/videos/` 下，按 classifier
标记为非 compact 私有诊断 artifact，因此只保存在本机，不读取、不提交。原始轨迹、
privileged state、Role1 消息和 worker log 同样没有进入仓库或 LoopX board。

## 2026-09-01 — Goal-T task2 正式 Harness 演化链

目标为 `put the wine bottle in the bowl`，使用冻结 revision
`d0463d0c249164a5490a4c5cf36bf43a32abc153`、50 个 development seeds 与隔离的
held-out seeds 1–20，按 `Pure VLA → Cluster → Diagnose → Recovery Proposal →
Same-seed → Regression → Held-out → Promote/Reject` 执行。原始视频与轨迹仅保存在
campaign 本地目录；本日志只记录公开安全的聚合状态。

### a0：并发配置导致的 runner-invalid

- run id：`paper-v1-goal-t-t02-dev50-d0463d0-a0`。
- 结果：3 条有效 episode、94 次 infrastructure-invalid attempt，47 个 logical seed
  耗尽每 seed 两次基础设施重试预算，runner 以
  `rollout_blocked_on_infrastructure`（exit 4）终止；这些失败不计作任务失败。
- 根因：同一 `local0` runtime 上错误地追加了 `--concurrency 3` worker，与原单 worker
  争用单环境 rank，造成快速基础设施失败。
- 处置：保留原 `state/queue`、视频和日志，不删除、不覆盖；LoopX board 已更新为
  `runner_invalid`，classification 为
  `worker_concurrency_infrastructure_exhaustion`，并释放 a0 并发租约。

### a1：单 worker 干净重跑

- run id：`paper-v1-goal-t-t02-dev50-d0463d0-a1`。
- 使用同一 immutable manifest 与同一批 50 development seeds，写入新的
  `state-a1/queue-a1`；source revision fence 为 clean/pass。
- 运行约束：只允许一个 `local0` worker，worker `--concurrency 1`；LoopX 总 active
  case 上限和目标均为 1。
- 启动状态：Ray runtime 健康，provider broker 以独立长驻会话恢复；队列已成功进入
  `49 pending / 1 running`。后续以首条 `valid` episode 和持续无 infra-invalid 为
  运行健康判据，再推进 Cluster 及后续 gate。

### a1 rollout、诊断与 Harness 修复

- Pure VLA rollout 最终为 `50 completed / 0 failed`；supervisor 随后完成 Cluster 和
  Diagnose，进入 `propose`，证明单 worker 重跑消除了 a0 的基础设施污染。
- Stage2 连续生成 8 个候选，但 seed-blind compact reducer 显示 8/8 均为
  `trajectory_feature_contract_rejection`，不是 API 或模型请求失败。候选字段在部分
  action state 中出现后又消失，无法满足 shadow replay 的 suffix-stable 可评估约束；
  reducer 未输出 seed、轨迹、prompt 或候选正文。
- 根因是 Stage2 feature catalog 对所有 action rows 做字段并集，而 shadow gate 要求
  每条轨迹中字段自首次出现后持续存在，两者契约不一致。修复后 catalog 只暴露每条
  轨迹内 suffix-stable 且跨轨迹共有的字段。
- 同时修复候选轮次耗尽后的状态机缺口：此前 `propose` 直接抛出 `ValueError`；现在
  按既有 bounded-search 语义进入 `complete`，记录
  `no_candidate_passed_primary_or_secondary`，形成正式 Reject 而不是 runner crash。
- 定向验证：39 项 lifecycle/refinement/CLI 测试通过；另 102 项 evolution、campaign、
  LIBERO runtime 与论文矩阵测试通过。

### a2：修复 revision 上的同 seed 重跑

- 修复 revision：`44fc338992faefbdb84720cb5428ce08a1c4728d`，已推送
  `origin/main`，并建立 detached clean source worktree；source revision fence pass。
- 重新物化论文 4×10 campaign matrix，沿用 master seed `260816590`。a2 与 a1 的
  50 个 development seeds、20 个 held-out seeds 及逐 seed policy RNG 完全相同。
- run id：`paper-v1-goal-t-t02-dev50-44fc338-a2`；使用独立
  `state-a2/queue-a2`，仍限制为一个 `local0` worker、`--concurrency 1`。
- 启动后首条 episode 已被接受为 valid，队列为
  `1 completed / 48 pending / 1 running / 0 failed`。
- Pure VLA 最终完成 `50/50 valid`、`7 success / 43 failure`，成功率
  `14.0%`，`0 infra-invalid`；Cluster 选择主簇后进入 Stage1 Diagnose。
- Diagnose 调用实际读取了 30 条视觉记录并返回 11 条视觉引用；seed-blind
  compact receipt 显示其中 1 条引用的 `access_record_id` 被模型写错，但对应
  `content_id` 已读取且只有一个可解析的视觉记录。原 revision 的严格校验因此
  fail closed，a2 作为 `runner_invalid` 归档，不在旧源码上热修复续跑。

### a3 前置修复：唯一视觉内容的审计 ID 规范化

- Harness 仅在引用的 immutable `content_id` 已实际作为图片字节交付，且该内容
  在当前与继承审计日志中恰好对应一个视觉访问记录时，规范化模型写错的
  `access_record_id`；同一视频多帧导致歧义、内容未读取或 ID/内容冲突仍 fail closed。
- 定向验证覆盖唯一绑定修复、视频多帧歧义拒绝、访问日志摘要校验与 Stage
  lifecycle：`67 passed`；扩大到 evolution、campaign、LIBERO runtime 与论文
  矩阵相关测试后为 `381 passed`（仅 3 条第三方 deprecation warning）。
- 修复提交 `635696466073623c00cef44ee4e94c7a8a8e34b8` 已推送
  `origin/main`；detached clean source 的 revision fence 通过。新矩阵仍为
  4×10 tasks、每 task 50 个 development seeds 与 20 个 held-out seeds；针对
  Goal-T task2 的 compact equivalence receipt 确认除 source revision 外，seed、
  policy RNG、horizon、evolution policy 与 latency contract 均和 a2 相同。

### a3：视觉引用修复 revision 上的同协议重跑

- run id：`paper-v1-goal-t-t02-dev50-6356964-a3`；独立
  `state-a3/queue-a3`，单 `local0` worker、`--concurrency 1`。
- Pure VLA 最终为 `50/50 valid`、`10 success / 40 failure`，成功率 `20.0%`，
  `0 infra-invalid`；队列终态为 `50 completed / 0 failed`。该结果仅属于
  development baseline，不是 held-out 正式分数。
- Cluster 选择 `visual-cluster-e831c25681cfb65b`；Diagnose 的公开安全结论为：
  酒瓶已被抓取并偏心接近碗，随后碰撞造成碗倾倒或位移，在形成 containment 前
  提前松爪或失去抓持。
- Stage2 在冻结预算内生成 8 个真实 Recovery Proposal。8/8 均由 shadow replay
  fail closed，success-control 假阳性率依次为
  `0.5, 0.5, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7`，而配置上限为 `0`；每个候选均写入
  immutable rejection，没有放宽阈值、授权 falsification 或绕过门禁。
- 第 8 个候选登记后，supervisor 正常进入 `phase=complete`，终态为
  `candidate_round_limit_exhausted` / `no_candidate_passed_primary_or_secondary`。
  因没有候选通过 Proposal 门禁，Same-seed、Regression、Held-out 1–20 和 Promote
  均未执行；本次 Harness 结论为正式 Reject，而不是 runner-invalid。

#### a3 延迟与 artifact 汇总

50 个 episode 的 50 份 compact latency summary 共记录 `21786` 个事件。下表的
mean 按事件数加权；p50/p95 是 50 个 episode 各自 mean 的分位数，max 是所有
episode summary 中的最大单次值。

| 组件 | count | weighted mean (ms) | episode-mean p50 (ms) | episode-mean p95 (ms) | max (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| action decode/postprocess | 2592 | 0.157 | 0.155 | 0.179 | 4.184 |
| model inference | 2592 | 200.021 | 199.869 | 218.482 | 501.712 |
| policy queue wait | 2592 | 20.842 | 20.701 | 21.421 | 37.346 |
| policy request end-to-end | 2592 | 242.441 | 241.498 | 263.127 | 543.945 |
| observation preprocess | 2592 | 2.657 | 2.554 | 3.181 | 43.478 |
| environment execution | 3092 | 135.781 | 129.663 | 168.028 | 1184.032 |
| Critic evaluation | 3092 | 0.007 | 0.007 | 0.007 | 0.054 |
| chunk end-to-end | 2592 | 534.875 | 524.419 | 601.793 | 1740.437 |
| episode end-to-end | 50 | 34964.853 | 38743.049 | 43927.243 | 49899.880 |

`role1_llm_request` 与 `recovery_execution` 没有事件，原因是 8 个候选均在 shadow
门禁被拒绝，不能进入 live Recovery。campaign 本地共有 `200` 个非空 MP4；仅做
文件计数和空文件校验，不读取、不提交视频、轨迹、agent transcript 或 worker log。
terminal board 写回与 concurrency release 完成后，`18730` runtime 已优雅停止，
Ray 与模型进程退出，GPU compute process 列表为空；provider broker 保持运行。

#### a3 恢复运行时问题

- `run_campaign.py --worker-command` 接收的是后续 argv；若将整条 worker 命令包成
  一个 shell 字符串，会以该完整字符串作为可执行文件并触发 `FileNotFoundError`。
  修复为按参数传入 Python、模块、queue、host 和 concurrency。
- 非登录 shell 不会自动继承 provider 密钥；Stage2 会以
  `Missing environment variable: CODEX_GATEWAY_API_KEY` 失败。启动前加载既有
  `configs/providers.env` 并设置 `CODEX_HOME` 后可原位重试。日志只记录变量名和
  配置路径，不记录密钥值。

### a4 前置修复：shadow rejection 反馈闭环

a3 的 8 个 Stage2 `input.json` 中 `refinement_context` 均为 `null`。根因不是
provider 或模型失效，而是 lifecycle 只会从已注册候选的 live gate rejection 和
operator no-op rejection 构造 refinement context；shadow gate 在注册前拒绝候选，
所以下一轮看不到上一候选及其假阳性统计，并反复生成近似的 gripper detector。

修复后的 lifecycle 从 append-only shadow rejection 指向的 immutable Stage2
attempt output 重建上一候选，并逐项校验 candidate output、candidate digest、shadow
report 与 precommit digest。给下一轮的 prompt-safe context 只包含候选机制、target
detection 聚合、unknown-divergence 数量和 success-control FP 聚合，不包含 seed、路径、
trajectory ID 或 raw outcome。Stage2 必须使用 fresh provider thread，且 validator
拒绝当前 cluster 历史中任何已拒绝 mechanism digest 的精确重复；冻结的 zero-FP
门禁保持不变。

对 a3 本地 immutable artifacts 的只读兼容性检查成功重建最新上下文：
`target_count=33`、`target_detected_at_divergence=0`、
`target_triggered_anywhere=31`、`target_unknown_divergence_count=33`、
`success_control_false_positives=7/10`，并载入 8 个禁止重复的历史机制。定向及扩大
回归分别为 `42 passed` 和 `105 passed`；Ruff lint 与 `git diff --check` 通过。
另有 fail-closed 测试证明 shadow/precommit digest 被修改时不会生成 refinement。

a4 仍须在新的 clean source revision 上重新物化并 source-fence；只有新候选通过
zero-FP Proposal 门禁后，才能实际进入 Same-seed、Regression 与隔离的 held-out
seeds 1–20。本节只记录前置修复，不预报 a4 的最终 Promote/Reject。

### 2026-09-01T09:10:46Z — a4 source-fenced run 启动

- source revision：`80c3385564a10ae920826049dd42c35183fee553`。detached source
  worktree 为 clean；本地、expected revision 与刷新后的 `origin/main` 完全一致，
  LoopX source revision fence 返回 `admitted=true`。
- 重新物化的论文矩阵仍为 4 个 setting、每 setting 10 个 task、每 task 50 个
  development seeds；所有 init state 非空，held-out seeds 1–20 与 development
  分区隔离。归一化 source revision 后，a4 与 a3 的 campaign plan 无差异。
- LoopX board 已预登记 running row
  `paper-v1-goal-t-t02-dev50-80c3385-a4`，attempt 为 4；运行期间 metrics 为空且
  `score_countable=false`。
- Runtime 使用短 Ray 临时目录，避免 AF_UNIX socket 超过 107 字节；健康检查为
  1/1 env rank healthy。运行限定单 `local0` worker 和 `--concurrency 1`，provider
  配置只通过进程环境注入，不记录密钥。
- 首个运行检查点为 `4 completed / 0 failed / 1 running`；4 条均已生成 compact
  latency summary，共有 16 个非空 MP4。尚未进入 Cluster/Diagnose/Proposal，
  因此当前不报告成功率或 Recovery 结论。

### a4 终止：Diagnose 视觉证据合同未满足

- Pure VLA 完成 `50/50 valid`、`15 success / 35 failure`，development 成功率
  `30.0%`，`0 infra-invalid`。Cluster 正常完成并选出主失败簇；这仍不是 held-out
  正式分数。
- Stage1 Diagnose 的同一 provider thread 完成 4 个模型 turn、36 次工具调用，实际读取
  3 条 compact telemetry 和 11 张图片。成功对照与事件窗要求均满足，但目标失败簇的
  episode overview 只读取并引用了 2 个，低于冻结合同要求的 3 个，validator 因此
  fail closed。
- a4 在 `phase=diagnose` 终止，未生成 Recovery Proposal；Same-seed、Regression、
  held-out 1–20 和 Promote/Reject 均未开始。因此该 run 记为 `runner_invalid`，不是
  Proposal Reject，也不能用 30% baseline 声称 Harness 提升。
- 50 份 compact latency summary 共 `20610` 个事件：model inference weighted mean
  `186.043 ms`、policy request end-to-end `226.570 ms`、episode end-to-end
  `30826.847 ms`。本地保存 `200` 个非空 MP4；仅核验数量与非空性，不读取或提交
  视频、轨迹、provider transcript 和密钥。
- LoopX board 已将同一 run id 从 `running` 更新为 `runner_invalid`，classification
  为 `diagnosis_visual_evidence_contract_runner_error`，`score_countable=false`。

### a5 前置修复：有上限的 validator 纠错

Stage 提示原本已经明确要求 3 个失败 overview，故此次不是 API、Ray 或门禁阈值问题；
缺口在于模型输出可局部修正时 Harness 直接终止。修复保持所有视觉/遥测 gate 不变：

1. validator 失败后最多允许 1 次定向纠错，并必须优先续接同一 provider thread；
2. 纠错请求只携带原始请求、失败输出 digest 和 validator 原因，不把失败输出改写为
   已接受结果；
3. 前一 attempt 的 immutable evidence-access 日志按 digest 验证后加入视觉与结构化
   证据审计连续性，纠错只需补读缺失证据；
4. provider thread 无法续接时仍走既有 fresh reconstruction；纠错后再次不满足合同则
   fail closed，跨进程恢复也不会无限增加纠错次数。

验证结果：Stage session、framework repair、lifecycle 与 refinement 定向集合
`90 passed`；扩大 evolution 集合除一个未改动的 fake capacity throughput 用例外
`187 passed / 1 deselected`。该 capacity 用例单独复跑仍因其自身 capacity level
判定为 false 失败，与本次改动文件无交集。下一步在新 revision 上建立 clean source、
重新物化同协议矩阵并启动 a5；held-out seeds 在前置阶段继续保持隔离。

### a5 停止与 a6 冻结 artifact 复用

- a5 在新 revision 上启动后产生 12 条完整 Pure VLA rollout。因 a4 已有 50/50
  valid baseline，且离线 Harness 修复不改变环境、policy、seed、horizon 或 rollout
  command，继续重跑会重复消耗 GPU；故主动停止 a5，并在 LoopX board 以
  `operator_superseded_by_validated_baseline_reuse` 归档为 `runner_invalid`。
- a6 run id 为
  `paper-v1-goal-t-t02-dev50-80c3385-0cb765f-a6`。复用前重新校验 a4 rollout、queue、
  gate runner、campaign、lifecycle 文件及 episode/cluster ledger 摘要；准入 receipt
  保存为 `.loopx/a4-offline-harness-resume-receipt.json`。允许复用范围仅为离线
  baseline、Cluster 与失败 Diagnose 上下文，禁止跨 revision 性能归因。
- a6 因而登记为 `diagnostic_only`、`score_countable=false`。后续同类离线 Harness
  修复默认复用已冻结 rollout、视频、cluster、provider thread 与 latency summary；
  只有无法证明 manifest、seed、协议和执行路径等价时才重跑。

### a6 Diagnose、Proposal 与 Same-seed 进行中

- Diagnose 在同一 provider thread 上执行一次有上限的定向纠错，补齐缺失的第 3 个
  target-failure overview 后通过原视觉/遥测合同；没有放宽 validator。
- 首个 Proposal 的 shadow replay 在 15 个 success controls 上为 `0/15` 假阳性，按
  默认严格零 FP 门槛获准进入 live Same-seed。27 个 parent arm 全部从 a4 冻结
  baseline 采用，只运行 candidate arm。
- 首轮 candidate 未通过 Same-seed 推进条件，状态机以
  `optimization_outcome=refine_active_cluster` 生成第二候选；没有跳过 Regression 或
  直接触碰 held-out seeds 1–20。
- live Recovery 首次暴露 venv 依赖漂移：`pydantic-ai-slim 2.36.0` 要求
  `pydantic>=2.12`，实际为 2.10.6，触发缺失 `_function_like` 的 `infra_invalid`。
  将同一 venv 升级为 Pydantic 2.13.5 后，Pydantic-AI/Role1 导入烟测通过；策略结果
  未受该无效 attempt 污染。
- 自定义 Responses gateway 随后拒绝跨工具 turn 回放的 provider-owned encrypted
  reasoning item。修复仅在中央 broker 模式设置
  `openai_send_reasoning_ids=false` 和 `openai_reasoning_context=current_turn`，保留
  portable function-call/output history；61 项 API loop、provider pool、broker 和
  Role1 定向测试通过。由于 a6 已是跨 revision 诊断 lane，同一修复也同步到本地
  source 副本以继续复用现有 candidate；该副本不再满足 clean source fence，a6
  仍明确不可计分。
- 修复后第二候选已完成一条真实 Goal-T task2
  `Critic → Role1 decision → Recovery execution`。对应 compact latency summary：
  Critic 71 次，Role1 LLM request 1 次、17.506 s，Recovery execution 1 次、
  4.347 s，episode end-to-end 55.322 s。Same-seed 尚未 terminal，不能提前声明
  Recovery 带来成功率提升。

### a6 终止：Same-seed 候选轮次预算耗尽

- a6 最终状态为 `phase=complete`、`candidate_round=2`、
  `optimization_outcome=same_seed_gate_iteration_budget_exhausted`；冻结的
  `same_seed_max_rounds=2` 已用完，终态为 Reject。
- 第一候选完成 18 条有效 candidate episode，成功 `4/18`；即使余下 9 条全部成功，
  上界也只有 `13/27`，低于冻结的 `14/27` 门槛，因此按确定性早停进入第二轮。
- 第二候选完成 19 条有效 candidate episode，成功 `5/19`；即使余下 8 条全部成功，
  上界同样只有 `13/27`，再次触发确定性早停。两轮 Proposal 在 15 个冻结
  success controls 上均保持 `0` 假阳性，没有降低 zero-FP 标准。
- 第二候选累计产生 4 次真实 Role1 decision 和 4 次 Recovery execution，分布于
  3 个 episode；其中一个 episode 连续执行 2 次 Recovery，证明一次恢复失败后仍可
  再次尝试。19 个 accepted candidate episode 共保存 57 个非空 MP4。
- 聚合延迟为：Role1 LLM request 平均 `14167.403 ms`、Recovery execution 平均
  `4315.946 ms`、episode end-to-end 平均 `36928.312 ms`。
- 因 Same-seed 未通过，Regression 与 held-out seeds 1–20 均未启动；held-out 分区
  继续保持未使用。早停后 queue 中未消费项作为 terminal artifact 保留，不删除也不
  伪装成已执行结果。
- LoopX board 的同一 a6 run id 已从 `running` 更新为 `completed`，classification
  为 `same_seed_iteration_budget_exhausted_terminal_reject`。该跨 revision resume
  仍为 `diagnostic_only`、`score_countable=false`，matched comparison 不可用于论文
  成功率归因。
- 下一独立 run 必须基于新提交后的 clean source revision 重新 source-fence，保持
  `14/27` Same-seed 门槛和 zero-FP success-control 门禁，将候选轮次预算提高到 8；
  复用 a4 的冻结 baseline、cluster、diagnosis、视频与 latency，并携带 a6 两个已拒绝
  mechanism 的摘要/digest，避免重复生成。

### a7：扩大候选预算及原框架 Critic 缺陷

- a7 在 clean revision `8ec06f5010ed5e38ff6c9a327cc749d0790a7566` 上通过
  source fence，继续复用 a4 的 50 条冻结 Pure VLA、Cluster、Diagnose、视频与延迟，
  并继承 a6 两轮已拒绝候选历史；held-out seeds 1–20 仍保持隔离且未使用。
- 第 5 轮候选的 success-control shadow 假阳性为 `7/15`（46.67%），按冻结的
  zero-FP 门禁拒绝。第 6 轮候选通过 `0/15` shadow 门禁，但 Same-seed 在 19 条有效
  candidate episode 后仅成功 `5/19`；余下 8 条即使全部成功也最多为 `13/27`，低于
  `14/27` 门槛，因此确定性早停并拒绝。
- 第 7 轮候选 `08b088b8bd78abd5d25192ec5efb4e9314386d90432a5d122b1cc81dd8563335`
  通过 zero-FP shadow 门禁并进入 Same-seed，但连续 candidate attempt 均在首个物理
  step 触发相同 `KeyError`，没有产生可计分 candidate episode；这些 attempt 只能归为
  `infra_invalid`，不能计作任务失败，也不能消耗 Same-seed 性能预算。
- 根因位于项目原框架：canonical `TemporalCritic` 与独立 LIBERO runtime Critic 都在
  检查 activation conditions 之前解析主特征。首步没有 previous EEF，因而
  `command.realization.stalled` 尚不存在；尽管
  `command.realization.direction_available=false` 本应屏蔽该规则，主特征的提前读取仍
  抛出异常。该缺陷在 a7 revision 的 `origin/main` 中已存在，不是 LIBERO-PRO 注册、
  候选模型输出或 Recovery actor 引入。
- 修复将主特征解析移动到 activation guard 之后，并让 feature extractor 在没有
  previous EEF 时显式输出 `command.realization.direction_available=false`。新增
  canonical、runtime 与 LIBERO feature extractor 回归测试；定向集合为
  `64 passed`（3 条既有 robosuite deprecation warning），Ruff 与
  `git diff --check` 通过。扩大 runtime 集合另有 17 个环境依赖失败：16 个因当前
  venv 未安装 `prometheus_client`，1 个因未安装 RoboCasa；均不涉及此次改动路径。
- a7 已停止，避免对同一确定性基础设施错误继续重试；其 LoopX running 行将在新
  revision admission 前以 runner-invalid 终结。第 7 轮候选将迁移到 a8，修复前的
  infra-invalid attempt 不计分，并从同一冻结 Same-seed 配对集合继续。

### a8：第 7 轮确定性 Reject 与中断恢复缺口

- a8 在 clean revision `acfa3cf085b483138114d2d8e6172e68eb5ae772` 上恢复第 7 轮
  Same-seed。EGL 修复后得到 14 条有效 candidate episode，成功 `0/14`；此前 32 条
  EGL 基础设施错误保留为不计分证据。剩余 13 条即使全部成功也只能达到 `13/27`，
  低于冻结门槛 `14/27`，因此 gate 已形成确定性 early Reject。
- gate decision 已 append，但进程在 phase 迁移前中断。原 gate runner 恢复逻辑只
  处理“无 decision”的状态，无法重放已有决定；修复提交
  `8ef82750e5f691a7b75ca23dcf79c4b454bca9e9` 后，38 项 gate/lifecycle 测试通过，
  clean source fence 通过。
- a8 的旧 shadow rejection 与 gate plan 绑定旧 manifest，不能直接作为新 manifest
  权限使用。a8 因而在 LoopX board 归档为 `runner_invalid`，classification 为
  `cross_revision_shadow_rejection_manifest_binding_runner_error`，不是策略失败；其
  candidate rollout、视频和延迟证据原样保留。

### a9：跨 revision locator 恢复失败与前置修复

- a9 将旧 shadow rejection 和 gate plan 派生重签到新 manifest，并保持 parent
  EpisodeRecord 原字节；恢复重放已从 `same_seed_gate` 正确推进到第 8 轮
  `propose`。旧 infrastructure-recovery authorization 绑定退役 plan digest，按规则
  只归档、不继承权限。
- 首次启动在 Proposal artifact index 构建阶段 fail closed：
  `accepted episode artifact locator is unsafe`。此时尚未调用模型、未运行新 episode，
  held-out seeds 1–20 仍未使用。
- 根因是 immutable EpisodeRecord 中的绝对 rollout locator 必须保持原字节，迁移后
  仍指向旧 campaign；私有、manifest-scoped artifact resolver 已正确重绑到新 campaign，
  但生命周期的 frozen-digest 快速路径没有使用该 resolver。
- 前置修复只允许按 accepted digest、campaign-scoped keyed content ID 和当前 campaign
  内文件恢复 locator；不改写 EpisodeRecord，不允许越界路径，也不跳过实际证据读取时
  的 SHA-256 复核。新增回归证明跨 root 后 episode ledger 字节不变、Agent index
  不变且证据仍可解析。扩大 evolution/gate/runtime 定向集合为 `267 passed`；Ruff
  lint 与 `git diff --check` 通过。下一次必须在包含此修复的新 clean revision 上迁移
  为独立 run，再继续第 8 轮 Proposal。
