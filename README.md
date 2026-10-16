# 米家空调控制 Skill

让支持 `SKILL.md` 的 Agent 读取米家空调状态，并按明确请求设置**目标温度**、开关和模式。仓库包含两部分：[`mijia-ac-control`](skills/mijia-ac-control/SKILL.md) 是给 Agent 的操作说明；`mijia-ac` 是实际执行读写的本地 CLI。Codex 等能加载 Skill、执行本机命令的 Agent 可以使用；只想在终端操作，也可以单独使用 CLI。

例如，用户说“升高一度”时，Skill 先读取当前**设定温度**，再计算目标值交给 CLI；CLI 的 `set-temp 24` 表示“设为 24 度”。本项目不测量室温，也不提供自动恒温。控制走米家云端，需要使用者自己的小米账号和设备；可用性取决于设备实际公开的属性。

## 开始使用

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/) 和 Git。先审查本仓库及 [Skill 指令](skills/mijia-ac-control/SKILL.md)，再在本机安装 CLI 和 Skill。Skill 目录不包含 CLI、设备配置或授权文件；两者分别准备。登录、设备发现和 spec 查询会访问你的米家账号，请在自己的终端完成。

### 1. 获取项目并安装 CLI

```console
git clone https://github.com/yyyzl/mijia-ac-skill.git
cd mijia-ac-skill
uv sync --locked
uv run --locked mijia-ac --help
```

最后一条只显示帮助，不访问米家。`uv.lock` 和仓库内固定版本的 [mi_home_cli](https://github.com/slightc/mi_home_cli) 源码用于安装本项目依赖。

### 2. 将 Skill 装载到 Agent

把本仓库的 `skills/mijia-ac-control/` **整个目录**放进所用 Agent 的 Skill 搜索目录，确保 `SKILL.md` 与 `references/` 一起保留。不要把整个仓库当作 Skill 安装；运行时仍需访问上一步安装的 CLI。

以 Codex 为例，可放在用户级 `~/.agents/skills/mijia-ac-control/`，或某个项目的 `.agents/skills/mijia-ac-control/`。其他支持 `SKILL.md` 的 Agent 按其文档选择目录；能读取 Skill 并不代表它有本机命令执行能力。若目标目录已有同名 Skill，先检查来源，不要直接覆盖。Codex 的目录与加载规则见 [官方 Skill 文档](https://developers.openai.com/codex/skills/)。

从仓库根目录安装到 Codex 用户级目录，例如：

```powershell
$skillTarget = Join-Path $HOME '.agents/skills/mijia-ac-control'
if (Test-Path $skillTarget) { throw '同名 Skill 已存在，请先检查' }
New-Item -ItemType Directory -Force (Split-Path $skillTarget -Parent) | Out-Null
Copy-Item -LiteralPath 'skills/mijia-ac-control' -Destination $skillTarget -Recurse
```

macOS / Linux（bash、zsh）：

```bash
skill_target="$HOME/.agents/skills/mijia-ac-control"
if [ -e "$skill_target" ]; then echo '同名 Skill 已存在，请先检查'; exit 1; fi
mkdir -p "$(dirname "$skill_target")"
cp -R skills/mijia-ac-control "$skill_target"
```

在 Codex 中可输入 `$mijia-ac-control` 显式调用，也可以直接提出“读取米家空调状态”这样的请求，由 Agent 根据 Skill 描述判断是否使用。首次使用时，只提供**本机仓库位置和仓库外的配置文件路径**，不粘贴配置内容、完整 DID、授权码或设备清单。若 CLI 或配置尚未准备好，Agent 应按 [首次准备](skills/mijia-ac-control/references/setup.md) 引导用户完成。

### 3. 准备仓库外的配置

把示例复制到仓库**外面**。下面约定仓库、私有配置目录和授权状态目录是同级目录；后续命令均采用这组路径。

| 用途 | 示例位置 | 是否上传到 GitHub |
| --- | --- | --- |
| 本项目源码与无真实数据的示例 | `mijia-ac-skill/` | 是 |
| 你的设备配置 | `mijia-ac-private/config.toml` | 否 |
| 米家授权及设备缓存 | `mijia-ac-state/` | 否 |

PowerShell：

```powershell
New-Item -ItemType Directory -Force ../mijia-ac-private | Out-Null
if (-not (Test-Path ../mijia-ac-private/config.toml)) { Copy-Item config.example.toml ../mijia-ac-private/config.toml }
$env:MI_HOME_CONFIG_DIR = (Join-Path (Split-Path (Get-Location) -Parent) 'mijia-ac-state')
```

macOS / Linux（bash、zsh）：

```bash
mkdir -p ../mijia-ac-private
if [ ! -e ../mijia-ac-private/config.toml ]; then cp config.example.toml ../mijia-ac-private/config.toml; fi
export MI_HOME_CONFIG_DIR="$(cd .. && pwd)/mijia-ac-state"
```

先打开 `../mijia-ac-private/config.toml`，确认 `profile = "ac_control"`、`state_dir = "../mijia-ac-state"`。`state_dir` 相对于**配置文件所在目录**解析，须与 `MI_HOME_CONFIG_DIR` 指向同一位置。不要把它指向已有的其他账号状态目录。

### 4. 在本机授权并识别设备

保持上一步设置的 `MI_HOME_CONFIG_DIR`，在**同一个终端**运行：

```console
uv run --locked mi --profile ac_control --channel cloud auth login --manual
uv run --locked mi --profile ac_control --channel cloud device sync
uv run --locked mi --profile ac_control --channel cloud --output json device list
uv run --locked mi --profile ac_control --channel cloud spec show REPLACE_WITH_DEVICE_ID
```

登录按上游 CLI 的终端提示完成。第三条会在本机显示设备清单：找到目标空调的**完整 DID**，只在自己的终端将它替换进第四条命令和私有配置文件。不要把回调地址、授权码、授权文件或完整设备清单贴到聊天、Issue 或提交中。

在 `spec show` 输出中逐项核对下表，再填写私有配置。表中的默认属性名只是常见写法，设备不匹配时按实际 spec 修改；缺少必需的可读属性时，本 CLI 不适用该设备。

| 配置项 | 从设备 spec 核对什么 |
| --- | --- |
| `device_id` | 目标设备的完整 DID，而非名称或型号 |
| `on_property` | 可读的开关属性；状态值须为布尔值 |
| `temperature_property` | 可读的目标温度属性；确认可写、范围和步长 |
| `mode_property` | 可读的模式属性；状态值须为整数 |
| `min_temperature`、`max_temperature`、`temperature_step` | 目标温度的实际范围和步长，不能直接沿用示例数值 |
| `mode_cool`、`mode_heat` | 仅在使用模式切换时填写 spec 中对应的整数枚举，不能猜测 |

此时私有配置中的 `device_id` 已替换，温度范围与步长已核对，`profile` 和 `state_dir` 与授权步骤一致，才算准备完成。配置无默认账号或隐式路径；每次调用都须传 `--config`。

### 5. 先预览，再读取状态

```console
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml set-temp 24
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml status
```

第一条仅在 **24 位于你配置的合法范围**时可用。它只生成本地计划，不读取账号、不写设备；返回中 `"preview": true` 表示尚未执行。第二条需要网络和本机授权，返回 `on`、`temperature`（目标温度字符串）和 `mode`（设备原始整数值）。读不到这些字段时，先在本机重新检查授权和 spec。

例如，某个**虚构设备**的 `status` 可能返回 `{"on": true, "temperature": "24", "mode": 2}`。这里的 `24` 是目标温度；`2` 只是该设备的原始枚举，不能直接当作通用的“制冷”值。

### 6. 明确要求实际控制时执行

以下命令会改变真实设备状态。每次写入都须加 `--apply`；关机时设温或切换模式，只有明确允许**先开机**，才加 `--allow-power-on`。

```console
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml set-temp 24 --apply
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml power off --apply
```

开关机还支持 `power on`；模式切换支持 `mode cool|heat`，前提是已核对并填写对应枚举。若设备关机，`set-temp` 和 `mode` 默认停止且不写入；获得开机许可后，CLI 先开机并确认，再写目标值。写入后 CLI 进行独立回读；失败时停止，不自动重试或回滚，设备可能已经改变。云端回读匹配不代表物理制冷或制热已发生。

## 兼容性与常见问题

- 当前只支持 `cloud` 通道，并要求 `on`、目标温度和 `mode` 三个属性可读；模式值须为整数。设备 spec 不符时会停止，而不会猜测属性或设备。
- CLI 只接受配置中的精确 DID。预览不证明设备在线；`status` 和 `--apply` 会访问云端。
- 温度按配置的范围和步长精确检查，不舍入。`status` 的 `temperature` 是**设定温度**，不是室温。
- 操作超时、回读不匹配或返回非零时，先在本机核对设备实际状态、网络、授权和 spec；不要自动重发写命令。
- Agent 找不到 Skill 时，检查目录是否符合该客户端的发现规则；找得到 Skill 却无法执行时，检查本机命令工具、CLI、仓库和私有配置路径。Skill 不会替 Agent 增加终端权限或登录米家账号。
- 需要了解实现细节和适配限制，见 [设计说明](DESIGN.md)；凭据处理与问题报告见 [安全说明](SECURITY.md)。

## 公开仓库与维护

本仓库应包含 CLI 源码、Skill 及其必要引用、无真实设备绑定的配置示例、锁文件、固定上游源码及许可证、测试和发布检查器。真实 `config.toml`、授权状态、设备清单、DID、凭据、私人路径、日志、虚拟环境、构建产物和本地评测报告留在仓库外。`.gitignore` 不能保护已经跟踪的文件；发布前还要人工查看候选文件与暂存内容。

```console
uv sync --locked
uv run --locked pytest -q
uv run --locked python tools/check_public_tree.py
```

测试使用虚构数据和 fake runner，不登录真实账号或控制设备。公开检查器是静态防护，不能替代人工审查。测试和设计依据见 [Skill 质量约束](docs/skill-quality.md)、[评测说明](skills/mijia-ac-control/references/evaluation.md)；第三方来源及版权见 [第三方声明](THIRD_PARTY_NOTICES.md)。本项目非小米官方产品。

### 不使用 uv

在独立虚拟环境中先安装仓库内上游源码，再安装本项目：

```console
python -m pip install ./vendor/mi-home-cli
python -m pip install .
mijia-ac --help
```

`pip install .` 单独运行不保证使用仓库内固定的上游版本。pip 安装后将上面示例里的 `uv run --locked mijia-ac` 换成 `mijia-ac`。
