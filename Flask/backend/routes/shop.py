"""shop 模块路由（蓝本）"""
from flask import request, jsonify

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.extensions import db
from backend.models import Goods, Cart, Collect
from backend.utils import fix_image_url

bp = Blueprint('shop', __name__)

@bp.route('/api/cart/list', methods=['GET'])
@jwt_required()
def cart_list():
    """获取当前用户的购物车列表"""
    try:
        user_id = int(get_jwt_identity())
        cart_items = Cart.query.filter_by(user_id=user_id).all()
        res = []
        for item in cart_items:
            g = item.goods
            res.append({
                'id': item.id,
                'goods_id': g.id,
                'name': g.name,
                'price': float(g.price),
                'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
                'num': item.num,
                'stock': g.stock,
                'status': g.status
            })
        return jsonify({'code': 200, 'data': res})
    except Exception as e:
        print(f"获取购物车错误: {e}")
        return jsonify({'code': 500, 'msg': '获取购物车失败'})


@bp.route('/api/cart/add', methods=['POST'])
@jwt_required()
def cart_add():
    """添加商品到购物车"""
    try:
        user_id = int(get_jwt_identity())
        goods_id = request.get_json().get('goods_id')
        goods = Goods.query.get(goods_id)
        if not goods:
            return jsonify({'code': 404, 'msg': '商品不存在'})
        if goods.status == '下架':
            return jsonify({'code': 400, 'msg': '商品已下架'})
        if goods.stock <= 0:
            return jsonify({'code': 400, 'msg': '商品已售罄'})
        item = Cart.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        if item:
            item.num += 1
        else:
            item = Cart(user_id=user_id, goods_id=goods_id, num=1)
            db.session.add(item)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '加入购物车成功'})
    except Exception as e:
        db.session.rollback()
        print(f"加入购物车错误: {e}")
        return jsonify({'code': 500, 'msg': '加入购物车失败'})


@bp.route('/api/cart/update', methods=['POST'])
@jwt_required()
def cart_update():
    """修改购物车中商品数量"""
    try:
        data = request.get_json()
        item = Cart.query.get(data['id'])
        if not item:
            return jsonify({'code': 404, 'msg': '购物车项不存在'})
        item.num = data['num']
        db.session.commit()
        return jsonify({'code': 200, 'msg': '修改成功'})
    except Exception as e:
        print(f"修改数量错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '修改失败'})


@bp.route('/api/cart/delete/<int:id>', methods=['DELETE'])
@jwt_required()
def cart_delete(id):
    """删除购物车中的单个商品"""
    try:
        item = Cart.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '删除成功'})
    except Exception as e:
        print(f"删除商品错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '删除失败'})


@bp.route('/api/cart/clear', methods=['DELETE'])
@jwt_required()
def clear_cart():
    """支付成功后调用"""
    try:
        user_id = int(get_jwt_identity())
        Cart.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'code': 200, 'msg': '支付成功，购物车已清空'})
    except Exception as e:
        db.session.rollback()
        print(f"清空购物车错误: {e}")
        return jsonify({'code': 500, 'msg': '支付失败，请重试'})


@bp.route('/api/collect/add', methods=['POST'])
@jwt_required()
def add_collect():
    """添加收藏"""
    try:
        user_id = int(get_jwt_identity())
        goods_id = request.get_json().get('goods_id')
        if not goods_id:
            return jsonify({'code': 400, 'msg': '商品ID不能为空'}), 400
        goods = Goods.query.get(goods_id)
        if not goods:
            return jsonify({'code': 404, 'msg': '商品不存在'}), 404
        exist = Collect.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        if exist:
            return jsonify({'code': 400, 'msg': '已收藏该商品'}), 400
        new_collect = Collect(user_id=user_id, goods_id=goods_id)
        db.session.add(new_collect)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '收藏成功'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'添加收藏失败: {e}')
        return jsonify({'code': 500, 'msg': '收藏失败'}), 500


@bp.route('/api/collect/delete', methods=['POST'])
@jwt_required()
def delete_collect():
    """取消收藏"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        collect_id = data.get('id')
        goods_id = data.get('goods_id')
        if not collect_id and not goods_id:
            return jsonify({'code': 400, 'msg': '参数错误'}), 400
        if collect_id:
            collect = Collect.query.get(collect_id)
        else:
            collect = Collect.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        if not collect:
            return jsonify({'code': 404, 'msg': '收藏记录不存在'}), 404
        db.session.delete(collect)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '取消收藏成功'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'取消收藏失败: {e}')
        return jsonify({'code': 500, 'msg': '操作失败'}), 500


@bp.route('/api/collect/list', methods=['GET'])
@jwt_required()
def get_collect_list():
    """获取当前用户的收藏列表"""
    try:
        user_id = int(get_jwt_identity())
        collects = Collect.query.filter_by(user_id=user_id).order_by(Collect.created_at.desc()).all()
        res = []
        for item in collects:
            g = item.goods
            res.append({
                'id': item.id,
                'goods_id': g.id,
                'name': g.name,
                'price': float(g.price),
                'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
                'created_at': item.created_at.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'code': 200, 'data': res}), 200
    except Exception as e:
        print(f'获取收藏列表失败: {e}')
        return jsonify({'code': 500, 'msg': '获取失败'}), 500


@bp.route('/api/collect/check', methods=['GET'])
@jwt_required()
def check_collect():
    """检查当前用户是否收藏了某商品"""
    try:
        user_id = int(get_jwt_identity())
        goods_id = request.args.get('goods_id')
        if not goods_id:
            return jsonify({'code': 400, 'msg': '商品ID不能为空'}), 400
        exist = Collect.query.filter_by(user_id=user_id, goods_id=goods_id).first()
        return jsonify({'code': 200, 'data': {'is_collected': exist is not None}}), 200
    except Exception as e:
        print(f'检查收藏状态失败: {e}')
        return jsonify({'code': 500, 'msg': '检查失败'}), 500

