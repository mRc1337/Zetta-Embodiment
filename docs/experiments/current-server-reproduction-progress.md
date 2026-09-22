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

## 建议的下一步

在 GPU3 空闲时，使用 `rollout_runtime/config/presets/zetta_libero_pi05.yaml` 的单卡配置，设置标准 LIBERO、Pi0.5 cache 路径、EGL 环境和 `CUDA_VISIBLE_DEVICES=3`，先完成一个短 horizon 的真实 reset/action smoke；通过后再决定是否扩展到完整标准 LIBERO campaign。所有 LLM 请求继续使用 `--role1-planner codex`，不配置 API key。<!-- end -->
