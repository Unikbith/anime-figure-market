"""数据模型（2026-09-25 重构：user_info 并入 users，快照表合并，goods 去冗余）"""
from backend.extensions import db


class User(db.Model):
    """用户表（原 user_info 的资料字段已并入）"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_banned = db.Column(db.Integer, default=0)
    apply_status = db.Column(db.String(20), default='none')   # 入驻申请状态
    apply_time = db.Column(db.DateTime, nullable=True)         # 入驻申请时间
    # —— 以下为原 user_info 字段（1:1 拆表无必要，并入主表）——
    avatar = db.Column(db.String(255), default='')
    birthday = db.Column(db.String(20), default='')
    gender = db.Column(db.String(10), default='secret')
    email = db.Column(db.String(100), default='')
    phone = db.Column(db.String(20), default='')
    receiver_name = db.Column(db.String(50), default='')
    address = db.Column(db.Text, default='')


class Goods(db.Model):
    """商品表（merchant_name 冗余字段已删除，商家昵称经 merchant_id 关联 users）"""
    __tablename__ = 'goods'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=1)
    images = db.Column(db.Text, nullable=False)  # 逗号分隔的图片URL
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=True)  # 上架/下架
    brand = db.Column(db.String(50), nullable=True)
    ip = db.Column(db.String(50), nullable=True)  # 所属IP
    charactername = db.Column(db.String(50), nullable=True)  # 角色名
    merchant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    specs = db.Column(db.Text, nullable=True)              # JSON 规格参数（材质/比例/尺寸/厂商/发售等）
    tags = db.Column(db.String(200), default='')           # 逗号分隔标签：新品,热销,限定
    sales = db.Column(db.Integer, default=0)               # 累计销量
    services = db.Column(db.String(200), default='')       # 服务承诺（逗号分隔，商家填写）
    merchant = db.relationship('User', backref='goods_list', lazy='joined')
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class Cart(db.Model):
    """购物车表"""
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    num = db.Column(db.Integer, default=1, nullable=False)
    goods = db.relationship('Goods', backref='cart_items', lazy='joined')


class Collect(db.Model):
    """用户收藏表"""
    __tablename__ = 'collects'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    goods = db.relationship('Goods', backref='collect_items', lazy='joined')


class History(db.Model):
    """浏览历史表"""
    __tablename__ = 'user_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    browse_time = db.Column(db.DateTime, server_default=db.func.now())
    goods = db.relationship('Goods', backref='history_items', lazy='joined')


class Comment(db.Model):
    """商品评论表"""
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship('User', backref='comments', lazy='joined')


class Order(db.Model):
    """订单主表"""
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    receiver_name = db.Column(db.String(50), default='')
    receiver_phone = db.Column(db.String(20), default='')
    receiver_address = db.Column(db.String(255), default='')
    status = db.Column(db.String(20), default='pending_pay')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    items = db.relationship('OrderItem', backref='order', lazy='joined', cascade='all, delete-orphan')


class OrderItem(db.Model):
    """订单商品明细表"""
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    goods_name = db.Column(db.String(100), nullable=False)
    goods_image = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    num = db.Column(db.Integer, nullable=False)


class ReturnRequest(db.Model):
    """售后申请表"""
    __tablename__ = 'return_requests'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    merchant_id = db.Column(db.Integer, nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    order = db.relationship('Order', backref='return_requests', lazy='joined')
    user = db.relationship('User', backref='return_requests', lazy='joined')
    goods = db.relationship('Goods', backref='return_requests', lazy='joined')


class NotificationLog(db.Model):
    """用户通知记录表"""
    __tablename__ = 'notification_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    goods_id = db.Column(db.Integer, db.ForeignKey('goods.id'), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, server_default=db.func.now())
    status = db.Column(db.String(20), default='pending')
    user = db.relationship('User', backref='notifications', lazy='joined')
    goods = db.relationship('Goods', backref='notifications', lazy='joined')
    order = db.relationship('Order', backref='notifications', lazy='joined')


class Snapshot(db.Model):
    """监控快照表（原 search_keyword_snapshots + order_status_snapshots 合并）"""
    __tablename__ = 'snapshots'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)      # search_keyword / order_status
    name = db.Column(db.String(100), nullable=False)      # 关键词或状态名
    count = db.Column(db.Integer, default=0)
    today_orders = db.Column(db.Integer, default=0)       # 仅 order_status 使用
    today_revenue = db.Column(db.Float, default=0.0)      # 仅 order_status 使用
    updated_at = db.Column(db.DateTime, server_default=db.func.now())


class Banner(db.Model):
    """首页轮播运营位（管理后台可维护，避免前端硬编码）"""
    __tablename__ = 'banners'
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(100), default='')
    button_text = db.Column(db.String(50), default='查看详情')
    link = db.Column(db.String(200), default='')
    sort = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
