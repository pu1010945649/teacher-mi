from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import hash_password, require_teacher
from ..database import get_db
from ..models import AssignmentTarget, Course, CourseFeedback, Feedback, Submission, User, Worksheet
from ..schemas import StudentCreate, StudentUpdate, UserOut

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("", response_model=list[UserOut])
def list_students(keyword: str = "", db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    query = db.query(User).filter(User.role == "student")
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.real_name.like(like), User.username.like(like),
                                 User.student_no.like(like), User.class_name.like(like)))
    return query.order_by(User.id.desc()).all()


@router.post("", response_model=UserOut)
def create_student(body: StudentCreate, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password), role="student",
                real_name=body.real_name, student_no=body.student_no, class_name=body.class_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{student_id}", response_model=UserOut)
def update_student(student_id: int, body: StudentUpdate, db: Session = Depends(get_db),
                   _: User = Depends(require_teacher)):
    user = db.get(User, student_id)
    if not user or user.role != "student":
        raise HTTPException(404, "学生不存在")
    user.real_name = body.real_name
    user.student_no = body.student_no
    user.class_name = body.class_name
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    user = db.get(User, student_id)
    if not user or user.role != "student":
        raise HTTPException(404, "学生不存在")
    # 级联清理该学生的全部关联数据
    db.query(Feedback).filter(Feedback.teacher_id == user.id).delete()
    db.query(CourseFeedback).filter(CourseFeedback.teacher_id == user.id).delete()
    db.query(CourseFeedback).filter(CourseFeedback.course_id.in_(
        db.query(Course.id).filter(Course.student_id == user.id))).delete(synchronize_session=False)
    db.query(Course).filter(Course.student_id == user.id).delete()
    db.query(Worksheet).filter(Worksheet.student_id == user.id).delete()
    db.query(Feedback).filter(Feedback.submission_id.in_(
        db.query(Submission.id).filter(Submission.student_id == user.id))).delete(synchronize_session=False)
    db.query(Submission).filter(Submission.student_id == user.id).delete()
    db.query(AssignmentTarget).filter(AssignmentTarget.student_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}
