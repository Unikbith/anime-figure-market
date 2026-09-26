"""Elasticsearch 轻量接入（REST 直调，无额外依赖）。

- /api/goods/search 优先走 ES 全文检索，ES 不可用时自动降级 MySQL LIKE
- 同步时机：商品发布/更新/删除实时同步；应用启动时按需全量重建
- ES 故障后 60 秒内不再重试，避免拖慢请求
"""
import threading
import time

import requests as _http

from backend.config import ES_HOST, ES_PORT
from backend.extensions import app
from backend.models import Goods

INDEX = 'goods_index'

_es_down_until = 0        # ES 故障冷却截止时间戳
_es_lock = threading.Lock()


def _url(path):
    return f'http://{ES_HOST}:{ES_PORT}{path}'


def _is_down():
    return time.time() < _es_down_until


def _mark_down():
    global _es_down_until
    with _es_lock:
        _es_down_until = time.time() + 60


def available():
    """ES 是否可用（探测一次，失败进入 60s 冷却）"""
    if _is_down():
        return False
    try:
        return _http.get(_url('/'), timeout=2).status_code == 200
    except Exception:
        _mark_down()
        return False


def ensure_index():
    """索引不存在则创建（standard 分词：中文按单字切分，够用且无插件依赖）"""
    try:
        if _http.head(_url(f'/{INDEX}'), timeout=2).status_code == 200:
            return True
        body = {
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
            'mappings': {'properties': {
                'name': {'type': 'text', 'analyzer': 'standard'},
                'description': {'type': 'text', 'analyzer': 'standard'},
                'category': {'type': 'text', 'analyzer': 'standard',
                             'fields': {'raw': {'type': 'keyword'}}},
                'brand': {'type': 'text', 'analyzer': 'standard'},
                'ip': {'type': 'text', 'analyzer': 'standard'},
                'charactername': {'type': 'text', 'analyzer': 'standard'},
                'status': {'type': 'keyword'},
            }}
        }
        r = _http.put(_url(f'/{INDEX}'), json=body, timeout=5)
        return r.status_code in (200, 201)
    except Exception:
        _mark_down()
        return False


def _doc(g):
    """goods 模型对象 → ES 文档"""
    return {
        'name': g.name or '',
        'description': g.description or '',
        'category': g.category or '',
        'brand': g.brand or '',
        'ip': g.ip or '',
        'charactername': g.charactername or '',
        'status': g.status or '',
    }


def index_goods(goods):
    """同步单个商品到 ES"""
    if not available():
        return
    try:
        _http.put(_url(f'/{INDEX}/_doc/{goods.id}'), json=_doc(goods), timeout=3)
    except Exception:
        _mark_down()


def delete_goods(goods_id):
    if not available():
        return
    try:
        _http.delete(_url(f'/{INDEX}/_doc/{goods_id}'), timeout=3)
    except Exception:
        _mark_down()


def search_ids(q, page, size):
    """全文检索，返回 (按相关度排序的 goods id 列表, 命中总数)。

    失败返回 None，调用方降级 MySQL LIKE。
    """
    if not available() or not ensure_index():
        return None
    body = {
        'query': {'bool': {
            'must': [{'multi_match': {
                'query': q,
                'fields': ['name^3', 'description', 'category', 'brand', 'ip', 'charactername'],
            }}],
            'must_not': [{'term': {'status': '下架'}}],
        }},
        'from': (page - 1) * size,
        'size': size,
        'track_total_hits': True,
        '_source': False,
    }
    try:
        r = _http.post(_url(f'/{INDEX}/_search'), json=body, timeout=4)
        if r.status_code != 200:
            return None
        hits = r.json().get('hits', {})
        total = int(hits.get('total', {}).get('value', 0))
        ids = [int(h['_id']) for h in hits.get('hits', [])]
        return ids, total
    except Exception:
        _mark_down()
        return None


def rebuild_all():
    """全量重建索引（MySQL → ES），后台线程调用"""
    with app.app_context():
        try:
            if not ensure_index():
                return
            goods_list = Goods.query.all()
            for g in goods_list:
                _http.put(_url(f'/{INDEX}/_doc/{g.id}'), json=_doc(g), timeout=3)
            print(f'ES 索引全量重建完成，共 {len(goods_list)} 个商品')
        except Exception as e:
            _mark_down()
            print(f'ES 全量重建失败（搜索将降级 MySQL）: {e}')


def rebuild_async():
    """应用启动时后台重建（不阻塞启动）"""
    threading.Thread(target=rebuild_all, daemon=True).start()
