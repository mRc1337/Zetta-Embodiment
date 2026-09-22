# Recovery paired same-seed evidence

更新时间：2026-09-22

## 运行设计

对 `libero_10/task0` 使用相同 `seed=22`、相同 `policy_rng=22001`、相同标准 LIBERO runtime 和 GPU3，分别运行：

1. `strict_pure_vla` baseline，无 candidate bundle、无 Role1；
2. development-only synthetic bundle，启用官方 Codex Role1 和 bounded Recovery。

两次均使用 520 action budget、15 个 wait steps、5-action chunks。原始视频和轨迹只保留在服务器 `.local-repro/`，不提交到 Git。

## 结果

| arm | status | success | elapsed | action count | candidate intervention | action artifact SHA-256 |
|---|---|---:|---:|---:|---:|---|
| baseline | valid | true | 77.23 s | 352 | false | `723b6cf49ed4867702e748e97209c9ca3b3ec59a18d9e93b1819650f79b5ca36` |
| Codex + Recovery | valid | true | 152.07 s | 352 | true | `2e85a99ba377af7204028a44f3ce64d8fa3656e28d6c8f6f5cf096f9a653d9d` |

Recovery arm 的在线事件：

- synthetic Critic 在 environment step 12 触发；
- 官方 Codex Role1 decision：`role1-dd7f2233941168d3b93fe9e5`
- `proposal_disposition=accept`；
- selected tool：`libero.set_gripper`；
- bounded Recovery 执行 2 steps，状态为 `completed`；
- `candidate_intervention=true`。

## 严谨结论

这组 paired evidence 证明：

- 两次使用相同 seed；
- Recovery 确实触发并执行；
- Recovery arm 的动作 artifact 与 baseline 不同，说明发生了 action divergence；
- 两次 episode 都成功完成。

但它**不能证明 Recovery 救回了一个 baseline 必败的任务**，因为 baseline 在同一 seed 上也成功。因此当前可宣称的是“Recovery 机制执行有效、产生了受控动作改变并保持成功”，不能宣称“因果成功率提升”或“救援成功”。后者需要 baseline 失败、Recovery 成功的 paired seed，并通过严格因果归因门禁。

## 视频

Baseline：

- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/paired-baseline-seed22/videos/episode_agentview.mp4`
- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/paired-baseline-seed22/videos/episode_agentview_wrist.mp4`
- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/paired-baseline-seed22/videos/episode_agentview_multiview.mp4`

Codex + Recovery：

- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/rollout-role1/videos/episode_agentview.mp4`
- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/rollout-role1/videos/episode_agentview_wrist.mp4`
- `/usr1/home/s125mdg56_02/Zetta-Embodiment/.local-repro/rollout-role1/videos/episode_agentview_multiview.mp4`
<!-- end -->
