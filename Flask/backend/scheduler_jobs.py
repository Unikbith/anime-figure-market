"""定时任务（APScheduler，从原 app.py 抽取）"""
from datetime import datetime, timedelta

from backend.extensions import scheduler, app, redis_client, db
from backend.models import Order, Snapshot
from backend.utils import cancel_expired_orders

@scheduler.task('interval', id='cancel_expired_orders_task', minutes=1, misfire_grace_time=300)
def scheduled_cancel_expired_orders():
    """每分钟执行一次，取消超时未支付的订单"""
    cancel_expired_orders()


@scheduler.task('interval', id='refresh_search_keywords_task', days=7, misfire_grace_time=3600)
def scheduled_refresh_search_keywords():
    """每7天执行一次，聚合Redis中7天的搜索关键词数据并持久化到MySQL"""
    try:
        # 聚合最近7天的搜索关键词
        keyword_totals = {}
        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            data = redis_client.zrevrange(f'monitor:search_keywords:{day}', 0, -1, withscores=True)
            for kw, count in data:
                kw_str = kw.decode() if isinstance(kw, bytes) else kw
                keyword_totals[kw_str] = keyword_totals.get(kw_str, 0) + int(count)

        # 取Top10写入MySQL
        top10 = sorted(keyword_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        with app.app_context():
            Snapshot.query.filter_by(type='search_keyword').delete()
            for keyword, count in top10:
                db.session.add(Snapshot(type='search_keyword', name=keyword, count=count))
            db.session.commit()
        print(" 热门搜索关键词快照已更新（7天周期）")
    except Exception as e:
        print(f"更新搜索关键词快照错误: {e}")


@scheduler.task('interval', id='refresh_order_status_task', minutes=5, misfire_grace_time=300)
def scheduled_refresh_order_status():
    """每5分钟执行一次，统计今日订单状态分布并持久化到MySQL（快照表备用）"""
    try:
        # APScheduler 工作线程无 Flask 上下文，全部 DB 操作必须包进 app_context
        with app.app_context():
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_orders = Order.query.filter(Order.created_at >= today_start).all()
            today_order_count = len(today_orders)

            paid_statuses = ('pending_ship', 'pending_receive', 'completed')
            today_revenue = sum(float(o.total_price) for o in today_orders if o.status in paid_statuses)

            status_labels = {
                'pending_pay': '待付款', 'pending_ship': '待发货',
                'pending_receive': '待收货', 'completed': '已完成',
                'cancelled': '已取消', 'refund': '退款中', 'refunded': '已退款'
            }
            status_map = {}
            for o in today_orders:
                label = status_labels.get(o.status, o.status)
                status_map[label] = status_map.get(label, 0) + 1

            Snapshot.query.filter_by(type='order_status').delete()
            for name, count in status_map.items():
                db.session.add(Snapshot(
                    type='order_status', name=name, count=count,
                    today_orders=today_order_count,
                    today_revenue=round(today_revenue, 2)
                ))
            db.session.commit()
        print("订单状态分布快照已更新（5分钟周期）")
    except Exception as e:
        db.session.rollback()
        print(f"更新订单状态分布快照错误: {e}")

