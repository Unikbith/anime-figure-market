"""Celery 异步任务（从原 app.py 抽取）"""

from backend.extensions import celery, db, redis_client, app
from backend.models import Goods, Order, Cart, NotificationLog

@celery.task
def cancel_expired_order_task(order_id):
    """异步取消超时订单（延迟执行）"""
    with app.app_context():
        order = Order.query.get(order_id)
        if not order or order.status != 'pending_pay':
            return
        print(f"自动取消超时订单: {order.order_no}")
        order.status = 'cancelled'
        for item in order.items:
            goods = Goods.query.get(item.goods_id)
            if goods:
                goods.stock += item.num
                redis_client.incrby(f"goods_stock:{item.goods_id}", item.num)
        for item in order.items:
            existing_cart = Cart.query.filter_by(user_id=order.user_id, goods_id=item.goods_id).first()
            if existing_cart:
                existing_cart.num += item.num
            else:
                new_cart = Cart(user_id=order.user_id, goods_id=item.goods_id, num=item.num)
                db.session.add(new_cart)
        db.session.commit()
        return f"订单{order_id}已取消"

@celery.task
def notify_price_drop(goods_id, old_price, new_price):
    """降价通知：发送给所有购物车中有该商品的用户"""
    with app.app_context():
        try:
            goods = Goods.query.get(goods_id)
            if not goods:
                return
            cart_users = Cart.query.filter_by(goods_id=goods_id).all()
            for cart_item in cart_users:
                user_id = cart_item.user_id
                # 24小时内去重，避免重复通知
                dedup_key = f"notify:price_drop:{goods_id}:{user_id}"
                if redis_client.exists(dedup_key):
                    continue
                content = f"【次元模仓】您购物车中的「{goods.name}」降价啦！从 ¥{old_price} 降到 ¥{new_price}，快去看看吧！"
                log = NotificationLog(
                    user_id=user_id,
                    goods_id=goods_id,
                    type='price_drop',
                    content=content,
                    status='sent'
                )
                db.session.add(log)
                redis_client.setex(dedup_key, 86400, '1')  # 去重标记24小时
            db.session.commit()
            return f"降价通知已处理，商品ID: {goods_id}"
        except Exception as e:
            db.session.rollback()
            print(f"降价通知任务失败: {e}")
            raise

@celery.task
def notify_off_shelf(goods_id):
    """下架通知：通知所有购物车中有该商品的用户"""
    with app.app_context():
        try:
            goods = Goods.query.get(goods_id)
            if not goods:
                return
            cart_users = Cart.query.filter_by(goods_id=goods_id).all()
            for cart_item in cart_users:
                user_id = cart_item.user_id
                dedup_key = f"notify:off_shelf:{goods_id}:{user_id}"
                if redis_client.exists(dedup_key):
                    continue
                content = f"【次元模仓】很抱歉，您购物车中的「{goods.name}」已被商家下架，请及时处理。"
                log = NotificationLog(
                    user_id=user_id,
                    goods_id=goods_id,
                    type='off_shelf',
                    content=content,
                    status='sent'
                )
                db.session.add(log)
                redis_client.setex(dedup_key, 86400, '1')
            db.session.commit()
            return f"下架通知已处理，商品ID: {goods_id}"
        except Exception as e:
            db.session.rollback()
            print(f"下架通知任务失败: {e}")
            raise

@celery.task
def notify_shipment(order_id):
    """商家发货通知"""
    with app.app_context():
        try:
            order = Order.query.get(order_id)
            if not order:
                return
            first_item = order.items[0] if order.items else None
            if not first_item:
                print(f"订单 {order_id} 无商品项，无法发送发货通知")
                return
            user_id = order.user_id
            goods_name = first_item.goods_name
            dedup_key = f"notify:shipment:{order_id}:{user_id}"
            if redis_client.exists(dedup_key):
                return
            content = f"【次元模仓】您的订单 {order.order_no} 已发货！商品「{goods_name}」正在配送中，请注意查收。"
            log = NotificationLog(
                user_id=user_id,
                goods_id=first_item.goods_id,
                type='shipment',
                content=content,
                status='sent',
                order_id=order_id
            )
            db.session.add(log)
            redis_client.setex(dedup_key, 86400, '1')
            db.session.commit()
            return f"发货通知已发送，订单ID: {order_id}"
        except Exception as e:
            db.session.rollback()
            print(f"发货通知任务失败: {e}")
            raise

@celery.task
def notify_goods_update(goods_id, old_name, new_name):
    """商品名称更新通知"""
    with app.app_context():
        try:
            goods = Goods.query.get(goods_id)
            if not goods:
                return
            cart_users = Cart.query.filter_by(goods_id=goods_id).all()
            for cart_item in cart_users:
                user_id = cart_item.user_id
                dedup_key = f"notify:goods_update:{goods_id}:{user_id}"
                if redis_client.exists(dedup_key):
                    continue
                content = f"【次元模仓】您购物车中的商品「{old_name}」已更新为「{new_name}」，快去看看吧！"
                log = NotificationLog(
                    user_id=user_id,
                    goods_id=goods_id,
                    type='goods_update',
                    content=content,
                    status='sent'
                )
                db.session.add(log)
                redis_client.setex(dedup_key, 86400, '1')
            db.session.commit()
            return f"商品更新通知已处理，商品ID: {goods_id}"
        except Exception as e:
            db.session.rollback()
            print(f"商品更新通知任务失败: {e}")
            raise
