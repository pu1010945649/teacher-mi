import os
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import ensure_ai_allowed, get_current_user, require_staff, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, AssignmentTarget, Feedback, Submission, TeacherStudentLink, User
from ..schemas import AssignmentOut, AssignmentDescGenerate, AssignmentDescOut, FeedbackOut
from ..services.ai_service import chat, get_ai_config
from ..services.events import publish_to_students
from ..services.push_service import send_to_users

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_VIDEO_SIZE = 200 * 1024 * 1024
VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}


def remove_video_file(item: Assignment):
    """删除作业的讲解视频文件（磁盘 + 记录）"""
    if item.video_path:
        path = os.path.join(UPLOAD_DIR, item.video_path)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    item.video_filename, item.video_path = "", ""


def to_out(db: Session, item: Assignment, user: User) -> AssignmentOut:
    count = db.query(Submission).filter(Submission.assignment_id == item.id).count()
    out = AssignmentOut.model_validate(item)
    out.has_video = bool(item.video_path)
    out.video_filename = item.video_filename
    out.submission_count = count
    out.assigned_to_all = not item.targets
    out.target_count = len(item.targets)
    if user.role != "student" and item.targets:
        ids = [t.student_id for t in item.targets]
        out.target_ids = ids
        out.target_names = [
            (u.real_name or u.username) for u in
            db.query(User).filter(User.id.in_(ids)).all()
        ]
    if user.role == "student":
        mine = db.query(Submission).filter(
            Submission.assignment_id == item.id, Submission.student_id == user.id)\
            .order_by(Submission.attempt.desc()).first()
        out.submitted = bool(mine)
        out.returned = bool(mine and mine.status == "returned")
        # 最近一次有反馈的提交（重交后仍可查看上一轮教师反馈）
        graded = db.query(Submission).join(Feedback, Feedback.submission_id == Submission.id).filter(
            Submission.assignment_id == item.id, Submission.student_id == user.id)\
            .order_by(Submission.attempt.desc()).first()
        if graded and graded.feedback:
            fb = FeedbackOut.model_validate(graded.feedback)
            fb.has_annotated_file = bool(graded.feedback.file_path)
            out.my_feedback = fb
    return out


def student_visible(db: Session, assignment_id: int, student_id: int) -> bool:
    targets = db.query(AssignmentTarget).filter(
        AssignmentTarget.assignment_id == assignment_id).all()
    return not targets or any(t.student_id == student_id for t in targets)


@router.get("", response_model=list[AssignmentOut])
def list_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                     sort: str = "created_desc",
                     start_date: str | None = None, end_date: str | None = None):
    order_map = {
        "created_desc": Assignment.created_at.desc(),
        "created_asc": Assignment.created_at.asc(),
        "deadline_asc": Assignment.deadline.asc().nullslast(),
        "deadline_desc": Assignment.deadline.desc().nullsfirst(),
    }
    order = order_map.get(sort, Assignment.created_at.desc())
    query = db.query(Assignment).order_by(order)
    if start_date:
        try:
            query = query.filter(Assignment.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            # 结束日期取当天 23:59:59，保证“含当天”
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            query = query.filter(Assignment.created_at <= end_dt)
        except ValueError:
            pass
    if user.role == "student":
        all_ids = {t.assignment_id for t in db.query(AssignmentTarget).all()}
        mine_ids = {t.assignment_id for t in db.query(AssignmentTarget).filter(
            AssignmentTarget.student_id == user.id).all()}
        ids = [a.id for a in query.all() if a.id not in all_ids or a.id in mine_ids]
        items = db.query(Assignment).filter(Assignment.id.in_(ids)).order_by(order).all() if ids else []
    else:
        if user.role == "teacher":
            query = query.filter(Assignment.created_by == user.id)  # 教师只看自己下发的作业
        items = query.all()
    return [to_out(db, item, user) for item in items]


@router.post("", response_model=AssignmentOut)
async def create_assignment(title: str = Form(...), description: str = Form(""),
                            deadline: str | None = Form(None),
                            student_ids: str = Form(""),  # 逗号分隔；空 = 全体学生
                            file: UploadFile | None = File(None),
                            db: Session = Depends(get_db),
                            teacher: User = Depends(require_teacher)):
    dl = datetime.fromisoformat(deadline) if deadline else None
    item = Assignment(title=title, description=description, deadline=dl, created_by=teacher.id)

    if file and file.filename:
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, "文件大小不能超过 20MB")
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
        with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
            f.write(data)
        item.filename, item.file_path = file.filename, safe_name

    db.add(item)
    db.commit()
    db.refresh(item)

    ids = [int(x) for x in student_ids.split(",") if x.strip()]
    if not ids:
        # 空表示"全体学生"：仅指已绑定该教师的学生（含各科目绑定）
        ids = list({r[0] for r in db.query(TeacherStudentLink.student_id)
                    .filter(TeacherStudentLink.teacher_id == teacher.id).all()})
    # 资源隔离：下发对象必须是已绑定该教师的学生
    bound = {r[0] for r in db.query(TeacherStudentLink.student_id)
             .filter(TeacherStudentLink.teacher_id == teacher.id,
                     TeacherStudentLink.student_id.in_(ids)).all()}
    if set(ids) - bound:
        raise HTTPException(403, "只能向已绑定自己的学生下发作业")
    for sid in ids:
        db.add(AssignmentTarget(assignment_id=item.id, student_id=sid))
    db.commit()
    # 广播在线学生 + PushPlus 定向推送
    publish_to_students("assignment", ids or None)
    # PushPlus 推送：按接收学生的 Token 定向推送
    receivers = db.query(User).filter(User.id.in_(ids)).all()
    await send_to_users(db, receivers, "新作业通知", f"老师下发了新作业《{title}》，请及时查看并完成。")
    return to_out(db, item, teacher)


@router.post("/generate-description", response_model=AssignmentDescOut)
async def generate_description(body: AssignmentDescGenerate, db: Session = Depends(get_db),
                               user: User = Depends(require_teacher)):
    """根据学生学习反馈综合生成作业要求"""
    ensure_ai_allowed(db, user)
    get_ai_config(db, user)
    q = db.query(Feedback).join(Submission, Feedback.submission_id == Submission.id)
    if body.student_ids:
        q = q.join(User, Submission.student_id == User.id).filter(
            Submission.student_id.in_(body.student_ids))
    records = q.order_by(Feedback.id.desc()).limit(30).all()
    lines = []
    for fb in records:
        sub = db.get(Submission, fb.submission_id)
        name = sub.student.real_name or sub.student.username
        score = fb.score if fb.score is not None else "-"
        lines.append(f"- {name}，作业《{sub.assignment.title}》，得分：{score}，"
                     f"评语：{(fb.content or '无')[:100]}")
    if not lines:
        record_text = "（暂无历史反馈记录，请出一道通用巩固练习）"
    else:
        record_text = "\n".join(lines)
    hint = f"\n教师关注点：{body.hint}" if body.hint else ""
    messages = [
        {"role": "system", "content": "你是小学教师助手，根据学生学习情况设计作业要求，200字以内，分条描述，直接输出内容。"},
        {"role": "user", "content": f"以下是学生近期学习反馈：\n{record_text}{hint}\n\n请综合这些情况生成一份新作业的要求内容。"},
    ]
    return {"description": await chat(db, messages, user=user)}


@router.get("/{assignment_id}/file")
def download_file(assignment_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if user.role == "student" and not student_visible(db, assignment_id, user.id):
        raise HTTPException(403, "该作业未下发给你")
    if user.role == "teacher" and item.created_by != user.id:
        raise HTTPException(403, "只能下载自己创建的作业附件")
    if not item.file_path:
        raise HTTPException(404, "该作业没有附件")
    path = os.path.join(UPLOAD_DIR, item.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, filename=item.filename)


@router.post("/{assignment_id}/video", response_model=AssignmentOut)
async def upload_video(assignment_id: int, file: UploadFile = File(...),
                       db: Session = Depends(get_db),
                       teacher: User = Depends(require_teacher)):
    """上传/替换作业讲解视频（仅下发该作业的教师），旧视频会被覆盖删除"""
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if item.created_by != teacher.id:
        raise HTTPException(403, "只能操作自己下发的作业")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, "仅支持 mp4/webm/ogg/mov/m4v 格式视频")
    data = await file.read()
    if len(data) > MAX_VIDEO_SIZE:
        raise HTTPException(400, "视频大小不能超过 200MB")
    # 覆盖上传：先删旧视频文件
    remove_video_file(item)
    safe_name = f"{uuid.uuid4().hex}_video{ext}"
    with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
        f.write(data)
    item.video_filename, item.video_path = file.filename, safe_name
    db.commit()
    db.refresh(item)
    publish_to_students("assignment", [t.student_id for t in item.targets] or None)
    return to_out(db, item, teacher)


@router.delete("/{assignment_id}/video", response_model=AssignmentOut)
def delete_video(assignment_id: int, db: Session = Depends(get_db),
                 teacher: User = Depends(require_teacher)):
    """删除作业讲解视频（仅下发该作业的教师）"""
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if item.created_by != teacher.id:
        raise HTTPException(403, "只能操作自己下发的作业")
    remove_video_file(item)
    db.commit()
    return to_out(db, item, teacher)


@router.get("/{assignment_id}/video")
def stream_video(assignment_id: int, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """在线播放讲解视频（支持 Range 分段播放）"""
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if user.role == "student" and not student_visible(db, assignment_id, user.id):
        raise HTTPException(403, "该作业未下发给你")
    if not item.video_path:
        raise HTTPException(404, "该作业没有讲解视频")
    path = os.path.join(UPLOAD_DIR, item.video_path)
    if not os.path.exists(path):
        raise HTTPException(404, "视频文件已丢失")
    file_size = os.path.getsize(path)
    range_header = request.headers.get("range")
    media_type = "video/mp4" if item.video_path.endswith(".mp4") else "video/webm"
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else file_size - 1
        end = min(end, file_size - 1)
        if start > end:
            raise HTTPException(416, "Range Not Satisfiable")
        with open(path, "rb") as f:
            f.seek(start)
            chunk = f.read(end - start + 1)
        return StreamingResponse(iter([chunk]), status_code=206, media_type=media_type,
                                 headers={
                                     "Content-Range": f"bytes {start}-{end}/{file_size}",
                                     "Accept-Ranges": "bytes",
                                     "Content-Length": str(len(chunk)),
                                 })
    return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})


class TargetAdd(BaseModel):
    student_ids: list[int]


@router.post("/{assignment_id}/targets", response_model=AssignmentOut)
async def add_targets(assignment_id: int, body: TargetAdd, db: Session = Depends(get_db),
                      teacher: User = Depends(require_teacher)):
    """已布置的作业抄送给更多学生（增量添加下发对象，仅限下发该作业的教师操作）"""
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if item.created_by != teacher.id:
        raise HTTPException(403, "只能操作自己下发的作业")
    if not body.student_ids:
        raise HTTPException(400, "请选择要抄送的学生")

    existing = {t.student_id for t in db.query(AssignmentTarget)
                .filter(AssignmentTarget.assignment_id == assignment_id).all()}
    if not existing:
        # 原为"全体绑定学生"：先物化当前范围，再叠加抄送对象，避免语义漂移
        existing = {r[0] for r in db.query(TeacherStudentLink.student_id)
                    .filter(TeacherStudentLink.teacher_id == teacher.id).all()}
        for sid in existing:
            db.add(AssignmentTarget(assignment_id=assignment_id, student_id=sid))
        db.flush()

    new_ids = [sid for sid in body.student_ids if sid not in existing]
    if not new_ids:
        raise HTTPException(400, "所选学生均已在下发范围内")
    # 资源隔离：抄送对象必须是已绑定该教师的学生
    bound = {r[0] for r in db.query(TeacherStudentLink.student_id)
             .filter(TeacherStudentLink.teacher_id == teacher.id,
                     TeacherStudentLink.student_id.in_(new_ids)).all()}
    if set(new_ids) - bound:
        raise HTTPException(403, "只能抄送给已绑定自己的学生")
    for sid in new_ids:
        db.add(AssignmentTarget(assignment_id=assignment_id, student_id=sid))
    db.commit()
    db.refresh(item)

    publish_to_students("assignment", new_ids)
    receivers = db.query(User).filter(User.id.in_(new_ids)).all()
    await send_to_users(db, receivers, "新作业通知", f"老师向你下发了作业《{item.title}》，请及时查看并完成。")
    return to_out(db, item, teacher)


@router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db),
                      user: User = Depends(require_teacher)):
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if item.created_by != user.id:
        raise HTTPException(403, "只能删除自己下发的作业")
    targets = db.query(AssignmentTarget).filter(
        AssignmentTarget.assignment_id == assignment_id).all()
    remove_video_file(item)  # 讲解视频随作业一并删除
    db.query(Submission).filter(Submission.assignment_id == assignment_id).delete()
    db.query(AssignmentTarget).filter(AssignmentTarget.assignment_id == assignment_id).delete()
    db.delete(item)
    db.commit()
    publish_to_students("assignment", [t.student_id for t in targets] or None)
    return {"ok": True}
