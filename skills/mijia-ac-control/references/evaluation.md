# 维护与评测分支

修改 description、流程或准备公开分发时读取。owner：yyyzl；每次发布前及至少每季度审查。按 Library 维护策略管理，当前 experimental，不代表所有发布门禁已通过。

范围锁定为本仓库 skills/mijia-ac-control。评测引擎及已安装私人同名 skill 保持只读。参考源限定五类：writing-for-agents（含格式机制）、yao-meta-skill（含方法 references）、本项目 CLI/schema、固定上游 cli-spec、docs/skill-quality.md。仅提炼按分支披露、完成条件、安全授权、输出证据，不复制元技能或客户端适配器。

## 可复跑检查

在仓库根执行 `uv sync --locked`、`uv run --locked mijia-ac --help`、`uv run --locked pytest -q`、`uv run --locked python tools/check_public_tree.py`。后台测试使用 60 秒上限。fake runner 验证动作序列；真实子进程控制测试仅 --help。索引回归使用 scratch 中的独立虚构 fixture 仓库。工作树和索引内容不同须审查后重新暂存；一般文本按 Git attributes 规范化，vendor 则逐字节一致。

Yao 引擎另行安装并保持只读，以 `python -B` 执行下面脚本；先查真实 --help，报告路径显式指向仓库外 scratch（以下 ENGINE/TARGET/OUT 是变量，不是发布内容中的私人路径）：

- resource_boundary_check.py TARGET --max-initial-tokens 1300；context_sizer.py TARGET --json（stdout 重定向 OUT）。
- trigger_eval.py --description DESCRIPTION --cases TARGET/evals/trigger_cases.json --semantic-config TARGET/evals/semantic-config.json（DESCRIPTION 从当前 frontmatter 提取，仅评估描述，不把整份 SKILL.md 当作描述；stdout 重定向 OUT）。
- export_skill_ir.py TARGET --output-json OUT/skill-ir.json。
- trust_check.py TARGET --output-json OUT/trust.json --output-md OUT/trust.md。
- validate_skill.py TARGET：缺 PyYAML 时使用 `uv run --no-project --python 3.12 --with PyYAML==6.0.3 python -B ENGINE/validate_skill.py TARGET`；不修改项目依赖。
- run_output_eval.py --cases TARGET/evals/output/cases.jsonl，并显式传 --output-json、--output-md、--blind-pack-json、--blind-pack-md、--blind-answer-key-json 到 OUT。

## 证据解释与当前缺口

`evals/trigger_cases.json` 包含中英正例、反例、近邻；semantic-config 是静态词汇代理，不是模型路由。`evals/output/cases.jsonl` 是人工记录式 fixture，覆盖相对调温、预览、关机未许可、失败、模式开关副作用、室温误认。两个输出栏相同，delta=0；断言和 pytest 的字段/场景/负向变异检查可执行，不声称模型提升。command 证据来自实际 pytest、安装入口和构建；model 证据缺失。

本机独立检查：结构、资源边界、上下文、静态 trigger、IR、输出断言与 skill-only trust 检查通过。描述压缩至 44 字符，静态词汇代理的 18 例无误触发或漏触发；这不是模型路由效果。agents/interface.yaml 仅声明通用 Markdown 的中性接口、禁止远端内联执行和元数据降级，不生成额外客户端适配器或原生权限沙箱。结构检查保留 canonical Skill IR 来源回退警告；trust 保留 skill 内没有独立锁文件的警告。实际依赖锁位于仓库根 uv.lock，wrapper 网络/子进程边界由仓库测试和独立审查覆盖，skill-only trust 不能替代整仓库审计。上下文估算器将 JSONL 标为 binary_or_other，输出检查器和 pytest 单独覆盖该数据。

missing evidence：统一 CLI 在 Windows 导入 fcntl 失败；完整 SkillOS2 compiler、Atlas、conformance、governance/promotion、package/install adapter、upgrade、drift、waiver、Review Studio、优化描述与盲测/route confusion 尚未运行或缺真实审查数据。未请求额外适配器的运行权限探针不适用；不能声称完整 SkillOS2 发布通过。盲审包已生成但无人判定，真实模型与物理设备证据仍缺失。三系统 × Python 3.11/3.12 的真实通过状态以对应提交的 Actions 结果为准；配置矩阵或触发运行不等于通过。

独立 scratch 快照与干净检出核验上游 blob、vendor SHA256 和候选内容；wheel 仅 wrapper，sdist 必须含 vendor 源码、原始 MIT 许可证和 skill。维护者人工审查后安排发布。评测过程不提交或推送，也不访问账号或设备。原始报告默认不进入 Git；只发布去标识摘要和复跑方法。
