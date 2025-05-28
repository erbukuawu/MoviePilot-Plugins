import random
import re
import time
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger
from app.schemas.types import EventType
from app.utils.http import RequestUtils
from app.schemas import Notification, NotificationType, MessageChannel


class SSDForumSignin(_PluginBase):
    # 插件名称
    plugin_name = "SSDForum签到"
    # 插件描述
    plugin_desc = "SSDForum自动签到，支持随机延迟。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/imaliang/MoviePilot-Plugins/main/icons/ssdforum.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "imaliang"
    # 作者主页
    author_url = "https://github.com/imaliang"
    # 插件配置项ID前缀
    plugin_config_prefix = "ssdforumsignin_"
    # 加载顺序
    plugin_order = 3
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    # 任务执行间隔
    _cron = None
    _cookie = None
    _onlyonce = False
    _notify = False
    _history_days = None
    _random_delay = None
    _clear = False
    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    # 事件管理器
    # event: EventManager = None

    def init_plugin(self, config: dict = None):
        # self.event = EventManager()
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._cookie = config.get("cookie")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")
            self._history_days = config.get("history_days") or 30
            self._random_delay = config.get("random_delay")
            self._clear = config.get("clear")

        # 清除历史
        if self._clear:
            self.del_data('history')
            self._clear = False
            self.__update_config()

        if self._onlyonce:
            # 定时服务
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info(f"SSDForum签到服务启动，立即运行一次")
            self._scheduler.add_job(func=self.signin, trigger='date',
                                    run_date=datetime.now(tz=pytz.timezone(
                                        settings.TZ)) + timedelta(seconds=5),
                                    name="SSDForum签到")
            # 关闭一次性开关
            self._onlyonce = False
            self.__update_config()

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def __update_config(self):
        self.update_config({
            "onlyonce": False,
            "cron": self._cron,
            "enabled": self._enabled,
            "cookie": self._cookie,
            "notify": self._notify,
            "history_days": self._history_days,
            "random_delay": self._random_delay,
            "clear": self._clear
        })

    def __send_fail_msg(self, text):
        logger.info(text)
        if self._notify:
            sign_time = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
            self.post_message(
                mtype=NotificationType.Plugin,
                title="🏷︎ SSDForum签到 ✴️",
                text=f"执行时间：{sign_time}\n"
                f"{text}")

    def __send_success_msg(self, text):
        logger.info(text)
        if self._notify:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="🏷︎ SSDForum签到 ✅",
                text=text)

    @eventmanager.register(EventType.PluginAction)
    def signin(self, event: Event = None):
        """
        SSDForum签到
        """
        if event:
            event_data = event.event_data
            if not event_data or event_data.get("action") != "ssdforum_signin":
                return
            logger.info("收到命令，开始执行...")

        _url = "ssdforum.org"
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                   'Accept - Encoding': 'gzip, deflate, br',
                   'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                   'cache-control': 'max-age=0',
                   'Upgrade-Insecure-Requests': '1',
                   'Host': _url,
                   'Cookie': self._cookie,
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62'}

        res = RequestUtils(headers=headers).get_res(
            url='https://' + _url + '/dsu_paulsign-sign.html?mobile=no')
        if not res or res.status_code != 200:
            self.__send_fail_msg("获取基本信息失败-status_code=" + res.status_code)
            return

        user_info = res.text
        user_name = re.search(r'title="访问我的空间">(.*?)</a>', user_info)
        if user_name:
            user_name = user_name.group(1)
            logger.info("登录用户名为：" + user_name)
        else:
            self.__send_fail_msg("未获取到用户名-cookie或许已失效")
            return

        is_sign = re.search(r'(您今天已经签到过了或者签到时间还未开始)', user_info)
        if is_sign:
            self.__send_success_msg("您今天已经签到过了或者签到时间还未开始")
            return

        # 使用正则表达式查找 formhash 的值
        formhash_value = re.search(
            r'<input[^>]*name="formhash"[^>]*value="([^"]*)"', user_info)

        if formhash_value:
            formhash_value = formhash_value.group(1)
            logger.info("formhash：" + formhash_value)
        else:
            self.__send_fail_msg("未获取到 formhash 值")
            return

        totalContinuousCheckIn = re.search(
            r'<p>您本月已累计签到:<b>(.*?)</b>', user_info)
        if totalContinuousCheckIn:
            totalContinuousCheckIn = int(totalContinuousCheckIn.group(1)) + 1
            logger.info(f"您本月已累计签到：{totalContinuousCheckIn}")
        else:
            totalContinuousCheckIn = 1

        # 随机获取心情
        default_text = "一别之后，两地相思，只道是三四月，又谁知五六年。"
        max_attempts = 10
        xq = RequestUtils().get_res("https://v1.hitokoto.cn/?encode=text").text
        attempts = 1  # 初始化计数器
        logger.info(f"尝试想说的话-{attempts}: {xq}")

        # 保证字数符合要求并且不超过最大尝试次数
        while (len(xq) < 6 or len(xq) > 50) and attempts < max_attempts:
            xq = RequestUtils().get_res("https://v1.hitokoto.cn/?encode=text").text
            attempts += 1
            logger.info(f"尝试想说的话-{attempts}: {xq}")

        # 如果循环结束后仍不符合要求，使用默认值
        if len(xq) < 6 or len(xq) > 50:
            xq = default_text

        logger.info("最终想说的话：" + xq)

        # 获取签到链接,并签到
        qd_url = 'plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1'

        qd_data = {
            "formhash": formhash_value,
            "qdxq": "kx",
  
