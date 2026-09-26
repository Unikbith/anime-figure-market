# -*- coding: utf-8 -*-
"""扩展对象与基础设施（不依赖 app 实例，避免循环导入）

这里只创建“无状态”或“可延迟绑定 app”的扩展实例；
app 实例由 backend/__init__.py 的 create_app() 创建并注入。
"""
import redis
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_apscheduler import APScheduler
from minio import Minio
from celery import Celery

from backend.config import (
    REDIS_HOST, REDIS_PORT,
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE,
)

db = SQLAlchemy()

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

jwt = JWTManager()

scheduler = APScheduler()

# 连接参数统一来自 backend.config（其值由环境变量 / 根目录 .env 提供）
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)
# 导入时确保桶存在并设置公开读策略（MinIO 未运行会抛异常，由调用方 try/except）
try:
    if not minio_client.bucket_exists(MINIO_BUCKET):
        minio_client.make_bucket(MINIO_BUCKET)
    _policy = """{
  "Version": "2012-10-17",
  "Statement": [{"Effect":"Allow","Principal":{"AWS":["*"]},"Action":["s3:GetObject"],"Resource":["arn:aws:s3:::%s/*"]}]
}""" % MINIO_BUCKET
    minio_client.set_bucket_policy(MINIO_BUCKET, _policy)
except Exception as e:
    print(f"MinIO 初始化跳过（MinIO 未运行？）: {e}")

celery = None
app = None  # app 实例占位，由 create_app 注入，供 utils/tasks 取 app_context 使用

def set_app(flask_app):
    global app
    app = flask_app

def make_celery(flask_app):
    """根据 app.config 创建 Celery 实例（broker / backend 指向 Redis）"""
    global celery
    celery = Celery(
        flask_app.import_name,
        backend=flask_app.config.get('CELERY_RESULT_BACKEND'),
        broker=flask_app.config.get('CELERY_BROKER_URL')
    )
    celery.conf.update(
        timezone='Asia/Shanghai',
        enable_utc=False,
        task_soft_time_limit=30,   # 软超时30秒
        task_time_limit=60,        # 硬超时60秒
    )
    return celery
