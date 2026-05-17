import datetime
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

try:
    from lunarcalendar import Converter, Lunar

    LUNAR_SUPPORT = True
except ImportError:
    LUNAR_SUPPORT = False


HELP_TEXT = (
    "年龄插件指令说明\n"
    "----------------\n"
    "设置生日（公历）：/age_set 2000.05.13\n"
    "设置生日（农历）：/age_set_lunar 2000.05.13\n"
    "查询年龄：/age\n"
    "查看帮助：/age_help\n"
    "\n"
    "兼容旧格式：/age_set_2000.05.13、/age_set_lunar_2000.05.13"
)


class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config or {}
        self.enable_lunar = self.config.get("enable_lunar", True)

        base = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        base.mkdir(parents=True, exist_ok=True)

        self.DB_PATH = base / "db.sqlite3"
        self.BACKUP_PATH = base / "backup.json"

        self.init_db()

    def init_db(self):
        try:
            with closing(sqlite3.connect(self.DB_PATH)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_birthday (
                        user_id TEXT PRIMARY KEY,
                        birth_date TEXT NOT NULL,
                        is_lunar INTEGER NOT NULL
                    )
                    """
                )
                conn.commit()
        except Exception as e:
            logger.critical(f"db_init_failed:{e}")

    def load_backup(self):
        if not self.BACKUP_PATH.exists():
            return {}
        try:
            with open(self.BACKUP_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.critical(f"backup_load_failed:{e}")
            return {}

    def save_backup(self, user_id, birth_date, is_lunar):
        try:
            data = self.load_backup()
            data.setdefault("user_birthday", {})
            data["user_birthday"][str(user_id)] = {
                "birth_date": birth_date,
                "is_lunar": int(bool(is_lunar)),
            }
            with open(self.BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"backup_save_failed:{e}")

    def save_user(self, user_id, birth_date, is_lunar):
        is_lunar_value = int(bool(is_lunar))
        try:
            with closing(sqlite3.connect(self.DB_PATH)) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_birthday
                    (user_id, birth_date, is_lunar)
                    VALUES (?, ?, ?)
                    """,
                    (str(user_id), birth_date, is_lunar_value),
                )
                conn.commit()
            self.save_backup(user_id, birth_date, is_lunar_value)
            return True
        except Exception as e:
            logger.critical(f"save_user_failed:{e}")
            return False

    def get_user(self, user_id):
        try:
            with closing(sqlite3.connect(self.DB_PATH)) as conn:
                row = conn.execute(
                    "SELECT birth_date, is_lunar FROM user_birthday WHERE user_id=?",
                    (str(user_id),),
                ).fetchone()
            if row:
                return row
        except Exception as e:
            logger.error(f"db_read_failed:{e}")

        backup = self.load_backup()
        row = backup.get("user_birthday", {}).get(str(user_id))
        if isinstance(row, dict):
            return row.get("birth_date"), row.get("is_lunar", 0)
        return row

    @filter.command("生日")
    async def birthday_help(self, event: AstrMessageEvent):
        yield event.plain_result(HELP_TEXT)

    @filter.command("age_help")
    async def age_help(self, event: AstrMessageEvent):
        yield event.plain_result(HELP_TEXT)

    @filter.command("age")
    async def age(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        yield event.plain_result(self.build_age_reply(user_id))

    @filter.command("age_set")
    async def age_set(self, event: AstrMessageEvent, date_part: str = ""):
        user_id = event.get_sender_id()
        yield event.plain_result(self.set_birthday(user_id, date_part, is_lunar=False))

    @filter.command("age_set_lunar")
    async def age_set_lunar(self, event: AstrMessageEvent, date_part: str = ""):
        user_id = event.get_sender_id()
        yield event.plain_result(self.set_birthday(user_id, date_part, is_lunar=True))

    @filter.event_message_type(filter.EventMessageType.ALL, priority=sys.maxsize - 1)
    async def legacy_underscore_commands(self, event: AstrMessageEvent):
        message = event.message_str.strip()
        if not message.startswith("/"):
            return

        command_text = message[1:].split(maxsplit=1)[0]
        user_id = event.get_sender_id()

        if command_text.startswith("age_set_lunar_"):
            date_part = command_text.removeprefix("age_set_lunar_")
            event.stop_event()
            yield event.plain_result(self.set_birthday(user_id, date_part, is_lunar=True))
            return

        if command_text.startswith("age_set_"):
            date_part = command_text.removeprefix("age_set_")
            event.stop_event()
            yield event.plain_result(self.set_birthday(user_id, date_part, is_lunar=False))
            return

    def set_birthday(self, user_id, date_part, is_lunar=False):
        if is_lunar and not self.enable_lunar:
            return "农历生日功能已关闭。"
        if is_lunar and not LUNAR_SUPPORT:
            return "农历依赖未安装，请管理员安装 requirements.txt 中的 lunarcalendar。"

        parsed = self.parse_birth_date(date_part, is_lunar)
        if parsed is None:
            return "格式不正确，请使用 /age_set 2000.05.13 或 /age_set_lunar 2000.05.13。"

        birth_date, _ = parsed
        if parsed[1] > datetime.date.today():
            return "生日不能晚于今天。"

        if not self.save_user(user_id, birth_date, is_lunar):
            return "保存失败，请稍后重试或联系管理员查看日志。"

        calendar_name = "农历" if is_lunar else "公历"
        return f"已保存{calendar_name}生日：{birth_date}"

    def build_age_reply(self, user_id, today=None):
        row = self.get_user(user_id)
        if not row or len(row) != 2:
            return "还没有保存生日，请先发送 /age_set 2000.05.13。"

        birth_date_str, is_lunar = row
        if bool(is_lunar) and not LUNAR_SUPPORT:
            return "当前环境缺少农历依赖，暂时无法计算农历生日。"

        parsed = self.parse_birth_date(birth_date_str, bool(is_lunar))
        if parsed is None:
            return "已保存的生日数据无效，请重新设置。"

        normalized_birth_date, birth = parsed
        today = today or datetime.date.today()
        age = today.year - birth.year
        birthday_this_year = self.get_birthday_in_year(
            normalized_birth_date, bool(is_lunar), today.year
        )
        if birthday_this_year is None:
            return "已保存的生日数据无效，请重新设置。"
        if today < birthday_this_year:
            age -= 1

        calendar_name = "农历" if bool(is_lunar) else "公历"
        return f"你现在 {age} 岁，保存的生日是{calendar_name} {birth_date_str}。"

    def get_birthday_in_year(self, birth_date_str, is_lunar, year):
        try:
            _, m, d = [int(part) for part in birth_date_str.split(".")]
            if is_lunar:
                lunar = Lunar(year, m, d)
                solar = Converter.Lunar2Solar(lunar)
                return datetime.date(solar.year, solar.month, solar.day)
            return datetime.date(year, m, d)
        except (TypeError, ValueError):
            return None

    def parse_birth_date(self, date_part, is_lunar=False):
        if not date_part:
            return None

        try:
            y, m, d = [int(part) for part in date_part.replace("-", ".").replace("/", ".").split(".")]
            birth_date = f"{y:04d}.{m:02d}.{d:02d}"

            if is_lunar:
                if not LUNAR_SUPPORT:
                    logger.error("lunar_support_missing")
                    return None
                lunar = Lunar(y, m, d)
                solar = Converter.Lunar2Solar(lunar)
                birth = datetime.date(solar.year, solar.month, solar.day)
            else:
                birth = datetime.date(y, m, d)

            return birth_date, birth
        except (TypeError, ValueError):
            return None

    async def terminate(self):
        logger.info("plugin_age_unloaded")
