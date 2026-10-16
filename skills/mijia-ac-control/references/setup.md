# 首次安装或平台环境未就绪时读取

在独立源码仓库运行 `uv sync --locked`，再运行 `uv run --locked mijia-ac --help`。要求 Python 3.11+；Windows PowerShell、macOS zsh/bash 与 Linux 使用同一 wrapper。pip 安装方式见仓库 README。

将 config.example.toml 复制到仓库外，按目标型号 spec 填写；state_dir 相对配置解析，解析链接后仍须在仓库外。使用独立 profile/state，凭据由使用者手工建立；不让用户向聊天提供授权回调、令牌或设备清单。

由使用者在自己的终端按 README 的 PowerShell 或 macOS shell 分支手工 OAuth、发现设备和核对 spec。完成后只确认本机配置已就绪，不上传内容。已安装私人同名 skill 与本目标独立，安装前由使用者审查复制边界。
