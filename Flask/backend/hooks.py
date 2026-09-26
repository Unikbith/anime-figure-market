"""请求监控与 JWT 钩子（从原 app.py 抽取，需在 app/jwt 创建后导入注册）"""
import time
import json
from datetime import datetime

from flask import g as flask_g, jsonify, request
from flask_jwt_extended import decode_token

from backend.extensions import app, jwt, redis_client

@app.before_request
def monitor_before_request():
    """记录请求开始时间"""
    flask_g.monitor_start = time.time()

@app.after_request
def monitor_after_request(response):
    """采集请求指标，存入Redis"""
    try:
        path = request.path
        if not path.startswith('/api/'):
            return response

        duration = int((time.time() - flask_g.monitor_start) * 1000)  # 毫秒级耗时
        size = len(response.get_data()) if hasattr(response, 'get_data') else 0
        status = response.status_code
        ip = request.remote_addr or '0.0.0.0'
        now = datetime.now()

        metric = json.dumps({
            'path': path,
            'method': request.method,
            'status': status,
            'duration': duration,
            'size': size,
            'ip': ip,
            'time': now.strftime('%Y-%m-%d %H:%M:%S')
        })

        redis_client.lpush('monitor:raw', metric)
        redis_client.ltrim('monitor:raw', 0, 1999)

        minute_key = now.strftime('%Y%m%d%H%M')
        redis_client.incr(f'monitor:minute:{minute_key}:total')
        if status >= 400:
            redis_client.incr(f'monitor:minute:{minute_key}:error')
        redis_client.incrby(f'monitor:minute:{minute_key}:bytes', size)
        redis_client.incrby(f'monitor:minute:{minute_key}:duration', duration)

        for suffix in ['total', 'error', 'bytes', 'duration']:
            redis_client.expire(f'monitor:minute:{minute_key}:{suffix}', 7200)

        redis_client.zincrby('monitor:ip_count', 1, ip)

        redis_client.zincrby('monitor:path_count', 1, path)

        try:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token_str = auth_header[7:]
                decoded = decode_token(token_str)
                user_id = decoded.get('sub')
                if user_id and user_id != '0':  # 排除管理员
                    today_key = now.strftime('%Y%m%d')
                    hour_key = now.strftime('%Y%m%d%H')
                    redis_client.sadd(f'monitor:active_users:{today_key}', user_id)
                    redis_client.sadd(f'monitor:active_hour:{hour_key}', user_id)
                    redis_client.expire(f'monitor:active_users:{today_key}', 86400 * 3)
                    redis_client.expire(f'monitor:active_hour:{hour_key}', 7200)
        except Exception:
            pass

    except Exception as e:
        print(f"监控采集异常: {e}")

    return response

@jwt.invalid_token_loader
def invalid_token_callback(error):
    """token无效时"""
    return jsonify({'code': 401, 'msg': f'Token无效: {error}'}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """token过期"""
    return jsonify({'code': 401, 'msg': '登录已过期，请重新登录'}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    """缺少token"""
    return jsonify({'code': 401, 'msg': '请先登录，缺少Token'}), 401

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    """检查token是否在黑名单中（用于登出）"""
    jti = jwt_payload['jti']
    return redis_client.get(f"jwt_blacklist:{jti}") is not None

