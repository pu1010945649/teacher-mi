from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import Course, CourseFeedback, User
from ..schemas import (CourseCreate, CourseFeedbackCreate, CourseOut,
                       CourseReplyCreate, FeedbackPolishIn, PolishOut)
from ..services.ai_service import chat, get_ai_config
from ..services.events import publish_to_students, publish_to_teachers

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
    publish_to_students("course", [course.student_id])
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
    publish_to_students("course", [course.student_id])
    return to_out(course, db)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  _: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db)
    student_id = course.student_id
    db.query(CourseFeedback).filter(CourseFeedback.course_id == course_id).delete()
    db.delete(course)
    db.commit()
    publish_to_students("course", [student_id])
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
    publish_to_students("course", [course.student_id])
    return to_out(course, db)


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int, db: Session = Depends(get_db),
                    _: User = Depends(require_teacher)):
    fb = db.query(CourseFeedback).get(feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    course = get_course_or_404(fb.course_id, db)
    db.delete(fb)
    db.commit()
    publish_to_students("course", [course.student_id])
    return {"ok": True}


# ===== 教师：AI 练习关注点来源 =====
@router.get("/feedback-source")
def feedback_source(db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    """全部课程反馈（扁平列表），供 AI 练习选择关注点来源"""
    from ..schemas import CourseFeedbackSourceOut
    rows = (db.query(CourseFeedback)
            .join(Course, CourseFeedback.course_id == Course.id)
            .order_by(Course.start_time.desc()).all())
    out = []
    for fb in rows:
        out.append(CourseFeedbackSourceOut(
            id=fb.id, student_id=fb.course.student_id,
            student_name=fb.course.student.real_name or fb.course.student.username,
            course_title=fb.course.title,
            content=fb.content, created_at=fb.created_at,
        ).model_dump(mode="json"))
    return out


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
    publish_to_teachers("course")
    return to_out(course, db)


# ===== 教师：课程反馈 AI 润色 =====
@router.post("/feedback/polish", response_model=PolishOut)
async def polish_feedback(body: FeedbackPolishIn, db: Session = Depends(get_db),
                          _: User = Depends(require_teacher)):
    """AI 润色扩写课程反馈：根据教师的简单输入生成更完整的反馈文案，供教师编辑确认"""
    raw = body.content.strip()
    if not raw:
        raise HTTPException(400, "请先填写反馈要点")
    # AI 未配置时直接拦截并提示
    get_ai_config(db)
    prompt = (
        "你是一位经验丰富的辅导教师。请把下面的课程反馈要点润色扩写为一段通顺、专业、"
        "亲切的课堂学习反馈，面向家长/学生。保留原意，可补充常规教学建议，"
        "不要虚构具体成绩或事实，300 字以内，直接输出正文。\n"
        + (f"润色侧重：{body.hint.strip()}\n" if body.hint.strip() else "")
        + f"\n反馈要点：\n{raw}"
    )
    result = await chat(db, [{"role": "user", "content": prompt}])
    return PolishOut(content=result.strip())
