import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, Feedback, Submission, User
from ..schemas import FeedbackOut, SubmissionOut
from ..services.events import publish_to_students
from ..services.push_service import send_to_users

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_FILE_SIZE = 20 * 1024 * 1024


def require_own_assignment(db: Session, teacher: User, assignment_id: int | None):
    """校验提交所属作业确为本人创建，防止教师横向越权操作他人作业的提交"""
    if assignment_id is None:
        raise HTTPException(404, "提交记录不存在")
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.created_by != teacher.id:
        raise HTTPException(403, "无权操作他人作业的提交")


def mark_graded(db: Session, submission_id: int):
    sub = db.get(Submission, submission_id)
    if sub and sub.status != "completed":  # 已确认完成的不回退状态
        sub.status = "graded"
        db.commit()


@router.post("/{submission_id}", response_model=FeedbackOut)
async def create_feedback(submission_id: int, score: float | None = Form(None),
                          content: str = Form(""), annotation: str = Form(""),
                          ai_assisted: bool = Form(False),
                          file: UploadFile | None = File(None),
                          db: Session = Depends(get_db),
                          teacher: User = Depends(require_teacher)):
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "提交记录不存在")
    require_own_assignment(db, teacher, sub.assignment_id)
    fb = db.query(Feedback).filter(Feedback.submission_id == submission_id).first()
    if not fb:
        fb = Feedback(submission_id=submission_id, teacher_id=teacher.id)
        db.add(fb)
    fb.score, fb.content, fb.annotation, fb.ai_assisted = score, content, annotation, ai_assisted

    if file and file.filename:
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, "文件大小不能超过 20MB")
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
        with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
            f.write(data)
        fb.filename, fb.file_path = file.filename, safe_name

    db.commit()
    db.refresh(fb)
    mark_graded(db, submission_id)
    publish_to_students("feedback", [sub.student_id])
    # PushPlus 推送：提醒学生收到批改反馈
    if sub.student:
        await send_to_users(db, [sub.student], "批改反馈通知",
                            f"你的作业《{sub.assignment.title}》有新的老师反馈，请查看批改意见。")
    out = FeedbackOut.model_validate(fb)
    out.has_annotated_file = bool(fb.file_path)
    return out


@router.get("/my", response_model=list[SubmissionOut])
def my_feedback(db: Session = Depends(get_db), student: User = Depends(require_student)):
    items = db.query(Submission).filter(
        Submission.student_id == student.id,
        Submission.status.in_(["graded", "returned", "completed"])).all()
    out_list = []
    for item in items:
        out = SubmissionOut.model_validate(item)
        out.assignment_title = item.assignment.title if item.assignment else ""
        out.has_file = bool(item.file_path)
        if out.feedback:
            out.feedback.has_annotated_file = bool(item.feedback.file_path)
        out_list.append(out)
    return out_list


@router.get("/submission/{submission_id}", response_model=FeedbackOut)
def submission_feedback(submission_id: int, db: Session = Depends(get_db),
                        teacher: User = Depends(require_teacher)):
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "提交记录不存在")
    require_own_assignment(db, teacher, sub.assignment_id)
    fb = db.query(Feedback).filter(Feedback.submission_id == submission_id).first()
    out = FeedbackOut.model_validate(fb)
    out.has_annotated_file = bool(fb.file_path)
    return out


@router.get("/submission/{submission_id}/annotated-file")
def download_annotated(submission_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    fb = db.query(Feedback).filter(Feedback.submission_id == submission_id).first()
    if not fb or not fb.file_path:
        raise HTTPException(404, "该反馈没有批注文件")
    if user.role == "student":
        sub = db.get(Submission, submission_id)
        if not sub or sub.student_id != user.id:
            raise HTTPException(403, "无权下载他人批注文件")
    elif user.role == "teacher":
        sub = db.get(Submission, submission_id)
        if not sub or sub.assignment.created_by != user.id:
            raise HTTPException(403, "无权下载他人作业的批注文件")
    path = os.path.join(UPLOAD_DIR, fb.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, filename=fb.filename)
