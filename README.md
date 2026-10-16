# 米家空调双向调温 skill

通过明确授权、独立回读的命令行 wrapper 上调或下调**设定温度**。包含可安装的 `mijia-ac`、Hermes 通用技能，以及原样保留的 [slightc/mi_home_cli](https://github.com/slightc/mi_home_cli) v0.1.3 源码。

本项目 wrapper、技能和测试由 yyyzl 提供，MIT；上游 CLI 作者为 slightc，独立 MIT 版权见 [第三方声明](THIRD_PARTY_NOTICES.md)。本仓库不是 Hermes 主仓库贡献，也不是小米官方产品。项目仓库为 `yyyzl/mijia-ac-skill`。

## 能力和边界

- `status` 仅输出 on、temperature、mode；读取需要网络与用户自行建立的授权。
- `set-temp` 支持升温和降温，默认本地预览，不读账号、不下发操作。
- `power on|off`、`mode cool|heat` 均须显式 `--apply` 才写入。模式必须先配置设备 spec 对应的原始枚举。
- 关机设温或模式操作默认拒绝；额外授权 `--allow-power-on` 后，分开执行开机、独立确认 on、写目标、独立确认目标与 on。
- 每次写入使用上游 `--verify`，之后 wrapper 仍单独 `get` 核对；不匹配或超时立即非零退出，不自动重写、重试或回滚。失败时设备可能已改变。
- 每个受控子进程在实际解析入口只接受配置的精确 DID，并保留家庭过滤；不存在、被过滤或重复 DID 均拒绝，不回退到名称、别名或型号。
- 写入前将数学整数温度无损序列化为十进制整数：`23`、`23.0`、`23.00`、`23e0` 均传入 `23`，兼容上游整数属性；非整数保留精度。

“双向调温”不等于制热实测，也不等于房温反馈或自动恒温。使用者曾观察确认 `lumi.acpartner.mcn02` 的本地制冷调温；该经验不推广到其他型号、制热、固件或空调红外适配。本项目开发只用 fake runner，没有访问真实账号或设备。本版没有后台任务、监听、定时控制或 ESP32 闭环。

## 安装（推荐 uv）

要求 Python 3.11+、uv 和 git。克隆后在仓库根运行：

```console
git clone https://github.com/yyyzl/mijia-ac-skill.git
cd mijia-ac-skill
uv sync --locked
uv run --locked mijia-ac --help
```

`uv.lock` 锁定依赖，`[tool.uv.sources]` 将 `mi-home-cli==0.1.3` 指向 `vendor/mi-home-cli`，默认安装仓库中的源码。不要把独立安装的其他 skill 或其授权文件复制过来。

pip 不识别 uv 的 vendor 路由；请在独立虚拟环境里明确执行：

```console
python -m pip install ./vendor/mi-home-cli
python -m pip install .
mijia-ac --help
```

单独 `pip install .` 不保证使用 vendor。wrapper wheel 只包含 wrapper，分发源码仓库须同时保留 vendor、许可证和清单。pip 的间接依赖不受 uv.lock 约束；可复现安装优先用 uv。

## 本地配置与手工授权

将 `config.example.toml` 复制到**仓库外**自选目录，改名为 `config.toml`，自行填写设备 DID、独立 profile 和状态目录。示例的 `REPLACE_WITH_DEVICE_ID` 不能直接运行。所有本地配置、状态、授权与设备清单都不要提交。

`--config` 必填，没有隐式路径或默认账号。必填 `device_id`、`profile`、`state_dir`、`min_temperature`、`max_temperature`、`temperature_step`。本版只允许 cloud；timeout 为 0 到 120 秒之间的有限正数。相对 `state_dir` 按**配置文件目录**解析，必须位于本项目之外；不要使用符号链接指向其他账号目录。

以下 PowerShell 示例中 `../ac-local-state` 是仓库外的通用占位目录，`fixture` 是示例 profile，`REPLACE_WITH_DEVICE_ID` 是占位值。**本步骤由使用者在自己的终端手工执行**，会登录或查询账号；agent 的开发测试不执行这些命令：

```powershell
$env:MI_HOME_CONFIG_DIR = (Join-Path (Split-Path (Get-Location) -Parent) 'ac-local-state')
uv run --locked mi --profile fixture --channel cloud auth login --manual
uv run --locked mi --profile fixture --channel cloud device sync
uv run --locked mi --profile fixture --channel cloud --output json device list
uv run --locked mi --profile fixture --channel cloud spec show REPLACE_WITH_DEVICE_ID
```

macOS zsh/bash（Linux 同理）的手工步骤与 PowerShell 使用同一仓库外状态目录和 profile；下列命令同样只由使用者本地执行：

```bash
export MI_HOME_CONFIG_DIR="$(cd .. && pwd)/ac-local-state"
uv run --locked mi --profile fixture --channel cloud auth login --manual
uv run --locked mi --profile fixture --channel cloud device sync
uv run --locked mi --profile fixture --channel cloud --output json device list
uv run --locked mi --profile fixture --channel cloud spec show REPLACE_WITH_DEVICE_ID
```

OAuth 仅在小米页面和自己的本地终端完成。不要向 agent 或聊天粘贴回调地址、授权码、token、auth.json 或完整设备列表。只在本机查看列表里的目标 DID，填入仓库外配置；检查该型号 spec 的服务属性全名、读写权限、温度最小/最大/步长和模式枚举。配置中 `state_dir` 必须与上述显式 `MI_HOME_CONFIG_DIR` 指向同一目录，profile 也须一致。wrapper 启动上游时会显式覆盖状态目录、profile、cloud 和 timeout。

示例范围 16–30、步长 1 仅示范，不保证任何型号通用。步长以 min_temperature 为基准进行十进制精确校验；所有数字拒绝 bool、NaN、Inf；数值文本最多 128 字符、系数最多 32 位、十进制指数绝对值最多 32，绝对值不超过 1000000。超限直接拒绝，不截断、不舍入。网格通过精确分数运算校验，JSON 小数回读保留 Decimal，比较前不转浮点；人类可读的最终 JSON 将 temperature 输出为十进制字符串，防止下游误读精度。默认属性为 `air-conditioner.on`、`air-conditioner.target-temperature`、`air-conditioner.mode`；可按 spec 改配置，不能猜测。当前 wrapper 要求三者可读，on 返回 JSON bool，mode 返回整数；不兼容时安全失败。

## 调用

下面假设仓库外已有 `../ac-local/config.toml`：

```console
uv run --locked mijia-ac --config ../ac-local/config.toml status
uv run --locked mijia-ac --config ../ac-local/config.toml set-temp 24
uv run --locked mijia-ac --config ../ac-local/config.toml set-temp 22
uv run --locked mijia-ac --config ../ac-local/config.toml power off
```

后面三条只是计划。计划不证明设备在线或接受参数。以下命令有**真实副作用**，仅在使用者明确要求此操作时执行：

```console
uv run --locked mijia-ac --config ../ac-local/config.toml set-temp 24 --apply
uv run --locked mijia-ac --config ../ac-local/config.toml set-temp 22 --apply --allow-power-on
uv run --locked mijia-ac --config ../ac-local/config.toml power off --apply
uv run --locked mijia-ac --config ../ac-local/config.toml mode heat --apply
# 另有明确开机许可时才添加 --allow-power-on（set-temp / mode 均支持）
```

最后一条仅在配置 `mode_heat` 后可用，返回匹配只证明云端 mode 值回读，不证明物理制热。`power on` 是明确开机请求，不需额外 `--allow-power-on`。`mode` 先读取状态：关机无许可零写入拒绝；有许可时先显式开机并独立确认 on，再改模式并独立确认 mode 与 on；已开机改模式也核对 on，意外开关变化立即失败。没有“保持关机但先偷偷开机”的选项。

非零退出后停止，向使用者报告失败阶段；在本地检查授权、网络、spec 和设备状态，不把上游原始错误或完整设备清单转发到聊天。回读是即时快照，其他控制端可能并发改变设备；本版不提供事务锁或最终物理状态保证。

## Hermes skill 安装

只安装本仓库 `skills/mijia-ac-control` 目录，不复制 vendor 或任何账号文件到 skill。使用者根据自己 Hermes 安装所配置的 skills 目录，将整个目录复制为 `mijia-ac-control`；重载或重启后确认发现该 skill。本项目不自动修改已有 Hermes 安装。

在 skill 的使用上下文中提供仓库位置与仓库外配置路径；通过 terminal 在仓库根执行上面的 `uv run --locked mijia-ac ...`。普通 pip 安装者可直接执行 `mijia-ac`。技能包含授权、范围核对、关机副作用与失败处理的完整步骤，见 [SKILL.md](skills/mijia-ac-control/SKILL.md)。

## 开发与公开检查

```console
uv sync --locked
uv run --locked pytest -q
uv run --locked python tools/check_public_tree.py
```

测试使用明确标记的虚构 fixtures 和 fake subprocess runner；精确 DID 和整数温度回归接入真实上游 Registry/Device、Property/parse_value 的纯内存对象。仅 `--help` 集成测试启动真实 wrapper 或适配入口，不连米家。GitHub Actions 配置 Ubuntu/Windows/macOS × Python 3.11/3.12，无账号、无 secrets，权限仅 contents:read。不要将该矩阵配置误认为所有平台已经本机跑过。

两个第一方入口 `mijia-ac` 和 `python -m mijia_ac.upstream` 的标准输出、标准错误统一使用 UTF-8，重定向接收端应按 UTF-8 解码；受控 Python 子进程也显式使用 UTF-8。CI 为 pytest 和公开树检查等维护工具设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`；本地旧代码页环境运行维护命令时同样设置。入口回归另行覆盖关闭 UTF-8 模式并指定 cp1252 的环境，帮助文本断言按去除 ANSI 样式后的可见内容验证。

发布检查器检查 git 已跟踪文件（即使已忽略）和未忽略的拟发布文件，拒绝常见凭据文件、真实配置、状态、设备绑定值、私人用户路径、虚拟环境、本地报告和链接；读取暂存 blob 并校验文件模式，同时检查未跟踪候选；工作树与暂存内容不同则拒绝并提示重新审查暂存，避免发布旧内容。vendor 的工作树与暂存快照分别核验全量 SHA256。`.gitattributes` 使一般文本 LF，vendor 禁止 Git 文本转换，逐文件字节以官方固定提交 blob 为准。它是静态防护，仍需人工审查新文件；认证实现中合法的 token 字段不会被当成凭据。开发报告应存仓库外。

目录：

```text
src/mijia_ac/cli.py                标准库 wrapper
skills/mijia-ac-control/SKILL.md    通用 Hermes skill
vendor/mi-home-cli/                原样上游源码与 MIT 许可证
UPSTREAM.json                     来源和逐文件 SHA256
config.example.toml               无设备绑定的配置示例
tests/                            fake runner、入口、公开树、完整性测试
tools/check_public_tree.py        发布候选树检查
.github/workflows/ci.yml           无账号测试矩阵
```

安全说明见 [SECURITY.md](SECURITY.md)，设计与限制见 [DESIGN.md](DESIGN.md)。Skill 编写与验收依据见 [质量约束](docs/skill-quality.md)；实际执行的检查、证据类型和缺口见 [评测说明](skills/mijia-ac-control/references/evaluation.md)。
