from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..services.events import event_stream

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def sse(user: User = Depends(get_current_user)):
    """Server-Sent Events：登录后长连接，接收站内数据变更事件驱动页面刷新"""
    return StreamingResponse(
        event_stream(user.id, user.role),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
