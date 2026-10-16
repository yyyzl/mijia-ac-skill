# 首次准备

首次使用、找不到 CLI 或配置路径、授权尚未完成时读取。具体 PowerShell 与 bash/zsh 命令见项目仓库根目录的 README.md；此处只列 Agent 的交接规则。

1. 确认 Python 3.11+ 和 CLI 可用：uv 安装在仓库根执行 `uv run --locked mijia-ac --help`；pip 安装执行 `mijia-ac --help`。帮助命令不访问账号。若入口不存在，指导用户先安装 CLI，不把安装 Skill 当成安装 CLI。
2. 询问缺失的**仓库路径或私有配置文件路径**，不要求用户粘贴配置正文、完整 DID、设备清单、授权回调或令牌。已知路径可用于调用 CLI；不要搜索其他账号的状态目录或复用其他 Skill 的授权文件。
3. 用户在自己的终端按 README 完成登录、设备发现和 spec 核对。`config.example.toml` 只是占位示例；真实配置和 `state_dir` 保持在仓库外，`profile`、`state_dir` 与授权时的设置一致。设备须提供可读的 on、目标温度和整数 mode；模式写入还要核对枚举。
4. 先用 `set-temp` 不带 `--apply` 检查本地配置与目标温度，再用 `status` 检查在线回读。预览成功只代表本地参数合法；`status` 成功才证明当前账号、目标设备和必需属性可读。任何一步失败，停在该步并给用户相应的本机排查方向。
