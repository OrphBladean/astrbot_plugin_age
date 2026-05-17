# astrbot_plugin_age

一个用于 AstrBot 的年龄计算插件。用户设置一次生日后，可以随时用指令查询当前年龄；支持公历生日，并可选支持农历生日。

## 功能

- 保存每个用户自己的生日信息
- 查询当前周岁年龄
- 支持公历生日
- 支持农历生日换算（依赖 `lunarcalendar`）
- 使用 SQLite 持久化数据，并同步写入 `backup.json`
- 兼容旧版下划线指令格式

## 安装

1. 将本仓库放入 AstrBot 插件目录：

   ```text
   data/plugins/astrbot_plugin_age
   ```

2. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 在 AstrBot 管理面板中重载插件，或重启 AstrBot。

## 指令

| 用途 | 推荐指令 | 兼容旧指令 |
| --- | --- | --- |
| 查看帮助 | `/生日` 或 `/age_help` | - |
| 设置公历生日 | `/age_set 2000.05.13` | `/age_set_2000.05.13` |
| 设置农历生日 | `/age_set_lunar 2000.05.13` | `/age_set_lunar_2000.05.13` |
| 查询年龄 | `/age` | - |

日期也支持 `2000-05-13`、`2000/05/13` 这类写法，插件会统一保存为 `YYYY.MM.DD`。

## 配置

`_conf_schema.json` 中提供了一个配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `enable_lunar` | `true` | 是否允许用户设置农历生日 |

如果关闭 `enable_lunar`，`/age_set_lunar` 会返回“农历生日功能已关闭”。

## 数据存储

插件数据保存在 AstrBot 数据目录下：

```text
data/plugin_data/astrbot_plugin_age/
├── db.sqlite3
└── backup.json
```

迁移机器人时，请一起迁移该目录。数据库读取异常时，插件会尝试从 `backup.json` 读取用户生日。

## 维护说明

早期版本只注册了 `/age` 一个命令，再在消息文本里拆 `_` 判断子命令。部分 AstrBot 版本会把 `/age_set_2000.05.13` 当成独立命令，导致 handler 不命中；同时旧代码在 handler 中 `await` 了带 `yield` 的 async generator，实际执行会报错。

当前版本已显式注册 `/age_set`、`/age_set_lunar`、`/age_help`，并额外保留旧下划线格式的兼容处理。
