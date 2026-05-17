# 年龄计算插件 · 管理员文档

## 一、设计原则

- `/生日` → **仅展示指令对照表**
- `/age*` → **真正执行业务逻辑**
- 不做隐式行为
- 不修改用户数据

---

## 二、指令对照表（给用户看的）

| 中文含义 | 实际指令 |
|---|---|
| 查看指令说明 | `/生日` |
| 设置公历生日 | `/age_set 2000.05.13` |
| 设置农历生日 | `/age_set_lunar 2000.05.13` |
| 查询年龄 | `/age` |
| 查看帮助 | `/age_help` |

---

## 三、指令逻辑说明

### `/生日`
- 不做任何数据操作
- 不访问数据库
- 只返回纯文本说明

### `/age_set` / `/age_set_lunar`
1. 校验日期
2. 写入 SQLite
3. 写入 backup.json
4. 返回结果

### `/age`
1. 读取 SQLite
2. 失败则读 backup.json
3. 计算年龄
4. 返回结果

---

## 四、数据存储

```
data/plugin_data/astrbot_plugin_age/
├── db.sqlite3
└── backup.json
```

---

## 五、迁移与恢复

- 迁移服务器：连同 plugin_data 一起迁移
- 数据库损坏：自动从 backup.json 恢复
- 两文件都坏：需用户重新设置

---

## 六、日志关键字

- db_init_failed
- backup_load_failed
- save_user_failed
