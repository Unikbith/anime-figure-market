"""user 模块路由（蓝本）"""
from flask import request, jsonify
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.extensions import db, redis_client
from backend.models import Goods, History, NotificationLog
from backend.utils import fix_image_url

bp = Blueprint('user', __name__)

@bp.route('/api/user/history/add', methods=['POST'])
@jwt_required()
def add_history():
    """手动添加浏览记录"""
    try:
        user_id = int(get_jwt_identity())
        goods_id = request.get_json().get('goods_id')
        if not goods_id:
            return jsonify({'code': 400, 'msg': '商品ID不能为空'})
        goods = Goods.query.get(goods_id)
        if not goods:
            return jsonify({'code': 404, 'msg': '商品不存在'})
        existing_history = History.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        if existing_history:
            existing_history.browse_time = datetime.now()  # 更新浏览时间
        else:
            new_history = History(user_id=user_id, goods_id=goods_id)
            db.session.add(new_history)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '足迹记录成功'})
    except Exception as e:
        print(f"记录足迹错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '记录足迹失败'})


@bp.route('/api/user/history', methods=['GET'])
@jwt_required()
def get_history():
    """获取当前用户的浏览历史列表"""
    try:
        user_id = int(get_jwt_identity())
        history_list = History.query.filter_by(user_id=user_id).order_by(History.browse_time.desc()).all()
        res = []
        for item in history_list:
            g = item.goods
            res.append({
                'id': item.id,
                'goodsId': g.id,
                'name': g.name,
                'price': float(g.price),
                'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
                'browseTime': item.browse_time.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'code': 200, 'data': res})
    except Exception as e:
        print(f"获取足迹错误: {e}")
        return jsonify({'code': 500, 'msg': '获取足迹失败'})


@bp.route('/api/user/history/delete', methods=['POST'])
@jwt_required()
def delete_history():
    """删除单条浏览记录"""
    try:
        history_id = request.get_json().get('id')
        history = History.query.get(history_id)
        if not history:
            return jsonify({'code': 404, 'msg': '足迹不存在'})
        db.session.delete(history)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '删除成功'})
    except Exception as e:
        print(f"删除足迹错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '删除失败'})


@bp.route('/api/user/history/clear', methods=['POST'])
@jwt_required()
def clear_history():
    """清空所有浏览记录"""
    try:
        user_id = int(get_jwt_identity())
        History.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'code': 200, 'msg': '清空成功'})
    except Exception as e:
        print(f"清空足迹错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '清空失败'})


@bp.route('/api/user/behavior', methods=['POST'])
@jwt_required()
def record_user_behavior():
    """
    行为权重：浏览=1，收藏=3，购买=5
    """
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        goods_id = data.get('goods_id')
        behavior_type = data.get('type', 'view')

        if not goods_id:
            return jsonify({'code': 400, 'msg': '商品ID不能为空'})

        goods = Goods.query.get(goods_id)
        if not goods:
            return jsonify({'code': 404, 'msg': '商品不存在'})

        # 权重映射
        weight_map = {'view': 1, 'collect': 3, 'purchase': 5}
        weight = weight_map.get(behavior_type, 1)

        # 使用Redis存储用户行为权重
        pipe = redis_client.pipeline()
        if goods.ip:
            key = f'user_pref:{user_id}:ip'
            pipe.zincrby(key, weight, goods.ip)
        if goods.charactername:
            key = f'user_pref:{user_id}:character'
            pipe.zincrby(key, weight, goods.charactername)
        if goods.category:
            key = f'user_pref:{user_id}:category'
            pipe.zincrby(key, weight, goods.category)
        if goods.brand:
            key = f'user_pref:{user_id}:brand'
            pipe.zincrby(key, weight, goods.brand)
        pipe.execute()

        return jsonify({'code': 200, 'msg': '记录成功'})
    except Exception as e:
        print(f"记录用户行为错误: {e}")
        return jsonify({'code': 500, 'msg': '记录失败'})


@bp.route('/api/user/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """获取当前用户的所有通知"""
    try:
        user_id = int(get_jwt_identity())
        notifications = NotificationLog.query.filter_by(user_id=user_id).order_by(NotificationLog.sent_at.desc()).all()
        res = []
        for n in notifications:
            res.append({
                'id': n.id,
                'type': n.type,
                'content': n.content,
                'status': n.status,
                'goods_id': n.goods_id,
                'order_id': n.order_id,
                'goods_name': n.goods.name if n.goods else '',
                'goods_image': fix_image_url(n.goods.images.split(',')[0]) if n.goods and n.goods.images else '',
                'sent_at': n.sent_at.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'code': 200, 'data': res})
    except Exception as e:
        print(f"获取通知错误: {e}")
        return jsonify({'code': 500, 'msg': '获取通知失败'})


@bp.route('/api/user/notifications/read/<int:notification_id>', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    """将通知标记为已读"""
    try:
        user_id = int(get_jwt_identity())
        notification = NotificationLog.query.filter_by(id=notification_id, user_id=user_id).first()
        if not notification:
            return jsonify({'code': 404, 'msg': '通知不存在'})
        notification.status = 'read'
        db.session.commit()
        return jsonify({'code': 200, 'msg': '已标记为已读'})
    except Exception as e:
        print(f"标记通知错误: {e}")
        return jsonify({'code': 500, 'msg': '操作失败'})


@bp.route('/api/user/notifications/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """获取未读通知数量"""
    try:
        user_id = int(get_jwt_identity())
        count = NotificationLog.query.filter_by(user_id=user_id, status='sent').count()
        return jsonify({'code': 200, 'data': {'count': count}})
    except Exception as e:
        print(f"获取未读数错误: {e}")
        return jsonify({'code': 500, 'msg': '获取失败'})


