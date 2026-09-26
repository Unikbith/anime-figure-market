# 次元模仓 · 手办模型交易平台

基于 Vue 3 + Flask 的全栈手办模型电商网站，覆盖用户端浏览下单、商家端上架经营、管理端审核与数据看板三套角色体系。
业务数据落在 MySQL，缓存与异步队列使用 Redis + Celery，商品图片存 MinIO，商品检索接入 Elasticsearch 并在其不可用时自动降级为 MySQL 模糊匹配，另外接入智谱 GLM 提供 AI 客服。

当前形态为本地开发运行版，不依赖 Nginx 与 HTTPS 证书，前端跑 Vite 开发服务器，后端直接运行 Flask + Celery。

---

## 一、技术栈

前端

- Vue 3 Composition API + `<script setup>`、Vite
- Vue Router 路由懒加载与三级权限守卫（用户 / 商家 / 管理员）
- Pinia 状态管理、Element Plus 组件库、ECharts 图表
- Axios 统一封装，含 JWT 鉴权注入与 401 自动跳转
- IntersectionObserver 实现无限滚动列表，替代传统分页

后端

- Flask 蓝图拆分，9 个蓝图共 80 余个 `/api` 接口
- SQLAlchemy ORM，12 张业务表
- Flask-JWT-Extended 双角色鉴权
- Redis 缓存热点数据、JWT 黑名单、验证码与限流计数，并作为 Celery broker
- Celery 异步任务 + APScheduler 定时任务（超时订单取消、监控快照）
- MinIO 对象存储管理商品图片
- Elasticsearch 商品检索，不可用时自动降级

---

## 二、功能

用户端

- 首页轮播、分类导航、无限滚动商品流、猜你喜欢推荐
- 商品搜索、按 IP / 品牌 / 角色 / 状态筛选
- 商品详情：多图、规格参数、标签、服务承诺、累计销量、评论区
- 购物车、订单结算、模拟支付、订单状态流转、退换货申请
- 个人中心：资料维护、头像上传、收货地址、收藏夹、浏览足迹
- 邮箱验证码注册与找回密码、AI 智能客服

商家端

- 商品发布与编辑：图片上传、规格参数键值对、标签、服务承诺
- 我的商品、订单发货、售后处理、店铺信息维护

管理端

- 用户管理、商品审核与下架、订单管理、退换货审核
- 轮播图管理（增删改与排序）
- 数据监控看板：销量趋势、订单状态分布、热门搜索词

---

## 三、目录结构

```text
.
├── Flask/                      后端
│   ├── app.py                  入口，同时供 celery -A app.celery 发现
│   ├── requirements.txt
│   └── backend/
│       ├── __init__.py         create_app：加载 .env、装配扩展、注册蓝图
│       ├── config.py           配置集中管理，全部读取 .env
│       ├── extensions.py       db / jwt / redis / minio / celery 单例
│       ├── models.py           12 张表 ORM 模型
│       ├── es.py               Elasticsearch REST 客户端与降级逻辑
│       ├── utils.py            密码哈希、邮件、缓存、分布式锁、权限装饰器
│       ├── tasks.py            Celery 异步任务
│       ├── hooks.py            请求监控与 JWT 异常处理
│       ├── scheduler_jobs.py   APScheduler 定时任务
│       ├── safe_stdio.py       stdout 失效保护
│       └── routes/             9 个蓝图
├── Vue/                        前端
│   ├── vite.config.js          开发服务器，代理 /api 与 /goods-images
│   └── src/
│       ├── api/request.js      axios 实例与拦截器
│       ├── config/index.js     VITE_* 环境变量
│       ├── router/             路由与权限守卫
│       ├── views/              页面
│       ├── components/         组件
│       ├── composables/        useInfiniteLoad、useDialogForm
│       ├── utils/              图片兜底、弹窗工具
│       └── styles/common.css   全局设计令牌与共享样式
└── .env.example                配置模板，可提交
```

---

## 四、环境要求

| 组件 | 说明 |
| --- | --- |
| Python | 3.10 及以上，Flask 与 Celery 必须使用同一个解释器 |
| Node.js | 20.19 及以上，或 22.12 及以上 |
| MySQL | 5.7 / 8.0，需存在数据库 `vue_db`（utf8mb4） |
| Redis | 必需，缓存 + Celery broker |
| MinIO | 必需，商品图片对象存储 |
| Elasticsearch | 可选，7.x；未启动或连接失败时检索自动降级为 MySQL 模糊匹配 |
| 智谱 API Key | 可选，未配置时 AI 客服降级为本地兜底回复 |

---

## 五、快速开始

### 1. 安装依赖

```bash
# 后端
cd Flask
pip install -r requirements.txt

# 前端
cd Vue
npm install
```

### 2. 配置环境变量

所有配置集中在仓库根目录的 `.env`，代码中不硬编码任何口令或密钥。

```bash
cp .env.example .env
```

建库（后端启动时会执行 `db.create_all()`，表无需手工创建）：

```sql
CREATE DATABASE IF NOT EXISTS vue_db DEFAULT CHARSET utf8mb4;
```

### 3. 启动中间件

Redis、MinIO 需自行启动（MySQL 为系统服务）：

```bash
redis-server --port 6379
minio server <数据目录> --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
```

Redis 与 Celery 共用同一个实例，`.env` 中的 `CELERY_BROKER_URL` 需指向它。

### 4. 启动后端

```bash
cd Flask
python app.py
```

默认监听 <http://127.0.0.1:5000>。

异步任务依赖 Celery worker（工作目录为 `Flask/`，Windows 下用 `--pool=solo`）：

```bash
celery -A app.celery worker --loglevel=info --pool=solo
```

### 5. 启动前端

```bash
cd Vue
npm run dev
```

- 用户端 <http://localhost:5173>
- 管理端 <http://localhost:5173/admin/login>

Vite 已将 `/api` 代理到 Flask(5000)、`/goods-images` 代理到 MinIO(9000)，前后端与图片资源之间不存在跨域问题。

---

## 六、主要配置项

完整列表见 `.env.example`。

| 变量 | 说明 |
| --- | --- |
| `SQLALCHEMY_DATABASE_URI` | MySQL 连接串，库名 `vue_db` |
| `REDIS_HOST` / `REDIS_PORT` | Redis 地址 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery 队列与结果后端 |
| `JWT_SECRET_KEY` | JWT 签名密钥；留空则自动生成并持久化到 `Flask/jwt.key` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理端登录口令 |
| `SMTP_USER` / `SMTP_PASSWORD` | 发件邮箱与授权码 |
| `ZHIPU_API_KEY` | 智谱 AI Key，可选 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` | MinIO 对象存储 |
| `ES_HOST` / `ES_PORT` | Elasticsearch 地址，可选 |
| `CORS_ORIGINS` | 允许跨域的来源 |

---

## 七、请求链路

```text
浏览器 :5173 (Vite dev server)
   |
   ├── /api/*          ---->  Flask :5000  ----+--> MySQL  :3306   业务主库
   |                                           +--> Redis  :6379   缓存 / 队列 / 黑名单 / 锁
   |                                           +--> MinIO  :9000   商品图片
   |                                           +--> ES     :9200   商品检索（可降级）
   |                                           +--> Celery worker
   |
   └── /goods-images/* ---->  MinIO :9000
```

---

## 八、数据模型

| 表 | 用途 |
| --- | --- |
| `users` | 用户与商家账号，含头像、地址等资料 |
| `goods` | 商品，含图片、规格参数、标签、服务承诺、销量 |
| `cart` | 购物车 |
| `collects` | 收藏 |
| `user_history` | 浏览足迹，用于个性化推荐 |
| `comments` | 商品评论 |
| `orders` / `order_items` | 订单与订单明细 |
| `return_requests` | 退换货申请 |
| `notification_logs` | 站内通知 |
| `snapshots` | 监控快照，按类型区分搜索热词与订单状态分布 |
| `banners` | 首页轮播图 |

---

## 九、安全约定

- 配置外置：数据库口令、邮箱授权码、管理员口令、JWT 密钥全部来自 `.env`；`.env`、`Flask/jwt.key`、`Flask/secret.key` 均已被 `.gitignore` 忽略。
- 密码存储：新密码一律存 werkzeug 不可逆哈希。
- 鉴权：JWT + 角色校验，涉及资源归属的写操作均校验归属，避免越权。
- 限流：验证码发送与校验、AI 客服接口均按 IP 或邮箱限流。
- 订单号：`ORD` + 秒级时间戳 + `uuid4`，避免被遍历。

提交前可确认敏感文件未被跟踪：

```bash
git check-ignore .env Flask/jwt.key Flask/secret.key
```

---

## 十、常见问题

| 现象 | 处理 |
| --- | --- |
| 后端启动报 MySQL 连接失败 | 确认 MySQL 服务已启动、连接串口令正确、`vue_db` 已创建 |
| 报 `No module named 'redis' / 'celery' / 'pymysql'` | 当前解释器未安装本项目依赖，执行 `pip install -r requirements.txt` |
| Celery 启动后立即退出 | 当前解释器缺少 celery，换成与 Flask 相同的解释器后重装依赖 |
| Celery 任务一直不执行 | 确认 Redis 在跑，`CELERY_BROKER_URL` 正确，Windows 上使用 `--pool=solo` |
| 商品图片 404 | 确认 MinIO 在跑且桶存在，后端首次启动会自动创建 |
| 管理端登录提示未配置 | 在 `.env` 中设置 `ADMIN_PASSWORD` |
| 注册收不到验证码 | 检查 `SMTP_USER` / `SMTP_PASSWORD`，需填授权码而非登录密码 |
| 搜索结果排序不理想 | 确认 Elasticsearch 是否启动；未启动时会降级为 MySQL 模糊匹配 |

---

## 十一、说明

- 支付为模拟流程，未接入真实支付网关。
- 商品图片与数据为本地演示数据。
- 项目以功能完整性为目标，未做生产环境部署与性能压测。
