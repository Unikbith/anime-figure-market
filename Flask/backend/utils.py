"""通用工具与辅助函数（从原 app.py 抽取）"""
from flask_jwt_extended import jwt_required, get_jwt
from celery import Celery
from cryptography.fernet import Fernet
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import hashlib
import os
import uuid
from contextlib import contextmanager
import time
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import jsonify, request

from werkzeug.security import generate_password_hash, check_password_hash

from backend.extensions import db, redis_client, app
from backend.config import FERNET_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from backend.models import Goods, Order, Cart

_goods_cache = {'data': None, 'updated_at': 0}
_GOODS_CACHE_TTL = 300  # 缓存有效期5分钟

# 密钥文件固定放在 Flask/（与后端入口同级），不依赖进程工作目录
_SECRET_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'secret.key'
)

def _load_fernet_key():
    """密钥优先级：`.env` 的 FERNET_KEY → Flask/secret.key → 新生成并落盘。

    ⚠️ 这个密钥一旦更换/丢失，历史 Fernet 密文将永远无法解密（对应账号无法登录），
       所以 Flask/secret.key 与 .env 都要一起备份。
    """
    if FERNET_KEY:
        return FERNET_KEY.encode()
    if os.path.exists(_SECRET_KEY_FILE):
        with open(_SECRET_KEY_FILE, 'rb') as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(_SECRET_KEY_FILE, 'wb') as f:
        f.write(key)
    print('[安全] 未配置 FERNET_KEY 且缺少 Flask/secret.key，已生成新密钥 —— '
          '历史 Fernet 密文将无法解密')
    return key

cipher_suite = Fernet(_load_fernet_key())

class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'

class RedisLock:
    """Redis分布式锁"""
    def __init__(self, key, timeout=10):
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.value = str(uuid.uuid4())  # 唯一标识，防止误删其他客户端的锁

    def acquire(self, retry=3, delay=0.1):
        """尝试获取锁，支持重试"""
        for _ in range(retry):
            if redis_client.set(self.key, self.value, nx=True, ex=self.timeout):
                return True
            time.sleep(delay)
        return False

    def release(self):
        """释放锁"""
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            redis_client.eval(lua, 1, self.key, self.value)
        except:
            pass

@contextmanager
def distributed_lock(key, timeout=10):
    """分布式锁上下文管理器，使用with语句自动获取/释放锁"""
    lock = RedisLock(key, timeout)
    if not lock.acquire():
        raise Exception(f"获取锁失败: {key}")
    try:
        yield
    finally:
        lock.release()

def admin_required(fn):
    """管理员权限装饰器：要求JWT中role为admin"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'code': 403, 'msg': '无管理员权限'}), 403
        return fn(*args, **kwargs)
    return wrapper

def cache(key_prefix, expire=3600):
    """缓存装饰器：基于Redis缓存GET请求结果。

    - 缓存键包含路由参数与查询参数：?page=2&size=3 与 ?page=1 缓存互不串扰
    - 命中时回存**完整响应体**（含 pagination 等全部字段），而非只有 data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if args:
                cache_key = f"{key_prefix}:{args[0]}"
            elif kwargs.get('id'):
                cache_key = f"{key_prefix}:{kwargs.get('id')}"
            else:
                cache_key = f"{key_prefix}:default"
            try:
                qs = sorted((k, v) for k, v in request.args.items())
                if qs:
                    digest = hashlib.md5(
                        json.dumps(qs, ensure_ascii=False).encode('utf-8')
                    ).hexdigest()[:16]
                    cache_key = f"{cache_key}:{digest}"
            except Exception:
                pass

            cached_body = redis_client.get(cache_key)
            if cached_body:
                return app.response_class(cached_body, mimetype='application/json')

            result = func(*args, **kwargs)
            try:
                if result.status_code == 200:
                    body = result.get_data(as_text=True)
                    if json.loads(body).get('code') == 200:
                        redis_client.setex(cache_key, expire, body)
            except Exception as e:
                print(f"缓存写入失败: {e}")
            return result

        return wrapper

    return decorator

def cache_invalidate(pattern):
    """按通配符清除缓存键（SCAN 逐批删除，避免 KEYS 阻塞）。

    cache 装饰器的键现在包含查询参数哈希，固定键名的 delete 清不干净，
    失效一律走本函数，如 cache_invalidate('goods_list:*')。
    """
    try:
        keys = list(redis_client.scan_iter(match=pattern, count=200))
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        print(f"缓存清除失败: {e}")

def parse_int(value, default, minimum=None, maximum=None):
    """安全整数解析：None/非法值回落 default，并按需夹在 [minimum, maximum]。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    if minimum is not None:
        v = max(v, minimum)
    if maximum is not None:
        v = min(v, maximum)
    return v

def generate_code():
    """生成6位数字验证码（使用密码学安全随机源，避免可预测）"""
    import secrets
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def send_email(email, code):
    """发送QQ邮箱验证码"""
    sender = SMTP_USER
    nickname = "次元模仓"
    encoded_nickname = Header(nickname, 'utf-8').encode()
    from_header = f"{encoded_nickname} <{sender}>"

    msg = MIMEText(f'您的注册验证码是：{code}，5分钟内有效，请勿泄露。', 'plain', 'utf-8')
    msg['From'] = from_header
    msg['To'] = email
    msg['Subject'] = Header('【次元模仓】注册验证码', 'utf-8')

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()  # 启用TLS加密
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(sender, [email], msg.as_string())
        print(f" 验证码发送成功至：{email}")
        return True
    except Exception as e:
        print(f" 邮件发送失败: {e}")
        return False

def encrypt_password(password):
    """存储密码：不可逆哈希（werkzeug 格式，形如 scrypt:32768:8:1$...）。"""
    return generate_password_hash(password)

def decrypt_password(encrypted_password):
    """解密历史 Fernet 密文（仅用于校验旧数据，勿用于新密码）。

    密钥不匹配时返回 None，由 verify_password 判为校验失败。
    """
    try:
        return cipher_suite.decrypt(encrypted_password.encode()).decode()
    except Exception:
        return None

def verify_password(stored_password, raw_password):
    """校验密码：兼容「werkzeug 哈希（新）」与「Fernet 密文（历史数据）」。"""
    if not stored_password or raw_password is None:
        return False
    if stored_password.startswith(('pbkdf2:', 'scrypt:', 'argon2')):
        try:
            return check_password_hash(stored_password, raw_password)
        except Exception:
            return False
    return decrypt_password(stored_password) == raw_password

def is_legacy_password_hash(stored_password):
    """是否为历史 Fernet 密文（登录成功后会被静默升级为哈希）"""
    return not (stored_password or '').startswith(('pbkdf2:', 'scrypt:', 'argon2'))

def deduct_stock_redis(goods_id, num):
    """Redis原子扣减库存，并同步数据库"""
    stock_key = f"goods_stock:{goods_id}"
    try:
        current_stock = redis_client.get(stock_key)
        if not current_stock:
            goods = Goods.query.get(goods_id)
            if not goods:
                return False
            current_stock = goods.stock
            redis_client.set(stock_key, current_stock)

        current_stock = int(current_stock)
        if current_stock < num:
            return False  # 库存不足

        new_stock = current_stock - num
        redis_client.set(stock_key, new_stock)

        goods = Goods.query.get(goods_id)
        if goods:
            goods.stock = new_stock
            db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"扣减库存失败: {e}")
        return False

def cancel_expired_orders():
    """定时任务：取消超时未支付的订单，恢复库存和购物车"""
    with app.app_context():
        expired_time = datetime.now() - timedelta(minutes=15)
        expired_orders = Order.query.filter(
            Order.status == 'pending_pay',
            Order.created_at < expired_time
        ).all()
        for order in expired_orders:
            print(f"自动取消超时订单: {order.order_no}")
            order.status = 'cancelled'
            for item in order.items:
                with distributed_lock(f"goods_{item.goods_id}", timeout=5):
                    goods = Goods.query.get(item.goods_id)
                    if goods:
                        goods.stock += item.num
                        redis_client.incrby(f"goods_stock:{item.goods_id}", item.num)
                existing_cart = Cart.query.filter_by(user_id=order.user_id, goods_id=item.goods_id).first()
                if existing_cart:
                    existing_cart.num += item.num
                else:
                    new_cart = Cart(user_id=order.user_id, goods_id=item.goods_id, num=item.num)
                    db.session.add(new_cart)
        if expired_orders:
            db.session.commit()
            print(f"已自动取消 {len(expired_orders)} 个超时订单")

def make_celery(app):
    """创建Celery实例并配置时区与超时"""
    celery = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND'),
        broker=app.config.get('CELERY_BROKER_URL')
    )
    celery.conf.update(
        timezone='Asia/Shanghai',
        enable_utc=False,
        task_soft_time_limit=30,  # 软超时30秒
        task_time_limit=60,  # 硬超时60秒
    )
    return celery

def fix_image_url(url):
    """把 MinIO 的绝对图片地址转成相对路径 /goods-images/...

    Vite 开发服务器已把 /goods-images 代理到 MinIO(9000)，前端可直接使用。
    """
    if not url:
        return url
    if url.startswith('http://127.0.0.1:9000/goods-images/'):
        return '/goods-images/' + url.split('/goods-images/', 1)[1]
    if url.startswith('http://localhost:9000/goods-images/'):
        return '/goods-images/' + url.split('/goods-images/', 1)[1]
    return url

def rebuild_redis_goods_index(goods_list):
    """将商品多字段索引写入Redis，支持按字段加权搜索"""
    pipe = redis_client.pipeline()
    for key in redis_client.keys('ai_index:*'):
        pipe.delete(key)
    pipe.delete('ai_index:goods_map')

    goods_map = {}
    for g in goods_list:
        price = float(g.price) if g.price else 0
        goods_map[str(g.id)] = json.dumps({
            'id': g.id,
            'name': g.name or '',
            'price': price,
            'ip': g.ip or '',
            'charactername': g.charactername or '',
            'brand': g.brand or '',
            'category': g.category or '',
            'image': fix_image_url(g.images.split(',')[0]) if g.images else ''
        }, ensure_ascii=False)

        # 按字段类型分别建索引，权重不同
        field_weights = {
            'ip': 5,            # IP匹配权重最高
            'charactername': 5, # 角色名匹配权重最高
            'name': 4,          # 商品名次之
            'brand': 3,         # 品牌再次
            'category': 2       # 分类最低
        }
        for field, weight in field_weights.items():
            val = getattr(g, field, None)
            if val and val.strip():
                key = val.strip().lower()
                redis_key = f'ai_index:field:{field}:{key}'
                pipe.sadd(redis_key, g.id)
                pipe.expire(redis_key, 600)

    pipe.execute()
    redis_client.hset('ai_index:goods_map', mapping=goods_map)
    redis_client.expire('ai_index:goods_map', 600)
    print(f"[Redis索引] 已构建，共 {len(goods_list)} 个商品")

def get_cached_goods():
    """获取缓存的商品列表，索引从Redis读取"""
    import time
    now = time.time()

    if _goods_cache['data'] is not None and (now - _goods_cache['updated_at']) < _GOODS_CACHE_TTL:
        return _goods_cache['data']

    try:
        goods_list = Goods.query.filter(Goods.status != '下架').all()
        _goods_cache['data'] = goods_list
        _goods_cache['updated_at'] = now
        rebuild_redis_goods_index(goods_list)
        print(f"[商品缓存] 已更新，共 {len(goods_list)} 个商品")
    except Exception as e:
        print(f"[商品缓存] 加载失败: {e}")
        if _goods_cache['data'] is not None:
            return _goods_cache['data']
        return []

    return _goods_cache['data']

def search_by_redis_index(keywords, user_message=''):
    """使用AI提取的关键词在Redis多字段索引中进行加权搜索
    keywords: AI提取的关键词列表，如 ['初音未来', '200']
    user_message: 原始用户消息，用于提取预算等额外信息
    """
    import re
    try:
        if not keywords:
            return None

        budget_max = None
        budget_match = re.search(r'(\d+)\s*[元块]?', user_message)
        if budget_match and any(w in user_message for w in ['预算', '以内', '以下', '不超过', '只有', '就', '左右', '块钱']):
            budget_max = int(budget_match.group(1))
        # 也从关键词中提取预算（AI可能把数字作为关键词）
        for kw in keywords:
            if kw.isdigit() and int(kw) >= 10:
                budget_max = int(kw)

        all_index_keys = redis_client.keys('ai_index:field:*')
        if not all_index_keys:
            return None

        field_weights = {
            'ip': 5,            # IP匹配权重最高
            'charactername': 5, # 角色名匹配权重最高
            'name': 4,          # 商品名次之
            'brand': 3,         # 品牌再次
            'category': 2       # 分类最低
        }

        goods_scores = {}  # {goods_id: total_score}

        for keyword in keywords:
            kw_lower = keyword.lower()

            for redis_key in all_index_keys:
                parts = redis_key.split(':', 3)
                if len(parts) < 4:
                    continue
                field = parts[2]
                index_word = parts[3]

                # 双向匹配：关键词包含索引词，或索引词包含关键词
                if kw_lower in index_word or index_word in kw_lower:
                    weight = field_weights.get(field, 1)

                    # 关键词越长匹配越精确，额外加分
                    length_bonus = min(len(kw_lower), 3)
                    weight += length_bonus

                    member_ids = redis_client.smembers(redis_key)
                    for gid in member_ids:
                        gid = int(gid)
                        if gid not in goods_scores:
                            goods_scores[gid] = 0
                        goods_scores[gid] += weight

        if not goods_scores:
            return None

        candidates = []
        for gid, score in goods_scores.items():
            raw = redis_client.hget('ai_index:goods_map', str(gid))
            if not raw:
                continue
            g = json.loads(raw)
            price = g.get('price', 0)

            if budget_max:
                if price > budget_max * 1.2:
                    score -= 20  # 超预算20%以上大幅扣分
                elif price > budget_max:
                    score -= 5   # 微超预算轻微扣分
                else:
                    ratio = price / budget_max if budget_max > 0 else 0
                    score += int(5 * ratio)

            if score > 0:
                candidates.append((g, score))

        if not candidates:
            for gid, score in goods_scores.items():
                raw = redis_client.hget('ai_index:goods_map', str(gid))
                if raw:
                    candidates.append((json.loads(raw), score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0][0]
        print(f"[Redis搜索] 关键词:{keywords} → 匹配商品: {best['name']}, 分数: {candidates[0][1]}")
        return best

    except Exception as e:
        print(f"[Redis搜索] 异常: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_fallback_reply(message):
    """降级回复：当AI服务不可用时使用预设回复"""
    if not message:
        return "您好，请问有什么可以帮您？"

    message = message.lower()

    if '订单' in message or '发货' in message:
        return '关于订单问题，您可以在"我的订单"中查看详情。如有其他问题，请详细描述，我们会尽快处理。'
    elif '退款' in message or '退货' in message:
        return '退款/退货申请请在订单详情中提交售后申请，商家会在1-3个工作日内处理。'
    elif '商品' in message or '手办' in message:
        return '关于商品问题，您可以在商品详情页查看更多信息，或直接联系商家咨询。'
    elif '支付' in message:
        return '支付问题请联系客服或在工作时间咨询。'
    elif '收藏' in message:
        return '您可以在商品详情页点击收藏按钮，收藏的商品在个人中心的"我的收藏"中查看。'
    else:
        return '感谢您的咨询，我们会尽快为您处理！'
