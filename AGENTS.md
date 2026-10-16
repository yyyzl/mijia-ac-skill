# 维护约定

使用简体中文说明。只修改本仓库；不要读取或复制真实米家授权、设备列表和其他 skill 的状态。所有例子与测试采用明确虚构 fixture。

新增控制行为必须先添加测试并实际观察 RED，再最小实现观察 GREEN。测试只使用 fake runner；真实子进程仅限 --help，不能访问真实账号或设备。后台测试上限 60 秒。

保持 vendor/mi-home-cli 原样；上游升级需核对官方版本、逐文件哈希、版权及锁文件，不通过改上游行为让 wrapper 测试通过。

新参数同步 README、配置示例、SKILL.md 与测试。写操作默认预览，实际写入必须 --apply，关机调温另需 --allow-power-on；写后始终独立回读，失败立即停止。

发布前运行 uv sync --locked、pytest 与 tools/check_public_tree.py，人工检查候选文件及打包内容。不得提交真实配置、state、auth、token、设备 DID、私人路径、虚拟环境或本地报告。发布操作须由维护者审查安排。
