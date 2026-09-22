# 当前服务器端到端复现阶段性记录

更新时间：2026-09-22（Asia/Singapore）

## 结论

当前服务器已经完成 Zetta 的基础运行环境配置，并验证了标准 LIBERO 资产、GPU3 约束和官方 OpenAI/Codex 登录链路。Zetta 的最小演化合约测试通过，但尚未形成可宣称为论文结果的完整正式成功率。

本次使用的是服务器已有的标准 LIBERO 资产，不是此前正式日志中的 LIBERO-Pro 资产。因此当前结果应称为“标准 LIBERO 复现准备和运行时验证”，不能与 LIBERO-Pro 的正式 benchmark 数字混用。

## 已完成

### Conda 与 Python 环境

复用 Conda 环境 `openpi`：

- Python 3.11
- PyTorch 2.7.1+cu126
- MuJoCo 3.4.0
- Zetta editable install
- Ray 2.58.0
- RoboSuite 1.4.1
- BDDL 3.6.0
- OpenAI 3.17.0
- Pydantic-AI 2.46.0
- OpenAI Codex CLI 0.155.1

安装命令：

```bash
conda activate openpi
python -m pip install -e ".[test,ray]"
python -m pip install "robosuite==1.4.1" "bddl>=1.0.1" easydict h5py
```

### GPU 约束

所有运行命令均使用：

```bash
export CUDA_VISIBLE_DEVICES=3
```

验证时 GPU3 为 NVIDIA RTX A5000，约 24 GB 显存；验证时占用约 12 MiB、利用率 0%。GPU1 当时由其他任务占用，本复现未使用 GPU1。

### OpenAI / Codex 登录

服务器上的 Codex CLI 返回：

```text
Logged in using ChatGPT
```

仓库自带 Codex planner 探针通过：

- model: `gpt-5.6-sol`
- provider mode: `default`
- raw stream parse: passed
- persistent thread id: present
- terminal event: present
- elapsed: 6.9 s

因此当前 Zetta LLM 路径可以优先使用已登录的官方 ChatGPT/Codex 账户，不需要配置 `OPENAI_API_KEY`。本次没有发送邮件，也没有触发“只能 API 时暂停”的条件。

### 标准 LIBERO 资产

资产根目录：`/usr1/home/s125mdg56_02/LIBERO`，配置目录：`/usr1/home/s125mdg56_02/.libero`。

在 `LIBERO_CONFIG_PATH=/usr1/home/s125mdg56_02/.libero` 下验证：

| suite | 任务数 | 每任务 init states | task 0 language 示例 |
|---|---:|---:|---|
| `libero_spatial` | 10 | 50 | pick up the black bowl between the plate and the ramekin and place it on the plate |
| `libero_object` | 10 | 50 | pick up the alphabet soup and place it in the basket |
| `libero_goal` | 10 | 50 | open the middle drawer of the cabinet |
| `libero_10` | 10 | 50 | put both the alphabet soup and the tomato sauce in the basket |

PyTorch 2.6+ 加载旧版 init-state 文件时需要显式使用受信任本地文件模式：

```bash
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
```

### 自动化测试

已运行：

```bash
CUDA_VISIBLE_DEVICES=3 python -m pytest -q \
  tests/test_evolution_protocol.py \
  tests/test_evolution_core.py \
  tests/test_libero_eval_horizon.py
```

结果：`32 passed`。

## 尚未完成与风险

1. 当前服务器已有的是标准 LIBERO，而此前正式复现日志使用的是 LIBERO-Pro。标准 LIBERO 可以用于运行时和流程验证，但不能直接作为 LIBERO-Pro 论文结果。
2. 尚未完成 GPU3 上的完整 Pi0.5 policy rollout 和完整 Zetta campaign gate（development、Same-seed、Regression、held-out、Promotion）。
3. Pi0.5 权重位于 OpenPI cache：`/usr1/home/s125mdg56_02/.cache/openpi/openpi-assets/checkpoints/pi05_libero`。还需要将该路径明确映射到标准 LIBERO preset 后再启动 runtime。
4. 任何短 rollout、reset 成功或单 suite 结果都只能作为 smoke/infrastructure evidence，不能写成正式成功率。
5. `.local-repro/` 下的 Codex 原始探针输出已加入 `.gitignore`，其中可能包含 provider 运行细节，不进入公开提交；公开文档只保留摘要。

### 2026-09-22 标准 runtime 烟测

使用 `zetta_libero_pi05.yaml` 的单卡配置，将模型路径指向现有 Pi0.5 cache，并设置 `CUDA_VISIBLE_DEVICES=3`、EGL 和标准 LIBERO 配置。Ray 本地实例可以启动，但约 90 秒内 HTTP 服务端口 `18731` 始终未监听，GPU3 保持约 12 MiB/0%，说明流程卡在 worker/channel 初始化阶段，尚未进入模型加载或环境 reset。该进程随后已停止，未留下运行中的 Ray/runtime 服务。

这次结果记录为 runtime infrastructure smoke failure，不计入策略成功率，也不代表 LIBERO 任务失败。下一次应优先使用更小的 `local`/`inproc` 配置或直接调用 runtime smoke harness，逐步隔离 Ray channel 初始化与 OpenPI backend 初始化问题。

### 2026-09-22 in-process smoke 的进一步定位

将 transport 改为 `inproc` 后，最小 smoke 不再卡在 Ray 初始化。第一次失败是当前环境缺少 OpenPI 要求的 `transformers_replace`；已按 OpenPI 版本要求确认 `transformers==4.53.2` 并把替换模块安装到环境中。第二次 smoke 已进入 Zetta Pi0 backend，但随后失败：

```text
FileNotFoundError: .../pi05_libero/model.safetensors
```

服务器现有 `/usr1/home/s125mdg56_02/.cache/openpi/openpi-assets/checkpoints/pi05_libero` 只包含 OpenPI OCDBT/JAX 参数文件（`params/manifest.ocdbt`、`_METADATA` 等），没有 Zetta 当前 PyTorch backend 所需的 `model.safetensors`。因此当前不能安全启动真实 Pi0.5 rollout；这不是 LIBERO task failure，也不是 LLM/API 问题。需要获得或转换兼容的 PyTorch checkpoint 后，才能继续 GPU3 上的端到端 action smoke。

### 2026-09-22 checkpoint 转换与真实 smoke 通过

OpenPI 自带的 `examples/convert_jax_model_to_pytorch.py` 已将现有 OCDBT checkpoint 转换为 PyTorch 格式：

```text
/usr1/home/s125mdg56_02/.cache/openpi/openpi-assets/checkpoints/pi05_libero_pytorch/model.safetensors
```

转换使用 `CUDA_VISIBLE_DEVICES=3`，没有覆盖原始 checkpoint。补齐对应的 LIBERO `norm_stats.json` 后，继续补装标准 LIBERO worker 所需的 `gym==0.25.2` 和 `matplotlib`。

最终使用标准 LIBERO、in-process transport、单 session、单 policy step 的真实 smoke 结果：

```text
transport=inproc env_family=libero
create_sessions  1 session(s)     74.31 ms
reset                               24242.38 ms
observe                                 0.17 ms
policy_step #1 horizon=[5]        12168.29 ms
run_episode max_steps=1              334.83 ms
close_sessions                         0.11 ms
inference requests=2 responses=2 rejected=0 late=0
total 104723.92 ms
==> OK
```

这证明 GPU3 上的 Zetta runtime、标准 LIBERO reset、Pi0.5 PyTorch inference 和最小 episode 生命周期已经连通。它仍是 infrastructure/action smoke，不是正式 benchmark 成功率，也不等同于 LIBERO-Pro 论文复现。

## 建议的下一步

在 GPU3 空闲时，使用 `rollout_runtime/config/presets/zetta_libero_pi05.yaml` 的单卡配置，设置标准 LIBERO、Pi0.5 cache 路径、EGL 环境和 `CUDA_VISIBLE_DEVICES=3`，先完成一个短 horizon 的真实 reset/action smoke；通过后再决定是否扩展到完整标准 LIBERO campaign。所有 LLM 请求继续使用 `--role1-planner codex`，不配置 API key。<!-- end -->
