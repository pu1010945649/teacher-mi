from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import Course, CourseFeedback, User
from ..schemas import CourseCreate, CourseFeedbackCreate, CourseOut, CourseReplyCreate

router = APIRouter(prefix="/api/courses", tags=["courses"])


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("T", " "))
    except ValueError:
        raise HTTPException(400, f"时间格式不正确：{s}")


def to_out(item: Course, db: Session) -> CourseOut:
    out = CourseOut.model_validate(item)
    out.student_name = item.student.real_name or item.student.username
    out.feedbacks = sorted(item.feedbacks, key=lambda f: f.id)
    return out


def get_course_or_404(course_id: int, db: Session) -> Course:
    course = db.query(Course).get(course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    return course


# ===== 教师：课表管理 =====
@router.get("", response_model=list[CourseOut])
def list_courses(start: str | None = None, end: str | None = None,
                 student_id: int | None = None,
                 db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    q = db.query(Course).order_by(Course.start_time)
    if start:
        q = q.filter(Course.start_time >= parse_dt(start))
    if end:
        q = q.filter(Course.start_time < parse_dt(end))
    if student_id:
        q = q.filter(Course.student_id == student_id)
    return [to_out(c, db) for c in q.all()]


@router.post("", response_model=CourseOut)
def create_course(body: CourseCreate, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    if not body.title.strip():
        raise HTTPException(400, "请填写课程名称")
    student = db.query(User).get(body.student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    course = Course(teacher_id=user.id, student_id=body.student_id,
                    title=body.title.strip(), start_time=parse_dt(body.start_time),
                    end_time=parse_dt(body.end_time), location=body.location, note=body.note)
    db.add(course)
    db.commit()
    db.refresh(course)
    return to_out(course, db)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, body: CourseCreate, db: Session = Depends(get_db),
                  _: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db)
    student = db.query(User).get(body.student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    course.student_id = body.student_id
    course.title = body.title.strip()
    course.start_time = parse_dt(body.start_time)
    course.end_time = parse_dt(body.end_time)
    course.location = body.location
    course.note = body.note
    db.commit()
    db.refresh(course)
    return to_out(course, db)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  _: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db)
    db.query(CourseFeedback).filter(CourseFeedback.course_id == course_id).delete()
    db.delete(course)
    db.commit()
    return {"ok": True}


@router.post("/{course_id}/feedback", response_model=CourseOut)
def add_feedback(course_id: int, body: CourseFeedbackCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db)
    if not body.content.strip():
        raise HTTPException(400, "请填写反馈内容")
    fb = CourseFeedback(course_id=course_id, teacher_id=user.id, content=body.content.strip())
    db.add(fb)
    db.commit()
    db.refresh(course)
    return to_out(course, db)


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int, db: Session = Depends(get_db),
                    _: User = Depends(require_teacher)):
    fb = db.query(CourseFeedback).get(feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    db.delete(fb)
    db.commit()
    return {"ok": True}


# ===== 学生：我的课表与回复 =====
@router.get("/my", response_model=list[CourseOut])
def my_courses(db: Session = Depends(get_db), student: User = Depends(require_student)):
    q = db.query(Course).filter(Course.student_id == student.id).order_by(Course.start_time.desc())
    return [to_out(c, db) for c in q.all()]


@router.post("/feedback/{feedback_id}/reply", response_model=CourseOut)
def reply_feedback(feedback_id: int, body: CourseReplyCreate, db: Session = Depends(get_db),
                   student: User = Depends(require_student)):
    fb = db.query(CourseFeedback).get(feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    course = get_course_or_404(fb.course_id, db)
    if course.student_id != student.id:
        raise HTTPException(403, "无权回复他人课程的反馈")
    if not body.content.strip():
        raise HTTPException(400, "请填写回复内容")
    fb.reply = body.content.strip()
    fb.replied_at = datetime.now()
    db.commit()
    db.refresh(course)
    return to_out(course, db)
