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
