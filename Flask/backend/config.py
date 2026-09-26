# -*- coding: utf-8 -*-
"""配置集中管理：所有连接串 / 密钥 / 地址统一从环境变量读取。

环境变量来源（按优先级）：
  1. 进程环境变量（start-all.ps1 注入 / 手动 export）
  2. 项目根目录 `.env`（由 backend/__init__.py 顶部的 python-dotenv 加载）

模板见根目录 `.env.example`；真实值放 `.env`（已 gitignore）。
本模块只依赖 os，不导入任何 backend 内部模块，可被任意模块安全导入。
"""
import os


def _env(key, default=''):
    """读取字符串环境变量（空字符串也视为已设置，仅未定义时取默认值）"""
    value = os.getenv(key)
    return default if value is None else value


def _env_int(key, default):
    """读取整型环境变量，非法值回退默认"""
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(key, default=False):
    """读取布尔环境变量（true/1/yes/on 视为真）"""
    return _env(key, 'true' if default else 'false').strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(key, default=''):
    """读取逗号分隔的列表环境变量"""
    return [item.strip() for item in _env(key, default).split(',') if item.strip()]


# ----------------------------- 数据库（MySQL） -----------------------------
SQLALCHEMY_DATABASE_URI = _env(
    'SQLALCHEMY_DATABASE_URI',
    'mysql+pymysql://root:root@127.0.0.1:3306/handmade_platform'
)

# ----------------------------- Redis / Celery -----------------------------
REDIS_HOST = _env('REDIS_HOST', '127.0.0.1')
REDIS_PORT = _env_int('REDIS_PORT', 6379)
CELERY_BROKER_URL = _env('CELERY_BROKER_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/1')
CELERY_RESULT_BACKEND = _env('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)

# ----------------------------- JWT -----------------------------
# 留空则由 __init__.py 生成随机密钥并持久化到 Flask/jwt.key（不入库）
JWT_SECRET_KEY = _env('JWT_SECRET_KEY')
JWT_ACCESS_TOKEN_EXPIRES_DAYS = _env_int('JWT_ACCESS_TOKEN_EXPIRES_DAYS', 7)

# ----------------------------- 管理员账号（原为 admin/admin 硬编码，已外置） -----------------------------
ADMIN_USERNAME = _env('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = _env('ADMIN_PASSWORD')

# ----------------------------- 邮件（QQ 邮箱 SMTP） -----------------------------
SMTP_HOST = _env('SMTP_HOST', 'smtp.qq.com')
SMTP_PORT = _env_int('SMTP_PORT', 587)
SMTP_USER = _env('SMTP_USER')            # 发件 QQ 邮箱，如 123456@qq.com
SMTP_PASSWORD = _env('SMTP_PASSWORD')    # 邮箱授权码（非登录密码）

# ----------------------------- 智谱 AI 客服（可选） -----------------------------
ZHIPU_API_KEY = _env('ZHIPU_API_KEY')    # 未配置时 AI 客服降级为本地兜底回复
ZHIPU_API_URL = _env('ZHIPU_API_URL', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')

# ----------------------------- MinIO 对象存储 -----------------------------
MINIO_ENDPOINT = _env('MINIO_ENDPOINT', '127.0.0.1:9000')
MINIO_ACCESS_KEY = _env('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = _env('MINIO_SECRET_KEY', 'minioadmin')
MINIO_BUCKET = _env('MINIO_BUCKET', 'goods-images')
MINIO_SECURE = _env_bool('MINIO_SECURE', False)

# ----------------------------- 密码兼容（历史数据） -----------------------------
# 历史数据的 password 列是 Fernet 密文，需要一个固定密钥才能校验；
# 优先读本项，留空则回退到 Flask/secret.key（旧布局）。新密码一律存哈希，不走这里。
FERNET_KEY = _env('FERNET_KEY')

# ----------------------------- Elasticsearch（可选，不可用自动降级 MySQL） -----------------------------
ES_HOST = _env('ES_HOST', '127.0.0.1')
ES_PORT = _env_int('ES_PORT', 9200)

# ----------------------------- CORS 允许来源 -----------------------------
# 本地开发：Vite 开发服务器（5173）直连后端时需要放行；走 Vite 代理时不涉及 CORS
CORS_ORIGINS = _env_list(
    'CORS_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://127.0.0.1'
)

# ----------------------------- 定时任务调度器 -----------------------------
class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = _env('SCHEDULER_TIMEZONE', 'Asia/Shanghai')
