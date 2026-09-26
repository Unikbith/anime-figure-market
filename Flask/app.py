# -*- coding: utf-8 -*-
"""次元模仓 · Flask 入口

后端已从单文件重构为 backend/ 包（按业务域拆分为蓝本）。
本文件只负责：装配应用并启动。

启动（工作目录均为 Flask/）：
  · Web 服务：PyCharm 直接运行本文件，或命令行 python app.py   → http://127.0.0.1:5000
  · 异步任务：celery -A app.celery worker --loglevel=info
"""
import os

from backend import app
# 下面这行不是多余的：celery 命令通过 `-A app.celery` 读取本模块的 celery 属性，勿删
from backend import celery  # noqa: F401
from backend.extensions import scheduler
from collections import defaultdict
if __name__ == '__main__':
    # 避免 Flask debug 模式 reloader 重复启动调度器
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        scheduler.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
