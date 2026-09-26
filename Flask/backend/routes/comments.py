"""comments 模块路由（蓝本）"""
from flask import request, jsonify

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.extensions import db
from backend.models import Goods, Comment
from backend.utils import fix_image_url

bp = Blueprint('comments', __name__)

@bp.route('/api/comments/list/<int:goods_id>', methods=['GET'])
def get_comments_list(goods_id):
    """获取某商品的所有评论"""
    try:
        comments = Comment.query.filter_by(goods_id=goods_id).order_by(Comment.created_at.desc()).all()
        res = []
        for c in comments:
            res.append({
                'id': c.id,
                'user_id': c.user_id,
                'username': c.user.nickname,
                'avatar': fix_image_url((c.user.avatar if c.user else '') or ''),
                'content': c.content,
                'time': c.created_at.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({'code': 200, 'data': res})
    except Exception as e:
        print(f"获取评论失败: {e}")
        return jsonify({'code': 500, 'msg': '获取评论失败'})


@bp.route('/api/comments/add', methods=['POST'])
@jwt_required()
def add_comment():
    """发表评论"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        goods_id = data.get('goods_id')
        content = (data.get('content') or '').strip()
        if not goods_id or not content:
            return jsonify({'code': 400, 'msg': '商品ID和评论内容不能为空'})
        goods = Goods.query.get(goods_id)
        if not goods:
            return jsonify({'code': 404, 'msg': '商品不存在'})
        new_comment = Comment(user_id=user_id, goods_id=goods_id, content=content)
        db.session.add(new_comment)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '评论成功'})
    except Exception as e:
        db.session.rollback()
        print(f"发表评论失败: {e}")
        return jsonify({'code': 500, 'msg': '发表评论失败'})


@bp.route('/api/comments/delete/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    """删除自己的评论"""
    try:
        current_user_id = int(get_jwt_identity())
        comment = Comment.query.get_or_404(comment_id)
        if str(comment.user_id) != str(current_user_id):
            return jsonify({'code': 403, 'msg': '无权限删除他人评论'}), 403
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '评论删除成功'})
    except Exception as e:
        db.session.rollback()
        print(f"删除评论失败: {e}")
        return jsonify({'code': 500, 'msg': '删除失败'}), 500


