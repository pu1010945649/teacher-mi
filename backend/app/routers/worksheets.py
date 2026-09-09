import os

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, AssignmentTarget, User, Worksheet
from ..schemas import WorksheetOut

router = APIRouter(prefix="/api/worksheets", tags=["worksheets"])


def to_out(item: Worksheet, student: User | None) -> WorksheetOut:
    out = WorksheetOut.model_validate(item)
    out.student_name = (student.real_name or student.username) if student else ""
    out.has_pdf = bool(item.pdf_path)
    return out


@router.get("", response_model=list[WorksheetOut])
def list_worksheets(student_id: int = 0, db: Session = Depends(get_db),
                    _: User = Depends(require_teacher)):
    query = db.query(Worksheet).order_by(Worksheet.id.desc())
    items = query.filter(Worksheet.student_id == student_id).all() if student_id else query.all()
    students = {s.id: s for s in db.query(User).filter(User.role == "student")}
    return [to_out(item, students.get(item.student_id)) for item in items]


@router.get("/my", response_model=list[WorksheetOut])
def my_worksheets(db: Session = Depends(get_db), student: User = Depends(require_student)):
    # 学生只可见已发布（确认发送）的练习
    items = db.query(Worksheet).filter(
        Worksheet.student_id == student.id, Worksheet.status == "published").all()
    return [to_out(item, student) for item in items]


@router.post("/{worksheet_id}/publish", response_model=WorksheetOut)
def publish_worksheet(worksheet_id: int, db: Session = Depends(get_db),
                      teacher: User = Depends(require_teacher)):
    """教师确认后发送给学生：创建一条学生作业（练习条目）并定向给该学生"""
    ws = db.get(Worksheet, worksheet_id)
    if not ws:
        raise HTTPException(404, "练习不存在")
    if ws.status == "published":
        raise HTTPException(400, "该练习已发送")

    assignment = Assignment(
        title=f"[个性化练习] {ws.title}",
        description=ws.content,
        created_by=teacher.id,
    )
    db.add(assignment)
    db.flush()
    db.add(AssignmentTarget(assignment_id=assignment.id, student_id=ws.student_id))

    ws.status = "published"
    ws.published_at = datetime.now()
    ws.published_as_assignment_id = assignment.id
    db.commit()
    db.refresh(ws)
    return to_out(ws, db.get(User, ws.student_id))


@router.post("/{worksheet_id}/reject", response_model=WorksheetOut)
def reject_worksheet(worksheet_id: int, db: Session = Depends(get_db),
                     teacher: User = Depends(require_teacher)):
    """教师驳回：不满意的生成结果，不会发送给学生"""
    ws = db.get(Worksheet, worksheet_id)
    if not ws:
        raise HTTPException(404, "练习不存在")
    if ws.status == "published":
        raise HTTPException(400, "已发送的练习不能驳回")
    ws.status = "rejected"
    db.commit()
    db.refresh(ws)
    return to_out(ws, db.get(User, ws.student_id))


@router.get("/{worksheet_id}/pdf")
def download_pdf(worksheet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ws = db.get(Worksheet, worksheet_id)
    if not ws:
        raise HTTPException(404, "练习不存在")
    if user.role == "student" and ws.student_id != user.id:
        raise HTTPException(403, "无权下载他人练习")
    path = os.path.join(UPLOAD_DIR, ws.pdf_path)
    if not ws.pdf_path or not os.path.exists(path):
        raise HTTPException(404, "PDF 文件已丢失")
    return FileResponse(path, filename=f"practice_{ws.id}.pdf")
