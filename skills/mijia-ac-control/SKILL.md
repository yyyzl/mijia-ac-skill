---
name: mijia-ac-control
description: 米家空调状态、设定温度、开关和模式控制；室温测量、自动恒温、账号客服与硬件选购另行处理.
version: "0.1.0"
author: "yyyzl"
license: MIT
platforms: ['windows', 'macos', 'linux']
---

# 米家空调控制

1. **定位**：确认目标配置和请求动作。首次安装、平台环境或手工授权未完成时，读 [准备](references/setup.md)。完成条件：入口可用、配置和独立凭据状态均在仓库外，目标无歧义；授权内容留在用户本机。
2. **选分支**：查询用 `status`；绝对设温用 `set-temp`；相对调温先读取当前**设定温度**，精确加减后按配置范围/步长检查；明确开关用 `power`；模式用 `mode`，首次适配读 [模式与故障](references/modes-failures.md)。完成条件：请求已转为有限、合法的明确动作；设定温度不当作室温。
3. **预览与授权**：在已安装仓库根用 terminal 调用 `uv run --locked mijia-ac`，显式传 `--config`；pip 安装用 `mijia-ac`。参数独立传递，参数详情查分支 `--help`。默认预览不读设备；仅对应动作已有明确授权才加 `--apply`。关机设温和模式另需开机许可及 `--allow-power-on`。完成条件：计划、执行授权与开机副作用一致；未许可时停止写入。
4. **核对**：写后以 wrapper 独立回读为准；模式同时核对 on。失败立即停止，读 [模式与故障](references/modes-failures.md)，不补偿或盲重试。完成条件：回读匹配，或明确失败阶段及可能已改变的状态。禁止无人值守联动和复制其他 skill 的账号状态。
5. **交付**：报告 target/config、requested action、preview/executed、必要 before/after、independent readback、match/failure、side effects、physical evidence/unknown。隐藏 DID、凭据和私人绝对路径。预览标明未读/未写；失败写明已知动作及未知结果。云端匹配仅是快照，物理制冷/制热与室温证据缺失时标 unknown。

维护时按 [评测](references/evaluation.md) 运行 `evals/` 的触发与输出契约；fixture、command、model 证据分别记录。
