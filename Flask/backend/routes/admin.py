"""admin 模块路由（蓝本）"""
from flask import request, jsonify
from datetime import datetime, timedelta

from flask import Blueprint
from flask_jwt_extended import create_access_token

from backend.extensions import db, redis_client
from backend.config import ADMIN_USERNAME, ADMIN_PASSWORD
from backend.models import (
    User, Goods, Cart, Collect, History, Comment,
    Order, OrderItem, ReturnRequest, NotificationLog, Snapshot, Banner
)
from backend.tasks import notify_off_shelf
from backend.scheduler_jobs import scheduled_refresh_search_keywords
from backend.utils import fix_image_url, admin_required, cache_invalidate
from backend import es

bp = Blueprint('admin', __name__)

@bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """管理员专用登录（口令来自环境变量 ADMIN_USERNAME / ADMIN_PASSWORD）"""
    import secrets as _secrets
    data = request.get_json(silent=True) or {}
    username = data.get('username') or ''
    password = data.get('password') or ''
    admin_user = ADMIN_USERNAME
    admin_pwd = ADMIN_PASSWORD
    # 未配置管理员口令时禁用该入口，避免硬编码/弱口令
    if not admin_pwd:
        return jsonify({'code': 500, 'msg': '管理员登录未配置，请设置 ADMIN_PASSWORD 环境变量'}), 500
    user_ok = _secrets.compare_digest(username, admin_user)
    pwd_ok = _secrets.compare_digest(password, admin_pwd)
    if not (user_ok and pwd_ok):
        return jsonify({'code': 400, 'msg': '账号或密码错误'}), 400
    access_token = create_access_token(
        identity='0',
        additional_claims={'id': 0, 'role': 'admin', 'nickname': '管理员'}
    )
    return jsonify({
        'code': 200,
        'msg': '登录成功',
        'token': access_token,
        'nickname': '管理员',
        'role': 'admin',
        'userId': 0
    })


@bp.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """管理员获取所有用户列表"""
    try:
        users = User.query.all()
        data = []
        for user in users:
            data.append({
                'id': user.id,
                'nickname': user.nickname,
                'username': user.username,
                'role': user.role,
                'is_banned': user.is_banned,
                'apply_status': user.apply_status or 'none',
                'apply_time': user.apply_time.strftime('%Y-%m-%d %H:%M') if user.apply_time else '',
                'phone': user.phone or '',
                'avatar': fix_image_url(user.avatar or ''),
                'receiver_name': user.receiver_name or '',
                'address': user.address or ''
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f"管理员获取用户列表错误: {e}")
        return jsonify({'code': 500, 'msg': '获取用户列表失败'}), 500


@bp.route('/api/admin/user/delete/<int:id>', methods=['DELETE'])
@admin_required
def admin_delete_user(id):
    """管理员删除用户（级联删除相关数据）"""
    try:
        user = User.query.get_or_404(id)
        Cart.query.filter_by(user_id=id).delete()
        History.query.filter_by(user_id=id).delete()
        Comment.query.filter_by(user_id=id).delete()
        ReturnRequest.query.filter_by(user_id=id).delete()
        NotificationLog.query.filter_by(user_id=id).delete()
        Order.query.filter_by(user_id=id).delete()
        db.session.delete(user)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '用户删除成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员删除用户错误: {e}")
        return jsonify({'code': 500, 'msg': '删除用户失败'}), 500


@bp.route('/api/admin/user/update/<int:id>', methods=['POST'])
@admin_required
def admin_update_user(id):
    """管理员修改用户信息"""
    try:
        user = User.query.get_or_404(id)
        data = request.get_json()

        # 处理 User 表字段
        if 'nickname' in data and data['nickname'].strip():
            user.nickname = data['nickname'].strip()
        if 'role' in data:
            allowed_roles = ['user', 'merchant']
            if data['role'] not in allowed_roles:
                return jsonify({'code': 400, 'msg': '无效角色，仅支持普通用户和商家'}), 400
            user.role = data['role']

        # 用户资料字段（原 UserInfo 已并入 users）
        if 'avatar' in data:
            user.avatar = fix_image_url(data['avatar'].strip())
        if 'phone' in data:
            user.phone = data['phone'].strip()
        if 'address' in data:
            user.address = data['address'].strip()

        db.session.commit()
        return jsonify({'code': 200, 'msg': '用户信息修改成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员修改用户错误: {e}")
        return jsonify({'code': 500, 'msg': '修改用户信息失败'}), 500


@bp.route('/api/admin/merchant/approve/<int:user_id>', methods=['POST'])
@admin_required
def admin_approve_merchant(user_id):
    """管理员通过商家入驻申请"""
    try:
        user = User.query.get(user_id)

        if not user:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404

        if user.role != 'merchant':
            return jsonify({'code': 400, 'msg': '该用户不是商家角色'}), 400

        if user.apply_status != 'pending':
            return jsonify({'code': 400, 'msg': '该商家未提交申请或已审核'}), 400

        user.apply_status = 'approved'
        db.session.commit()

        return jsonify({'code': 200, 'msg': '已通过该商家的入驻申请'})
    except Exception as e:
        db.session.rollback()
        print(f"通过入驻申请失败: {e}")
        return jsonify({'code': 500, 'msg': '操作失败'}), 500


@bp.route('/api/admin/merchant/reject/<int:user_id>', methods=['POST'])
@admin_required
def admin_reject_merchant(user_id):
    """管理员拒绝商家入驻申请"""
    try:
        user = User.query.get(user_id)

        if not user:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404

        if user.role != 'merchant':
            return jsonify({'code': 400, 'msg': '该用户不是商家角色'}), 400

        if user.apply_status != 'pending':
            return jsonify({'code': 400, 'msg': '该商家未提交申请或已审核'}), 400

        user.apply_status = 'rejected'
        db.session.commit()

        return jsonify({'code': 200, 'msg': '已拒绝该商家的入驻申请'})
    except Exception as e:
        db.session.rollback()
        print(f"拒绝入驻申请失败: {e}")
        return jsonify({'code': 500, 'msg': '操作失败'}), 500


@bp.route('/api/admin/user/detail/<int:id>', methods=['GET'])
@admin_required
def admin_get_user_detail(id):
    """管理员获取单个用户的详细信息"""
    try:
        user = User.query.get_or_404(id)

        # 统计用户相关数据
        order_count = Order.query.filter_by(user_id=id).count()
        cart_count = Cart.query.filter_by(user_id=id).count()
        collect_count = Collect.query.filter_by(user_id=id).count()
        comment_count = Comment.query.filter_by(user_id=id).count()

        data = {
            'id': user.id,
            'nickname': user.nickname,
            'username': user.username,
            'role': user.role,
            'is_banned': user.is_banned,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'created_at') else '未知',
            'info': {
                'avatar': fix_image_url(user.avatar or ''),
                'birthday': user.birthday or '',
                'gender': user.gender or '',
                'email': user.email or '',
                'phone': user.phone or '',
                'receiver_name': user.receiver_name or '',
                'address': user.address or ''
            },
            'stats': {
                'order_count': order_count,
                'cart_count': cart_count,
                'collect_count': collect_count,
                'comment_count': comment_count
            }
        }
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f"管理员获取用户详情错误: {e}")
        return jsonify({'code': 500, 'msg': '获取用户详情失败'}), 500


@bp.route('/api/admin/user/ban/<int:id>', methods=['POST'])
@admin_required
def admin_ban_user(id):
    """管理员封禁用户"""
    try:
        user = User.query.get_or_404(id)

        user.is_banned = True
        db.session.commit()

        return jsonify({'code': 200, 'msg': '用户封禁成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员封禁用户错误: {e}")
        return jsonify({'code': 500, 'msg': '封禁用户失败'}), 500


@bp.route('/api/admin/user/unban/<int:id>', methods=['POST'])
@admin_required
def admin_unban_user(id):
    """管理员解封用户"""
    try:
        user = User.query.get_or_404(id)
        user.is_banned = False
        db.session.commit()
        return jsonify({'code': 200, 'msg': '用户解封成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员解封用户错误: {e}")
        return jsonify({'code': 500, 'msg': '解封用户失败'}), 500


@bp.route('/api/admin/goods', methods=['GET'])
@admin_required
def admin_get_goods():
    """管理员获取所有商品列表"""
    try:
        goods = Goods.query.order_by(Goods.created_at.desc()).all()
        data = []
        for g in goods:
            data.append({
                'id': g.id,
                'name': g.name,
                'price': float(g.price),
                'stock': g.stock,
                'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
                'category': g.category,
                'status': g.status,
                'merchant_name': g.merchant.nickname if g.merchant else '',
                'brand': g.brand,
                'ip': g.ip,
                'charactername': g.charactername,
                'description': g.description
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f"管理员获取商品列表错误: {e}")
        return jsonify({'code': 500, 'msg': '获取商品列表失败'}), 500


@bp.route('/api/admin/goods/delete/<int:id>', methods=['DELETE'])
@admin_required
def admin_delete_goods(id):
    """并清除关联数据与缓存"""
    try:
        goods = Goods.query.get_or_404(id)
        # 级联删除关联数据
        Cart.query.filter_by(goods_id=id).delete()
        History.query.filter_by(goods_id=id).delete()
        Comment.query.filter_by(goods_id=id).delete()
        ReturnRequest.query.filter_by(goods_id=id).delete()
        NotificationLog.query.filter_by(goods_id=id).delete()
        OrderItem.query.filter_by(goods_id=id).delete()
        redis_client.delete(f"goods_stock:{id}")
        redis_client.delete(f'goods_detail:{id}')
        cache_invalidate('goods_list:*')
        db.session.delete(goods)
        db.session.commit()
        es.delete_goods(id)   # 同步 ES 索引
        return jsonify({'code': 200, 'msg': '商品删除成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员删除商品错误: {e}")
        return jsonify({'code': 500, 'msg': '删除商品失败'}), 500


@bp.route('/api/admin/goods/update/<int:id>', methods=['POST'])
@admin_required
def admin_update_goods(id):
    """管理员修改商品信息"""
    try:
        goods = Goods.query.get_or_404(id)
        data = request.get_json()
        goods.name = data.get('name', goods.name)
        goods.price = data.get('price', goods.price)
        goods.stock = data.get('stock', goods.stock)
        goods.category = data.get('category', goods.category)
        goods.status = data.get('status', goods.status)
        goods.brand = data.get('brand', goods.brand)
        goods.ip = data.get('ip', goods.ip)
        goods.charactername = data.get('charactername', goods.charactername)
        goods.description = data.get('description', goods.description)
        # 同步Redis缓存
        redis_client.set(f"goods_stock:{id}", goods.stock)
        redis_client.delete(f'goods_detail:{id}')
        cache_invalidate('goods_list:*')
        db.session.commit()
        es.index_goods(goods)   # 同步 ES 索引
        return jsonify({'code': 200, 'msg': '商品修改成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员修改商品错误: {e}")
        return jsonify({'code': 500, 'msg': '修改商品失败'}), 500


@bp.route('/api/admin/goods/status/<int:id>', methods=['POST'])
@admin_required
def admin_toggle_goods_status(id):
    """管理员切换商品 上架/下架 状态"""
    try:
        goods = Goods.query.get_or_404(id)
        old_status = goods.status
        stock = goods.stock
        if old_status == "下架":
            if stock <= 0:
                goods.status = "缺货"
            else:
                goods.status = "现货"
        else:
            goods.status = "下架"
        db.session.commit()
        es.index_goods(goods)   # 同步 ES 索引
        # 清理 Redis 缓存
        cache_invalidate('goods_list:*')
        redis_client.delete(f'goods_detail:{id}')

        # 下架操作触发异步通知告知购物车用户
        if goods.status == "下架":
            notify_off_shelf.delay(id)
        return jsonify({'code': 200, 'msg': '商品状态切换成功'})
    except Exception as e:
        db.session.rollback()
        print(f"商品上下架操作失败: {e}")
        return jsonify({'code': 500, 'msg': '操作失败，服务器异常'}), 500


@bp.route('/api/admin/orders', methods=['GET'])
@admin_required
def admin_get_orders():
    """可按状态筛选"""
    try:
        status = request.args.get('status', '')
        query = Order.query.order_by(Order.created_at.desc())
        if status:
            query = query.filter_by(status=status)
        orders = query.all()
        data = []
        for order in orders:
            user = User.query.get(order.user_id)
            user_nickname = user.nickname if user else '未知用户'
            data.append({
                'id': order.id,
                'order_no': order.order_no,
                'user_id': order.user_id,
                'user_nickname': user_nickname,
                'receiver_name': order.receiver_name,
                'receiver_phone': order.receiver_phone,
                'receiver_address': order.receiver_address,
                'total_price': float(order.total_price),
                'status': order.status,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f"管理员获取订单列表错误: {e}")
        return jsonify({'code': 500, 'msg': '获取订单列表失败'}), 500


@bp.route('/api/admin/order/update/<int:id>', methods=['POST'])
@admin_required
def admin_update_order(id):
    """管理员修改订单信息（收货人、总价、状态等）"""
    try:
        order = Order.query.get_or_404(id)
        data = request.get_json()
        order.receiver_name = data.get('receiver_name', order.receiver_name)
        order.receiver_phone = data.get('receiver_phone', order.receiver_phone)
        order.receiver_address = data.get('receiver_address', order.receiver_address)
        order.total_price = data.get('total_price', order.total_price)
        order.status = data.get('status', order.status)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '订单修改成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员修改订单错误: {e}")
        return jsonify({'code': 500, 'msg': '修改订单失败'}), 500


@bp.route('/api/admin/order/delete/<int:id>', methods=['DELETE'])
@admin_required
def admin_delete_order(id):
    """管理员删除订单（同时删除关联售后）"""
    try:
        order = Order.query.get_or_404(id)
        ReturnRequest.query.filter_by(order_id=id).delete()
        db.session.delete(order)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '订单删除成功'})
    except Exception as e:
        db.session.rollback()
        print(f"管理员删除订单错误: {e}")
        return jsonify({'code': 500, 'msg': '删除订单失败'}), 500


@bp.route('/api/admin/monitor/realtime', methods=['GET'])
@admin_required
def monitor_realtime():
    """最近60分钟实时数据"""
    try:
        minutes = []
        now = datetime.now()
        for i in range(59, -1, -1):
            t = now - timedelta(minutes=i)
            key = t.strftime('%Y%m%d%H%M')
            total = int(redis_client.get(f'monitor:minute:{key}:total') or 0)
            errors = int(redis_client.get(f'monitor:minute:{key}:error') or 0)
            duration_sum = int(redis_client.get(f'monitor:minute:{key}:duration') or 0)
            avg_dur = int(duration_sum / total) if total > 0 else 0
            minutes.append({
                'time': t.strftime('%H:%M'),
                'total': total,
                'errors': errors,
                'avg_duration': avg_dur
            })

        # 今日汇总
        today_total = sum(m['total'] for m in minutes)
        today_errors = sum(m['errors'] for m in minutes)
        today_avg = int(sum(m['avg_duration'] * m['total'] for m in minutes) / today_total) if today_total > 0 else 0

        return jsonify({
            'code': 200,
            'data': {
                'timeline': minutes,
                'summary': {
                    'total_requests': today_total,
                    'avg_duration': today_avg,
                    'error_rate': round(today_errors / today_total * 100, 2) if today_total > 0 else 0
                }
            }
        })
    except Exception as e:
        print(f"获取实时监控数据错误: {e}")
        return jsonify({'code': 500, 'msg': '获取监控数据失败'}), 500


@bp.route('/api/admin/monitor/user-activity', methods=['GET'])
@admin_required
def monitor_user_activity():
    """用户活跃度：今日活跃用户、新注册、每小时活跃趋势"""
    try:
        today_key = datetime.now().strftime('%Y%m%d')
        active_users = redis_client.scard(f'monitor:active_users:{today_key}')
        new_registrations = int(redis_client.get(f'monitor:new_registrations:{today_key}') or 0)

        # 每小时活跃用户趋势
        hourly = []
        now = datetime.now()
        for i in range(23, -1, -1):
            h = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
            hour_key = h.strftime('%Y%m%d%H')
            count = redis_client.scard(f'monitor:active_hour:{hour_key}')
            hourly.append({'hour': h.strftime('%H:00'), 'count': count})

        return jsonify({
            'code': 200,
            'data': {
                'active_users': active_users,
                'new_registrations': new_registrations,
                'hourly_trend': hourly
            }
        })
    except Exception as e:
        print(f"获取用户活跃度错误: {e}")
        return jsonify({'code': 500, 'msg': '获取数据失败'}), 500


@bp.route('/api/admin/monitor/product-ranking', methods=['GET'])
@admin_required
def monitor_product_ranking():
    """商品热度排行：销量Top10"""
    try:
        # 销量Top10
        from sqlalchemy import func
        sales = db.session.query(
            Goods.name, func.sum(OrderItem.num).label('count')
        ).join(OrderItem, OrderItem.goods_id == Goods.id
               ).join(Order, Order.id == OrderItem.order_id
                      ).filter(Order.status != 'cancelled'
                               ).group_by(Goods.id, Goods.name
                                          ).order_by(func.sum(OrderItem.num).desc()
                                                     ).limit(10).all()
        by_sales = [{'name': s.name, 'count': int(s.count)} for s in sales]

        return jsonify({
            'code': 200,
            'data': {'by_sales': by_sales}
        })
    except Exception as e:
        print(f"获取商品排行错误: {e}")
        return jsonify({'code': 500, 'msg': '获取数据失败'}), 500


@bp.route('/api/admin/monitor/order-overview', methods=['GET'])
@admin_required
def monitor_order_overview():
    """订单交易概览：实时从订单表计算"""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. 今日所有订单
        today_orders = Order.query.filter(Order.created_at >= today_start).all()
        today_order_count = len(today_orders)

        # 2. 今日交易额（已付款/发货/收货/完成的订单）
        paid_statuses = ('pending_ship', 'pending_receive', 'completed')
        today_revenue = sum(
            float(o.total_price) for o in today_orders if o.status in paid_statuses
        )

        # 3. 今日订单状态分布
        status_labels = {
            'pending_pay': '待付款', 'pending_ship': '待发货',
            'pending_receive': '待收货', 'completed': '已完成',
            'cancelled': '已取消', 'refund': '退款中', 'refunded': '已退款'
        }
        status_map = {}
        for o in today_orders:
            label = status_labels.get(o.status, o.status)
            status_map[label] = status_map.get(label, 0) + 1

        status_dist = [{'name': name, 'value': count} for name, count in status_map.items()]

        return jsonify({
            'code': 200,
            'data': {
                'today_orders': today_order_count,
                'today_revenue': round(today_revenue, 2),
                'status_distribution': status_dist
            }
        })
    except Exception as e:
        print(f"获取订单概览错误: {e}")
        return jsonify({'code': 500, 'msg': '获取数据失败'}), 500


@bp.route('/api/admin/monitor/search-keywords', methods=['GET'])
@admin_required
def monitor_search_keywords():
    """搜索关键词排行Top10：从MySQL快照读取"""
    try:
        snapshots = Snapshot.query.filter_by(type='search_keyword').order_by(Snapshot.count.desc()).all()
        if not snapshots:
            # 快照为空时实时计算一次并写入
            scheduled_refresh_search_keywords()
            snapshots = Snapshot.query.filter_by(type='search_keyword').order_by(Snapshot.count.desc()).all()

        result = [{'keyword': s.name, 'count': s.count} for s in snapshots]
        return jsonify({'code': 200, 'data': result})
    except Exception as e:
        print(f"获取搜索关键词错误: {e}")
        return jsonify({'code': 500, 'msg': '获取数据失败'}), 500




def _safe_int(val, default=0):
    """安全转 int：非法值返回默认值，避免 500"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

# ==================== 轮播运营位管理 ====================

@bp.route('/api/admin/banners', methods=['GET'])
@admin_required
def admin_get_banners():
    """管理员获取轮播列表"""
    try:
        banners = Banner.query.order_by(Banner.sort.desc(), Banner.id.asc()).all()
        data = [{
            'id': b.id,
            'image': fix_image_url(b.image),
            'title': b.title or '',
            'button_text': b.button_text or '查看详情',
            'link': b.link or '',
            'sort': b.sort or 0,
            'enabled': b.enabled
        } for b in banners]
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f'管理员获取轮播失败: {e}')
        return jsonify({'code': 500, 'msg': '获取轮播失败'}), 500


@bp.route('/api/admin/banner/add', methods=['POST'])
@admin_required
def admin_add_banner():
    """新增轮播（image 必填）"""
    try:
        data = request.get_json(silent=True) or {}
        image = (data.get('image') or '').strip()
        if not image:
            return jsonify({'code': 400, 'msg': '轮播图片地址不能为空'}), 400
        banner = Banner(
            image=image,
            title=(data.get('title') or '').strip()[:100],
            button_text=(data.get('button_text') or '查看详情').strip()[:50],
            link=(data.get('link') or '').strip()[:200],
            sort=_safe_int(data.get('sort')),
            enabled=1 if str(data.get('enabled', 1)) in ('1', 'true', 'True') else 0
        )
        db.session.add(banner)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '轮播添加成功', 'id': banner.id})
    except Exception as e:
        db.session.rollback()
        print(f'添加轮播失败: {e}')
        return jsonify({'code': 500, 'msg': '添加失败'}), 500


@bp.route('/api/admin/banner/update/<int:id>', methods=['POST'])
@admin_required
def admin_update_banner(id):
    """修改轮播（标题/排序/启用状态）"""
    try:
        banner = Banner.query.get_or_404(id)
        data = request.get_json(silent=True) or {}
        if 'image' in data and (data.get('image') or '').strip():
            banner.image = data['image'].strip()
        if 'title' in data:
            banner.title = (data.get('title') or '')[:100]
        if 'button_text' in data:
            banner.button_text = (data.get('button_text') or '查看详情')[:50]
        if 'link' in data:
            banner.link = (data.get('link') or '')[:200]
        if 'sort' in data:
            banner.sort = _safe_int(data.get('sort'))
        if 'enabled' in data:
            banner.enabled = 1 if str(data.get('enabled')) in ('1', 'true', 'True') else 0
        db.session.commit()
        return jsonify({'code': 200, 'msg': '轮播已更新'})
    except Exception as e:
        db.session.rollback()
        print(f'修改轮播失败: {e}')
        return jsonify({'code': 500, 'msg': '修改失败'}), 500


@bp.route('/api/admin/banner/delete/<int:id>', methods=['DELETE'])
@admin_required
def admin_delete_banner(id):
    """删除轮播"""
    try:
        banner = Banner.query.get_or_404(id)
        db.session.delete(banner)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '轮播已删除'})
    except Exception as e:
        db.session.rollback()
        print(f'删除轮播失败: {e}')
        return jsonify({'code': 500, 'msg': '删除失败'}), 500
