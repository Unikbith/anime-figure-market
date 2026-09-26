# -*- coding: utf-8 -*-
"""输出流保护。

场景：Flask/Celery 进程若从已关闭的终端或失效管道启动（Windows 下常见），
sys.stdout 的写入会抛 OSError: [Errno 22] Invalid argument —— 而 send_email、
AI 客服等接口的正常路径都会 print，一次写失败就把整个请求打成 500。

方案：用 _SafeStream 包裹 sys.stdout / sys.stderr，写入失败时静默丢弃
（只丢日志，不影响业务响应）。
"""
import io
import sys

class _SafeStream:
    """包装原始流：write/flush 失败时静默丢弃，其余属性透传。"""

    def __init__(self, raw):
        self._raw = raw

    def write(self, *args, **kwargs):
        try:
            return self._raw.write(*args, **kwargs)
        except (OSError, ValueError):
            return 0

    def flush(self):
        try:
            self._raw.flush()
        except (OSError, ValueError):
            pass

    def isatty(self):
        return False

    def fileno(self):
        raise io.UnsupportedOperation('底层流已失效，fileno 不可用')

    def __getattr__(self, name):
        return getattr(self._raw, name)

def install():
    """包裹 stdout/stderr（幂等，可重复调用）。"""
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None or isinstance(stream, _SafeStream):
            continue
        setattr(sys, name, _SafeStream(stream))
