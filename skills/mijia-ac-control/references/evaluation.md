# 维护与评测

修改 Skill 的触发描述、执行流程或准备发布时阅读。评测只使用公开的虚构 fixture；真实账号、设备清单和控制日志不得作为提交材料。

## 离线检查

在仓库根运行：

```console
uv sync --locked
uv run --locked mijia-ac --help
uv run --locked pytest -q
uv run --locked python tools/check_public_tree.py
```

`pytest` 使用 fake runner 验证控制顺序，真实子进程仅运行 `--help`，不访问设备。`check_public_tree.py` 同时比较暂存区与工作区；先审查并暂存候选文件再运行。检查通过后仍要人工核对最终提交和打包内容，尤其是新文件、私有路径与凭据。公开范围见仓库 README 的“公开仓库与维护”。

## Skill 行为证据

- `evals/trigger_cases.json` 包含中英文正例、反例和相近请求。改动 `description` 后重新运行触发检查，并检查是否误触发室温测量、自动恒温等请求。
- `evals/output/cases.jsonl` 是**记录式样例**。现有 `baseline_output` 与 `with_skill_output` 相同；它只检验场景字段和负向变异，不能证明 Skill 优于无 Skill 的模型输出。
- 命令测试、记录式样例、真实模型运行、真实设备效果是不同证据。当前仓库不提供后两种证据，不应把静态检查或 CI 矩阵写成物理控制已验证。

需要使用 Yao Meta Skill 检查结构、资源边界、触发、输出和信任时，以本目录为目标，先核对该工具版本的 `--help`。将生成的报告写在仓库外；工具在当前平台不可用时记录实际错误，继续使用上面的独立检查，不伪造通过结果。

## 发布边界

公开发布应包含 `SKILL.md`、执行所需的 `references/`、无真实绑定的配置示例、CLI 与固定上游源码、版权声明和离线测试。供 Agent 装载的 Skill 目录是 `skills/mijia-ac-control/`；它不包含 Python CLI、配置或授权状态。用户应先在本机审查来源，再分别准备 CLI 与 Skill，并按所用 Agent 的发现规则安装。
