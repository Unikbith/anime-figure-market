"""recommend 模块路由（蓝本）"""
from flask import jsonify
import random

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.extensions import redis_client
from backend.models import Goods
from backend.utils import fix_image_url

bp = Blueprint('recommend', __name__)

@bp.route('/api/recommend/personal', methods=['GET'])
@jwt_required()
def get_personal_recommend():
    """
    有权重记录时，偏好相关商品概率更高，但所有商品都有机会出现
    """
    try:
        user_id = int(get_jwt_identity())
        all_goods = Goods.query.filter(Goods.status != '下架').all()
        if not all_goods:
            return jsonify({'code': 200, 'data': []})

        ip_prefs = redis_client.zrevrange(f'user_pref:{user_id}:ip', 0, 5, withscores=True)
        char_prefs = redis_client.zrevrange(f'user_pref:{user_id}:character', 0, 5, withscores=True)
        cate_prefs = redis_client.zrevrange(f'user_pref:{user_id}:category', 0, 5, withscores=True)

        pref_weights = {}
        for k, score in list(ip_prefs) + list(char_prefs) + list(cate_prefs):
            if k:
                keyword = k.decode() if isinstance(k, bytes) else k
                pref_weights[keyword] = pref_weights.get(keyword, 0) + score

        goods_scores = []
        base_score = 1  # 基础分

        for g in all_goods:
            score = base_score
            if g.ip and g.ip in pref_weights:
                score += pref_weights[g.ip] * 2
            if g.charactername and g.charactername in pref_weights:
                score += pref_weights[g.charactername] * 2
            if g.category and g.category in pref_weights:
                score += pref_weights[g.category]
            if g.brand and g.brand in pref_weights:
                score += pref_weights.get(g.brand, 0)
            for keyword, weight in pref_weights.items():
                if keyword.lower() in g.name.lower():
                    score += weight * 0.5

            goods_scores.append((g, score))

        total_score = sum(score for _, score in goods_scores)
        rand_val = random.random() * total_score
        cumulative = 0
        selected_goods = goods_scores[0][0]  # 默认第一个
        for g, score in goods_scores:
            cumulative += score
            if rand_val <= cumulative:
                selected_goods = g
                break

        goods_data = {
            'id': selected_goods.id,
            'name': selected_goods.name,
            'price': float(selected_goods.price),
            'image': fix_image_url(selected_goods.images.split(',')[0]) if selected_goods.images else '',
            'ip': selected_goods.ip,
            'charactername': selected_goods.charactername
        }

        return jsonify({'code': 200, 'data': [goods_data]})
    except Exception as e:
        print(f"猜你喜欢错误: {e}")
        return jsonify({'code': 500, 'msg': '获取推荐失败'})
