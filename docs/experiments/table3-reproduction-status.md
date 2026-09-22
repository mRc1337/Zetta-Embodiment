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
