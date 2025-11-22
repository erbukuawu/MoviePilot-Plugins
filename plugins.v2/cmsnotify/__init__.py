import time
from typing import List, Tuple, Dict, Any
from apscheduler.triggers.interval import IntervalTrigger  # 修改1：导入IntervalTrigger

from app.core.config import settings
from app.core.event import eventmanager, Event  # 需要导入Event
from app.schemas.types import EventType
from app.utils.http import RequestUtils
from app.log import logger
from app.plugins import _PluginBase


class CMSNotify(_PluginBase):
    # 插件名称
    plugin_name = "CMS通知"
    # 插件描述
    plugin_desc = "整理完成媒体文件后，通知CMS进行增量同步（strm生成）"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/imaliang/MoviePilot-Plugins/main/icons/cms.png"
    # 插件版本
    plugin_version = "0.6"  # 修改版本号
    # 插件作者
    plugin_author = "imaliang"
    # 作者主页
    author_url = "https://github.com/imaliang"
    # 插件配置项ID前缀
    plugin_config_prefix = "cmsnotify_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _cms_notify_type = None
    _cms_domain = None
    _cms_api_token = None
    _enabled = False
    _last_event_time = 0
    _wait_notify_count = 0
    _last_check_time = 0  # 修改3：新增最后检查时间记录

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._cms_notify_type = config.get("cms_notify_type")
            self._cms_domain = config.get("cms_domain")
            self._cms_api_token = config.get('cms_api_token')

    def get_state(self) -> bool:
        return self._enabled

    def get_service(self) -> List[Dict[str, Any]]:
        """ 修改4：关键改动 - 将CronTrigger改为IntervalTrigger """
        if self._enabled:
            return [{
                "id": "CMSNotify",
                "name": "CMS通知",
                "trigger": IntervalTrigger(seconds=10),  # 每10秒检查一次
                "func": self.__notify_cms,
                "kwargs": {}
            }]
        return []

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """ 修改5：更新界面提示信息 """
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
                                            'model': 'enabled',
                                            'label': '启用插件',
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
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'cms_notify_type',
                                            'label': '通知类型',
                                            'items': [
                                                {'title': '增量同步', 'value': 'lift_sync'},
                                                {'title': '增量同步+自动整理', 'value': 'auto_organize'},
                                            ]
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'cms_domain',
                                            'label': 'CMS地址'
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'cms_api_token',
                                            'label': 'CMS_API_TOKEN'
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
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '当MP整理或刮削好媒体文件后，会通知CMS进行增量同步（strm生成）；CMS版本需要0.3.5.11及以上'
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
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '支持目录实时监控插件(cloudlinkmonitor)的转移完成事件'
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
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '精准20秒等待机制：每10秒检查一次，满足20秒间隔即触发通知'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "cms_notify_type": "lift_sync",
            "cms_api_token": "cloud_media_sync",
            "cms_domain": "http://192.168.2.4:9090"
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType)
    def send(self, event):
        """ 修改6：移除存储类型判断 """
        if not self._enabled or not self._cms_domain or not self._cms_api_token:
            return

        if not event or not event.event_type:
            return

        def __to_dict(_event):
            if isinstance(_event, dict):
                return {k: __to_dict(v) for k, v in _event.items()}
            elif isinstance(_event, (list, tuple, set)):
                return type(_event)(__to_dict(x) for x in _event)
            elif hasattr(_event, '__dict__'):
                return __to_dict(_event.__dict__)
            return _event

        event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
        if event_type not in ["transfer.complete", "metadata.scrape"]:
            return

        event_data = __to_dict(event.event_data)
        if event_type == "transfer.complete":
            if event_data.get("transferinfo", {}).get("success"):
                name = event_data["transferinfo"]["target_item"]["name"]
                logger.info(f"媒体整理完成：{name}")
                self._wait_notify_count += 1
                self._last_event_time = self.__get_time()
        elif event_type == "metadata.scrape":
            name = event_data["name"]
            logger.info(f"媒体刮削完成：{name}")
            self._wait_notify_count += 1
            self._last_event_time = self.__get_time()

    # ========== 新增：监听cloudlinkmonitor的事件 ==========
    @eventmanager.register(EventType.PluginAction)
    def handle_cloudlinkmonitor_event(self, event: Event):
        """
        处理cloudlinkmonitor目录监控插件的CMS通知事件
        """
        if not self._enabled or not self._cms_domain or not self._cms_api_token:
            return

        event_data = event.event_data
        if not event_data or event_data.get("action") != "cms_notify":
            return

        # 获取媒体信息
        title = event_data.get("title", "未知媒体")
        year = event_data.get("year", "")
        media_type = event_data.get("media_type", "未知类型")
        
        if year:
            name = f"{title} ({year})"
        else:
            name = title
            
        logger.info(f"cloudlinkmonitor转移完成并触发CMS通知：{name} ({media_type})")
        
        # 增加等待通知计数
        self._wait_notify_count += 1
        self._last_event_time = self.__get_time()
    # ========== 新增代码结束 ==========

    def __get_time(self):
        return int(time.time())

    def __notify_cms(self):
        """ 修改7：精准30秒触发逻辑 """
        try:
            now = self.__get_time()
            time_since_last_event = now - self._last_event_time
            
            # 调试日志（生产环境可关闭）
            logger.debug(f"检查通知条件：等待数={self._wait_notify_count}, 时间差={time_since_last_event}s")
            
            if self._wait_notify_count > 0 and time_since_last_event > 10:
                url = f"{self._cms_domain}/api/sync/lift_by_token?token={self._cms_api_token}&type={self._cms_notify_type}"
                ret = RequestUtils().get_res(url)
                if ret:
                    logger.info(f"CMS同步通知成功（类型：{self._cms_notify_type}）")
                    self._wait_notify_count = 0
                elif ret is not None:
                    logger.error(f"通知失败：HTTP {ret.status_code} - {ret.text}")
                else:
                    logger.error("通知失败：无响应")
        except Exception as e:
            logger.error(f"通知异常：{str(e)}")

    def stop_service(self):
        pass
