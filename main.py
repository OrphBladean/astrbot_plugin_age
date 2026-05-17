# =========================
# 导入库
# =========================

import datetime
import json
import sqlite3
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# =========================
# 农历支持
# =========================

try:
    from lunarcalendar import Lunar, Converter
    LUNAR_SUPPORT = True
except ImportError:
    LUNAR_SUPPORT = False


# =========================
# 插件主类
# =========================

class MyPlugin(Star):

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.enable_lunar = config.get("enable_lunar", True)

        base = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        base.mkdir(parents=True, exist_ok=True)

        self.DB_PATH = base / "db.sqlite3"
        self.BACKUP_PATH = base / "backup.json"

        self.init_db()

    # =========================
    # 数据库
    # =========================

    def init_db(self):
        try:
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_birthday (
                    user_id TEXT PRIMARY KEY,
                    birth_date TEXT NOT NULL,
                    is_lunar INTEGER NOT NULL
                )
            """)
            cursor.execute("PRAGMA journal_mode=WAL")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.critical(f"db_init_failed:{e}")

    def load_backup(self):
        if not self.BACKUP_PATH.exists():
            return {}
        try:
            with open(self.BACKUP_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.critical(f"backup_load_failed:{e}")
            return {}

    def save_backup(self, user_id, birth_date, is_lunar):
        try:
            data = self.load_backup()
            data.setdefault("user_birthday", {})
            data["user_birthday"][user_id] = {
                "birth_date": birth_date,
                "is_lunar": is_lunar
            }
            with open(self.BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"backup_save_failed:{e}")

    def save_user(self, user_id, birth_date, is_lunar):
        try:
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_birthday
                (user_id, birth_date, is_lunar)
                VALUES (?, ?, ?)
            """, (user_id, birth_date, is_lunar))
            conn.commit()
            conn.close()
            self.save_backup(user_id, birth_date, is_lunar)
        except Exception as e:
            logger.critical(f"save_user_failed:{e}")

    def get_user(self, user_id):
        try:
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT birth_date, is_lunar FROM user_birthday WHERE user_id=?",
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()
            return row
        except Exception:
            backup = self.load_backup()
            return backup.get("user_birthday", {}).get(user_id)

    # =========================
    # 指令区
    # =========================

    @filter.command("生日")
    async def shengri(self, event: AstrMessageEvent):
        """
        /生日
        仅展示指令对照表
        """
        text = (
            "📖 年龄插件指令说明\n"
            "──────────────\n"
            "设置生日（公历）\n"
            "/age_set_2000.05.13\n"
            "\n"
            "设置生日（农历）\n"
            "/age_set_lunar_2000.05.13\n"
            "\n"
            "查询年龄\n"
            "/age\n"
            "\n"
            "查看帮助\n"
            "/age_help"
        )
        yield event.plain_result(text)

    @filter.command("age")
    async def age(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split("_")
        user_id = event.get_sender_id()

        if len(parts) == 1:
            await self._query(user_id, event)
            return

        if parts[1] == "help":
            yield event.plain_result("查看 使用说明_普通用户.txt")
            return

        if parts[1] == "set":
            await self._set(user_id, parts, event)
            return

        yield event.plain_result("invalid_command")

    async def _set(self, user_id, parts, event):
        try:
            is_lunar = False
            date_part = parts[-1]

            if "lunar" in parts:
                if not self.enable_lunar:
                    yield event.plain_result("lunar_disabled")
                    return
                is_lunar = True

            y, m, d = map(int, date_part.split("."))
            birth_date = f"{y:04d}.{m:02d}.{d:02d}"

            self.save_user(user_id, birth_date, is_lunar)
            yield event.plain_result(
                f"birthday_saved:{birth_date}"
                f"{'_lunar' if is_lunar else ''}"
            )
        except Exception:
            yield event.plain_result("invalid_format")

    async def _query(self, user_id, event):
        row = self.get_user(user_id)
        if not row or len(row) != 2:
            yield event.plain_result("no_birthday_found")
            return

        birth_date_str, is_lunar = row
        y, m, d = map(int, birth_date_str.split("."))

        try:
            if is_lunar and LUNAR_SUPPORT:
                lunar = Lunar(y, m, d)
                solar = Converter.Lunar2Solar(lunar)
                birth = datetime.date(solar.year, solar.month, solar.day)
            else:
                birth = datetime.date(y, m, d)
        except Exception:
            yield event.plain_result("invalid_birthday_data")
            return

        today = datetime.date.today()
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1

        yield event.plain_result(
            f"age:{age}_birth:{birth_date_str}"
        )

    async def terminate(self):
        logger.info("plugin_age_unloaded")