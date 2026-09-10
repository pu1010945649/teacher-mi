"""上课提醒：课程开始前 30 分钟通过 PushPlus 推送教师与学生"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Course
from .push_service import send_to_user

logger = logging.getLogger(__name__)
_window = timedelta(minutes=30)
_task: asyncio.Task | None = None


def fmt_hm(dt: datetime) -> str:
    return dt.strftime("%m月%d日 %H:%M")


async def check_and_send(db: Session):
    """推送 30 分钟内即将开始的课程提醒，并标记已提醒"""
    now = datetime.now()
    courses = db.query(Course).filter(
        Course.reminded_at.is_(None),
        Course.start_time >= now,
        Course.start_time <= now + _window,
    ).all()
    for c in courses:
        title = "上课提醒"
        time_text = fmt_hm(c.start_time)
        when = f"{time_text}开始" if c.start_time > now else "即将开始"
        loc = f"，地点：{c.location}" if c.location else ""
        # 标记先落库再推送，避免推送期间重复触发
        c.reminded_at = now
        db.commit()
        await send_to_user(db, c.student, title, f"您的课程《{c.title}》将于{when}{loc}，请提前准备。")
        await send_to_user(db, c.teacher, title, f"课程《{c.title}》将于{when}{loc}，学生：{c.student.real_name or c.student.username}。")


async def reminder_loop():
    """每分钟检查一次即将开始的课程"""
    while True:
        db = SessionLocal()
        try:
            await check_and_send(db)
        except Exception as e:
            logger.warning("上课提醒任务异常: %s", e)
        finally:
            db.close()
        await asyncio.sleep(60)


def start_reminder():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(reminder_loop())


def stop_reminder():
    global _task
    if _task:
        _task.cancel()
        _task = None
