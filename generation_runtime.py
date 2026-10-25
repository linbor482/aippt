"""Per-request network budget; safe across concurrent serverless requests."""
import time
from contextvars import ContextVar

deadline = ContextVar('generation_deadline', default=None)


def check_budget():
    end = deadline.get()
    if end is not None and time.monotonic() >= end:
        raise ValueError('生成超时，请减少页数、关闭视觉校验或选择纯排版后重试。')


def network_timeout(seconds):
    check_budget()
    end = deadline.get()
    remaining = max(0.1, end - time.monotonic()) if end is not None else seconds + 10
    return (min(10, remaining / 2), min(seconds, remaining / 2))
