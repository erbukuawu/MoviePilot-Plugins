import json
import random
import re
import subprocess
import time
from datetime import datetime, timedelta
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import Notification, NotificationType, MessageChannel


class CustomCommandPlus(_PluginBase):
    # 插件名称
    plugin_name = "自定义命令自用版"
    # 插件描述
    plugin_desc = "自定义执行周期执行命令并推送结果。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/imaliang/MoviePilot-Plugins/main/icons/bot.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "imaliang"
    # 作者主页
    author_url = "https://github.com/imaliang"
    # 插件配置项ID前缀
    plugin_config_prefix = "customcommandplus_"
    # 加载顺序
    plugin_order = 5
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = False
    _clear: bool = False
    _msgtype: str = None
    _time_confs = None
    _history_days = None
    _notify_keywords = None
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._msgtype = config.get("msgtype")
            self._clear = config.get("clear")
            self._history_days = config.get("history_days") or 30
            self._notify_keywords = config.get("notify_keywords")
            self._time_confs = config.get("time_confs")

            # 清除历史
            if self._clear:
                self.del_data('history')
                self._clear = False
                self.__update_config()

            if (self._enabled or self._onlyonce) and self._time_confs:
                # 周期运行
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                # 分别执行命令，输入结果
                for time_conf in self._time_confs.split("\n"):
                    if time_conf:
                        if str(time_conf).startswith("#"):
                            logger.info(f"已被注释，跳过 {time_conf}")
                            continue
                        if str(time_conf).count("#") == 2 or str(time_conf).count("#") == 3:
                            name = str(time_conf).split("#")[0]
                            cron = str(time_conf).split("#")[1]
                            command = str(time_conf).split("#")[2]
                            random_delay = None
                            if str(time_conf).count("#") == 3:
                                random_delay = str(time_conf).split("#")[3]

                            if self._onlyonce:
                                # 立即运行一次
                                logger.info(f"{name}服务启动，立即运行一次")
                                self._scheduler.add_job(self.__execute_command, 'date',
                                                        run_date=datetime.now(
                                                            tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                                        name=name,
                                                        args=[name, command])
                            else:
                                try:
                                    self._scheduler.add_job(func=self.__execute_command,
                                                            trigger=CronTrigger.from_crontab(
                                                                str(cron)),
                                                            name=name + (
                                                                f"随机延时{random_delay}秒" if random_delay else ""),
                                                            args=[name, command, random_delay])
                                except Exception as err:
                                    logger.error(f"定时任务配置错误：{err}")
                                    # 推送实时消息
                                    self.systemmessage.put(f"执行周期配置错误：{err}")
                        else:
                            logger.error(f"{time_conf} 配置错误，跳过处理")

                if self._onlyonce:
                    # 关闭一次性开关
                    self._onlyonce = False
                    # 保存配置
                    self.__update_config()
                # 启动任务
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()

    def __execute_command(self, name, command, random_delay=None):
        """
        执行命令
        """
        if random_delay:
            random_delay = random.randint(int(str(random_delay).split(
                "-")[0]), int(str(random_delay).split("-")[1]))
            logger.info(f"随机延时 {random_delay} 秒")
            time.sleep(random_delay)

        last_output = None
        last_error = None

        result = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        while True:
            output = result.stdout.readline()
            if output == '' and result.poll() is not None:
                break
            if output:
                logger.info(output.strip())
                last_output = output.strip()

        while True:
            error = result.stderr.readline()
            if error == '' and result.poll() is not None:
                break
            if error:
                logger.error(error.strip())
                last_error = error.strip()

        if result.returncode == 0:
            logger.info(f"执行命令：{command} 成功")
        else:
            logger.error(f"执行命令：{command} 失败")

        result_obj = self.__load_result(
            last_output if last_output else last_error)

        # 读取历史记录
        history = self.get_data('history') or []

        history.append({
            "name": name,
            "command": command,
            "result": result_obj,
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        })

        thirty_days_ago = time.time() - int(self._history_days) * 24 * 60 * 60
        history = [record for record in history if
                   datetime.strptime(record["time"],
                                     '%Y-%m-%d %H:%M:%S').timestamp() >= thirty_days_ago]
        # 保存历史
        self.save_data(key="history", value=history)

        if self._notify and self._msgtype:
            if self._notify_keywords and not re.search(self._notify_keywords,
                                                       result_obj["status"] + result_obj["msg"]):
                logger.info(f"通知关键词 {self._notify_keywords} 不匹配，跳过通知")
               
