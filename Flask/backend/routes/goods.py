"""goods 模块路由（蓝本）"""
from flask import request, jsonify
from minio.error import S3Error
import uuid
import json
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, decode_token
from sqlalchemy import or_

from backend.extensions import db, redis_client, minio_client, MINIO_BUCKET
from backend.models import User, Goods, Cart, Collect, History, Banner
from backend.tasks import notify_price_drop, notify_off_shelf, notify_goods_update
from backend.utils import fix_image_url, cache, cache_invalidate, parse_int
from backend import es

bp = Blueprint('goods', __name__)

@bp.route('/api/upload/image', methods=['POST'])
@jwt_required()
def upload_image():
    """上传商品图片到MinIO，返回图片URL"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'msg': '请选择图片'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 400, 'msg': '文件名不能为空'})
    # 扩展名白名单：防止上传 svg/html 等可执行/可脚本内容（存储型 XSS）
    ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in ALLOWED_EXT:
        return jsonify({'code': 400, 'msg': '仅支持 jpg/jpeg/png/gif/webp/bmp 图片格式'}), 400
    file_name = f"{uuid.uuid4().hex}.{file_ext}"  # UUID命名避免冲突
    try:
        minio_client.put_object(MINIO_BUCKET, file_name, file, length=-1, part_size=10 * 1024 * 1024,
                                content_type=f"image/{file_ext}")
        return jsonify({'code': 200, 'msg': '上传成功', 'url': f"/goods-images/{file_name}"})
    except S3Error as e:
        print(f"MinIO错误: {e}")
        return jsonify({'code': 500, 'msg': '图片上传失败'})

@bp.route('/api/goods/publish', methods=['POST'])
@jwt_required()
def publish_goods():
    """商家发布新商品"""
    user = get_jwt()
    if user['role'] != 'merchant':
        return jsonify({'code': 403, 'msg': '仅商家可发布'})
    user_obj = User.query.get(user['id'])
    if not user_obj:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    if user_obj.apply_status != 'approved':
        if user_obj.apply_status == 'none':
            return jsonify({'code': 403, 'msg': '请先提交入驻申请，等待管理员审核通过后再发布商品'}), 403
        elif user_obj.apply_status == 'pending':
            return jsonify({'code': 403, 'msg': '您的入驻申请正在审核中，请等待管理员审核通过'}), 403
        elif user_obj.apply_status == 'rejected':
            return jsonify({'code': 403, 'msg': '您的入驻申请已被拒绝，无法发布商品，如有疑问请联系管理员'}), 403
    data = request.get_json(silent=True) or {}
    required_fields = ['name', 'price', 'images']
    if not all([data.get(field) for field in required_fields]):
        return jsonify({'code': 400, 'msg': '请完善商品名称、价格、图片'})
    # 边界校验：价格必须为正数、库存必须为非负整数
    try:
        price_val = float(data['price'])
        stock_val = int(data.get('stock', 1))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'msg': '价格或库存格式不正确'}), 400
    if price_val <= 0:
        return jsonify({'code': 400, 'msg': '价格必须大于0'}), 400
    if stock_val < 0:
        return jsonify({'code': 400, 'msg': '库存不能为负数'}), 400
    if len(str(data['name'])) > 100:
        return jsonify({'code': 400, 'msg': '商品名称过长'}), 400
    new_goods = Goods(
        name=data['name'],
        price=price_val,
        stock=stock_val,
        images=','.join(data['images']),
        description=data.get('description', ''),
        category=data.get('category', ''),
        status=data.get('status', ''),
        brand=data.get('brand', ''),
        ip=data.get('ip', ''),
        charactername=data.get('character', ''),
        specs=_dump_specs(data.get('specs')),
        tags=(data.get('tags') or '').strip()[:200],
        services=(data.get('services') or '').strip()[:200],
        sales=0,
        merchant_id=user['id']
    )
    try:
        db.session.add(new_goods)
        db.session.commit()
        es.index_goods(new_goods)   # 同步 ES 索引
        return jsonify({'code': 200, 'msg': '上架成功', 'goods_id': new_goods.id})
    except Exception as e:
        db.session.rollback()
        print(f"发布商品错误: {e}")
        return jsonify({'code': 500, 'msg': '上架失败'})

@bp.route('/api/goods/list', methods=['GET'])
@cache(key_prefix='goods_list', expire=600)
def get_goods_list():
    """分页获取商品列表（带缓存，10分钟过期；支持 category 筛选）"""
    page = parse_int(request.args.get('page'), 1, minimum=1)
    size = parse_int(request.args.get('size'), 20, minimum=1, maximum=100)
    category = (request.args.get('category') or '').strip()
    status = (request.args.get('status') or '').strip()
    query = Goods.query
    if category:
        query = query.filter(Goods.category == category)
    if status:
        query = query.filter(Goods.status == status)
    pagination = query.order_by(Goods.created_at.desc()).paginate(page=page, per_page=size, error_out=False)
    goods = pagination.items

    res = [{
        'id': g.id,
        'name': g.name,
        'price': float(g.price),
        'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
        'description': g.description,
        'category': g.category,
        'status': g.status,
        'brand': g.brand,
        'ip': g.ip,
        'charactername': g.charactername,
        'merchant_name': g.merchant.nickname if g.merchant else ''
    } for g in goods]
    return jsonify({
        'code': 200,
        'data': res,
        'pagination': {
            'total': pagination.total,
            'page': page,
            'size': size,
            'pages': pagination.pages
        }
    })

def _goods_brief(g):
    """列表/搜索用的商品摘要字段"""
    return {
        'id': g.id,
        'name': g.name,
        'price': float(g.price) if g.price else 0,
        'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
        'description': g.description or '',
        'category': g.category or '',
        'status': g.status or '',
        'brand': g.brand or '',
        'ip': g.ip or '',
        'charactername': g.charactername or '',
        'merchant_name': g.merchant.nickname if g.merchant else ''
    }

@bp.route('/api/goods/search', methods=['GET'])
def search_goods():
    """商品搜索：优先 Elasticsearch 全文检索，ES 不可用时自动降级 MySQL 模糊匹配"""
    try:
        q = (request.args.get('q') or '').strip()
        page = parse_int(request.args.get('page'), 1, minimum=1)
        size = parse_int(request.args.get('size'), 20, minimum=1, maximum=100)
        if not q:
            return jsonify({'code': 400, 'msg': '搜索关键词不能为空'})
        try:
            today_key = datetime.now().strftime('%Y%m%d')
            redis_client.zincrby(f'monitor:search_keywords:{today_key}', 1, q)
            redis_client.expire(f'monitor:search_keywords:{today_key}', 86400 * 7)
        except Exception:
            pass

        # 优先 ES：按相关度取 id，再回 MySQL 取完整字段（响应结构与 LIKE 版一致）
        es_result = es.search_ids(q, page, size)
        if es_result is not None:
            ids, total = es_result
            goods_map = {g.id: g for g in Goods.query.filter(Goods.id.in_(ids or [0])).all()}
            ordered = [goods_map[i] for i in ids if i in goods_map]
            return jsonify({
                'code': 200,
                'data': [_goods_brief(g) for g in ordered],
                'pagination': {
                    'total': total, 'page': page, 'size': size,
                    'pages': (total + size - 1) // size
                }
            })

        # 降级：MySQL 多字段模糊匹配
        like = f'%{q}%'
        pagination = Goods.query.filter(
            Goods.status != '下架',
            or_(
                Goods.name.like(like),
                Goods.description.like(like),
                Goods.category.like(like),
                Goods.brand.like(like),
                Goods.ip.like(like),
                Goods.charactername.like(like),
            )
        ).order_by(Goods.id.desc()).paginate(page=page, per_page=size, error_out=False)

        return jsonify({
            'code': 200,
            'data': [_goods_brief(g) for g in pagination.items],
            'pagination': {
                'total': pagination.total,
                'page': page,
                'size': size,
                'pages': pagination.pages
            }
        })
    except Exception as e:
        print(f"搜索商品错误: {e}")
        return jsonify({'code': 500, 'msg': '搜索失败'})

@bp.route('/api/goods/options', methods=['GET'])
def get_goods_options():
    """获取商品筛选选项（分类、品牌、IP列表）"""
    try:
        categories = db.session.query(Goods.category).filter(
            Goods.category != None,
            Goods.category != ''
        ).distinct().all()
        brands = db.session.query(Goods.brand).filter(
            Goods.brand != None,
            Goods.brand != ''
        ).distinct().all()
        ips = db.session.query(Goods.ip).filter(
            Goods.ip != None,
            Goods.ip != ''
        ).distinct().all()

        return jsonify({
            'code': 200,
            'data': {
                'categories': [c[0] for c in categories if c[0]],
                'brands': [b[0] for b in brands if b[0]],
                'ips': [i[0] for i in ips if i[0]]
            }
        })
    except Exception as e:
        print(f"获取商品选项错误: {e}")
        return jsonify({'code': 500, 'msg': '获取选项失败'})

@bp.route('/api/goods/detail/<int:id>', methods=['GET'])
@cache(key_prefix='goods_detail', expire=1800)
def get_goods_detail(id):
    """获取商品详情，同时自动记录浏览历史"""
    g = Goods.query.get_or_404(id)
    merchant_avatar = ''
    merchant_user = User.query.get(g.merchant_id)
    if merchant_user:
        merchant_avatar = merchant_user.avatar or ''

    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        try:
            decoded = decode_token(token.split(' ')[1])
            user_id = int(decoded['sub'])
            existing_history = History.query.filter_by(user_id=user_id, goods_id=id).first()
            if existing_history:
                existing_history.browse_time = datetime.now()  # 更新浏览时间
            else:
                new_history = History(user_id=user_id, goods_id=id)
                db.session.add(new_history)
            db.session.commit()
        except Exception as e:
            print(f"自动记录足迹失败: {e}")

    images = [fix_image_url(img) for img in g.images.split(',')] if g.images else []
    try:
        specs = json.loads(g.specs) if g.specs else {}
        if not isinstance(specs, dict):
            specs = {}
    except Exception:
        specs = {}
    return jsonify({
        'code': 200,
        'data': {
            'id': g.id,
            'name': g.name,
            'price': float(g.price),
            'stock': g.stock,
            'images': images,
            'description': g.description,
            'category': g.category,
            'status': g.status,
            'brand': g.brand,
            'ip': g.ip,
            'character': g.charactername,
            'specs': specs,
            'tags': [t for t in (g.tags or '').split(',') if t],
            'sales': g.sales or 0,
            'services': [s for s in (g.services or '').split(',') if s],
            'merchant_name': g.merchant.nickname if g.merchant else '',
            'merchant_avatar': fix_image_url(merchant_avatar),
            'created_at': g.created_at.strftime('%Y-%m-%d')
        }
    })

@bp.route('/api/goods/merchant', methods=['GET'])
@jwt_required()
def get_merchant_goods():
    """商家获取自己发布的商品列表"""
    try:
        user = get_jwt()
        if user['role'] != 'merchant':
            return jsonify({'code': 403, 'msg': '仅商家可访问'})
        goods = Goods.query.filter_by(merchant_id=user['id']).order_by(Goods.created_at.desc()).all()

        res = [{
            'id': g.id,
            'name': g.name,
            'price': float(g.price),
            'image': fix_image_url(g.images.split(',')[0]) if g.images else '',
            'status': g.status,
            'category': g.category
        } for g in goods]
        return jsonify({'code': 200, 'data': res})
    except Exception as e:
        print(f"获取商家商品错误: {e}")
        return jsonify({'code': 500, 'msg': '获取商品失败'})

@bp.route('/api/goods/update/<int:id>', methods=['POST'])
@jwt_required()
def update_goods(id):
    """商家更新商品信息，同时触发价格/下架/名称变更通知"""
    try:
        user = get_jwt()
        if user['role'] != 'merchant':
            return jsonify({'code': 403, 'msg': '仅商家可操作'})
        goods = Goods.query.get_or_404(id)
        if goods.merchant_id != user['id']:
            return jsonify({'code': 403, 'msg': '无权修改该商品'})
        data = request.get_json()
        old_price = float(goods.price)
        old_status = goods.status
        old_name = goods.name

        goods.name = data.get('name', goods.name)
        goods.price = data.get('price', goods.price)
        goods.stock = data.get('stock', goods.stock)
        goods.images = ','.join(data.get('images', [])) if data.get('images') else goods.images
        goods.description = data.get('description', goods.description)
        goods.category = data.get('category', goods.category)
        goods.status = data.get('status', goods.status)
        goods.brand = data.get('brand', goods.brand)
        goods.ip = data.get('ip', goods.ip)
        goods.charactername = data.get('character', goods.charactername)
        if isinstance(data.get('specs'), dict) and data.get('specs'):
            goods.specs = _dump_specs(data.get('specs'))
        if 'tags' in data:
            goods.tags = (data.get('tags') or '')[:200]
        db.session.commit()
        es.index_goods(goods)   # 同步 ES 索引

        new_stock = data.get('stock')
        if new_stock is not None:
            redis_client.set(f"goods_stock:{id}", new_stock)
        cache_invalidate('goods_list:*')
        redis_client.delete(f'goods_detail:{id}')

        # 降价通知：新价格低于旧价格时触发
        new_price = data.get('price')
        if new_price is not None and float(new_price) < old_price:
            notify_price_drop.delay(id, old_price, float(new_price))

        # 下架通知：状态从非下架变为下架时触发
        new_status = data.get('status')
        if old_status != '下架' and new_status == '下架':
            notify_off_shelf.delay(id)

        new_name = data.get('name')
        if new_name is not None and new_name != old_name:
            notify_goods_update.delay(id, old_name, new_name)

        return jsonify({'code': 200, 'msg': '更新成功'})
    except Exception as e:
        db.session.rollback()
        print(f"更新商品错误: {e}")
        return jsonify({'code': 500, 'msg': '更新失败'})

@bp.route('/api/goods/delete/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_goods(id):
    """商家删除商品"""
    try:
        user = get_jwt()
        if user['role'] != 'merchant':
            return jsonify({'code': 403, 'msg': '仅商家可操作'})
        goods = Goods.query.get_or_404(id)
        if goods.merchant_id != user['id']:
            return jsonify({'code': 403, 'msg': '无权删除该商品'})

        Cart.query.filter_by(goods_id=id).delete()
        Collect.query.filter_by(goods_id=id).delete()
        History.query.filter_by(goods_id=id).delete()

        db.session.delete(goods)
        db.session.commit()
        es.delete_goods(id)   # 同步 ES 索引

        redis_client.delete(f"goods_stock:{id}")
        cache_invalidate('goods_list:*')
        redis_client.delete(f'goods_detail:{id}')

        return jsonify({'code': 200, 'msg': '删除成功'})
    except Exception as e:
        db.session.rollback()
        print(f"删除商品错误: {e}")
        return jsonify({'code': 500, 'msg': '删除失败'})

def _dump_specs(specs):
    """规格参数序列化：只接受 dict，限制条数与字段长度（防超大 payload）"""
    if not isinstance(specs, dict) or not specs:
        return None
    items = list(specs.items())[:20]
    clean = {}
    for k, v in items:
        key = str(k).strip()[:20]
        val = str(v).strip()[:50]
        if key and val:
            clean[key] = val
    return json.dumps(clean, ensure_ascii=False) if clean else None

@bp.route('/api/banners', methods=['GET'])
def get_banners():
    """首页轮播运营位（管理后台维护，前端不硬编码）"""
    try:
        banners = Banner.query.filter_by(enabled=1).order_by(Banner.sort.desc(), Banner.id.asc()).all()
        data = [{
            'id': b.id,
            'image': fix_image_url(b.image),
            'title': b.title or '',
            'button_text': b.button_text or '查看详情',
            'link': b.link or ''
        } for b in banners]
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        print(f'获取轮播失败: {e}')
        return jsonify({'code': 500, 'msg': '获取轮播失败'})
