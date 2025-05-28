import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event as ThreadEvent
from typing import List, Tuple, Dict, Any

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.utils.system import SystemUtils
from app.schemas import Notification, NotificationType, MessageChannel

ffmpeg_lock = threading.Lock()


class FFmpegStrmThumb(_PluginBase):
    # 插件名称
    plugin_name = "FFmpegStrm缩略图"
    # 插件描述
    plugin_desc = "TheMovieDb没有背景图片时使用FFmpeg截取strm视频文件缩略图。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/imaliang/MoviePilot-Plugins/main/icons/ffmpegstrm.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "imaliang"
    # 作者主页
    author_url = "https://github.com/imaliang"
    # 插件配置项ID前缀
    plugin_config_prefix = "ffmpegstrmthumb_"
    # 加载顺序
    plugin_order = 4
    # 可使用的用户级别
    user_level = 1

    # 私有属性
    _scheduler = None
    _enabled = False
    _onlyonce = False
    _cron = None
    _timeline = "00:03:01"
    _scan_paths = ""
    _exclude_paths = ""
    _overlay = False
    _gen_strategy = "100=60"
    _gen_strategy_count = 0
    _gen_strategy_max_count = 100
    _gen_strategy_delay = 60
    # 退出事件
    _event = ThreadEvent()

    def init_plugin(self, config: dict = None):
        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._cron = config.get("cron")
            self._timeline = config.get("timeline")
            self._scan_paths = config.get("scan_paths") or ""
            self._exclude_paths = config.get("exclude_paths") or ""
            self._overlay = config.get("overlay") or False
            self._gen_strategy = config.get("gen_strategy") or "100=60"
            gen_strategy = self._gen_strategy.split("=")
            self._gen_strategy_max_count = int(gen_strategy[0])
            self._gen_strategy_delay = int(gen_strategy[1])

        # 停止现有任务
        self.stop_service()

        # 启动定时任务 & 立即运行一次
        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._cron:
                logger.info(f"FFmpegStrm缩略图服务启动，周期：{self._cron}")
                try:

                    self._scheduler.add_job(func=self.__libraryscan,
                                            trigger=CronTrigger.from_crontab(
                                                self._cron),
                                            name="FFmpegStrm缩略图",
                                            args=[False])
                except Exception as e:
                    logger.error(f"FFmpegStrm缩略图服务启动失败，原因：{str(e)}")
                    self.systemmessage.put(
                        f"FFmpegStrm缩略图服务启动失败，原因：{str(e)}", title="FFmpegStrm缩略图")
            if self._onlyonce:
                logger.info(f"FFmpegStrm缩略图服务，立即运行一次")
                is_overlay = self._overlay
                self._scheduler.add_job(func=self.__libraryscan, trigger='date',
                                        run_date=datetime.now(tz=pytz.timezone(
                                            settings.TZ)) + timedelta(seconds=3),
                                        name="FFmpegStrm缩略图",
                                        args=[is_overlay])
                # 关闭一次性开关
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "enabled": self._enabled,
                    "cron": self._cron,
                    "timeline": self._timeline,
                    "scan_paths": self._scan_paths,
                    "exclude_paths": self._exclude_paths,
                    "overlay": self._overlay,
                    "gen_strategy": self._gen_strategy,
                })
            if self._scheduler.get_jobs():
                # 启动服务
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                                    'md': 4
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
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'overlay',
                                            'label': '覆盖生成',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
               
