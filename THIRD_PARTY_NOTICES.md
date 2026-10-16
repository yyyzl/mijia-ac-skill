# 第三方声明

`vendor/mi-home-cli` 来自 slightc 的 [mi_home_cli](https://github.com/slightc/mi_home_cli)：

- tag：v0.1.3
- commit：c1a42765a7ad5f53ce5cd9296b877a26671f1f5f
- 许可证：MIT，Copyright (c) 2026 slightc
- 原始许可证完整保留在 `vendor/mi-home-cli/LICENSE`；上游源码未修改。
- 复制范围：官方 src、pyproject.toml、LICENSE、README.md、README.en.md，以及 README 所链接的必要 docs。
- 本地相对源路径及逐文件 SHA256 见根 `UPSTREAM.json`。没有复制上游 .git、.claude、.github、tools、缓存、环境或运行状态。

根 LICENSE 中 yyyzl 的版权适用于本项目新增 wrapper、技能、文档和测试，不替代或重新署名上游作品。上游 README 描述的是其自身能力，并不扩大本 wrapper 的支持范围或实测结论。

依赖树由 uv.lock 记录；httpx、typer、rich、paho-mqtt、cryptography、segno 等依赖并未复制入 vendor，其许可证由各依赖发行包提供。
