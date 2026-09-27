# LIBERO-Pro Table 3 复现状态

更新时间：2026-09-27

## 结论

论文 [Table 3](https://arxiv.org/html/2608.16590) 覆盖 Goal (T)、Goal (S)、LIBERO-10 (T)、LIBERO-10 (S) 四个 setting，共 40 个 task-setting 对。每个 task 的最终 success rate 来自隔离的 seeds 1--20；每组的 `Average` 是该组 10 个 task rate 的宏平均。演化另用每 task 50 个、排除 1--20 的 development seeds。当前仓库**尚未完成该实验**，因此不能报告本机 Table 3 的四组最终数值，也不能把论文或 README 的百分比当成本机结果。

## 早期单 episode artifact（非当前 v6 正式矩阵）

仓库内提交的早期演示只有少量单 episode 结果；本地 `.local-repro/` 的 v6 正式矩阵进度见文末，不应与下表混合计分：

| task | baseline | Zetta/recovery | 可计分结论 |
|---|---:|---:|---|
| task0 | valid failure（多次） | valid failure（已完成 horizon） | 0/1，仅单 episode |
| task1 | valid success | 未完成 paired recovery | 1/1，仅单 episode |
| task3 | valid failure | valid success（同 seed=21） | paired rescue 1/1，不是 task success rate |
| task7 | valid success（seed=21、22） | 未完成 paired recovery | 2/2，仅单 episode |

这些结果证明了运行链路和 task3 的 episode-level recovery，但没有覆盖 task2、4、5、6、8、9，也没有形成每个 task 的固定多 seed 统计。

## 完成 Table 3 所需的正式证据

1. 恢复可用的 LIBERO-Pro benchmark、Pi0.5 checkpoint 和 runtime 服务。
2. 固定四个 setting 各自的 task0--task9 及其 10-task 评测协议。
3. 对每个 task 使用相同的预注册 seeds，分别运行 baseline 和 Zetta；只使用 LIBERO 官方 termination 计为成功。
4. 对每个 task 计算 `successes / episodes × 100`，再分别计算四组各十个 task rate 的 macro-average。
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

GPU3-only runtime 已重新启动并通过 gateway health check。随后对 Goal-T/task0 做 development orchestrator dry-run，发现当前主机没有 `loopx` 可执行文件；`run_liberopro_development_batch.py` 在读取 experiment board 时以 `FileNotFoundError: loopx` fail closed。当时正式 episode 尚未入队，held-out seeds 未触碰。后续需要恢复 LoopX CLI，或使用下层 `run_campaign.py` 并补齐等价的审计记录，不能静默绕过论文协议中的可追溯性要求。

### 正式 development rollout 已启动（2026-09-23）

为继续推进 Zetta 自身产生 recovery 的论文闭环，现已通过同一套底层 campaign state/queue 执行 Goal-T/task0；没有使用 held-out seeds，也没有把人工 bundle 注入该 campaign。LoopX 缺失仍影响 experiment-board attestation，但不再阻止失败样本采集、严格 seed partition 和 campaign ingest。

当前可核验状态：

- campaign：`.local-repro/liberopro-paper-v2/campaigns/goal-t/task-00`；
- queue：44 pending / 0 running / 6 completed / 0 failed；
- ingest：6 accepted / 0 infra-invalid / 0 invalid envelope；
- development seeds：17520、49157、34556、8657、13946、67070；
- 6/6 records 均为 `valid`，当前 official success 为 0/6；
- 6/6 失败均归类为 `horizon_incomplete`；
- 每个 episode 均保存 agentview、wrist、multiview 三路视频及 trajectory、latency、failure segment、visual evidence；
- GPU3 runtime health 正常，执行期间仅该 runtime compute process 占用 GPU3（约 7.7 GiB）。

第一个正式样本位于 `state/attempts/g0000-rollout-000/attempt-000`，其 `bundle_sha256=null`、`candidate_intervention=false`。这是 generation 0 失败收集阶段的预期状态：recovery 应由后续 Cluster → Diagnose → Proposal → Implement → development validation 生成，而不是由 LIBERO-Pro 提供或预先手工指定。

因此，上文 task0/task3 的人工冻结 bundle 结果只作为运行链路 smoke test 和 episode-level 可执行性证据，不属于论文方法生成的正式 Table 3 recovery 成绩。正式 campaign 的下一门槛仍是完成该 task 的 50 个 development rollouts，再由 supervisor 进入聚类和 recovery 生成阶段。

### Goal-T/task0 正式 Zetta recovery 生成（2026-09-24）

Goal-T/task0 的 50/50 development episodes 已全部完成并由 campaign ingest：50/50 `valid`、0 infra-invalid、0 official success，且每条均有 agentview、wrist、multiview 视频。50 个失败片段被聚为一个主簇（prevalence 1.0、mean severity 0.6）。

Stage1 多模态诊断已完成，置信度 0.91。诊断将最早可支持的 divergence 定位到约 step 122--138 的首次把手获取窗口：两条强制检查的 compact trace 中夹爪命令始终为负值/张开，视觉证据也显示夹爪接近下层把手后未形成保持接触，后续拉动无法改变抽屉关节。

Stage2 随后由 Zetta 自动生成 candidate `0f1f42e7da7473ae1efecdece67143447e630aa8f8366dfda1dc2dcb1ac2fa16`，而非人工注入：连续 96 个有效动作仍命令张开且实际 opening > 0.06 时，Critic 拒绝当前动作；Role1 最多一次调用受审计的 `semantic_joint_interact`，目标为 `wooden_cabinet_1/bottom_level`，并设置 160-action cooldown。离线 shadow replay 在 50/50 target failures 上触发，但因为 baseline 无 success controls，按 fail-closed 协议进入在线 same-seed gate，而不是直接 promotion。

same-seed gate 复用已有 50 个 parent rollouts，仅排队 50 个 candidate arms。首个 candidate attempt 暴露两项基础设施问题：

1. 当前 Pydantic-AI 不再接受冻结 manifest 中的裸模型名 `gpt-5.6-sol`。planner provider 边界现将裸 `gpt-*` 规范化为 `openai-chat:gpt-*`，不修改 manifest、candidate 或其内容哈希；相关回归测试通过。
2. 规范化后 provider 成功初始化到凭据检查，但当前 worker 环境没有 `OPENAI_API_KEY`，也没有运行中的 provider broker 或 broker client env。该 attempt 继续被正确记录为 infra-invalid，不计作 candidate failure；外层串行 batch 在首错即停止，49 个 arms 未执行。

当前 gate 保留 50 pending（其中失败 logical arm 的 infrastructure retry 已重新排队）、2 个 infra-invalid attempt 和全部 partial videos。继续在线验证需要恢复正式 OpenAI/provider-broker 凭据；不得用人工动作或无审计的模型替代 Role1 后把结果计入 Table 3。

### Goal-T/task0 Codex Role1 正式闭环结果（2026-09-24）

为避免 API key 阻塞，同时保持正式 Role1 模型与推理强度不变，重新物化了
Codex transport 矩阵
`.local-repro/liberopro-paper-v3-codex-s20260922`。矩阵仍为 4 settings ×
10 tasks，固定代码 revision
`7ef1b91a93d9f6c942435e51d0f140aa7b4c873c`、Role1
`gpt-5.6-sol/high`、master seed `20260922`，且 Goal-T/task0 的 50 个
development seeds 与逐 seed policy RNG 和旧矩阵一致。held-out seeds 1--20
未被读取或执行。

Goal-T/task0 generation 0 baseline 完成 50/50 valid、0 infra-invalid、0 success；
失败均为 `horizon_incomplete`。主失败簇的 Stage1 诊断置信度为 0.88：冻结
Pi0.5 在接触前将任务中的 bottom drawer 错误落地为 middle drawer，约 step 75
开始移动中层关节，而底层关节保持关闭。

Stage2 共自动生成并在线验证两个 Critic--Recovery bundle，均不是人工注入：

| round | candidate SHA-256 | recovery | parent | candidate | causal rescue | gate |
|---:|---|---|---:|---:|---:|---|
| 1 | `a4e972d0f7db0659805e55ea02f40f287ecfd5325c5c9435925efbf3cebcacaa` | bottom-drawer `semantic_joint_interact` | 0/50 | 1/50 | 0 | reject |
| 2 | `b0cfed89214cec931cb7e8fbcb5f2b952174fc6d6127bff479e24b59e92020ad` | extended-contact bottom-drawer `semantic_joint_interact` | 0/50 | 1/50 | 1 | reject |

两轮均完成 50 个配对 seed、0 safety event、0 infra-invalid。冻结 same-seed
门槛为 25/50，因此两个候选均未进入 regression 或 held-out。第二轮唯一成功为
seed `67070`：parent 失败、candidate 成功，candidate attestation 为
`candidate_intervention=true`，Role1 recovery 有 activated/completed 事件，且
candidate/parent action SHA-256 不同；按 `gating.py` 的归因定义，这是 1 次
causally attributed rescue。gate 的失败 rationale 是包含多个条件的通用 `or`
模板；本轮实际失败原因是 1/50 未达到 25/50，而不是没有因果 rescue。

第二轮 decision id 为 `gate-7e8a080395a543be1e2b`。在两轮冻结
same-seed 预算耗尽后，campaign 正常进入 `phase=complete`，没有触碰 held-out。
该结果证明正式 Zetta 演化链能自动生成、触发并产生一次介入救援，但该 recovery
不满足 promotion 阈值，因此不能作为 Table 3 的已提升成功率；完整 Table 3 仍需
继续其余 39 个 task campaign，并按正式协议汇总可 promotion 的方法结果。

### Goal-T/task1 正式 Zetta recovery 结果（2026-09-24）

Goal-T/task1 的任务语言为 `Put the plate on the stove`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、5/50 official success；其余 45 个失败均为
`horizon_incomplete`。主视觉失败簇的 Stage1 诊断置信度为 0.88：失败轨迹在
约 step 59--78 把灰色花纹 bowl 错误落地为目标 plate，而成功对照抓取的是红边白色
plate，因此恢复目标必须保留 plate/stove 的 BDDL 语义，不能把任意容器放上炉灶。

Stage2 在冻结候选预算内产生了两个进入 live same-seed gate 的 bundle；另外两个
候选分别因 shadow success-control false positive 为 2/5 而在离线阶段拒绝，没有
污染在线统计：

| live round | candidate SHA-256 | recovery | paired baseline | candidate | interventions | causal rescue | gate |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `72424679acd1b53c534b7538303ab66acb039bc8824f651319215de192e04f49` | explicit VLA execution prompt | 0/44 | 1/44 | 40 | 0 | reject |
| 2 | `c0ea86024a2e7fe3573cb74c67eb3ea97bc2c02b4340663a672b82d2317e5c91` | wide-aperture semantic `privileged_pick_place` plate→stove | 0/44 | 1/44 | 3 | 0 | reject |

这里的 paired baseline 是从 45 个 baseline failures 中扣除 smoke 使用的 1 个 seed
后冻结得到的 44 对，并复用已有 parent records；不是把 baseline 的 5 个原生成功
算作 recovery 成绩。两轮均为 44/44 valid、0 infra-invalid、0 safety event。
冻结门槛是 22/44。第一轮虽然在 40 个 episode 实际介入，唯一 candidate success
发生在无介入 episode；第二轮 3 次介入也全部失败，其唯一 success 同样没有介入，
因此两轮的 causally attributed rescue 都是 0。

两轮 decision id 分别为 `gate-d09b5e668e450c4e3062` 和
`gate-1f956d788504b74a7295`。第二轮结束后 campaign 进入 `phase=complete`，未进入
regression 或 held-out，held-out seeds 1--20 未触碰。该结果说明 task1 的失败诊断
能够找到正确的对象落地问题，但当前自动生成的 Critic--Recovery 仍未把触发时机与
成功的 plate 抓取/放置闭环对齐；按论文协议必须记为 recovery 未通过，而不能把两个
无介入的 candidate-arm success 宣称为恢复效果。

### Goal-T/task2 正式 Zetta shadow 结果（2026-09-24）

Goal-T/task2 的任务语言为 `put the wine bottle in the bowl`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、22/50 official success；28 个失败形成主视觉簇
`visual-cluster-a39f47278733b390`。

Stage1 诊断置信度为 0.86：代表失败不是抓取失败。两条强制失败样本都成功抓住并
保持 wine bottle，但抓取后沿远离 bowl 的方向持续运输，随后分别在距离目标约
0.371 m 和 0.326 m、`in_target=false` 时释放。成功对照也会短暂绕行，但会在抓取后
约 30 steps 内反向回到 bowl；其中一条失败即使动作执行方向一致性很高仍朝 cabinet
侧移动，因此主因归于 VLA post-grasp transport/release selection，而不是单纯的
OSC/IK action-realization 故障。

Stage2 在冻结 `candidate_round_limit=8` 内自动生成 8 个 Critic--Recovery bundle。
全部候选都在 live 之前被 shadow success-control gate 拒绝；22 个 baseline success
controls 上的 false positives 依次为：

| candidate | false positives | rate | disposition |
|---:|---:|---:|---|
| 000 | 2/22 | 9.09% | shadow reject |
| 001 | 22/22 | 100.00% | shadow reject |
| 002 | 3/22 | 13.64% | shadow reject |
| 003 | 6/22 | 27.27% | shadow reject |
| 004 | 1/22 | 4.55% | shadow reject |
| 005 | 1/22 | 4.55% | shadow reject |
| 006 | 8/22 | 36.36% | shadow reject |
| 007 | 10/22 | 45.45% | shadow reject |

冻结门槛要求 success-control false-positive rate 为 0；因此即使 candidate-004/005
只误触发一个成功样本，也没有放宽门槛或进入 GPU live gate。每次 rejection 都通过
immutable candidate attempt output 写入 append-only audit artifact。候选预算耗尽后
campaign 正常进入 `phase=complete`，optimization outcome 为
`no_candidate_passed_primary_or_secondary`，未执行 same-seed、regression 或 held-out。
该 task 的正式结论是 baseline 22/50，自动 recovery 未通过 shadow specificity gate；
不能把未执行的 recovery 记作失败 episode，也不能声称产生了介入提升。

### Goal-T/task3 正式 Zetta recovery 结果（2026-09-24）

Goal-T/task3 的任务语言为 `Open the top layer of the drawer and put the cream cheese
inside`。generation 0 baseline 完成 50/50 valid、0 infra-invalid、0/50 official
success；50 个失败形成主视觉簇 `visual-cluster-633e826b26f718dd`。

Stage1 诊断置信度为 0.84：Pi0.5 能打开 top drawer，失败发生在随后约
steps 125--140 的 cream-cheese acquisition。一条强制样本在距物体约 0.102 m、尚无
contact 时提前闭合；另一条在约 0.049--0.033 m 形成 gripper contact 并命令闭合，
但 `grasped` 和 `retained` 始终为 false。之后的 open-gripper stall 是未抓住物体的
下游后果，不是抽屉未打开。

Stage2 自动生成并完成两轮 live same-seed gate：

| round | candidate SHA-256 | atomic recovery change | parent | candidate | interventions | causal rescue | gate |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `30280bf22fa3981097ccd1626490844f6cedf8e7c54467085fd6e5461b640341` | semantic cream-cheese→top-drawer pick-place, `grasp_pose_max_steps=32` | 0/49 | 1/49 | 8 | 0 | reject |
| 2 | `5f4a4d7e6b22cfc4a0e8f202e12085f2816c0337fb744f459764a99da7656355` | only extend `grasp_pose_max_steps` from 32 to 64 | 0/49 | 0/49 | 8 | 0 | reject |

两轮均复用 49 个 baseline parent failures，并各完成 49/49 valid candidate arms，
0 infra-invalid、0 safety event。冻结门槛为 25/49。第一轮唯一 success 不是可归因
介入成功；8 次真实介入均未成功。第二轮把最终接触收敛预算翻倍后仍是 8 次介入、
0 success，说明单纯延长 grasp convergence window 没有修复 retention failure。

两轮 decision id 分别为 `gate-f975e5b369ffe34933f6` 和
`gate-92fe75054f8715a2638a`。第二轮结束后 campaign 正常进入 `phase=complete`，没有
进入 regression 或 held-out；held-out seeds 1--20 未触碰。该 task 的正式结论是
baseline 0/50，Zetta 自动生成并真实执行了 recovery，但两轮均无 causal rescue，
因此不得用先前人工 task3 smoke bundle 的单 episode success 替代本次论文协议结果。

### Goal-T/task4 正式 Zetta recovery 结果（2026-09-24）

Goal-T/task4 的任务语言为 `Put the plate on the top of the drawer`。generation 0
baseline 完成 50/50 valid、0 infra-invalid、3/50 official success；47 个失败形成
主视觉簇 `visual-cluster-0b5a9d1cc633b97f`。

Stage1 诊断置信度为 0.84：失败轨迹在接触前把目标 plate 错误落地为灰色花纹 bowl，
随后抓取并把 bowl 搬向 drawer top，而红边白色 plate 保持未动。成功对照会抓取红边
plate，说明环境控制器具备完成任务的能力，主要故障是 VLA referent grounding。

Stage2 在冻结 `candidate_round_limit=8` 内自动生成 8 个 Critic--Recovery bundle。
candidate-003 通过 shadow success-control specificity gate，进入 45 个 baseline failure
组成的 live same-seed gate；其余候选在 shadow 阶段拒绝：

| candidate | shadow success-control false positives | disposition |
|---:|---:|---|
| 000 | 2/3 | shadow reject |
| 001 | 2/3 | shadow reject |
| 002 | 1/3 | shadow reject |
| 003 | 0/3 | live same-seed gate |
| 004 | 3/3 | shadow reject |
| 005 | 1/3 | shadow reject |
| 006 | 3/3 | shadow reject |
| 007 | 2/3 | shadow reject |

candidate-003 SHA-256 为
`8ca8866ea0abd00e27df4d2701893f22381828a665700a68f4364aa49b5878b3`。其 Critic
要求连续 112 个 physical actions 出现 commanded gripper closure、非完全闭合 gripper、
reward 0 且 episode active，Recovery 通过 VLA 执行对比指令：抓取 red-ringed plate，
而不是 patterned bowl，并放到 drawer top。shadow 对 45 个 target failures 没有触发，
因此只以 inconclusive/online-gate-required 进入 live。

live gate 完成 45/45 valid candidate arms、0 infra-invalid、0 safety event；parent 为
0/45，candidate 为 3/45，但 45 条 candidate arms 全部
`candidate_intervention=false`。因此 3 个 candidate wins 都是无介入原生成功，causal
rescue 为 0。正式 decision id 为 `gate-5997b1f722b724cea3fd`，拒绝理由是
`candidate never changed the failed parent action trajectory`，不是成功率门槛不足。

随后 candidate-004--007 均按冻结 false-positive 阈值 0 写入 append-only shadow
rejection，未进入 live。候选预算耗尽后 campaign 进入 `phase=complete`，optimization
outcome 为 `no_candidate_passed_primary_or_secondary`；未执行 regression 或 held-out，
held-out seeds 1--20 未触碰。该 task 的正式结论是 baseline 3/50，当前自动 recovery
未实际介入，因此不能把 candidate arm 的 3 次原生成功解释为恢复效果。

### Goal-T/task5 正式 Zetta recovery 结果（2026-09-25）

Goal-T/task5 的任务语言为 `Push the cream cheese to the front of the stove`。
generation 0 baseline 完成 50/50 valid、0 infra-invalid、0/50 official success；主失败
模式是闭合夹爪后沿低位直线路径搬运 cream-cheese carton，路径穿过 patterned bowl，
导致 carton 或 bowl 被卡住、倾倒或停滞。

Stage1 生成的 Critic 检测连续 3 个 physical actions 中闭合夹爪的主动运输仍未上升：
`command.translation.norm > 0.2`、`command.translation.z <= 0.05`、
`robot.gripper.opening < 0.07`，且 episode 未终止。该 Critic 在所有进入 live gate 的
candidate arms 中稳定介入，因而本 task 的主要剩余问题是 Recovery 的几何执行，而非
检测器漏触发。

Stage2 在冻结的 `candidate_round_limit=8` 内完成全部八个候选。前七轮先验证
vertical-first semantic `privileged_pick_place`，其中 candidate-000--006 只原子改变
`carry_height`；最后一轮按失败证据把 Recovery 机制替换为使用原任务指令和 5-action
chunks 的 authoritative full-task VLA replan：

| candidate | recovery change | same-seed success | regression success | disposition |
|---:|---|---:|---:|---|
| 000 | `carry_height=0.15 m` | 46/50 | 41/50 | regression reject |
| 001 | `carry_height=0.20 m` | 45/50 | 46/50 | regression reject |
| 002 | `carry_height=0.25 m` | 44/50 | 42/50 | regression reject |
| 003 | `carry_height=0.30 m` | 39/50 | 42/50 | regression reject |
| 004 | `carry_height=0.35 m` | 45/50 | 44/50 | regression reject |
| 005 | `carry_height=0.40 m` | 48/50 | 44/50 | regression reject |
| 006 | `carry_height=0.45 m` | 0/50 | not entered | same-seed reject |
| 007 | authoritative full-task VLA replan | 0/50 | not entered | same-seed reject |

same-seed 冻结门槛为 25/50；regression 要求解决全部历史回归种子，即严格 50/50。
candidate-000--005 均通过 same-seed gate，但都未通过 regression gate。candidate-006
证明 `0.45 m` 已越过机械臂稳定可达高度边界；candidate-007 证明重新运行同一 VLA
策略虽然真实介入，却没有改变失败结局。最后两个候选均为 50/50 valid、50/50
intervention、0 infra-invalid、0 success。

candidate-004、005、006、007 的 SHA-256 分别为
`527da88e4ebaaa40e758671055789cabbdd1a79162de10d5c22939bf533f6249`、
`4d050b836e60f7d91d8bb1405f45a710bb54c69a53e2fe3a5d680a93fa318ada`、
`f87080a31394657363004813f3fc91ed393f233d4b4f5da3cec393a4fe41e1da`、
`664e489037b2625871432aa296124c95029c0550cd6da6b9ac63bec324876b57`。
最后一次正式 decision id 为 `gate-64e8cd10934d6117970e`。

候选预算耗尽后 campaign 正常进入 `phase=complete`，optimization outcome 为
`no_candidate_passed_primary_or_secondary`。held-out seeds 1--20 未触碰。该 task 的
正式结论是 baseline 0/50；Zetta 自动构造的 Recovery 能稳定介入并在同种子集产生最高
48/50 causal rescues，但没有候选达到冻结的 50/50 regression 要求，因此不能宣称已
得到可晋级或 held-out 验证通过的 recovery bundle。

### Goal-T/task6 正式 Zetta recovery 结果（2026-09-25）

Goal-T/task6 的任务语言为 `put the wine bottle in the bowl`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、18/50 official success；32 个失败形成主视觉簇
`visual-cluster-a21684d14db787d9`。

Stage1 诊断置信度为 0.79：成功与失败轨迹在初始 approach 阶段没有可辩护差异；最早
支持的分歧约在 steps 55--62，即成功抓取之后。成功对照维持闭爪并把 object-to-target
distance 从约 0.1127 m 降至 0.0080 m；失败轨迹则留在 rack/cabinet 区域，反复开合
夹爪并放弃朝 bowl 的运输。主因因此归于 post-grasp VLA phase-control instability，
而不是初始抓取失败。

Stage2 在冻结 `candidate_round_limit=8` 内自动生成 8 个 Critic--Recovery bundle。
candidate-001 通过 shadow 零误触发门禁并进入 live same-seed；其余候选均在 18 个
baseline success controls 上产生 false positives：

| candidate | target triggered | success-control false positives | disposition |
|---:|---:|---:|---|
| 000 | 31/32 | 6/18 | shadow reject |
| 001 | 17/32 | 0/18 | live same-seed gate |
| 002 | 32/32 | 4/18 | shadow reject |
| 003 | 31/32 | 6/18 | shadow reject |
| 004 | 29/32 | 4/18 | shadow reject |
| 005 | 32/32 | 4/18 | shadow reject |
| 006 | 32/32 | 6/18 | shadow reject |
| 007 | 32/32 | 4/18 | shadow reject |

candidate-001 SHA-256 为
`b7fd3c1252e0dafdae2c6899aa5f55cf158bdcd45247bd4fbce8a89f8d8a4429`。其 Critic
检测 step 100 之后持续 5 个 physical actions 的 moving-open phase abandonment；
Recovery 由 Actor 执行一次 audited semantic `privileged_pick_place`，目标仍是权威的
wine-bottle-to-bowl task。

live same-seed gate 复用 32 个 baseline failures 作为 parent，并完成 32/32 valid
candidate arms、0 infra-invalid、0 safety event。parent 为 0/32，candidate 为 10/32；
正式 causal reducer 记录 19 次 candidate intervention、7 次 successful intervention、
32 条 action-diverged candidate trajectories、7 个 causally attributed rescues，以及
3 个 unattributed candidate wins。这是本轮正式矩阵中明确观测到的“Zetta 介入使原失败
同种子任务成功”的效果，不是无介入的原生成功。

冻结 same-seed 门槛仍要求至少 16/32 overall success。candidate-001 的 10/32 因此
未通过，decision id 为 `gate-cae8cb0d3d994a21eb61`，没有进入 regression 或 held-out。
后续 candidate-002--007 均在 shadow specificity gate 被拒。候选预算耗尽后 campaign
进入 `phase=complete`，optimization outcome 为
`no_candidate_passed_primary_or_secondary`；held-out seeds 1--20 未触碰。

本 campaign 在本地保存 328 个非空 MP4（50 个 baseline episode 和 32 个 live
candidate episode，各 4 个视频 artifact），根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/goal-t/task-06/state/`。
视频、原始轨迹和私有 evidence 不提交 Git；文档只记录 seed-blind 聚合结果。task6 的
正式结论是：recovery 已产生 7 个可归因 rescue，但覆盖不足以达到 promotion 门槛。

### Goal-T/task7 正式 Zetta recovery 结果（2026-09-25）

Goal-T/task7 的任务语言为 `Turn off the stove`。generation 0 baseline 完成 50/50
valid、0 infra-invalid、49/50 official success；唯一失败形成视觉簇
`visual-cluster-33f3380b39fb8702`。

Stage1 诊断置信度为 0.81：失败与成功对照在 sampled step 50 出现最早差异。失败策略
把 gripper request 从 open 切到近全闭合，随后在 steps 74--78 的接触中把 stove
actuate 到可见红色/on 状态，command realization 随后显著下降并持续到 step 310；成功
对照保持 open-contact 操作并约在 step 52 终止。因为只有一个失败样本，该诊断明确标为
episode-level hypothesis，而不是总体规律。

Stage2 共使用 3 个 candidate rounds；冻结 `same_seed_max_rounds=2` 在两轮 live gate
后先于 8 轮总候选预算耗尽：

| candidate | shadow FP | recovery | parent | candidate | interventions | causal rescue | disposition |
|---:|---:|---|---:|---:|---:|---:|---|
| 000 | 14/49 | open-contact retry draft | -- | -- | -- | -- | shadow reject |
| 001 | 0/49 | open gripper 5 steps + gripper-suppressed open-contact VLA retry | 0/1 | 0/1 | 1 | 0 | same-seed reject |
| 002 | 0/49 | authoritative full-task VLA replan through remaining horizon | 0/1 | 1/1 | 0 | 0 | same-seed reject |

candidate-001 和 candidate-002 SHA-256 分别为
`a2b6e6ce211f5983d4a9d3fc8ddce2c46abec3c2ea0a2dcdc9c7c9ab252da3f6` 和
`0bcec081596bbfd12195f552cf7140d9d4603c979abf8708003e49ab2198b964`。
第一轮真实执行了 Critic--Role1--Recovery，action trajectory 发生变化但任务仍失败；
第二轮 candidate arm 虽然成功且 action digest 与 parent 不同，
`candidate_intervention=false`，因此正式 reducer 将其记为 1 个 unattributed win，而不是
recovery rescue。两轮 decision id 分别为 `gate-688d08322d929854a0b0` 和
`gate-9dbc0fab46d225cfef8f`。

candidate-001 的首次 live attempt 暴露一个 Harness runtime 缺陷：首个 action 尚未
产生 `command.realization.stalled` 时，activation predicate 抛出 feature-unavailable，
造成 1 条 infrastructure-invalid。修复使“尚不可观察的 activation feature”按 inactive
处理，同时所有 guards 成立后的 primary feature 仍严格 fail closed；canonical 与
LIBERO runtime 定向/回归集合共 `77 passed`。修复提交为 `1a172ba`，attempt-000 被完整
保留，attempt-001 才是唯一计分 arm。

第二轮后 campaign 以 `same_seed_gate_iteration_budget_exhausted` 进入
`phase=complete`，未进入 regression 或 held-out；held-out seeds 1--20 未触碰。本地
保存 211 个非空 MP4，根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/goal-t/task-07/state/`；其中包括
50 个 baseline、两个有效 live candidate episode 及一个 infrastructure-invalid partial
attempt 的视频 artifacts。正式结论是 baseline 已达 98%，当前 recovery 没有增加可归因
成功。

### Goal-T/task8 正式 Zetta recovery 结果（2026-09-25）

Goal-T/task8 的任务语言为 `Put the wine bottle on the plate`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、21/50 official success；29 个失败中有 26 个进入主视觉
簇 `visual-cluster-31cb56e4ecf611a7`，其余 3 个属于不同失败子模式，没有混入当前
recovery 的因果分母。

Stage1 诊断置信度为 0.73。主子模式是 post-grasp release-phase omission：失败轨迹已把
wine bottle 运到 plate 附近，但 gripper request 维持约 `+0.998` 的闭合状态直到 horizon；
成功对照约在 step 116 打开夹爪，并在 step 120 左右由官方成功条件终止。medoid 另有朝
rack/off-target 运输的次级子模式，因此诊断没有把所有失败都强行归因于同一个空间目标
错误。

Stage2 在冻结 `candidate_round_limit=8` 内生成并审计全部八个候选。candidate-004 是唯一
通过零误触发 shadow gate 并进入 live same-seed 的候选：

| candidate | target triggered | success-control false positives | disposition |
|---:|---:|---:|---|
| 000 | 10/26 | 3/21 | shadow reject |
| 001 | 26/26 | 4/21 | shadow reject |
| 002 | 19/26 | 1/21 | shadow reject |
| 003 | 10/26 | 4/21 | shadow reject |
| 004 | 5/26 | 0/21 | live same-seed gate |
| 005 | 26/26 | 21/21 | shadow reject |
| 006 | 26/26 | 21/21 | shadow reject |
| 007 | 26/26 | 21/21 | shadow reject |

candidate-004 SHA-256 为
`299bb23c4ed3682556e9e86a11503f82bff832b0a2e6529d0462d56d68757181`。其 Critic
检测连续 16 个 physical actions 的闭爪、高 requested translation norm、但 EEF 实际
submillimeter motion；Recovery 只允许一次保持当前位置的 bounded release，最多 20 个
physical actions。

live same-seed gate 复用 26 个主簇 baseline failures 为 parent，并完成 26/26 valid
candidate arms、0 safety event。parent 为 0/26，candidate 为 8/26；正式证据重算得到
6 次 candidate intervention、6 次 successful intervention、26 条 action-diverged
candidate trajectories、6 个 causally attributed rescues，以及 2 个 unattributed
candidate wins。也就是说，这一任务同样明确出现了“Zetta 实际介入后把同一失败种子变为
官方成功”的效果，并非 recovery 没有运行。

冻结 same-seed 门槛要求至少 13/26 overall success，因此 8/26 未通过。decision id 为
`gate-a6d2a9a6d5b0537ce23a`；随后 candidate-005--007 均被 shadow specificity gate
拒绝。候选预算耗尽后 campaign 进入 `phase=complete`，optimization outcome 为
`no_candidate_passed_primary_or_secondary`；未执行 regression 或 held-out，held-out
seeds 1--20 未触碰。

首次 candidate-004 live attempt 还暴露了一个队列路径缺陷：当 campaign root 为相对路径
时，worker 已将 `output_dir` 设为 subprocess cwd，却又把相同相对 artifact 路径传给
rollout，导致结果写入重复嵌套目录。该 attempt 返回 0 但预期位置没有 result，已严格记为
1 条 infrastructure-invalid；修复在 worker 边界将 output/result/heartbeat 路径全部规范为
绝对路径，并对已入队 command 做等值替换，无需修改不可变 queue envelope。相关队列、恢复
与 gate 测试共 `60 passed`，attempt-001 才是该 logical arm 的唯一有效计分结果。

本 campaign 在本地保存 308 个非空 MP4，根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/goal-t/task-08/state/`；包含 50 个
baseline episode、26 个有效 live candidate episode，以及 1 个 infrastructure-invalid
partial attempt 的视频 artifacts。正式结论是：recovery 已产生 6 个严格可归因 rescue，
但覆盖率不足以达到 promotion 门槛。

### Goal-T/task9 正式 Zetta recovery 结果（2026-09-25）

Goal-T/task9 的任务语言为 `Put the cream cheese on the rack`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、0/50 official success；50 个失败全部进入主视觉簇
`visual-cluster-6e44020055e091ce`。

Stage1 诊断置信度为 0.79：失败不是初始抓取问题。代表轨迹均先成功抓取并抬起 cream
cheese，但在约 steps 78--100 进入错误的 post-grasp phase，把物体带到 pickup-side bowl
附近并过早张爪，随后反复进行局部 regrasp/release，直到官方 horizon 耗尽。非零 realized
motion 与 requested direction 高度一致，因此主要 owner 是 VLA target grounding/phase
transition，而不是控制器完全拒绝命令。

冻结 `same_seed_max_rounds=2` 允许了两轮 live recovery：

| candidate | shadow target trigger | recovery mechanism | interventions | candidate success | causal rescue |
|---:|---:|---|---:|---:|---:|
| 000 | 38/50 | 显式 keep-grasped、carry-to-rack、lower、then-open VLA subtask | 35/50 | 0/50 | 0 |
| 001 | 50/50 | 首次过早张爪时以权威完整任务指令重启 VLA | 50/50 | 0/50 | 0 |

candidate-000 和 candidate-001 SHA-256 分别为
`9e10a234899d9e3f161d6e9b249236fd217a9a93afcd3c185fd7ac2c381689ac` 和
`7b55ddcda448ef5e6dd73a1b592864306eeb6b4a7a5b689e935940f873f1d203`。
两轮均完成 50/50 valid candidate arms、0 infra-invalid、0 safety event，且所有 50 条
candidate action trajectories 都与复用的 parent 轨迹不同。也就是说 recovery 确实执行并
改变了行为，但没有一次达到官方 BDDL success；不能把“介入”本身当成 rescue。

两轮 decision id 分别为 `gate-969e542cf3607d3324fb` 和
`gate-60f9f1c06f8328626b54`。第二轮后 campaign 以
`same_seed_gate_iteration_budget_exhausted` 进入 `phase=complete`，没有进入 regression
或 held-out；held-out seeds 1--20 未触碰。本地保存 600 个非空 MP4，根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/goal-t/task-09/state/`，对应 50 个
baseline episode 和两轮各 50 个 live candidate episode 的四类视频 artifact。

### Goal-T setting 阶段汇总（2026-09-25）

Goal-T 的 task0--task9 generation-0 development baseline 已全部完成并达到 campaign
终态；每个 task 均为 50/50 valid，合计 500 个有效 episode、118 个 official success，
即 micro/macro success rate 均为 23.6%（每个 task 样本数相同）：

| task | baseline success | terminal outcome |
|---:|---:|---|
| 0 | 0/50 | same-seed round budget exhausted |
| 1 | 5/50 | same-seed round budget exhausted |
| 2 | 22/50 | no candidate passed primary/secondary gates |
| 3 | 0/50 | same-seed round budget exhausted |
| 4 | 3/50 | no candidate passed primary/secondary gates |
| 5 | 0/50 | same-seed round budget exhausted |
| 6 | 18/50 | no candidate passed primary/secondary gates |
| 7 | 49/50 | same-seed round budget exhausted |
| 8 | 21/50 | no candidate passed primary/secondary gates |
| 9 | 0/50 | same-seed round budget exhausted |

该 setting 已在 task5、task6、task8 的正式 paired gates 中观测到可因果归因的 recovery
rescue，但没有任何候选同时通过其冻结的 primary/secondary promotion 链，因此 Goal-T 尚无
可进入 held-out test 的 promoted bundle。此处是 development-stage 阶段成果，不等于整张
Table 3；LIBERO-10-S、LIBERO-10-O 和 LIBERO-10-L 的正式 10-task campaigns 仍需依次完成。

### LIBERO-10-S/task0 正式 Zetta recovery 结果（2026-09-25）

LIBERO-10-S/task0 的任务语言为
`put both the alphabet soup and the tomato sauce in the basket`。generation 0 baseline
完成 50/50 valid、0 infra-invalid、0/50 official success。49 个可用于配对门控的失败
进入主视觉簇 `visual-cluster-5833e260e427846c`；预留的 smoke seed 不重复计入正式配对。

Stage1 多模态诊断置信度为 0.84。代表轨迹能先把 tomato sauce 放入 basket，官方
predicate progress 达到 0.5，但随后没有形成针对 alphabet soup 的闭爪、接触、抓取或
保持序列，直到 step 530 horizon 耗尽。因此主因归于 VLA 在完成第一个物体后的 compound
instruction 子任务切换/action selection，而不是第一个物体的放置失败。

冻结 `same_seed_max_rounds=2` 允许两轮 live recovery：

| candidate | SHA-256 | recovery mechanism | interventions | candidate success | causal rescue | gate |
|---:|---|---|---:|---:|---:|---|
| 000 | `c0082bee7c6634371e689838b4a5114f2bf9358281f4e9ec354fb511fdde2ee9` | 触发后以 remaining-object VLA instruction 重启第二子任务 | 49/49 | 0/49 | 0 | reject |
| 001 | `263c16523f004adbf71bc67d79e6fb94535c09df801929424fefc653322f5741` | 保留触发器，改用权威完整任务指令并允许 64×5 actions 闭环重规划 | 46/49 | 0/49 | 0 | reject |

两轮均完成 49/49 valid candidate arms、0 infra-invalid、0 safety event。冻结门槛要求至少
25/49 overall success；两轮均为 0/49，因而没有进入 regression 或 held-out。正式
decision id 分别为 `gate-f9aa130006c085e3e596` 和
`gate-ea4d381f5c4b5cb4db69`。第二轮之后 campaign 以
`same_seed_gate_iteration_budget_exhausted` 进入 `phase=complete`，held-out seeds
1--20 未触碰。

这个结果区分了“recovery 实际执行”和“recovery 成功”：两轮共 95 次候选介入，动作被
恢复逻辑接管，但没有一次满足官方 BDDL 目标，因此严格的 causally attributed rescue 为
0。完整任务 prompt 相比 remaining-object prompt 也没有改善成功率，说明失败不能只靠语言
重提示修复；当前 VLA 仍没有形成可执行的 alphabet-soup acquisition/transport/place 闭环。

本 campaign 在本地保存 592 个非空 MP4，根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/libero-10-s/task-00/state/`，覆盖
50 个 baseline episode 与两轮各 49 个 live candidate episode 的 episode/visual-evidence
视频。视频、trajectory 和私有 evidence 不提交 Git；文档仅提交 seed-blind 聚合结果。

### LIBERO-10-S/task1 正式 Zetta recovery 结果（2026-09-26）

LIBERO-10-S/task1 的任务语言为
`put both the cream cheese box and the butter in the basket`。generation 0 baseline 完成
50/50 valid、0 infra-invalid、14/50 official success；36 个失败中，主视觉簇
`visual-cluster-3fdf16d06b702a93` 提供 30 个冻结 same-seed parent failures。Stage1 诊断置信度
为 0.58，结论保持 inconclusive；最强假设是 VLA 的语义目标选择和 compound-task 子任务排序
不稳定，但晚期 grasp retention/containment 失败仍是竞争解释。因诊断未达常规阈值，本 campaign
使用审计的 provisional authorization `provisional-26042719082375a656b3698f`；它仍要求至少
1/30 same-seed 改善、严格因果归因、完整 50-seed regression，且 held-out 不得被当作无偏
结果。

八轮 live 候选的冻结 gate 结果如下；`rescue` 仅计 parent failure、candidate success、动作
轨迹分叉且 intervention attestation 成立的严格因果救援：

| candidate SHA-256 前缀 | same-seed success | causal rescue | regression candidate / parent | regression wins / losses | 结论 |
|---|---:|---:|---:|---:|---|
| `af7cb68d9737` | 9/30 | 5 | 13/50 / 14/50 | 10 / 11 | regression reject |
| `8f799294cb3f` | 9/30 | 4 | 14/50 / 14/50 | 9 / 9 | 未逐个保住历史成功，reject |
| `c92067ef9e7a` | 5/30 | 0 | 未运行 | -- | same-seed reject |
| `adfab473aaa8` | 3/30 | 2 | 13/50 / 14/50 | 9 / 10 | regression reject |
| `ffe956ea915a` | 4/30 | 3 | 13/50 / 14/50 | 9 / 10 | regression reject |
| `dcbbde40db00` | 4/30 | 1 | 8/50 / 14/50 | 4 / 10 | regression reject |
| `63f7eb20d809` | 4/30 | 2 | 10/50 / 14/50 | 5 / 9 | regression reject |
| `01f5ef5ef63c` | 1/30 | 0 | 未运行 | -- | same-seed reject |

对应 gate decision id 依次为：candidate 0
`gate-be01c73392009b9e2615` / `gate-7014ac0735b30b6705c1`，candidate 1
`gate-3efa07507103b08fbe3c` / `gate-5d59acd4da7d2f2db9a6`，candidate 2
`gate-097b18192707e01dab13`，candidate 3 `gate-2df70a2890304f3c1996` /
`gate-f1282064b469c8bc8f8f`，candidate 4 `gate-878036c8eec70b674981` /
`gate-c25131f6ca3a4c0e1dd8`，candidate 5 `gate-5b2ed6d7c143763a4a67` /
`gate-b700fee0de70a5deab83`，candidate 6 `gate-451c09bd272ff28e0e22` /
`gate-fe28d7ceaecabfdf97f8`，candidate 7 `gate-fc69af3c6dba7e469fe1`。

这些结果证明 recovery 确实起作用：六个候选至少产生一次严格因果救援，累计观察到 17 次
causally attributed rescues（各候选同一冻结集合上的结果，不作为互斥 episode 相加成成功率）。
失败点是 promotion specificity，而不是“没有介入”：通过 same-seed 的候选在完整回归中都会
破坏部分 baseline 成功种子；即使 candidate 1 总成功数同为 14/50，也发生 9 wins 和 9 losses，
不能视为保住历史成功。

第八轮后 campaign 以 `same_seed_gate_iteration_budget_exhausted` 进入 `phase=complete`，没有
promoted bundle，也没有执行 held-out；held-out seeds 1--20 始终未触碰。本地保存 2360 个
非空 MP4，根目录为
`.local-repro/liberopro-paper-v3-codex-s20260922/campaigns/libero-10-s/task-01/state/`，覆盖 baseline、
八轮 same-seed 和六轮 regression 的 episode/visual-evidence artifacts。视频、trajectory、
privileged evidence 与 provider/worker 日志均不提交 Git；文档只记录聚合、seed-blind 结果。

### LIBERO-10-S/task2 正式 Zetta recovery 阶段结果（2026-09-27）

任务语言为 `turn on the stove and put the moka pot on it`。generation 0 baseline
完成 50/50 valid，official success 为 0/50。主要失败模式是炉灶已开启，但 VLA 未稳定取得并
搬运 moka pot。Stage1 对 post-stove grasp grounding/contact verification failure 的诊断
置信度为 0.78。当前 recovery 由 proposal-only critic 检测早期空抓后交给在线 Role1 调用有界
`privileged_pick_place`；官方 LIBERO termination 是唯一成功判据。

| candidate SHA-256 前缀 | 机制 | same-seed candidate / parent | 严格因果救援 | regression candidate / parent | 判定 |
|---|---|---:|---:|---:|---|
| `934f0a3b9a55` | 原始语义 pick-place | 37/49 / 0/49 | 37/37 | 41/50 / 0/50 | regression reject |
| `76f6e9c026f8` | 仅设 `vertical_first_carry=true` | 41/49 / 0/49 | 41/41 | 3/4 observed / 0/50 parent；46 未执行 | regression early reject |
| `d10b51cf69c8` | 保留 vertical-first，仅将 `grasp_confirm_steps` 从 4 增至 8 | 37/49 / 0/49 | 37/37 | 4/5 observed / 0/50 parent；45 未执行 | regression early reject |
| `62a611fae41d` | 保留 recovery，将空抓 critic 的 dwell 从 4 降至 1 | 仅部分完成 | 不可判定 | 未运行 | 因 runtime seed 缺陷终止；不计正式 paired 结果 |

第一候选的 same-seed decision 为 `gate-c7443f46a27e9d5b1bb3`；其 regression decision
为 `gate-3788dcdb7ee6f3e7610e`。虽然第一候选在 50 个开发种子中救援 41 次、无安全事件，
冻结的 regression 规则要求解决全部历史失败种子，故不能提升。第二候选的 same-seed
decision 为 `gate-46dcc4abb1ee17233390`：41/49 成功，高于冻结门槛 25/49，41 次成功均
有 intervention attestation、parent failure 和动作分叉证据，安全事件为 0。

第二候选运行中曾有 4 次 infrastructure-invalid attempt，其中 3 次和一个中断 lease 的
部分结果对应 Codex Role1 请求返回 401 Unauthorized。这些尝试没有进入策略分母；凭据恢复
经同模型最小调用验证后，supervisor 回收 lease、接纳 4 条失败审计记录，并在原定两次
infrastructure attempt 预算内补发 4 个 attempt-1 job。重试后 49/49 candidate arms 均取得
有效结果，未改动 seed、bundle 或门限。随后进入 `regression_gate`，50 个开发种子
candidate jobs 曾入队；held-out seeds 1--20 尚未使用。本地 trajectory、视频和 Role1 日志仍
保留在忽略的 campaign 目录中，不提交 Git。

第二候选 regression 在前 4 个有效 candidate arms 中取得 3 成功、1 失败；失败一旦出现，
冻结的 `all_historical_rollouts_must_succeed` 规则已不可能通过。supervisor 写入正式提前
拒绝 decision `gate-9af229d2e64d79ef195e`，并回到 `propose`。剩余 46 个未执行的旧
regression job 已原样归档到本地 queue 的 `cancelled/local/`，避免污染后续候选；因此上表的
3/4 observed 不是完整 50-seed 成功率，也不作为 Table 3 结果。第三候选 SHA
`d10b51cf69c8587c75dd9c7ee9e4d84be7714557a072b9293e3c54e65bcb0480` 已生成，
49 个同种子 candidate jobs 已入队，49 个 parent arms 复用冻结 baseline 证据。当前实际
phase 已转为 `same_seed_gate`。

协议复核（2026-09-27）：论文 2.6.2 节的 Historical Regression 是对**来源失败簇
`K_i`** 的每个 seed 要求 100% 成功，不是无条件对全部开发 seed 要求 100%。现有 v3
campaign 的冻结 manifest 没有 `regression_scope` 字段，继续保留原先 `all_development`
行为，故 task-02 仍按 50 个开发 seed 判定，不能事后改写门限或重释其 decision。
代码新增可显式预注册的 `target_cluster` 模式，从已冻结 same-seed plan 取得簇内 seed；
新 `EvolutionProtocol` 默认使用此论文一致模式。本任务主簇包含 49/50 个开发失败，
另 1 个失败在次簇。此前两轮候选的拒绝结果不因本次代码修改而改变；后续新 campaign
若采用按簇回归，必须重新预注册并独立报告，不能与 v3 的 50-seed regression 混算。

第三候选同种子 gate 已正式通过（decision `gate-49d53e84ce1f4cb67f27`）：49/49
candidate arms 有效，37 次成功均满足严格因果归因，parent 0/49，安全事件 0。
随后冻结 50-seed regression 的前 5 个 candidate arms 全部有效，4 成功、1 失败；
失败对应的 candidate 未触发 critic、无闭合夹爪命令、未抓起 moka pot。按冻结的 50/50
规则，supervisor 以 `gate-adec1220c8b84cc12e9b` 提前拒绝，余下 45 个未执行 job 已
原样归档到本地 `queue/cancelled/local/`；held-out seeds 1--20 仍未使用。代码据此修正
Stage2 refinement：当 regression 失败样本没有 intervention 时，下一候选须改进 critic
覆盖，而不能强制仅修改 recovery。该判断只使用正式 regression plan 与有效 episode
ledger；相关 70 项测试通过。第四候选 `62a611fae41d...` 已进入同种子 gate，其 dwell=1
假设针对短暂空抓，但不能确定覆盖上述完全无闭合命令的反例，仍须按正式 gate 验证。

协议有效性复核（2026-09-27）：v3 的 OpenPi runtime 实际忽略了 harness 传入的逐次
`policy_rng` seed。同一 development seed 92471 的第三候选 same-seed 与 regression arm
具有相同初始观测、相同 policy_rng 和相同 bundle，但第 11 步首次 VLA 动作已经不同
（最大绝对差 0.03085）；前者触发介入并成功，后者没有触发介入且失败。因此 v3 的
“same-seed”及严格因果归因仅是旧 harness 的名义判定，不能作为可信配对反事实或
Table 3 成绩。第四候选未完成的 44 个 job 已可恢复地归档，v3 campaign 标记为
`runtime_policy_seed_not_applied`，held-out seeds 1--20 未触碰。

现已在 `rlinf_policy` 后端将每次推理 seed 作用于 OpenPi 的 torch 噪声采样，并隔离
同批其他请求的随机状态；单元测试和 GPU3 在线复测均通过。在线复测在同一环境观测
上依次使用 seed A、seed B、seed A：两次 A 的完整 `(5, 7)` 动作块 SHA-256 完全
一致，B 不同。接下来必须在全新 campaign 中重跑 baseline、same-seed、按来源失败簇
的 historical regression，最后才可使用预留 held-out seeds；v3 的 401 重试虽已恢复
有效运行，却不能修复上述随机种子缺陷。

新一轮重跑已经启动：`094d9532a9e2e1448a10b70882a397abd32a7dee` 代码版本的
`liberopro-paper-v4-libero-10-s-t02-replay` campaign，复用 v3 冻结的 50/20 seed
划分，但重新生成 baseline 证据；`regression_scope=target_cluster`，held-out 仍为
`test` 模式。首个 baseline（development seed 16101）已完成，episode `valid`、
official success=false，视频和轨迹保存在本地新 campaign 的 `state/attempts/` 下。
其余 baseline 正由 GPU3 单 worker 执行，尚无可报告的 recovery 或 Table 3 成绩。
同级 `task-02` 是一次未执行的预注册草稿，code_commit 写错；正式重跑目录仅为
`task-02-replay`，该草稿不得计分。

完整范围也已重新预注册在本地
`.local-repro/liberopro-paper-v4-matrix-20260927/`：4 settings × 10 tasks = 40 个
独立 campaign，合计每轮 2,000 个 development rollout slots，并为各 task 单独预留
20 个 held-out seeds。矩阵审计确认 40 个 task 都有初始状态、使用官方 horizon、
development 与 held-out 分区互斥、回归范围为 `target_cluster`。该矩阵 task2 的
development schedule 与上述旧 seed 配对重跑不同，二者不能合并统计；目前矩阵只是
预注册，还没有 40-task outcome。

40 个 campaign 的 generation-0 state 已初始化，严格按每 task 50 个 development
seeds 向共享队列写入 2,000 个 baseline jobs；目前该矩阵队列尚未启动 GPU worker，
因此入队数不能算已运行或已成功的 episode。GPU3 仍由 task2 旧 schedule 的配对重跑
独占。该 task2 campaign 的 supervisor 和 worker 均保持运行；截至本次检查已有
5 个有效 baseline、0 个基础设施失败。还使用冻结的 `gpt-5.6-sol` 模型做最小
Codex 调用，确认当前凭据能返回有效响应；这只验证了认证链路，不能保证后续
Role1 介入成功。

新增只读、fail-closed 的 Table 3 汇总器：
`python -m scripts.evolution.report_liberopro_table3 --matrix-root <matrix-root>`。
它仅在 40 个 campaign 均终止、每 task 有 20 对有效 held-out arms、parent 确为
pure VLA、官方成功记录与 gate decision 一致，且视频/延迟证据齐备时才输出
4-setting × 10-task success rate 和宏平均。当前矩阵返回 `status=incomplete`、
`completed_tasks=0`，不会把 2,000 个排队 job 或 development 结果写成 Table 3
成绩。该首版汇总器只接受 generation-0 直接对 pure VLA 的 held-out；若以后形成
跨 generation 的累计 harness，须先为最终 harness 与 pure VLA 做同一 20-seed 的
独立配对评测，再扩展汇总器，不能把上一代 harness 误标为 pure VLA。

协议边界：论文 §4.1 描述在最大失败簇的 development seeds 上迭代至成功率至少
50%，但本地 preregistration 对连续 same-seed gate 失败设置了 2 轮上限。若
campaign 因此提前结束，属于本地预算受限的未完成复现，不能当作论文 Table 3
的 final harness 结果。

矩阵执行已启动：第二个 GPU3 worker 使用同一 runtime、单并发处理 40-task 队列，
配套 round-robin supervisor 使 40 个 campaign 各自入库和推进门禁。试运行期间
两个 worker 同时运行不同 task 时，GPU3 显存保持约 14.1/24.6 GiB，首个矩阵
baseline 为 valid，task2 replay 也继续推进。随后发现同一个
`libero_10_swap/task2` 被两个 campaign 同时请求时，该 EnvSpec 仅声明 1 个 pool
slot，矩阵 task2 的 attempt-0 因 `QUOTA_EXCEEDED` 成为 infrastructure-invalid；
该记录不进入策略成功率分母。没有修改已冻结的 runtime/rollout 协议。

为避免同一任务再争用池，矩阵 task2 尚未执行的 50 个队列 job 已可恢复地移到
`queue/pending/paused_task2/`；其余 39 个 task 继续运行。矩阵 supervisor 会在
独立 task2 replay campaign 达到终态后，验证暂停目录仅含该 task 的 job，再将
它们原样放回 GPU3 队列。此时已有 6 个有效矩阵 baseline、1 个基础设施失败
attempt；独立 task2 replay 为 24 个有效 baseline、0 个基础设施失败。

后续基础设施复核（2026-09-27）：独立 task2 replay 的 generation-0 baseline
已完成 50/50 valid、official success 0/50，进入最大失败簇的 Stage1 诊断，随后
转入候选提案；这些 development 结果仍不是 Table 3 held-out 成绩。矩阵的
`libero_goal_task` task7、8、9 首次 baseline reset 曾连续返回
`ENV_FAILURE: Connection reset by peer`，runtime 侧记录 MuJoCo EGL
`Offscreen framebuffer is not complete (0x8cdd)`。这 3 条是
infrastructure-invalid，不进入成功率分母；其 attempt-1 已由 supervisor 排队，
但当时没有继续消耗重试预算。矩阵 worker 和 supervisor 曾有序暂停，runtime
按原配置重启后，非计分的 task7、8、9 create/reset/close 检查均返回 `Ok`。
随后恢复了矩阵单并发 worker 和 round-robin supervisor；恢复检查时矩阵共有
39 个已完成、4 个失败 attempt，1 个运行中，`paused_task2/` 仍隔离 50 个
task2 job。继续观察 EGL 稳定性和正式 attempt-1 结果；在 40-task held-out
配对完成并通过汇总器前，不报告 Table 3 成绩。

同日后续进度：独立 task2 replay 的 Stage1 诊断和 Stage2 提案已结束，候选 bundle
SHA-256 为 `64a219cdb9334275155437f1ea67e637bbba23b759e0bf9205d96232d6f0ee4d`。
其 same-seed plan 冻结 50 对，50 个 parent arms 已由本轮有效 pure-VLA baseline
证据接入，50 个 candidate arms 已入队。首个 candidate 与矩阵 baseline 均持续
产生 rollout 心跳；截至该检查尚无 candidate 终态，不能声称 recovery 成功或
same-seed gate 通过。主机磁盘 I/O 等待偏高，但运行时健康且未新增 401 或失败
attempt，保留原进程与队列继续执行。

同日 I/O 事故与基础设施修复：共享 `/usr1` 磁盘持续高 I/O wait；原 rollout 每条
latency event、每行最终轨迹都执行 `fsync`。矩阵 task4 和 task5 的 baseline 已完成
动作与视频生成，却在后处理落盘阶段超过冻结的 240 秒 no-progress 窗口，被
`episode_no_progress_timeout` 记为 infrastructure-invalid。独立 task2 replay 的
首个 candidate 在第 114 步触发 Role1，并接受冻结 recovery 提案，实际执行
`vla_execute` 320 步；其 episode 仍因同样的后处理 watchdog 超时无效，**不能**
计为救援成功。被终止的 runtime session 暂时占满 1-slot 环境池，随后的 13 个
candidate attempt-0 立即因 `QUOTA_EXCEEDED` 无效；这些均不进入策略分母。

为阻止级联，矩阵和独立 task2 的 supervisor 已停止；矩阵约 1,910 个待运行 job、
task2 约 43 个待运行 job 原样移入各自 `queue/pending/paused_io/`，没有删除或
重排 seed。两个 worker 在已有作业终止、running claims 清零后退出。非计分
task2 create/reset/close 复核全部返回 `Ok`，runtime 不需重启。基础设施补丁
将 latency event 的 durability barrier 延至 episode finalize，将完整轨迹按批
写入并同步，并让 watchdog 识别同一 attempt 目录下视频、轨迹、visual evidence
的实际文件更新；它不改 VLA、recovery、随机种子、冻结 plan 或评分门限。
81 项相关测试通过，补丁应用前的正式结果仍留存以供审计。

基础设施修订代码提交为 `0ed1fd3`，与 campaign manifest 原始
`code_commit=094d953...` 明确区分。补丁后先单独放行矩阵 `goal-s/task-00`
的一条 fresh baseline：117 秒完成，
`status=valid`、official success=false、三路 MP4 非空、watchdog 无误报。该
作业只证明基础设施修复对短 horizon 有效；随后长 horizon 的 task4
attempt-1 也在 154 秒内完成，`status=valid`、official success=false、
三路 MP4 非空、watchdog 无误报。task2 环境池非计分 create/reset/close
复核通过，14 条 infrastructure-invalid attempt 已由幂等 supervisor 接纳；
其原预算内的 attempt-1 均已排队，只有 p000 candidate 的 attempt-1 被单独
放行验证，其余仍隔离。该 p000 attempt-1 在 145 秒内取得 `status=valid`、
三路 MP4 非空，Role1 在环境第 114 步接受冻结 recovery 并执行 320 步
`vla_execute`；official success 仍为 false。因此它是一次实际介入但未救援的
有效负样本，不是恢复成功。此处为冻结 campaign 启动后的基础设施实施修订；不能把之前
infra-invalid 的 attempt 追认成 valid，也不能在未完成 40-task held-out 前
汇报 Table 3 成绩。

矩阵继续执行时，旧 task5 watchdog 超时留下的同任务 env session 尚未释放；
task5 下一条 baseline attempt-0 因 `QUOTA_EXCEEDED` 基础设施无效。已将该
任务 49 个待运行 job 原样隔离在 `queue/pending/paused_task5/`，并给矩阵
controller 增加可显式指定、经过 task 名校验的 `--pause-task`，使 sweep 暂停
task5 而继续处理其他 campaign；相关 3 项测试通过。矩阵 task2 原有 50 个
job 仍在 `paused_task2/`，待独立 replay 结束后才释放。恢复 task5 前须先做
同 EnvSpec 的非计分 reset 检查或安全重启 runtime，不得直接耗掉其 attempt-1。
随后 task5 同 EnvSpec 的非计分 create/reset/close 均返回 `Ok`；旧 controller
在休眠时退出且无残留锁，49 个隔离 job 原样回到 GPU3 待运行队列，controller
恢复原调度配置。此操作只恢复基础设施可用性，不改任何 task5 seed、bundle
或判定门限。

### Runtime VLA recovery 指令未转发：v4 候选结果隔离（2026-09-27）

复核 v4 task2 的首批有效 candidate 时，6 条 episode 均在第 114 步触发
Role1、选择 `vla_execute` 并执行 320 个动作，官方成功为 0/6；离线真值中
炉灶目标已满足，但 moka pot 从未被抓起。进一步沿调用链检查发现：
`LiberoPrimitives._vlm_chunk` 把 recovery prompt 写入 `task_descriptions`，
而 `LiberoRuntimeVLAClient.predict_action_batch` 随后丢弃整个调用方观测，
没有把这条指令作为 `PolicyRequest.instruction_override` 送入 runtime。
因此这些有效的仿真轨迹**并未执行预注册 bundle 所指定的 VLA 恢复提示词**；
不能据其 0/6 推断该 recovery 策略无效，也不能用于同种子 gate 或 Table 3。

修复将单环境 `task_descriptions` 原样作为 per-request instruction override
传递；runtime backend 已支持此字段。适配器/后端相关 30 项测试通过，其中新增
回归测试断言 recovery 指令确实出现在 `policy_infer` 请求中。旧 v4 task2
worker、supervisor 和 v4 40-task matrix controller/worker 已停止，保留所有
append-only 证据、失败尝试和冻结 manifest；停止时在途子进程允许完成落盘，
但旧队列不再作为正式策略判定继续推进。下一轮须用新代码版本重新预注册并
重跑；旧 v3 的 401 重试仍保留历史审计记录，但 v3 随机种子缺陷和本次 v4
prompt plumbing 缺陷均不能靠重释旧结果修复。

修复提交 `eeb870af335debdc48e48a3a4d861aebffe9a145` 已推送；扩展测试集合
95 项通过。用同一非计分 LIBERO-Pro task2 reset 观测、固定 policy seed 做
`原指令 → moka 恢复指令 → 原指令` 三次在线推理：两次原指令动作块 SHA-256
相同，恢复指令动作块不同；会话已正常关闭。这验证了新的端到端指令通道，
但不是正式 rollout 成绩。

据此新建 `liberopro-paper-v5-matrix-20260927`：40/40 manifest 的
`code_commit` 固定为上述修复提交，沿用 v4 的 40 任务、全部 50 个开发种子、
20 个留出种子及逐种子 policy RNG（逐项比对相同），不导入任何旧 episode。
40 个 campaign 已初始化；GPU3 单 worker 开始执行全新 generation-0
pure-VLA baseline。旧 v4 矩阵和旧 task2 replay 均停止作为正式结果来源，
其本地目录仅作审计。新矩阵仍须完成完整 Zetta 演化、同种子与历史回归、
全部 held-out 测试及报告器核验，当前没有 Table 3 数值可报告。

v5 尚处于 generation-0 baseline 入队/首批执行时，复核发现其单簇
`same_seed_max_rounds=2` 与论文“在最大失败簇的错误开发种子上迭代至至少
50% 成功”的规则存在提前终止风险；v5 controller/worker 已停止，已经完成的
少量 baseline 仍保留为探索性证据，未混入下一轮。矩阵准备器现把同种子、
单簇和总候选轮数统一冻结为显式的本地 15 轮安全上限；若达到上限却未达到
论文门槛，必须报告“预算耗尽、复现未完成”，不能报告 Table 3 成绩。
矩阵 controller 也改为沿已验证的 generation continuation 继续调度
promoted child campaign，而非把一个完成的父代误算成整项任务终态。

另用 development seed 22035 对 v4 的旧 prompt-only bundle 做了**非计分**
回放，唯一行为差异是修复后的提示词转发。回放 `status=valid`、官方成功=false：
介入在第 114 步触发并执行 320 步；与旧轨迹的动作首次分叉在第 115 步，
恢复区间到 moka pot 的最短 EEF 距离由约 0.244 m 降至约 0.206 m，但仍没有
gripper contact 或 grasp，BDDL 满足目标仍为 1/2。三路 MP4 已留在
`.local-repro/non-scored-prompt-fix-smoke-20260927/task2-seed22035/videos/`。
这证明提示词现在确实改变动作，同时也只说明这个单种子 prompt-only 救援
仍失败；正式是否采用新的语义抓取恢复须由新 campaign 的完整门禁判定。

预算与跨代调度修订提交 `b04bd20673f9467f5e26b3d0c8d8db9e3aa6c8cf`
已推送，97 项相关测试通过。全新正式候选矩阵为
`.local-repro/liberopro-paper-v6-matrix-20260927/`：40 个任务全部重新预注册，
50 个 development / 20 个 held-out seeds、逐种子 policy RNG 与 v5 完全一致；
显式候选预算为 15 轮，同种子和历史回归门禁不变，held-out 仍为只报告的
`test` 模式。40 个 campaign 已初始化，GPU3 单 worker 与跨代 round-robin
controller 已开始新的 generation-0 baseline。v5 仅留下 3 条已完成的
探索性 baseline 和未消费的队列记录，不作为 v6 分母。v6 尚无可报告的
Table 3 held-out 成绩。

汇总器复核：旧 `report_liberopro_table3.py` 只接受 generation 0 的一条
held-out gate；即使矩阵跨代 promotion 成功，也会误报为不完整或只显示早期
候选。现改为沿不可变 generation continuation 核验代际链，使用第 0 代
held-out parent arm 作为 pure-VLA 对照、最后一次 promotion 的 held-out
candidate arm 作为最终 Zetta harness，并校验同一 1--20 seeds 的 policy RNG、
manifest/交接 digest、40 条有效 arm、视频、延迟摘要与 gate decision。
两次晋升的回归测试确认只取最终候选；当前 v6 仍运行时，汇总器严格返回
`incomplete`（0/40），不产生虚假的 Table 3 平均值。若某任务从未晋升且
没有纯 VLA held-out 测试，汇总器仍会拒绝报告，需补齐真实最终测试证据。

无晋升任务的最终测试边界现已补齐：`run_liberopro_final_pure_vla.py`
只在全部 40 个演化 campaign 达到终态后，才为未晋升的任务创建独立的
`final-pure-vla/` 测试 campaign。它只调度原先冻结的 1–20 seeds 及同一
policy RNG 的纯 VLA rollout；不运行聚类、Role1/Role2 提案或晋升，因此
测试反馈不会进入策略优化。若候选跑过 held-out gate 却未晋升，最终 harness
仍是纯 VLA，不能把该候选的测试 arm 误报为 Zetta 成绩。汇总器要求
20 条有效 episode、非空视频与延迟摘要，并在这种情形下将 baseline 与
Zetta 都记为纯 VLA 的实测成功数；若证据缺失则继续返回 `incomplete`。
当前 v6 尚有 40 个未终态任务，该路径的只读前置检查返回
`waiting_for_evolution`，未消费任何 held-out seed。全部演化完成后用
`python -m scripts.evolution.run_liberopro_final_pure_vla --matrix-root .local-repro/liberopro-paper-v6-matrix-20260927`
启动或重复运行该可恢复的最终测试路径，并继续让 GPU3 queue worker
处理新增 rollout。加 `--watch --poll-s 300` 可持续等待 40 个任务终态，
随后自动排队、收集至全部无晋升任务的 20 个有效最终测试完成；如基础设施
重试预算耗尽，会以非零状态退出并列出受阻任务，不会默默丢掉分母。

GPU3 并行试运行（2026-09-27）：v6 原单 worker 已完成 13 条有效 baseline，
0 条 queue failure。检查 queue 的主机级领取锁和 runtime 的 4-session 上限后，
启动第二个 `--once` worker；它与原 worker 同时处理不同的 task，试跑任务
`libero_10_swap/task4` 约 164 秒有效结束，原 worker 同期的 task3/task5
也有效结束，runtime `/healthz` 正常，GPU3 显存未增长，未见 infra-invalid。
据此继续用两个独立 `--concurrency 1` 的 GPU3 worker 处理同一冻结队列；
增加的是执行并行度，未改 manifest、种子、policy RNG、任务目标或 gate。
如后续超时/失败率上升，应撤回第二 worker 并按原 logical ID 重试基础设施
attempt，不能改用失败任务的其他种子代替。

继续并行验证：在双 worker 累计 27 条有效、0 条失败后，第三个 `--once`
worker 与原两条重叠执行 `libero_10_task/task9`，约 181 秒有效结束；同期
task7/task8 也有效结束，累计 30 条有效、0 条 queue failure，runtime
健康且 GPU3 显存仅小幅波动。现以 3 个独立 `--concurrency 1` worker
常驻同一 GPU3 queue；这只是调度并行度调整，不扩展 runtime 的 4-session
硬上限，也不修改任何 campaign manifest 或测试种子。后续继续监控长时间
infra-invalid、401、心跳与显存，一旦恶化先撤回新增 worker。

三并发长跑撤回：随后 Goal-S task6–9 的各一条初次 attempt 在 runtime
reset 阶段遇到 `ENV_FAILURE: [Errno 104] Connection reset by peer`，
4 条均为 `infra_invalid`，不是环境任务失败或 401，不计入成功率。故撤回
第三 worker，回到两个持续运行的 worker；同一时段之后的 Goal-T task0–2
已再次有效完成，表明 runtime 仍可服务。第三 worker 退出时遗留的
Goal-S task5 子进程随后写出 `status=valid` 的完整 result；核对其父
worker 已退出、claim 心跳约 97 秒而活 worker 只有 14–23 秒后，使用
queue 的 `recover_abandoned(stale_after_s=60)` 只回收该 claim，终态记录
`commit_source=recovery`、`recovery_reason=published_result_file_after_worker_crash`。
不删除失败 attempt，也不换种子；由 controller 对 4 个原 logical ID
按冻结的 max=2 基础设施尝试预算重新排队。鉴于本机 `local` runtime
在三并发下的这次异常，后续固定双 worker，不再以短时吞吐通过作为稳定
并发的充分证据。
后续核验：控制器已将 task6–9 的失败 attempt 写入 append-only ledger，
并为 4 个原 logical ID 排入 `attempt_index=1`；逐项核对 seed 与 policy RNG
均和初次 attempt 一致。恢复提交的 task5 有效 episode 也已入账。
截至同日后续巡检，v6 前 52 条完成的 rollout 均为 `status=valid`，逐条
核对其 seed/policy RNG、纯 VLA bundle 标记、非空视频文件与延迟摘要，
证据缺口为 0；这只是 development 证据完整性检查，不是 held-out 成绩。
队列分母审计：对 v6 全部 `pending/running/completed/failed` envelope 与 40 个
冻结 manifest 逐一比对，预期的 2,000 个 development logical ID 全部存在，
无额外 ID、无缺失、无不连续 attempt 链；当前 2,004 个 attempt job 恰为
2,000 个初次 attempt 加 4 个同 ID 基础设施重试。该检查只确认调度完整性，
不代表 2,000 条均已有效完成。
纯 VLA 对照审计：前 64 条已完成 development episode 的
`tool_events.jsonl` 均无事件，`safety_events` 也为空；结合前述无
bundle 的记录，确认这些 baseline episode 没有被 recovery 工具或
Critic 介入污染。此结论仅覆盖已完成的 64 条，后续仍需持续核验。
运行量级估算：截至 2026-09-27 11:29 UTC，已完成 67 条有效 rollout；
从首条完成至该时约 90 分钟，观察吞吐约 44 条/小时。若此速率保持，
剩余 development 的约 1,933 条需约 44 小时；这不包括后续诊断、
候选验证、跨代 rollout 和正式 1–20 留出测试，也不是停止预算或成绩预测。

跨代晋升框架修复（`17b1944e1b724f18f722b771f7809ce1d8014d6b`）：
`heldout_mode=test` 的判定层已把 1–20 留出集限定为只报告、不参与候选选择，
但旧跨代恢复函数错误地再次要求 held-out decision 的 `passed=true`。
这样即使候选通过同种子/回归开发门禁并被合法晋升，只要最终测试统计
未达显著性，下一代创建就会卡住。修复后跨代恢复仅要求 test-mode 的
held-out 决定已记录；validation-mode 仍须 `passed=true`。新增回归测试
覆盖失败 held-out 决定下的晋升、子代创建与幂等恢复，57 项相关测试通过。
v6 manifest 仍保留最初预注册的 `code_commit=b04bd206...`；这是对演化
控制器的协议实现热修复，未改变候选代码、50/20 种子、policy RNG 或任何
已生成的 rollout/gate 证据。仅在控制器处于轮询睡眠时停止旧进程并以
修复代码恢复；GPU3 runtime 与两个 queue worker 均未重启，已有 ledger
继续沿原 logical ID 累积。

Goal-S task6–9 的第二条不同 seed 的首次 attempt 后来又在环境 reset
阶段报 `Broken pipe`，累计 8 条 `infra_invalid`，仍无 401。独立、
不计分的环境探针复现了更具体的子进程错误：`CUDA_VISIBLE_DEVICES=3`
但不指定 EGL 时，task6 seed67688 的 reset 抛出 MuJoCo
`Offscreen framebuffer is not complete, error 0x8cdd`，父进程表现为
`Connection reset by peer`；清空仅模拟器子进程的 CUDA 可见性并设置
`MUJOCO_EGL_DEVICE_ID=1` 后，同一任务/seed 的 reset 正常。
进一步实测这台机器在 `CUDA_VISIBLE_DEVICES=3` 下 EGL 映射为
`{0: 1}`：CUDA 0 是进程内重编号的物理 GPU3，而 EGL 1 才是其渲染
设备。由此判断上述 8 条是渲染设备选择错误引起的基础设施失败，不能
解释为 recovery 策略或 BDDL 目标失败。

修复限定在 spawned LIBERO-Pro 模拟器子进程：按当前 CUDA 可见设备的
进程内 0 号查询 EGL 对应设备，设置 `MUJOCO_EGL_DEVICE_ID`，然后只
清空该子进程的 `CUDA_VISIBLE_DEVICES`，绕开 robosuite 假设 CUDA/EGL
序号相等的校验。policy 父进程仍使用 GPU3；非 Pro 环境不改变配置。
定向测试 53 项通过，实际映射探针得到 `child_cuda='' egl=1`。
为了避免在修复服务重启前继续消耗受影响任务的基础设施重试预算，
task6–9 尚未启动的 196 条 job（每任务 49 条）被可逆地移至
`queue/pending/paused_goal_s_task6_9/`；其他 36 个任务保留原队列，
manifest、logical ID、种子和 policy RNG 均未更改。

维护切换时先将其余 1,719 条待领取 job 暂存到
`queue/pending/paused_maintenance/`，待两条运行中 rollout 自然收尾后，
停止两个空闲 worker 和旧 runtime，再以相同配置、端口及物理 GPU3
启动新 runtime。健康接口恢复后，使用不入正式 queue/ledger 的 runtime
session 对 Goal-S task6–9 逐一做 seed67688 的 reset 探针：四项均成功，
task language 分别为 `Put the cream cheese on the bowl`、
`Turn on the stove`、`Put the bowl on the plate`、
`Put the wine bottle on the rack`。随后将两个暂停目录合计 1,915 条
原 job 原样移回 `pending/gpu3`，双 worker 和 controller 已重启。
这验证了环境启动修复，不是 4 个任务的策略成功率或 Table 3 成绩；
正式 infra-invalid logical ID 仍须等待原 seed、原 policy RNG 的 attempt-1
完成并经 controller 入账。runtime `/healthz` 返回 `auth=disabled`，
此次 v6 的 8 条环境错误与旧 v3 的 Codex Role1 401 是不同故障。
恢复后首两条完整正式 rollout（LIBERO-10-S task3/task4）均以
`status=valid` 收尾，`agentview`、`wrist`、`multiview` 视频及延迟摘要
均存在；两条的任务成功标志均为 false，不能当作 recovery 效果。
截至 2026-09-27 12:01 UTC，queue 为 88 completed / 8 failed / 2 running /
1,910 pending，8 条 failed 的同 logical ID attempt-1 均已入队；
runtime 健康接口 `env_ranks_healthy=1`、`heartbeat_failed=0`。
此时 Goal-S task6–9 的正式同种子重试尚未完成，不能据非计分 reset
探针宣称其有效 episode 或任务成功。

正式重试结果（2026-09-27 12:13 UTC）：在 queue 领取锁下将其他
1,901 条 pending job 可逆暂存，仅优先调度上述 8 条
`attempt_index=1`；这只是改变执行顺序，未改 seed、policy RNG、
bundle、任务或评估门禁。8 条现已全部 `status=valid`，均与原
`attempt_index=0` 的 task/logical ID/seed/policy RNG 逐项相符；
三路视频、延迟摘要完整，纯 VLA 的工具事件为空，审计缺口为 0。
task6 两条分别失败/失败，task7 成功/成功，task8 成功/失败，
task9 失败/失败；合计纯 VLA 任务成功 3/8。这是 development baseline
的一个极小样本，不是 Zetta recovery 效果，也不是 Table 3 留出集成绩。
旧 8 条基础设施失败 attempt 保留审计记录，但有效 episode 由原 ID 的
重试提供，不应重复计算。其余 1,901 条 job 已全部移回活跃队列；
此时 99 completed / 8 historical failed / 2 running / 1,899 pending，
冻结总数 2,000 logical ID、2,008 attempt job 不变。
控制器随后已在四个 Goal-S campaign 的 append-only episode ledger
各记录两条 `status=valid`、`attempt_index=1` 的正式 episode，
确认不是仅停留在 queue 的完成文件。

修复后的并行度复验（2026-09-27 12:26 UTC）：旧三并发失败现已由 EGL
设备误选解释，并非已证实的并发上限。在双 worker 正常运行时，第三个
`--once` worker 两次分别完成 Goal-T task3（137.2 秒，valid）和
Goal-T task7（29.5 秒提前成功，valid）；随后第三 worker 持续运行，
完成 LIBERO-10-S task0 的长 horizon rollout（230.3 秒，valid）。
同期其他两个 worker 的任务也正常完成，queue failed 数维持原有 8 条，
runtime 健康接口 `heartbeat_failed=0`；GPU3 显存约 14.2/24.6 GB。
截至该时已完成的 110 条 v6 episode 全部 `status=valid`，三路视频、
延迟摘要及纯 VLA 无工具事件审计缺口为 0。因此暂时保留三个独立
`--concurrency 1` worker，以后续更长窗口监控失败率和实际吞吐；
这仍只调整执行并行度，不修改冻结的 2,000 logical ID 或任何门禁。

三并发后的全矩阵审计：从 40 个冻结 manifest 重新推导全部 2,000 个
development `(task, logical ID, seed, policy RNG)`，与 queue 四类 envelope
逐一比对，观测到 2,000/2,000 logical ID、2,008 个 attempt job；
8 条历史基础设施重试均为连续的 `attempt_index=0,1`，无缺失、额外
logical ID、重复 job ID 或 seed/RNG 偏差。审计时 115 条 completed
全部 `status=valid`，三路视频、延迟摘要及纯 VLA 无工具事件审计均无
缺口；其余仍在 generation-0 baseline，不能报告任何 held-out SR。

候选阶段前的凭据预检：仓库自带的
`probe_codex_stage_runtime.py` 使用与 v6 manifest 相同的
`gpt-5.6-sol` / `high` 跑了一次无工具 nonce 调用，报告
`passed=true`（nonce、持久 thread ID、原始流解析和终止事件检查
均通过），耗时约 12.4 秒，未返回 401。审计报告在本地忽略目录
`.local-repro/liberopro-paper-v6-matrix-20260927/preflight/codex-stage-20260927-1230/report.json`。
这只验证了当前 Codex 调用链，不保证未来凭据不会过期，也不代替
正式 Role1/candidate rollout 的有效性审计。

四并发试验及 Goal-S task5 环境池恢复（2026-09-27）：在三并发长期
未新增失败后，以第四个 `--once` worker 做两条受控试跑，LIBERO-10-T
task8（95.6 秒成功）和 Goal-S task4（58.4 秒失败）均 `valid`，
视频/延迟齐全。随后短暂启动常驻第四 worker 时，Goal-S task5 的
`g0000-rollout-002`、seed63916 在 runtime reset 阶段报
`Connection reset by peer`，为第 9 条 `infra_invalid`，不能计作
任务失败。撤回第四 worker，返回三并发；四并发与故障时间相关，
但尚不足以证明并发本身是唯一根因，因此不继续用第四 worker 消耗预算。

对 task5 的同 seed 做非计分隔离探针：独立 `make_env` 的普通 reset
与 seed0+显式 init-state reset 均正常；旧 runtime session 在该 seed
以及此前正式成功过的 seed6961 上都立即 `Broken pipe`，说明旧 task5
环境池已损坏且不会自动自愈。为避免耗尽冻结的两次基础设施尝试，
48 条 task5 pending job 被可逆暂存，controller 临时以 `--pause-task`
运行；其余 1,784 条 pending job 在维护时也暂存。待三条运行中
rollout 自然收尾，空闲 worker 和旧 runtime 依次停止，按相同配置、
端口和 GPU3 重启 runtime。新 runtime 的非计分 seed63916 reset
成功；随后只释放该 logical ID 的正式 `attempt_index=1`，单 worker
取得 `status=valid`、任务失败、三路视频与延迟齐全，原 seed 和
policy RNG 不变。旧无效 attempt 保留审计，重试有效 episode 由
controller 入账。其余 1,784+47 条原 job 已全部原样恢复，三 worker
和无暂停标志的 controller 重新运行。此维护没有更换 seed、bundle、
任务目标或门禁；若旧池失效再现，应先隔离受影响 task 而非盲目耗尽
最后一次 attempt。

防止环境池持续中毒的基础设施热修复提交 `e7f4ff3`：EnvWorker
在 core 调用出现 `BrokenPipeError`、`ConnectionResetError` 或
`EOFError` 时将该池标记为 unhealthy；仍绑定的 session 未释放时
拒绝把同一池交给新 session，最后一个绑定释放后才关闭旧池并按相同
env spec 建立新池。普通 reset 参数错误不会触发回收；61 项相关
runtime 测试通过。它不替代 queue 的正式 infra-invalid attempt 记录，
也不会在同一 attempt 内暗中改变 seed/episode。
在安全维护窗口将 1,808 条待领取 job 可逆暂存，三条运行中 rollout
自然收尾后切换 runtime；新健康接口 epoch 为 `1790514475`，
三 worker 和 controller 均已恢复，1,808 条 job 全数移回。
切换后的 192 条 completed 均 `valid`，三路视频与延迟摘要缺口为 0，
failed 仍为 9 条历史基础设施 attempt；上述自愈分支目前仅有
单元回归验证，尚未以真实新故障验证其现场触发效果。

切换后的下一轮正常任务轮转中，Goal-S task5 的下一冻结种子
`g0000-rollout-003` / seed10569 在三并发下取得 `status=valid`、
任务失败，三路视频与延迟摘要均齐全；随后由 controller 写入该
campaign 的 append-only episode ledger。这验证了该任务的新环境池
在正常队列调度中可用，不是非计分探针或 recovery 成功。截至此轮审计，
225 条 completed 均 `valid`，证据缺口为 0，历史 failed 仍为 9 条；
自动重建分支仍等待真实断管后的现场验证。

### v6 鉴权复核与 LIBERO-10-S task7/8 环境断连（2026-09-27）

旧 v3 task2 的 4 条 Codex Role1 `401 Unauthorized` attempt 已在当时用原
seed、bundle 和门限补发 attempt-1，4 条均为 `valid`、official success=true；
但 v3 后来确认逐次 policy RNG 未生效，因此不能把这些重试当作 Table 3 的
可信 paired evidence。v6 使用修正后的 policy RNG 重新生成 baseline。
对当前 `gpt-5.6-sol` / `high` 配置重新执行无工具 nonce 鉴权探针，
`passed=true`，5 项检查全部通过，未出现 401；报告仅保存在本地
`preflight/codex-stage-401-retry-20260927-2139/report.json`，不计入任何
success rate。

v6 的 LIBERO-10-S task7 `g0000-rollout-006` / seed9372 与 task8 同 logical ID /
seed74291 在 reset 阶段先后出现 `Connection reset by peer`，均标为
`infra_invalid` 而非任务失败；故障发生于同一 queue worker，但涉及不同
task 环境池。事发时 runtime 留存 38 个模拟器子进程，空闲池未设上限。
这说明资源累积值得控制，尚不能证明其为断连的唯一原因。为保留原定
attempt 预算，曾将两任务 86 条待领取 job 可逆暂存，并让其他任务继续。

基础设施修复为 EnvWorker 新增可配置的 `max_idle_pools`（默认 0 保持旧
行为；本次 runtime 设为 4）：维护循环只关闭无活跃 session 且无待绑定
操作的旧空闲池，重新创建仍使用同一 env spec 和正式 reset seed。
并发绑定不会被误回收；22 项相关动态池测试通过。切换运行时前，
一条 Goal-T task1 rollout 在 worker 停止时变为孤儿进程；等待它自然完成
并发布 `status=valid` 结果后，通过 queue 的 abandoned-claim 恢复机制
将同一次 attempt 提交，未重复执行。新 runtime health epoch
`1790515957`，三 worker 运转时观测到 7 个模拟器子进程（3 活跃、4 空闲）。
task7 seed9372 和 task8 seed74291 均在同一服务上通过非计分 reset 探针。
原 86 条 job 已全部恢复，controller 已为两条失败 logical ID 补发冻结
`attempt_index=1`。两条正式重试均已完成，`status=valid`、official
success=false，seed 与 policy RNG 分别保持为 task7 `(9372, 188696758)`
和 task8 `(74291, 56782123)`；各有三路非空 MP4 和延迟目录。原始
attempt-0 `infra_invalid` 保留审计但不计入任务成功率。优先验证窗口
临时暂存的 1,734 条其他 pending job 已全部原样恢复；三 worker、
无暂停标志的 controller 已将两条有效 episode 写入各自的 append-only
ledger 并继续运行。有效重试说明这两个 seed 已能通过
正式 rollout，但不能单独证明空闲池上限就是原断连的根因。
