# Zetta 复现期间发现的项目问题

本文整理复现过程中确认属于 Zetta 项目代码、流程编排或项目内运行契约的问题。
结论来自 `docs/experiments/liberopro-evaluation-log.md` 及对应的测试、队列和审计产物。

## 摘要

复现已经暴露并修复了多处会导致错误归因、错误终止、跨 revision 无法恢复或错误计分的缺陷。
这些问题与策略本身是否成功是不同层次的问题：修复后仍需要重新进行 source fence 和门禁评测。
截至本文记录时，完整 Same-seed -> Regression -> Held-out -> Promotion 链尚未形成通过结果。

## 已确认的问题

### 1. TemporalCritic 首步提前读取不存在的特征

- **表现**：首个物理 step 在 `previous EEF` 尚不存在时读取
  `command.realization.stalled`，抛出 `KeyError`。
- **根因**：主特征解析发生在 activation condition 检查之前；即使
  `direction_available=false` 应该屏蔽规则，也无法避免提前读取。
- **影响**：候选 episode 被错误归类为基础设施失败，消耗重试并可能中断 gate。
- **状态**：已将特征解析移到 activation guard 之后，并为缺少 previous EEF 的情况显式
  输出 `direction_available=false`；已加入 canonical、runtime 和 LIBERO extractor 回归测试。

### 2. Gate runner 中断恢复不能重放已有 decision

- **表现**：Same-seed decision 已 append 后，进程在 phase 迁移前中断；恢复逻辑只处理
  “无 decision”，无法继续已有决定。
- **影响**：已完成的 gate 被错误留在中间状态，必须人工迁移或重新整理 LoopX 状态。
- **状态**：已修复为可重放已有 decision，并增加 gate/lifecycle 回归测试。

### 3. 跨 revision 迁移时 frozen artifact locator 使用错误路径

- **表现**：EpisodeRecord 必须保持原字节，但其中的绝对 rollout 路径仍指向旧 campaign。
  resolver 已能安全重绑，lifecycle 的 frozen-digest 快速路径却绕过 resolver。
- **影响**：accepted artifact 被误报为缺失，Proposal 在调用模型或运行 episode 前 fail closed。
- **状态**：已改为使用 manifest-scoped resolver，并在读取前重新校验 accepted SHA-256；
  EpisodeRecord 不改写，越界路径仍拒绝。

### 4. Stage2 observed feature catalog 未消费 manifest-scoped resolver

- **表现**：Stage2 仍用旧的直接路径解析 states，迁移后的 228 条 episode 全部被误判为
  没有可用 Critic feature，传入空 catalog。
- **影响**：合法 Proposal 因引用 catalog 外特征被 validator 拒绝；这是 Harness 解析错误，
  不是 Recovery 机制拒绝。
- **状态**：已统一 frozen-artifact 读取路径并重算安全 feature catalog，增加回归覆盖。

### 5. Shadow replay 仍有一条旧路径读取迁移后的 states

- **表现**：Proposal 输入索引已经修复，但 shadow replay/diagnostic telemetry 仍调用旧的
  `_existing_artifact_path()`。
- **影响**：shadow 计算前即失败，候选无法注册，也不会产生新的 Same-seed 证据。
- **状态**：已改为 manifest-scoped resolver + accepted SHA-256 复核，并增加迁移后非空
  telemetry 和 campaign 内路径测试。

### 6. Stage2 causal-isolation 约束曾位于嵌套历史，控制器无法可靠消费

- **表现**：模型没有逐字复用 Harness 选定的 proven Critic 时，旧控制器把任意 Proposal
  非零退出错误地当作已有 shadow Reject，随后报“没有 immutable replay”。
- **影响**：validator 前失败被错误分类，恢复/重试路径中断，真实候选搜索被阻塞。
- **状态**：已将 `preserve_critic_rules_byte_for_byte` 和
  `reuse_recovery_steps_byte_for_byte` 提升为顶层强制输出，并将 validator 前失败隔离处理。

### 7. Same-seed 反馈缺少因果归因计数

- **表现**：下一轮 Proposal 只收到 intervention 总数和成功数，无法区分自然成功、未改变
  action 的成功以及真正由 Recovery 救回 parent failure 的成功。
- **影响**：Stage2 可能优化名义成功率，却不能修复 trigger-to-action handoff，导致候选反复
  通过数值门槛但被因果门禁拒绝。
- **状态**：已加入 action divergence、causally attributed success、unattributed win 三类
  seed-blind 聚合，并接入 live-reject 和 shadow-reject 两条反馈路径。

### 8. 失败候选的早停和队列回收边界曾不一致

- **表现**：确定性上界已证明门槛不可能达到时，旧流程仍可能保留 pending claim；中断任务
  若已有 terminal artifact，又可能被重复重放。
- **影响**：浪费 GPU/API 配额，或把环境副作用重复执行，破坏 episode 计数和审计连续性。
- **状态**：已使用 conclusive early Reject、`recover_abandoned` 和 terminal artifact 回收，
  并将基础设施失败排除出 score。

### 9. 共享单卡 runtime 的并发能力声明与实际隔离不一致

- **表现**：曾错误提高 worker 并发，导致多个 reset 断连；runtime probe 只能证明 GPU 与
  Ray rank 健康，不能证明完整物理隔离。
- **影响**：产生 `infra_invalid`，并可能把资源竞争误认为策略失败。
- **状态**：development lane 已改为单卡串行；并发限制、`runtime_isolation_not_attested`
  和不可比硬件标签已显式记录。该问题仍是复现环境的剩余风险，不能仅凭 healthz 宣称隔离完整。

### 10. 子进程环境和 provider client 配置继承不完整

- **表现**：Role1 子进程曾加载 source checkout 中旧版 Zetta，触发 pydantic API 缺失；旧
  worker 也未继承 180 秒 Role1 timeout。
- **影响**：请求阶段长时间无结果或被错误归类为依赖/运行失败。
- **状态**：已固定 `PYTHONPATH` 顺序、升级复现 venv 依赖，并在本地/broker client 设置默认
  timeout；仍应在每个新 source-fenced run 中验证子进程环境。

### 11. Responses provider 的压缩响应兼容性缺陷

- **表现**：中转站返回压缩响应时，bundled `httpx2` 解压路径异常。
- **影响**：Role1/诊断请求失败，即使 API 返回 HTTP 200。
- **状态**：Responses client 固定发送 `Accept-Encoding: identity`，并设置 `store=false`。
  这是 provider 兼容层问题，不应与 LIBERO 策略成功率混合统计。

## 不应归因于项目本身的问题

以下因素在本次复现中单独标记，不应作为 Zetta 算法或流程缺陷计入成功率比较：

- Tiantian API 网络、配额、瞬时连接失败；
- 当前机器单张 RTX 4090 与历史 4×A800 的硬件/软件差异；
- EGL、可选 Python 包或 RoboCasa 等未安装依赖导致的 `infra_invalid`；
- LIBERO composite scene XML/资产 overlay 缺失；
- 校正前错误数据源或不完整 task asset；
- 当前候选的官方 LIBERO termination 未达到成功条件。

## 当前验证边界

项目闭环已经能实际执行 Critic -> Role1 -> bounded Recovery -> continuation，并生成可审计
产物；但修复后的完整正式评测仍必须重新通过 source fence、Same-seed、Regression、
held-out 和 Promotion。没有通过这些门禁前，任何成功率提升都不应写入论文成绩或 LoopX
`score_countable` 结果。
