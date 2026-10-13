"""简历生成进度：进程内发布/订阅，供 WebSocket 向前端实时推送进度。"""
import asyncio
from collections import defaultdict


class ProgressBroker:
    """按 resume_id 分组维护订阅者队列，发布时向所有订阅者广播进度消息。"""

    def __init__(self):
        self._subs = defaultdict(set)

    def subscribe(self, resume_id: int) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subs[resume_id].add(q)
        return q

    def unsubscribe(self, resume_id: int, q: asyncio.Queue):
        subs = self._subs.get(resume_id)
        if subs is None:
            return
        subs.discard(q)
        if not subs:
            self._subs.pop(resume_id, None)

    def publish(self, resume_id: int, msg: str):
        for q in list(self._subs.get(resume_id, ())):
            q.put_nowait(msg)


broker = ProgressBroker()