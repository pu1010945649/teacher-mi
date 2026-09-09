import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, AssignmentTarget, Feedback, Submission, User
from ..schemas import AssignmentOut, AssignmentDescGenerate, AssignmentDescOut, FeedbackOut
from ..services.ai_service import chat, get_ai_config

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

MAX_FILE_SIZE = 20 * 1024 * 1024


def to_out(db: Session, item: Assignment, user: User) -> AssignmentOut:
    count = db.query(Submission).filter(Submission.assignment_id == item.id).count()
    out = AssignmentOut.model_validate(item)
    out.submission_count = count
    out.assigned_to_all = not item.targets
    out.target_count = len(item.targets)
    if user.role == "student":
        mine = db.query(Submission).filter(
            Submission.assignment_id == item.id, Submission.student_id == user.id).first()
        out.submitted = bool(mine)
        if mine and mine.status == "graded" and mine.feedback:
            fb = FeedbackOut.model_validate(mine.feedback)
            fb.has_annotated_file = bool(mine.feedback.file_path)
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
    for sid in ids:
        db.add(AssignmentTarget(assignment_id=item.id, student_id=sid))
    db.commit()
    return to_out(db, item, teacher)


@router.post("/generate-description", response_model=AssignmentDescOut)
async def generate_description(body: AssignmentDescGenerate, db: Session = Depends(get_db),
                               _: User = Depends(require_teacher)):
    """根据学生学习反馈综合生成作业要求"""
    get_ai_config(db)
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
    return {"description": await chat(db, messages)}


@router.get("/{assignment_id}/file")
def download_file(assignment_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    if user.role == "student" and not student_visible(db, assignment_id, user.id):
        raise HTTPException(403, "该作业未下发给你")
    if not item.file_path:
        raise HTTPException(404, "该作业没有附件")
    path = os.path.join(UPLOAD_DIR, item.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, filename=item.filename)


@router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db),
                      _: User = Depends(require_teacher)):
    item = db.get(Assignment, assignment_id)
    if not item:
        raise HTTPException(404, "作业不存在")
    db.query(Submission).filter(Submission.assignment_id == assignment_id).delete()
    db.query(AssignmentTarget).filter(AssignmentTarget.assignment_id == assignment_id).delete()
    db.delete(item)
    db.commit()
    return {"ok": True}
