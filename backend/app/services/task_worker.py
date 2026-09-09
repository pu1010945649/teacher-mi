"""AI 练习生成后台任务队列：多任务排队，最大并发数可在设置中调整"""
import asyncio
import json
import os
import uuid
from datetime import datetime

from ..config import UPLOAD_DIR
from ..database import SessionLocal
from ..models import AppSetting, Course, CourseFeedback, Submission, User, WorksheetTask
from .ai_service import chat, parse_json_object
from .pdf_service import build_pdf
from .events import publish_to_students, publish_to_teachers

CONCURRENCY_KEY = "worksheet_task_concurrency"
DEFAULT_CONCURRENCY = 2
MAX_CONCURRENCY = 10

PROMPT = (
    "你是一位经验丰富的教师。请根据学生的学习记录，针对其薄弱环节生成一份个性化练习作业。\n"
    '以 JSON 返回：{{"title": "练习标题", "content": "练习内容"}}。\n'
    "content 为纯文本：用「一、二、三」分节（如 一、选择题 / 二、填空题 / 三、解答题），"
    "每题单独一行并用数字编号，共 6-10 题，难度围绕学生掌握较差的知识点。\n"
    "重点关注「每节课教师反馈与学生回复」中反映的问题。\n"
    "只返回 JSON，不要其他内容。\n\n学生姓名：{name}\n\n"
    "每节课教师反馈与学生回复（练习关注点来源）：\n{course_feedbacks}\n\n作业批改记录：\n{records}"
)

_queue: asyncio.Queue | None = None
_running: set[asyncio.Task] = set()
_scheduler: asyncio.Task | None = None


def get_concurrency() -> int:
    db = SessionLocal()
    try:
        row = db.get(AppSetting, CONCURRENCY_KEY)
        try:
            n = int(row.value) if row else DEFAULT_CONCURRENCY
        except (TypeError, ValueError):
            n = DEFAULT_CONCURRENCY
        return max(1, min(MAX_CONCURRENCY, n))
    finally:
        db.close()


def set_concurrency(n: int) -> int:
    n = max(1, min(MAX_CONCURRENCY, int(n)))
    db = SessionLocal()
    try:
        row = db.get(AppSetting, CONCURRENCY_KEY)
        if row:
            row.value = str(n)
        else:
            db.add(AppSetting(key=CONCURRENCY_KEY, value=str(n)))
        db.commit()
    finally:
        db.close()
    return n


def collect_records(db, student: User, submission_ids: list[int] | None = None) -> str:
    """收集学生的作业反馈记录；指定 submission_ids 时只取所选记录"""
    q = db.query(Submission).filter(Submission.student_id == student.id)
    if submission_ids:
        q = q.filter(Submission.id.in_(submission_ids))
    subs = q.all()
    lines = []
    for sub in subs:
        fb = sub.feedback
        score = fb.score if fb else "未批改"
        comment = fb.content if fb else ""
        excerpt = (sub.content or "")[:150]
        lines.append(f"- 作业《{sub.assignment.title}》得分：{score}；教师评语：{comment}；提交摘要：{excerpt}")
    return "\n".join(lines) if lines else "（暂无记录）"


def collect_course_feedbacks(db, student: User, feedback_ids: list[int] | None = None) -> str:
    """收集学生的课程反馈（含学生回复）；指定 feedback_ids 时只取所选记录"""
    q = (db.query(CourseFeedback)
         .join(Course, CourseFeedback.course_id == Course.id)
         .filter(Course.student_id == student.id))
    if feedback_ids:
        q = q.filter(CourseFeedback.id.in_(feedback_ids))
    fbs = q.order_by(Course.start_time).all()
    lines = []
    for fb in fbs:
        reply = f"；学生回复：{fb.reply}" if fb.reply else ""
        lines.append(f"- 课程《{fb.course.title}》：教师反馈：{fb.content}{reply}")
    return "\n".join(lines) if lines else "（暂无记录）"


def enqueue(task_id: int):
    if _queue is not None:
        _queue.put_nowait(task_id)


def recover_pending_tasks():
    """启动时把中断的 pending/running 任务重新入队"""
    db = SessionLocal()
    try:
        rows = db.query(WorksheetTask).filter(
            WorksheetTask.status.in_(["pending", "running"])).all()
        for t in rows:
            if t.status == "running":
                t.status = "pending"
        db.commit()
        ids = [t.id for t in rows]
    finally:
        db.close()
    for tid in ids:
        enqueue(tid)


async def run_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.get(WorksheetTask, task_id)
        if not task or task.status != "pending":
            return
        task.status = "running"
        db.commit()

        try:
            student = db.get(User, task.student_id)
            if not student or student.role != "student":
                raise RuntimeError("学生不存在")
            try:
                submission_ids = json.loads(task.submission_ids or "[]")
            except json.JSONDecodeError:
                submission_ids = []
            try:
                feedback_ids = json.loads(task.course_feedback_ids or "[]")
            except json.JSONDecodeError:
                feedback_ids = []
            records = collect_records(db, student, submission_ids or None)
            course_feedbacks = collect_course_feedbacks(db, student, feedback_ids or None)

            prompt = PROMPT.format(name=student.real_name or student.username,
                                   course_feedbacks=course_feedbacks, records=records)
            result = await chat(db, [{"role": "user", "content": prompt}])
            data = parse_json_object(result)
            title = str(data.get("title") or f"{student.real_name or student.username} 个性化练习")
            content = str(data.get("content") or result).strip()

            pdf_name = f"{uuid.uuid4().hex}_ws.pdf"
            build_pdf(title, content, os.path.join(UPLOAD_DIR, pdf_name))
            # 生成草稿，等待教师编辑确认后下发
            task.title, task.content, task.pdf_path = title, content, pdf_name
            task.status = "generated"
            task.finished_at = datetime.now()
            db.commit()
            publish_to_teachers("worksheet")
        except Exception as e:  # 单任务失败不影响队列
            db.rollback()
            task = db.get(WorksheetTask, task_id)
            if task:
                task.status = "failed"
                task.error = str(e)[:500]
                task.finished_at = datetime.now()
                db.commit()
    finally:
        db.close()


async def _run_and_track(task_id: int):
    try:
        await run_task(task_id)
    finally:
        _running.discard(asyncio.current_task())


async def scheduler_loop():
    """每秒检查一次：并发未满且队列有任务则启动新任务（动态读取并发配置）"""
    while True:
        try:
            limit = get_concurrency()
            while _queue is not None and len(_running) < limit and not _queue.empty():
                tid = _queue.get_nowait()
                t = asyncio.create_task(_run_and_track(tid))
                _running.add(t)
        except Exception:
            pass
        await asyncio.sleep(1)


def start_worker():
    global _queue, _scheduler
    if _queue is None:
        _queue = asyncio.Queue()
        recover_pending_tasks()
    if _scheduler is None or _scheduler.done():
        _scheduler = asyncio.create_task(scheduler_loop())


def stop_worker():
    global _queue, _scheduler
    if _scheduler:
        _scheduler.cancel()
        _scheduler = None
    if _running:
        for t in list(_running):
            t.cancel()
        _running.clear()
    _queue = None
