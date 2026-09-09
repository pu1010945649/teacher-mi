"""轻量级站内事件总线（SSE 数据源）：页面动态刷新用。

订阅者按用户注册队列；发布时按角色或指定用户投递。
仅适合单进程部署（uvicorn 单 worker），与现有部署方式一致。
"""
import asyncio
import json
import time

from collections import defaultdict

# user_id -> {"role": str, "queues": set[asyncio.Queue]}
_subscribers: dict[int, dict] = defaultdict(lambda: {"role": "", "queues": set()})


def subscribe(user_id: int, role: str) -> asyncio.Queue:
    sub = _subscribers[user_id]
    sub["role"] = role
    q: asyncio.Queue = asyncio.Queue()
    sub["queues"].add(q)
    return q


def unsubscribe(user_id: int, q: asyncio.Queue):
    sub = _subscribers.get(user_id)
    if sub:
        sub["queues"].discard(q)
        if not sub["queues"]:
            _subscribers.pop(user_id, None)


def _push(user_ids: list[int], event: dict):
    data = json.dumps(event, ensure_ascii=False)
    for uid in set(user_ids):
        for q in _subscribers.get(uid, {}).get("queues", ()):
            q.put_nowait(data)


def publish_to_users(user_ids: list[int], event_type: str):
    """推送给指定用户"""
    if user_ids:
        _push(user_ids, {"type": event_type, "ts": time.time()})


def publish_to_teachers(event_type: str):
    """推送给所有在线教师"""
    ids = [uid for uid, sub in _subscribers.items() if sub["role"] == "teacher"]
    _push(ids, {"type": event_type, "ts": time.time()})


def publish_to_students(event_type: str, student_ids: list[int] | None = None):
    """推送给学生；不指定 ids 时广播全部在线学生"""
    if student_ids:
        _push(student_ids, {"type": event_type, "ts": time.time()})
        return
    ids = [uid for uid, sub in _subscribers.items() if sub["role"] == "student"]
    _push(ids, {"type": event_type, "ts": time.time()})


async def event_stream(user_id: int, role: str):
    """SSE 生成器：注册队列后持续输出事件，15 秒一次心跳保活"""
    q = subscribe(user_id, role)
    try:
        yield ": connected\n\n"
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        unsubscribe(user_id, q)
