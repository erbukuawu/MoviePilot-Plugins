import threading
from typing import Any, List, Dict, Tuple
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.db.transferhistory_oper import TransferHistoryOper
from app.log import logger
from app.plugins import _PluginBase

lock = threading.Lock()


class HistoryClear(_PluginBase):
    # 插件名称
    plugin_name = "历史记录清理"
    # 插件描述
    plugin_desc = "支持手动或定时清理历史记录。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/InfinityPacer/MoviePilot-Plugins/main/icons/historyclear.png"
    # 插件版本
    plugin_version = "1.1"
    # 插件作者
    plugin_author = "InfinityPacer"
    # 作者主页
    author_url = "https://github.com/InfinityPacer"
    # 插件配置项ID前缀
    plugin_config_prefix = "historyclear_"
    # 加载顺序
    plugin_order = 61
    # 可使用的用户级别
    auth_level = 1
    # history_oper
    _history_oper = None

    # 配置项
    _clear_history = False  # 手动清理开关
    _enable_schedule = False  # 定时任务开关
    _cron_expression = "0 3 * * *"  # 默认每天凌晨3点执行

    def init_plugin(self, config: dict = None):
        self._history_oper = TransferHistoryOper()
        if not config:
            return

        # 加载配置
        self._clear_history = config.get("clear_history", False)
        self._enable_schedule = config.get("enable_schedule", False)
        self._cron_expression = config.get("cron_expression", "0 3 * * *")

        # 手动触发清理
        if self._clear_history:
            # 只更新clear_history字段，保留其他配置
            current_config = self.get_config() or {}
            current_config["clear_history"] = False
            self.update_config(current_config)
            self.__clear()

    def get_state(self) -> bool:
        return self._enable_schedule

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        新增定时任务配置选项
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'clear_history',
                                            'label': '立即清理',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enable_schedule',
                                            'label': '启用定时清理',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron_expression',
                                            'label': '定时任务表达式',
                                            'placeholder': '例如：0 3 * * *（每天凌晨3点）',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'error',
                                            'variant': 'tonal',
                                            'text': '警告：清理后数据无法恢复，请谨慎操作！'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "clear_history": False,
            "enable_schedule": False,
            "cron_expression": "0 3 * * *",
            "notify": True
        }

    def get_page(self) -> List[dict]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册定时任务服务
        """
        if not self._enable_schedule:
            return []

        return [{
            "id": "HistoryClear",
            "name": "历史记录定时清理",
            "trigger": CronTrigger.from_crontab(self._cron_expression),
            "func": self.__clear,
            "kwargs": {}
        }]

    def stop_service(self):
        """
        停止插件时关闭定时任务
        """
        pass

    def __clear(self):
        """执行清理逻辑"""
        try:
            logger.info("开始清理历史记录")
            self._history_oper.truncate()
            self.__log_and_notify("历史记录已清理")
        except Exception as e:
            self.__log_and_notify(f"清理失败：{e}")

    def __log_and_notify(self, message):
        """记录日志并发送通知"""
        logger.info(message)
        self.systemmessage.put(message, title="历史记录清理")
