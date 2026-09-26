# 安全审计与功能/边界测试报告

- **审计对象**：`Flask/`（后端，重构后 `backend/` 包，9 蓝图 / 80 余接口）+ `Vue/src`（前端）
- **审计日期**：2026-09-13
- **审计方式**：静态扫描（pyflakes / 正则）+ 动态验证（Flask test_client 全接口探活 + 漏洞复现 + 边界用例）+ 真机启动（Flask :5000 / Celery worker）
- **测试数据**：全部使用 `__audit_` / `__v2_` / `__rl_` 前缀，测试后已清理，未污染业务数据

> **版本说明（2026-09-24）**：其后项目已收敛为「本地开发运行版」，下文个别表述保留当时原貌，与现状的差异如下：>   
> 不再使用 Nginx / HTTPS；Elasticsearch 改为可选组件（未启动时检索降级为 MySQL 模糊匹配）；`Flask/config.py` 已并入 `backend/config.py`；>   
> `start-all.ps1` 已替换为启动 Redis + Celery + MinIO 的 `start-services.ps1`；>   
> 业务库已从空的 `handmade_platform` 切换到有真实数据的 `vue_db`，因此**恢复了 Fernet 历史密码兼容**
> （密钥见 `.env` 的 `FERNET_KEY` 与 `Flask/secret.key`）；老账号登录成功后会自动升级为哈希。

---

## 一、结论摘要

| 严重度          | 数量 | 状态          |
| ------------ | -- | ----------- |
| 严重（Critical） | 6  | 已修复         |
| 高危（High）     | 5  | 已修复         |
| 中危（Medium）   | 4  | 已修复         |
| 低危 / 加固建议    | 5  | 部分修复，部分列为建议 |

**全部 15 项已确认问题均已修复并通过回归验证。** 另发现并修复了 1 类**重构回归缺陷**（41 处未定义名），若不修复，商品发布、发货通知等 7 个关键调用点会在运行时报 `NameError`。

---

## 二、严重问题（Critical）

### C1. 硬编码 JWT 密钥，可伪造任意身份（含管理员）

- **位置**：`backend/__init__.py`（原 `JWT_SECRET_KEY = 'vue_jwt'`）
- **证据**：用公开的 `vue_jwt` 离线签发 `role=admin` 的 token，即可访问 `/api/admin/users`。
- **修复**：改为优先读环境变量 `JWT_SECRET_KEY`；未配置时用 `secrets.token_urlsafe(48)` 生成并持久化到 `Flask/jwt.key`（重启保持一致）。
- **回归**：V5 用旧密钥伪造 admin token → **401 被拒**。

### C2. 注册接口可自定义角色 → 自助提权为管理员

- **位置**：`backend/routes/auth.py` `/api/register`
- **证据**：请求体传 `role=admin` 即可注册成管理员。
- **修复**：角色白名单，仅允许 `user` / `merchant`，其余返回 400。
- **回归**：V3 注册 `role=admin` → **400「角色不合法」**。

### C3. 越权取消/删除他人订单（IDOR）

- **位置**：`backend/routes/orders.py` `cancel_order` / `delete_order`
- **证据**：用户 B 持自己的合法 token，可直接取消/删除用户 A 的订单（代码取了 `get_jwt()` 却从未校验 `order.user_id`）。
- **修复**：两处均增加 `order.user_id != user_id → 403`。
- **回归**：V1/V2 → **403「无权操作」**。

### C4. 无鉴权支付确认 → 支付绕过

- **位置**：`backend/routes/orders.py` `/api/order/confirm-public/<order_no>`
- **证据**：匿名 POST 即可把任意待支付订单标记为已支付。
- **修复**：加 `@jwt_required()` + 订单归属校验。
- **回归**：V6 匿名调用 → **401「请先登录」**。

### C5. 管理员口令硬编码在源码（`admin` / `admin`）

- **位置**：`backend/routes/admin.py` `/api/admin/login`
- **证据**：源码中直接比对 `username != 'admin' or password != 'admin'`。
- **修复**：口令改从环境变量 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 读取，未配置则拒绝登录并提示；比较用 `secrets.compare_digest`（防时序侧信道）。
- **回归**：V4a `admin/admin` → **400**；V4b 正确环境变量口令 → **登录成功**。

### C6. 公开订单号可枚举 → 遍历他人订单（信息泄露）

- **位置**：`backend/routes/orders.py` `create_order`：`order_no = f"ORD{int(time.time())}{random.randint(1000,9999)}"`
- **证据**：订单号 = 秒级时间戳 + 4 位 `random` 随机数，属非密码学随机。在已知下单时间窗口下仅需约 9000 次枚举即可命中，而 `/api/order/public/<order_no>` 为公开接口（收货人/电话/地址可被读取）。
- **修复**：随机段改为 `uuid.uuid4().hex[:12]`（48 位密码学随机），订单号形如 `ORD178930552087163801e123`（25 字符，仍可读、可排序），枚举不可行。
- **回归**：真实下单返回 `ORD178930552087163801e123`，正则 `^ORD\d{10}[0-9a-f]{12}$` 匹配通过。

---

## 三、高危问题（High）

### H1. 密码使用可逆加密存储（Fernet），而非哈希

- **位置**：`backend/utils.py` `encrypt_password` / `decrypt_password`
- **证据**：任何拿到 `secret.key` 的人可还原全部明文口令。
- **修复**：`encrypt_password` 改为 `werkzeug.generate_password_hash`（scrypt 单向哈希），新增 `verify_password` 统一校验。
- **后续**：Hermes 密钥文件 `secret.key`、`decrypt_password` 与 Fernet 依赖已于本地化改造中**整体移除**，密码只以哈希形式存储。
- **回归**：注册后密文为 `scrypt:...`（不可逆）；正确口令登录 200、错误口令 400。

### H2. 上传接口无扩展名白名单 → 可传恶意文件

- **位置**：`backend/routes/goods.py` `/api/upload/image`
- **证据**：`file_ext` 直接取自文件名，可上传 `.svg`（含脚本，可致存储型 XSS）/任意类型。
- **修复**：仅允许 `jpg/jpeg/png/gif/webp/bmp`，其余 400。
- **回归**：V7 上传 `evil.svg` → **400**。

### H3. 验证码用非密码学随机数生成

- **位置**：`backend/utils.py` `generate_code`：`random.randint`
- **修复**：改用 `secrets.randbelow(10)`。
- **回归**：功能正常（生成 6 位数字码）。

### H4. 注册验证码可暴力枚举 + 邮件轰炸

- **位置**：`backend/routes/auth.py` `/api/register`、`/api/send_code`
- **证据**：6 位验证码无尝试次数限制；发码接口无频率限制，可对任意邮箱反复发信。
- **修复**：
  - 验证码校验前计数 `code_try:{email}`，超过 10 次 → 429；计数 600s 自动过期（避免用户被永久锁定）；注册成功即清零。
  - 发码接口按邮箱 60s 限 1 次 + 按 IP 60s 限次 → 429。
- **回归**：第 1~10 次错误码 → 400，第 11 次起 → **429**（且超限后即便用正确码也 429，说明限流先于校验）；重复发码第 2 次起 → **429**。

### H5. 重构回归：41 处「未定义名」导致运行时崩溃

- **位置**：`backend/utils.py` / `tasks.py` / `routes/*.py`
- **证据**：模块拆分时模型、Celery 任务、`contextmanager`/`wraps`/`uuid` 等未随之导入。实测 `POST /api/goods/publish` 抛 `name 'sync_goods_to_es_async' is not defined`——且**报错前已 commit 商品入库**，产生脏数据。共 7 个 `.delay()` 调用点受影响。
- **修复**：补齐各模块 import；用 pyflakes 全量扫描至 **0 undefined name**。
- **回归**：`pyflakes` 0 处；全包 `py_compile` 通过；82 路由全部注册。

---

## 四、中危问题（Medium）

### M1. 错误信息泄露内部异常文本

- 多处 `return jsonify({'code': 500, 'msg': f'...{str(e)}'})`，把异常细节（栈/DB 信息）回显给客户端。→ 改为通用提示，细节只写服务端日志。

### M2. 非法 JSON 请求体触发 500

- `request.get_json()` 在 body 非 JSON 时抛异常。→ 改为 `get_json(silent=True) or {}`，非法体返回 400。

### M3. 弱邮箱校验（可被后缀注入绕过）

- 原判据 `'@qq.com' not in email`，`x@qq.com.evil.com` 可通过。→ 改为正则严格匹配 QQ 邮箱。
- **回归**：V8 `x@qq.com.evil.com` → **400**。

### M4. 商品价格/库存无下界校验

- 可发布 `price = -999`、`stock = -5` 的商品（实测确实入库）。→ 增加 `price > 0`、`stock >= 0` 校验。
- **回归**：B1 负数 → **400「价格必须大于0」**。

---

## 五、接口功能与边界测试

- **全接口探活**：82 个 `/api` 路由按正确方法 + 空载荷遍历，**无任何 500**。
- **鉴权覆盖**：`/api/admin/*` 全部要求 `admin` 角色；用户态接口未登录返回 401。
- **边界用例**：
  | 用例                    | 结果                     |
  | --------------------- | ---------------------- |
  | 超长昵称（5000 字符）         | 400「昵称长度不能超过80个字符」     |
  | 非法 JSON 登录体           | 400（不再 500）            |
  | 删除不存在订单               | 404                    |
  | 注册空对象                 | 400「请完善所有信息」           |
  | 负数价格/库存发布             | 400「价格必须大于0」           |
  | 公开 AI 接口超长输入（5000 字符） | 自动截断并降级回复              |
  | AI 接口每 IP 限流          | 1~20 次 200，第 21 次起 429 |

> 注：报告中 Part1 出现的 405/404 属测试脚本使用占位路径（`<int:id>` 字面量）所致——字符串型参数（如 `<string:order_no>`）会匹配成功故返回 401，整型参数不匹配则落到前端兜底路由。已用**真实 ID**复测确认路由正常（`R6a` 200 / `R6b`「仅商家可操作」/ `R6c` 404）。

---

## 六、前端审计

- **XSS**：全仓无 `v-html` / `innerHTML` / `document.write` / `eval`，Vue 默认转义生效，存储型 XSS 风险低。
- **敏感信息**：无硬编码 API Key / 口令 / 密钥。
- **Token 存储**：使用 `sessionStorage`（关闭标签即失效），未用 cookie，CSRF 面较小；缺点是 XSS 可读。
- **API 层**：已在上一轮重构中收敛为单一 axios 实例，无重复封装。

---

## 七、加固建议（未强制修改，供后续迭代）

1. **敏感配置外置**：`Flask/config.py` 与 `start-all.ps1` 内仍含真实 SMTP 授权码/邮箱明文，建议全部改读环境变量并加入 `.gitignore`。
2. **默认 DB 口令**：`__init__.py` 的默认连接串含 `root:root`，建议仅作本地开发默认值或直接移除，强制由环境变量提供。
3. **`confirm-public` 语义**：当前加鉴权后已安全。若将来接入真实支付网关回调，请改用**签名校验**而非用户 JWT（网关无法持有用户 token）。
4. **HTTPS / 安全响应头**：生产环境建议启用 HTTPS 并补充 `X-Content-Type-Options`、`Content-Security-Policy` 等头。
5. **REST 语义**：业务错误目前多以 HTTP 200 + body `code` 返回，前端可正常工作；若要严格化，可改为对应 HTTP 状态码。
6. **依赖告警**：`redis-py` 的 `setex` 已弃用，建议统一改为 `set(key, val, ex=...)`。

---

## 八、验证证据一览

| 项目              | 结果                                |
| --------------- | --------------------------------- |
| V1/V2 越权取消/删除订单 | 403 无权操作 ✅                        |
| V3 注册提权         | 400 角色不合法 ✅                       |
| V4a/V4b 管理员登录   | admin/admin 被拒；环境变量口令通过 ✅         |
| V5 伪造 JWT 访问后台  | 401 被拒 ✅                          |
| V6 匿名支付确认       | 401 请先登录 ✅                        |
| V7 上传恶意 .svg    | 400 格式不支持 ✅                       |
| V8 后缀注入邮箱       | 400 无效邮箱 ✅                        |
| B1 负数价格/库存      | 400 价格必须大于0 ✅                     |
| 验证码尝试限流         | 第 11 次起 429 ✅                     |
| 发码频率限制          | 第 2 次起 429 ✅                      |
| AI 接口限流         | 第 21 次起 429 ✅                     |
| 订单号不可枚举         | `ORD`+10 位时间戳+12 位十六进制 ✅          |
| 密码存储            | `scrypt` 单向哈希 + 老数据透明升级 ✅         |
| pyflakes 未定义名   | 0 处 ✅                             |
| 全包 py_compile   | 通过 ✅                              |
| 真机启动            | 82 路由；`GET /api/goods/list` 200 ✅ |
| Celery worker   | 6 个 `backend.tasks.*` 注册 ✅        |
