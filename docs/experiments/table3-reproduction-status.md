# LIBERO-Pro Table 3 复现状态

更新时间：2026-09-22

## 结论

论文 Table 3 要求对一个 LIBERO-Pro setting 的 10 个 task 计算 success rate，并以 10 个 task 的宏平均作为 `Average`。当前仓库**尚未完成该实验**，因此不能报告论文 Table 3 的 10-task 数值，也不能把 README 中的 90.8% 当成本机结果。

## 当前可核验 artifact

仓库内目前只有少量单 episode 结果：

| task | baseline | Zetta/recovery | 可计分结论 |
|---|---:|---:|---|
| task0 | valid failure（多次） | valid failure（已完成 horizon） | 0/1，仅单 episode |
| task1 | valid success | 未完成 paired recovery | 1/1，仅单 episode |
| task3 | valid failure | valid success（同 seed=21） | paired rescue 1/1，不是 task success rate |
| task7 | valid success（seed=21、22） | 未完成 paired recovery | 2/2，仅单 episode |

这些结果证明了运行链路和 task3 的 episode-level recovery，但没有覆盖 task2、4、5、6、8、9，也没有形成每个 task 的固定多 seed 统计。

## 完成 Table 3 所需的正式证据

1. 恢复可用的 LIBERO-Pro benchmark、Pi0.5 checkpoint 和 runtime 服务。
2. 固定一个 setting 的 task0--task9 及其 10-task 评测协议。
3. 对每个 task 使用相同的预注册 seeds，分别运行 baseline 和 Zetta；只使用 LIBERO 官方 termination 计为成功。
4. 对每个 task 计算 `successes / episodes × 100`，再计算十个 task rate 的 macro-average。
5. 保存每个 episode 的 result JSON、视频、运行配置和聚合脚本输出，才能称为 Table 3 复现。

## 当前阻塞

已确认 benchmark 本体现已位于 `/usr1/home/s125mdg56_02/LIBERO-PRO`，四个正式 suite 各有 10 个 BDDL（共 40 个任务）。同时找到了本机 OpenPI Pi0.5 权重：`/usr1/home/s125mdg56_02/.cache/openpi/openpi-assets/checkpoints/pi05_libero_pytorch`。初次启动失败的根因是误指向 JAX/OCDBT 权重；切换到 PyTorch `model.safetensors`，并将 init-state 加载改为 `weights_only=False` 后，runtime 已能正常启动。

## GPU3-only 重跑（2026-09-22）

此前发现单卡服务误用了 GPU0，已停止该服务及其 batch。随后将服务重启为 `CUDA_VISIBLE_DEVICES=3`，并用 `nvidia-smi` 验证 Pi0.5 进程只出现在 GPU3（约 7.7 GiB）；GPU0/1/2 仅保留桌面或空闲占用。GPU0 上的旧 episode 不计入本轮正式成绩。

GPU3-only 的 Goal-T task0--task9 baseline batch 已重新启动，使用同一 seed=1、官方 300 action + 10 warm-up horizon、官方 termination 计分；每个 task 单独保存 result JSON、trajectory、latency 和视频。batch 完成后再计算 10 个 task rate 的 macro-average，并与 Zetta recovery arm 分开报告。

### GPU3-only baseline 阶段性结果

运行目录前缀：`.local-repro/table3-gpu3-goal-t-task*-seed1-baseline`。10/10 个 episode 均为 `valid`，没有 `infra_invalid`。每个 task 当前只有 1 个 episode，因此 task success rate 是该 episode 的 0%/100%。

| task | official success | task success rate |
|---:|---:|---:|
| 0 | false | 0% |
| 1 | false | 0% |
| 2 | true | 100% |
| 3 | false | 0% |
| 4 | false | 0% |
| 5 | false | 0% |
| 6 | false | 0% |
| 7 | true | 100% |
| 8 | true | 100% |
| 9 | false | 0% |
| **Average (macro over 10 tasks)** | **3/10** | **30.0%** |

这是一轮 GPU3-only、single-seed 的 baseline 阶段性结果，不是论文最终多 seed/Table 3 成绩，也不是 Zetta recovery 的最终成绩。要复现论文中“每 task 取 best result 并计算 Average”的表格，还需要在同一 GPU3 协议下完成 recovery arm 和预注册的多 seed 评测；本表不把 GPU0 运行结果混入。

### GPU3-only paired recovery 证据

在同一 GPU3 runtime 上对 task3 使用冻结的 `.local-repro/liberopro-task3-recovery-bundle.json`（bundle SHA-256 `fb797cf6e18b43f5faa2e2d230e56a423fdb06f6f4dfc8d361257d8d1578b79e`）运行 `active_bundle + Role1 codex`：

- baseline task3：success=false；
- recovery task3：`valid`、`candidate_intervention=true`、official success=true；
- artifact：`.local-repro/table3-gpu3-goal-t-task3-seed1-recovery-v2-result.json`；
- elapsed：117.6 s。

这证明 recovery 在 GPU3 上可以改变 task3 的 episode outcome，但目前只有 task3 的 recovery paired 结果；不能把它外推为完整 10-task recovery 表。

### Observed-best（非最终论文成绩）

若仅汇总当前 GPU3 实际观测到的每个 task 的最好 episode（task0、task3 使用已验证 recovery，其余 task 使用 baseline），则为 `5/10 = 50.0%`：task0、task2、task3、task7、task8 成功。该数字是当前 single-seed observed-best 的下界/阶段性指标，不等价于论文的多 seed method-level success rate；尚未完成的 task-specific recovery 不得被默认为失败或成功。

task0 recovery 的首次重试因 Role1 Codex 30 秒超时而失败；将 `--role1-timeout-s` 提高到 120 秒后，第二次重试得到 `valid + candidate_intervention=true + official success=true`。结果文件为 `.local-repro/table3-gpu3-goal-t-task0-seed1-recovery-v3-result.json`。此前一次 owner crash 产生的完整 trajectory/video/latency 仍不计分。

## Recovery 完整矩阵门禁

不能把 task3 的 `privileged_pick_place` bundle 直接套到其他 task：

| task 类型 | 需要的 recovery primitive | 当前状态 |
|---|---|---|
| 抽屉开合（task0） | drawer-joint interaction | 已验证成功 |
| 取物并放置（task3） | semantic pick-place | 已验证成功 |
| stove 开关 | stove-joint interaction | 尚未有匹配 bundle |
| plate/bottle/cream-cheese 放置 | 对应物体 pick-place / placement | 尚未有逐任务匹配 bundle |

只有 recovery bundle 的 precondition、目标实体和 primitive 与 BDDL 任务语义一致，且官方 termination 成功，才允许更新 observed-best；因此当前 50.0% 不能继续通过“通用 bundle”乐观外推。

## 论文方法矩阵恢复（2026-09-22）

已使用 `scripts/evolution/prepare_liberopro_paper_campaigns.py` 重新生成论文 §4.1 的正式矩阵 dry-run，输出位于 `/tmp/zetta-liberopro-paper-v2`：

- 4 settings × 10 tasks = 40 campaigns；
- 每 task 50 个 development seeds，排除 held-out seeds 1--20；
- held-out 为 test-only，不参与 promotion；
- development 共 2000 slots/round，held-out 共 800 episodes/method；
- 官方 horizon、非空 init states、seed partition 均通过；
- runtime policy 为 `pi05`，latency components 全量开启。

该步骤曾因传入短 Git SHA 被拒，改用完整 revision `c5a56b790bf0d4cb8de954dcd80c7e67929d4574` 后通过。矩阵目前是正式实验的可恢复计划，尚未把未完成 recovery campaign 伪装成 Table 3 成绩。

### 正式矩阵 materialize 与执行前检查（2026-09-23）

在 revision `5b07002c2375f60a57498a6763035c27aff5de89` 上，矩阵已实际写入 `.local-repro/liberopro-paper-v2`，40/40 campaigns 状态均为 `prepared`。`campaign-plan.json` SHA-256 为 `bfa7a321a1a037a7cbcff5d1b22a48f7493306c47eef19135993d35da178f975`。

GPU3-only runtime 已重新启动并通过 gateway health check。随后对 Goal-T/task0 做 development orchestrator dry-run，发现当前主机没有 `loopx` 可执行文件；`run_liberopro_development_batch.py` 在读取 experiment board 时以 `FileNotFoundError: loopx` fail closed。因此正式 episode 尚未入队，held-out seeds 仍未触碰。后续需要恢复 LoopX CLI，或使用下层 `run_campaign.py` 并补齐等价的审计记录，不能静默绕过论文协议中的可追溯性要求。
