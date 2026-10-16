# 米家空调设定温度控制

用命令行读取米家空调状态，或在明确要求下设置**目标温度**、开关和模式。仓库提供两部分：`mijia-ac` 是执行操作的 CLI；`mijia-ac-control` 是让 Hermes Agent 使用该 CLI 的可选 Skill。只想在终端操作，安装 CLI 即可。

CLI 的 `set-temp 24` 表示“设为 24 度”。“升高一度”这类相对请求由 Skill 先读取当前**设定温度**，再计算绝对目标值。本项目不测量室温，也不提供自动恒温。控制使用米家云端，需要自己的小米账号和设备；可用性取决于设备实际公开的属性。

## 首次使用

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/) 和 Git。以下命令在仓库根目录执行；登录、设备发现和 spec 查询会访问你的米家账号，请在自己的终端完成。

### 1. 安装 CLI

```console
git clone https://github.com/yyyzl/mijia-ac-skill.git
cd mijia-ac-skill
uv sync --locked
uv run --locked mijia-ac --help
```

最后一条只显示帮助，不访问米家。`uv.lock` 和仓库内固定版本的 [mi_home_cli](https://github.com/slightc/mi_home_cli) 源码用于安装本项目依赖。

### 2. 准备仓库外的配置

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

### 3. 在本机授权并识别设备

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

### 4. 先预览，再读取状态

```console
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml set-temp 24
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml status
```

第一条仅在 **24 位于你配置的合法范围**时可用。它只生成本地计划，不读取账号、不写设备；返回中 `"preview": true` 表示尚未执行。第二条需要网络和本机授权，返回 `on`、`temperature`（目标温度字符串）和 `mode`（设备原始整数值）。读不到这些字段时，先在本机重新检查授权和 spec。

例如，某个**虚构设备**的 `status` 可能返回 `{"on": true, "temperature": "24", "mode": 2}`。这里的 `24` 是目标温度；`2` 只是该设备的原始枚举，不能直接当作通用的“制冷”值。

### 5. 明确要求实际控制时执行

以下命令会改变真实设备状态。每次写入都须加 `--apply`；关机时设温或切换模式，只有明确允许**先开机**，才加 `--allow-power-on`。

```console
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml set-temp 24 --apply
uv run --locked mijia-ac --config ../mijia-ac-private/config.toml power off --apply
```

开关机还支持 `power on`；模式切换支持 `mode cool|heat`，前提是已核对并填写对应枚举。若设备关机，`set-temp` 和 `mode` 默认停止且不写入；获得开机许可后，CLI 先开机并确认，再写目标值。写入后 CLI 进行独立回读；失败时停止，不自动重试或回滚，设备可能已经改变。云端回读匹配不代表物理制冷或制热已发生。

## 可选：在 Hermes Agent 中使用

如果只使用 CLI，跳过本节。Hermes Skill 需要单独安装；它不包含 Python CLI、设备配置或授权文件。先按上面的步骤准备好 CLI 与私有配置。

下面的命令仅供读者在**自己的 Hermes 环境**执行，不属于项目构建或发布流程。`inspect` 查看实际来源与内容，`install` 安装 Skill，`list` 确认 Hermes 已发现它。安装方式参见 [Hermes Skill 文档](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md)。

```console
hermes skills inspect yyyzl/mijia-ac-skill/skills/mijia-ac-control
hermes skills install yyyzl/mijia-ac-skill/skills/mijia-ac-control
hermes skills list
```

新会话中可直接说“读取米家空调状态”或“把米家空调设定温度调到 24 度”，也可显式使用 `/mijia-ac-control`。首次使用时，只向 Agent 提供**本机仓库位置和私有配置文件路径**，不要提供配置内容、DID、授权码或设备清单。Agent 会根据 [SKILL.md](skills/mijia-ac-control/SKILL.md) 先确定目标与动作；路径不明时应停下询问，不能猜测其他账号或设备。安装后的 Skill 需要能在本机使用 `terminal` 调用已安装的 CLI。

Hermes 安装 Skill 与安装 Python CLI 是两步；只完成其中一步，无法通过自然语言控制设备。如果 `inspect` 显示的仍是旧版，可在核对目录内容后，将本仓库的 `skills/mijia-ac-control` **整个目录**手动放入 `~/.hermes/skills/mijia-ac-control/`；已有同名 Skill 时先检查来源，避免覆盖自己的版本。安装后如当前会话未发现 Skill，开启新会话或按 Hermes 文档刷新。

## 兼容性与常见问题

- 当前只支持 `cloud` 通道，并要求 `on`、目标温度和 `mode` 三个属性可读；模式值须为整数。设备 spec 不符时会停止，而不会猜测属性或设备。
- CLI 只接受配置中的精确 DID。预览不证明设备在线；`status` 和 `--apply` 会访问云端。
- 温度按配置的范围和步长精确检查，不舍入。`status` 的 `temperature` 是**设定温度**，不是室温。
- 操作超时、回读不匹配或返回非零时，先在本机核对设备实际状态、网络、授权和 spec；不要自动重发写命令。
- 需要了解实现细节和适配限制，见 [设计说明](DESIGN.md)；凭据处理与问题报告见 [安全说明](SECURITY.md)。

## 公开仓库与维护

本仓库应包含 CLI 源码、Skill 及其必要引用、无真实设备绑定的配置示例、锁文件、固定上游源码及许可证、测试和发布检查器。真实 `config.toml`、授权状态、设备清单、DID、凭据、私人路径、日志、虚拟环境、构建产物和本地评测报告留在仓库外。`.gitignore` 不能保护已经跟踪的文件；发布前还要人工查看候选文件与暂存内容。

```console
uv sync --locked
uv run --locked pytest -q
uv run --locked python tools/check_public_tree.py
```

测试使用虚构数据和 fake runner，不登录真实账号或控制设备。公开检查器是静态防护，不能替代人工审查。测试和设计依据见 [Skill 质量约束](docs/skill-quality.md)、[评测说明](skills/mijia-ac-control/references/evaluation.md)；第三方来源及版权见 [第三方声明](THIRD_PARTY_NOTICES.md)。本项目由 yyyzl 维护，非小米官方产品，也非 Hermes 主仓库的一部分。

### 不使用 uv

在独立虚拟环境中先安装仓库内上游源码，再安装本项目：

```console
python -m pip install ./vendor/mi-home-cli
python -m pip install .
mijia-ac --help
```

`pip install .` 单独运行不保证使用仓库内固定的上游版本。pip 安装后将上面示例里的 `uv run --locked mijia-ac` 换成 `mijia-ac`。
