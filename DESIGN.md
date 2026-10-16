# 设计说明

## 设计目标

以少量标准库代码提供可审计的设温流程，保留上游 CLI 能力和版权。用户明确配置、每次明确授权；预览零子进程，测试零账号。

## 架构与关键决策

terminal → argparse → TOML Config → Controller → 当前 Python 的固定 CLI 入口 → mi-home-cli cloud。

- 配置文件必填，状态目录按文件位置解析且拒绝仓库内部；避免复用默认账号和提交授权。
- 温度边界、步长必填，Decimal 校验；所有数字有限且限制数量级以控制计算成本。timeout 不超过 120 秒。
- 直接使用 full English property names 的 raw `get` JSON；不解析本地化表格，不猜测模式枚举。
- 子进程使用参数列表、shell=False、有限 timeout；清除继承的 MI_* 和 Python 路径覆盖变量，显式指定 profile/cloud/state。
- 默认本地预览，而非上游 dry-run，避免上游解析设备时访问授权/缓存。真正写入统一 --verify，然后再独立 get。
- 关机设温分两次写入，开机确认后才设温；写入失败或回读不匹配终止，不自动补偿或重复写入。
- status 只公开 bool on、数字 temperature、整数 mode。上游 stdout/stderr 仅内部使用，失败只返回固定摘要。
- runner 注入隔离硬件与网络；真实子进程测试仅 --help。

## 方案选择与权衡

用固定 `sys.executable -c` 导入入口，避免 PATH 指向其他安装以及上游没有包级 -m 入口。保留独立 vendor 包而不合并源码，uv 用本地 source 路由，pip 分两步安装。

## 已知限制

只支持 cloud 及三项可读的标准类型属性。模式值必须来自用户 spec；不承诺物理制热。不提供房温闭环、ESP32、重试、事务锁或回滚。设备和云端可能延迟或被其他控制端修改；即时回读成功不等于物理执行完成。子进程总 timeout 可能比多次上游 verify 请求更短，超时一律停止并人工核对。

公开检查是防误提交的静态启发式检查，非通用秘密扫描器；不匹配已知模式的数据仍需审查。vendor manifest 应与固定官方来源逐文件比对，不能通过重新生成清单掩盖改动。

## 变更历史

- 2026-10-16，0.1.0：新建独立 wrapper、通用 skill 与 fake runner 测试；采用显式开机授权和两级回读，避免调温意外开机或把下发成功当执行成功。影响范围仅本仓库；未改固定上游源码。
