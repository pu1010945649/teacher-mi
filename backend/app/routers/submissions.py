import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, AssignmentTarget, Submission, User
from ..schemas import SubmissionOut
from ..services.events import publish_to_students, publish_to_teachers
from ..services.push_service import send_to_users
from .feedback import require_own_assignment

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def student_visible_assignment(db: Session, assignment_id: int, student_id: int) -> bool:
    """作业是否已下发给该学生（未指定目标时全体可见）"""
    targets = db.query(AssignmentTarget).filter(
        AssignmentTarget.assignment_id == assignment_id).all()
    return not targets or any(t.student_id == student_id for t in targets)

MAX_FILE_SIZE = 20 * 1024 * 1024


def to_out(db: Session, item: Submission) -> SubmissionOut:
    out = SubmissionOut.model_validate(item)
    out.has_file = bool(item.file_path)
    out.assignment_title = item.assignment.title if item.assignment else ""
    out.student_name = item.student.real_name or item.student.username
    out.assigned_at = item.assignment.created_at if item.assignment else None
    if out.feedback:
        out.feedback.has_annotated_file = bool(item.feedback.file_path)
    return out


def get_submission(db: Session, submission_id: int) -> Submission:
    item = db.get(Submission, submission_id)
    if not item:
        raise HTTPException(404, "提交记录不存在")
    return item


@router.post("", response_model=SubmissionOut)
async def submit(assignment_id: int = Form(...), content: str = Form(""),
                 file: UploadFile | None = File(None), db: Session = Depends(get_db),
                 student: User = Depends(require_student)):
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "作业不存在")
    if not student_visible_assignment(db, assignment_id, student.id):
        raise HTTPException(403, "该作业未下发给你")
    latest = db.query(Submission).filter(
        Submission.assignment_id == assignment_id, Submission.student_id == student.id)\
        .order_by(Submission.attempt.desc()).first()
    if latest and latest.status in ("graded", "completed"):
        raise HTTPException(400, "该作业已批改，如需重新提交请联系老师退回")

    file_path = ""
    if file and file.filename:
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, "文件大小不能超过 20MB")
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
        with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
            f.write(data)
        file_path = safe_name

    if latest and latest.status == "returned":
        # 被退回后的重交：新建记录，老提交与反馈保留为历史
        item = Submission(assignment_id=assignment_id, student_id=student.id, content=content,
                          filename=file.filename if file else "", file_path=file_path,
                          attempt=latest.attempt + 1)
        db.add(item)
    elif latest:  # 批改前重复提交：覆盖原记录，只保留最新
        old = latest
        old.content, old.submitted_at, old.status = content, __import__("datetime").datetime.now(), "submitted"
        if file_path:
            old.file_path, old.filename = file_path, file.filename
        item = old
    else:
        item = Submission(assignment_id=assignment_id, student_id=student.id, content=content,
                          filename=file.filename if file else "", file_path=file_path)
        db.add(item)
    db.commit()
    db.refresh(item)
    publish_to_teachers("submission")
    # PushPlus 推送：只提醒作业发布老师（created_by）
    sname = student.real_name or student.username
    publisher = db.get(User, assignment.created_by) if assignment.created_by else None
    if publisher and publisher.role in ("teacher", "admin"):
        await send_to_users(db, [publisher], "作业提交提醒",
                            f"学生「{sname}」提交了作业《{assignment.title}》"
                            f"{'（附件：' + item.filename + '）' if item.filename else ''}。")
    return to_out(db, item)


@router.post("/{submission_id}/return", response_model=SubmissionOut)
async def return_submission(submission_id: int, db: Session = Depends(get_db),
                            teacher: User = Depends(require_teacher)):
    """教师退回提交，要求学生重新提交（老提交与反馈保留为历史）"""
    item = get_submission(db, submission_id)
    require_own_assignment(db, teacher, item.assignment_id)
    if item.status == "completed":
        raise HTTPException(400, "已确认完成的作业不能退回")
    item.status = "returned"
    db.commit()
    db.refresh(item)
    publish_to_students("assignment", [item.student_id])
    publish_to_students("feedback", [item.student_id])
    # PushPlus 推送：提醒学生作业被退回，需重新提交
    await send_to_users(db, [item.student], "作业退回提醒",
                        f"你的作业《{item.assignment.title}》已被老师退回，请查看批改意见后重新提交。")
    return to_out(db, item)


@router.post("/{submission_id}/complete", response_model=SubmissionOut)
def complete_submission(submission_id: int, db: Session = Depends(get_db),
                        teacher: User = Depends(require_teacher)):
    """教师确认批改完成，学生不能再提交，也不能再退回"""
    item = get_submission(db, submission_id)
    require_own_assignment(db, teacher, item.assignment_id)
    item.status = "completed"
    db.commit()
    db.refresh(item)
    publish_to_students("feedback", [item.student_id])
    return to_out(db, item)


@router.get("/source", response_model=list[SubmissionOut])
def submission_source(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    """本人作业的提交记录（扁平列表），供 AI 练习选择关注点来源"""
    items = (db.query(Submission).join(Assignment, Submission.assignment_id == Assignment.id)
             .filter(Assignment.created_by == user.id)
             .order_by(Submission.submitted_at.desc()).limit(500).all())
    return [to_out(db, item) for item in items]


@router.get("/my", response_model=list[SubmissionOut])
def my_submissions(db: Session = Depends(get_db), student: User = Depends(require_student)):
    items = db.query(Submission).filter(Submission.student_id == student.id).all()
    return [to_out(db, item) for item in items]


@router.get("/by-assignment/{assignment_id}", response_model=list[SubmissionOut])
def by_assignment(assignment_id: int, student_id: int | None = None,
                  db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    assignment = db.get(Assignment, assignment_id)
    if not assignment or (user.role == "teacher" and assignment.created_by != user.id):
        raise HTTPException(404, "作业不存在")
    q = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    if student_id:
        q = q.filter(Submission.student_id == student_id)
    items = q.order_by(Submission.submitted_at.desc()).all()
    return [to_out(db, item) for item in items]


@router.get("/by-student/{student_id}", response_model=list[SubmissionOut])
def by_student(student_id: int, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(404, "学生不存在")
    q = db.query(Submission).join(Assignment, Submission.assignment_id == Assignment.id)\
        .filter(Submission.student_id == student_id)
    if user.role == "teacher":
        q = q.filter(Assignment.created_by == user.id)  # 只看提交给自己作业的记录
    items = q.order_by(Submission.submitted_at.desc()).all()
    return [to_out(db, item) for item in items]


@router.get("/{submission_id}/file")
def download_file(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_submission(db, submission_id)
    if user.role == "student" and item.student_id != user.id:
        raise HTTPException(403, "无权下载他人作业")
    if user.role == "teacher" and item.assignment.created_by != user.id:
        raise HTTPException(403, "只能下载自己作业的提交附件")
    if not item.file_path:
        raise HTTPException(404, "该提交没有附件")
    path = os.path.join(UPLOAD_DIR, item.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, filename=item.filename)
