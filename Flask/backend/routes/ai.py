"""ai 模块路由（蓝本）"""
from flask import request, jsonify
import requests

from flask import Blueprint

from backend.extensions import redis_client
from backend.config import ZHIPU_API_KEY, ZHIPU_API_URL
from backend.utils import get_cached_goods, search_by_redis_index, get_fallback_reply

_goods_cache = {'data': None, 'updated_at': 0}
_GOODS_CACHE_TTL = 300  # 缓存有效期5分钟

bp = Blueprint('ai', __name__)

@bp.route('/api/chat', methods=['POST'])
def chat_with_ai():
    """AI客服对话接口：AI做意图分析+对话，有购买意图时Redis加权搜索推荐商品"""
    import re
    try:
        data = request.get_json(silent=True) or {}

        # 防滥用：该接口公开且会调用付费大模型，按 IP 限流并限制输入长度
        ip = request.remote_addr or '0.0.0.0'
        rl_key = f"chat_limit:{ip}"
        hits = redis_client.incr(rl_key)
        if hits == 1:
            redis_client.expire(rl_key, 60)  # 每 IP 每分钟窗口
        if hits > 20:
            return jsonify({'code': 429, 'msg': '请求过于频繁，请稍后再试'}), 429

        user_message = (data.get('message') or '')
        if not isinstance(user_message, str):
            user_message = ''
        user_message = user_message.strip()[:500]  # 限制长度，防止超长输入刷 token
        conversation_history = data.get('history', [])
        if not isinstance(conversation_history, list):
            conversation_history = []

        if not user_message:
            return jsonify({'code': 400, 'msg': '消息不能为空'})

        # 确保商品缓存和Redis索引可用
        get_cached_goods()

        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }

        system_prompt = """你是次元模仓AI客服，负责手办、模型咨询。
你需要判断用户意图并回复。

【意图判断规则】
- 如果用户有购买/寻找商品的意图（如：想买、推荐、有没有、找、看看、想要、需要等），判定为"purchase"
- 如果用户只是闲聊/问订单/问售后等，判定为"chat"

【回复格式】
第一行输出意图标记，第二行开始是回复内容：
purchase:关键词1,关键词2,关键词3
回复内容...

chat
回复内容

示例：
purchase:初音未来,200
为您找到了初音相关的手办，请看推荐~

chat
关于订单问题，请在"我的订单"中查看。"""

        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history[-5:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        chat_payload = {
            "model": "glm-4.5-air",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.6
        }

        ai_reply = ""
        goods_data = None

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    ZHIPU_API_URL,
                    headers=headers,
                    json=chat_payload,
                    timeout=20
                )
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout) as e:
                print(f"[AI重试] 第{attempt + 1}次超时: {e}")
                if attempt == max_retries - 1:
                    raise

        if response.status_code == 200:
            result = response.json()
            raw_reply = result['choices'][0]['message']['content']
            print(f"[AI原始回复] {raw_reply}")

            lines = raw_reply.strip().split('\n', 1)
            first_line = lines[0].strip()
            reply_body = lines[1].strip() if len(lines) > 1 else first_line

            if first_line.lower().startswith('purchase:'):
                keywords_str = first_line[len('purchase:'):].strip()
                keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                print(f"[意图分析] 购买意图，关键词: {keywords}")

                goods_data = search_by_redis_index(keywords, user_message)
                ai_reply = reply_body

                # 清除回复中可能残留的商品编号
                ai_reply = re.sub(r'\[RECOMMEND:\d+\]', '', ai_reply).strip()
                ai_reply = re.sub(r'商品[ID编号：:]*\d+', '', ai_reply).strip()

            elif first_line.lower() == 'chat':
                ai_reply = reply_body
                print("[意图分析] 普通对话")
            else:
                ai_reply = raw_reply
                print("[意图分析] 解析失败，使用原始回复")
        else:
            print(f"智谱AI调用失败: {response.status_code}")
            ai_reply = get_fallback_reply(user_message)

        if not ai_reply:
            ai_reply = get_fallback_reply(user_message)

        return jsonify({
            'code': 200,
            'data': {
                'reply': ai_reply,
                'goods': goods_data
            }
        })

    except Exception as e:
        print(f"AI客服错误: {e}")
        import traceback
        traceback.print_exc()
        fallback_reply = get_fallback_reply(user_message if 'user_message' in dir() else '')
        return jsonify({'code': 200, 'data': {'reply': fallback_reply, 'goods': None}})
