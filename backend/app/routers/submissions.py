import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, Submission, User
from ..schemas import SubmissionOut
from ..services.events import publish_to_teachers

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

MAX_FILE_SIZE = 20 * 1024 * 1024


def to_out(db: Session, item: Submission) -> SubmissionOut:
    out = SubmissionOut.model_validate(item)
    out.has_file = bool(item.file_path)
    out.assignment_title = item.assignment.title if item.assignment else ""
    out.student_name = item.student.real_name or item.student.username
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
    old = db.query(Submission).filter(
        Submission.assignment_id == assignment_id, Submission.student_id == student.id).first()
    if old and old.status == "graded":
        raise HTTPException(400, "该作业已批改，不能重新提交")

    file_path = ""
    if file and file.filename:
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, "文件大小不能超过 20MB")
        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
        with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
            f.write(data)
        file_path = safe_name

    if old:  # 重新提交：覆盖原记录
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
    return to_out(db, item)


@router.get("/my", response_model=list[SubmissionOut])
def my_submissions(db: Session = Depends(get_db), student: User = Depends(require_student)):
    items = db.query(Submission).filter(Submission.student_id == student.id).all()
    return [to_out(db, item) for item in items]


@router.get("/by-assignment/{assignment_id}", response_model=list[SubmissionOut])
def by_assignment(assignment_id: int, student_id: int | None = None,
                  db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    q = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    if student_id:
        q = q.filter(Submission.student_id == student_id)
    items = q.order_by(Submission.submitted_at.desc()).all()
    return [to_out(db, item) for item in items]


@router.get("/by-student/{student_id}", response_model=list[SubmissionOut])
def by_student(student_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(404, "学生不存在")
    items = db.query(Submission).filter(Submission.student_id == student_id)\
        .order_by(Submission.submitted_at.desc()).all()
    return [to_out(db, item) for item in items]


@router.get("/{submission_id}/file")
def download_file(submission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = get_submission(db, submission_id)
    if user.role == "student" and item.student_id != user.id:
        raise HTTPException(403, "无权下载他人作业")
    if not item.file_path:
        raise HTTPException(404, "该提交没有附件")
    path = os.path.join(UPLOAD_DIR, item.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    return FileResponse(path, filename=item.filename)
