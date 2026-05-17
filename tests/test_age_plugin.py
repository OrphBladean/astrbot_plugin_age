import asyncio
import datetime
import importlib.util
import sys
import tempfile
import types
from pathlib import Path


class _Logger:
    def critical(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


class _Filter:
    class EventMessageType:
        ALL = "all"

    @staticmethod
    def command(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    @staticmethod
    def event_message_type(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


class _Star:
    name = "astrbot_plugin_age"

    def __init__(self, context):
        self.context = context


class _FakeEvent:
    def __init__(self, message, sender_id="user-1"):
        self.message_str = message
        self.sender_id = sender_id
        self.stopped = False

    def get_sender_id(self):
        return self.sender_id

    def plain_result(self, text):
        return text

    def stop_event(self):
        self.stopped = True


async def _collect_asyncgen(generator):
    return [item async for item in generator]


def _install_astrbot_stub(data_dir):
    astrbot = types.ModuleType("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_event = types.ModuleType("astrbot.api.event")
    astrbot_star = types.ModuleType("astrbot.api.star")
    astrbot_core = types.ModuleType("astrbot.core")
    astrbot_utils = types.ModuleType("astrbot.core.utils")
    astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")

    astrbot_api.logger = _Logger()
    astrbot_event.AstrMessageEvent = object
    astrbot_event.filter = _Filter
    astrbot_star.Context = object
    astrbot_star.Star = _Star
    astrbot_path.get_astrbot_data_path = lambda: str(data_dir)

    sys.modules.update(
        {
            "astrbot": astrbot,
            "astrbot.api": astrbot_api,
            "astrbot.api.event": astrbot_event,
            "astrbot.api.star": astrbot_star,
            "astrbot.core": astrbot_core,
            "astrbot.core.utils": astrbot_utils,
            "astrbot.core.utils.astrbot_path": astrbot_path,
        }
    )


def _load_plugin(data_dir):
    _install_astrbot_stub(data_dir)
    module_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("age_plugin_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.MyPlugin(None, {"enable_lunar": True})


def test_set_and_query_solar_birthday():
    with tempfile.TemporaryDirectory() as tmp:
        plugin = _load_plugin(tmp)

        assert plugin.set_birthday("user-1", "2000.05.13") == "已保存公历生日：2000.05.13"
        reply = plugin.build_age_reply("user-1", today=datetime.date(2026, 5, 17))

        assert "26 岁" in reply
        assert "公历 2000.05.13" in reply


def test_rejects_invalid_and_future_dates():
    with tempfile.TemporaryDirectory() as tmp:
        plugin = _load_plugin(tmp)

        assert "格式不正确" in plugin.set_birthday("user-1", "2000.02.31")
        assert "晚于今天" in plugin.set_birthday("user-1", "2999.01.01")


def test_reads_backup_when_database_has_no_row():
    with tempfile.TemporaryDirectory() as tmp:
        plugin = _load_plugin(tmp)
        plugin.save_backup("user-1", "2001.01.02", 0)

        reply = plugin.build_age_reply("user-1", today=datetime.date(2026, 1, 1))

        assert "24 岁" in reply
        assert "2001.01.02" in reply


def test_legacy_underscore_command_is_still_supported():
    with tempfile.TemporaryDirectory() as tmp:
        plugin = _load_plugin(tmp)
        event = _FakeEvent("/age_set_2000.05.13")

        results = asyncio.run(_collect_asyncgen(plugin.legacy_underscore_commands(event)))

        assert event.stopped
        assert results == ["已保存公历生日：2000.05.13"]
        assert "2000.05.13" in plugin.build_age_reply("user-1")
