# -*- coding: utf-8 -*-
"""应用工厂：装配扩展、注册蓝图与钩子、初始化数据库，对外暴露 app 与 celery。

启动方式：
  · Web 服务： python app.py            （PyCharm 直接运行 Flask/app.py）
  · 异步任务： celery -A app.celery worker

前端由 Vite 开发服务器独立提供（Vue/ 目录），Flask 只提供 /api。
"""
import os
from datetime import timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 输出流保护：stdout/stderr 失效（如从已关闭的终端/管道启动）时，写入静默丢弃。
# 必须放在最前——任何 print/日志写失败都不允许把请求打成 500（OSError: [Errno 22]）。
from backend.safe_stdio import install as _install_safe_stdio
_install_safe_stdio()

# ---------------------------------------------------------------------------
# 必须先加载项目根目录 .env，再导入 extensions / config ——
# 这两个模块在「导入时」就读取环境变量，dotenv 晚于它们则读不到。
# 未安装 python-dotenv 时降级：仅使用进程已导出的环境变量。
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
except ImportError:
    pass

from flask import Flask
from flask_cors import CORS

from backend.extensions import db, jwt, scheduler, make_celery, set_app
from backend.config import (
    Config,
    SQLALCHEMY_DATABASE_URI,
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    JWT_SECRET_KEY,
    JWT_ACCESS_TOKEN_EXPIRES_DAYS,
    CORS_ORIGINS,
)


def create_app():
    app = Flask(__name__)

    CORS(
        app,
        supports_credentials=True,
        resources={r"/api/*": {"origins": CORS_ORIGINS}},
        methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ------------------------- 配置 -------------------------
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_POOL_SIZE'] = 50            # 连接池大小
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 100        # 最大溢出连接数
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30         # 获取连接超时时间
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 3600       # 连接回收时间
    app.config['SQLALCHEMY_ECHO'] = False
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 上传文件最大50MB

    # JWT 密钥：优先环境变量；未配置时生成一次并持久化到 Flask/jwt.key（避免硬编码密钥可被伪造）
    jwt_secret = JWT_SECRET_KEY
    if not jwt_secret:
        import secrets
        jwt_key_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jwt.key'
        )
        if os.path.exists(jwt_key_file):
            with open(jwt_key_file, encoding='utf-8') as _f:
                jwt_secret = _f.read().strip()
        if not jwt_secret:
            jwt_secret = secrets.token_urlsafe(48)
            with open(jwt_key_file, 'w', encoding='utf-8') as _f:
                _f.write(jwt_secret)
            print('[安全] 未设置 JWT_SECRET_KEY，已生成随机密钥并持久化到 Flask/jwt.key')
    app.config['JWT_SECRET_KEY'] = jwt_secret
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=JWT_ACCESS_TOKEN_EXPIRES_DAYS)
    app.config['JWT_ALGORITHM'] = 'HS256'

    app.config['CELERY_RESULT_BACKEND'] = CELERY_RESULT_BACKEND
    app.config['CELERY_BROKER_URL'] = CELERY_BROKER_URL
    app.config.from_object(Config)

    # ------------------------- 初始化扩展 -------------------------
    db.init_app(app)
    jwt.init_app(app)
    scheduler.init_app(app)
    set_app(app)
    make_celery(app)  # 写入 extensions.celery

    # ------------------------- 导入子模块（触发注册） -------------------------
    # 顺序：模型 -> 工具 -> 任务 -> 钩子 -> 调度任务 -> 蓝图
    import backend.models      # noqa: F401  注册 ORM 模型
    import backend.utils       # noqa: F401  工具函数
    import backend.tasks       # noqa: F401  注册 Celery 任务
    import backend.hooks       # noqa: F401  注册 监控/JWT 钩子
    import backend.scheduler_jobs  # noqa: F401  注册定时任务

    from backend.routes import (
        auth, admin, goods, shop, user, orders, comments, recommend, ai
    )
    for module in (auth, admin, goods, shop, user, orders, comments, recommend, ai):
        app.register_blueprint(module.bp)

    # ------------------------- 建表 + ES 索引（ES 可选，不可用自动降级） -------------------------
    with app.app_context():
        db.create_all()
        from backend import es
        es.rebuild_async()   # 后台线程：索引缺失/内容变化时全量同步，不阻塞启动

    return app


# 模块级暴露，供 `celery -A app.celery` 与 `python app.py` 使用
app = create_app()
from backend.extensions import celery  # noqa: E402  create_app 之后 celery 才就绪
