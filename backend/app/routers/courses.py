from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import ensure_ai_allowed, get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import Course, CourseFeedback, TeacherStudentLink, User
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


def to_out(item: Course, db: Session, user: User | None = None) -> CourseOut:
    out = CourseOut.model_validate(item)
    out.student_name = item.student.real_name or item.student.username
    teacher = db.get(User, item.teacher_id) if item.teacher_id else None
    out.teacher_name = (teacher.real_name or teacher.username) if teacher else ""
    out.is_mine = bool(user and item.teacher_id == user.id)
    out.feedbacks = sorted(item.feedbacks, key=lambda f: f.id)
    return out


def get_course_or_404(course_id: int, db: Session, user: User | None = None) -> Course:
    course = db.query(Course).get(course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    if user and user.role == "teacher" and course.teacher_id != user.id:
        raise HTTPException(403, "只能操作自己排的课程")
    return course


def _course_end(c: Course) -> datetime:
    """课程结束时间；未填或异常时按开始后 1 小时估算"""
    if c.end_time and c.end_time > c.start_time:
        return c.end_time
    return datetime.fromtimestamp(c.start_time.timestamp() + 3600)


def ensure_no_conflict(db: Session, student_id: int, start: datetime,
                       end: datetime | None, teacher_id: int | None = None,
                       exclude_id: int | None = None):
    """排课双重冲突校验：
    1) 学生侧：该学生时段不能与任何老师的课程重叠
    2) 老师侧：该老师时段不能与名下其他学生的课程重叠"""
    if not start:
        return
    new_end = end if (end and end > start) \
        else datetime.fromtimestamp(start.timestamp() + 3600)

    def overlaps(c):
        return start < _course_end(c) and c.start_time < new_end

    q = db.query(Course).filter(Course.student_id == student_id)
    if exclude_id:
        q = q.filter(Course.id != exclude_id)
    for c in q.all():
        if overlaps(c):
            t = db.get(User, c.teacher_id)
            tname = (t.real_name or t.username) if t else "其他老师"
            raise HTTPException(
                409, f"排课冲突：该学生时段已被课程《{c.title}》（{tname}）占用"
                     f"（{c.start_time.strftime('%m-%d %H:%M')} ~ {_course_end(c).strftime('%H:%M')}）")

    if teacher_id:
        q2 = db.query(Course).filter(Course.teacher_id == teacher_id)
        if exclude_id:
            q2 = q2.filter(Course.id != exclude_id)
        for c in q2.all():
            if overlaps(c):
                s = db.get(User, c.student_id)
                sname = (s.real_name or s.username) if s else f"学生#{c.student_id}"
                raise HTTPException(
                    409, f"排课冲突：你在该时段已给学生「{sname}」排了课程《{c.title}》"
                         f"（{c.start_time.strftime('%m-%d %H:%M')} ~ {_course_end(c).strftime('%H:%M')}），"
                         f"同一时段不能排给多个学生")


def ensure_binding(db: Session, teacher_id: int, student_id: int, subject: str = ""):
    """排课即建立该科目的师生绑定（多对多），已存在则跳过。
    科目以教师任教科目为准（课程标题是自由文本，不能当科目）；教师未设科目则不建绑定"""
    t = db.get(User, teacher_id)
    subject = (t.subject if t else "").strip()
    if not subject:
        return
    if not db.query(TeacherStudentLink)\
            .filter(TeacherStudentLink.teacher_id == teacher_id,
                    TeacherStudentLink.student_id == student_id,
                    TeacherStudentLink.subject == subject).first():
        db.add(TeacherStudentLink(teacher_id=teacher_id, student_id=student_id, subject=subject))


# ===== 教师：课表管理 =====
@router.get("", response_model=list[CourseOut])
def list_courses(start: str | None = None, end: str | None = None,
                 student_id: int | None = None,
                 db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    """默认仅返回教师自己排的课程；指定 student_id 时返回该学生的全部课程
    （含其他老师排的，is_mine=False 只读展示，用于排课冲突校验与查看）"""
    q = db.query(Course).order_by(Course.start_time)
    if start:
        q = q.filter(Course.start_time >= parse_dt(start))
    if end:
        q = q.filter(Course.start_time < parse_dt(end))
    if student_id:
        q = q.filter(Course.student_id == student_id)
    else:
        q = q.filter(Course.teacher_id == user.id)
    return [to_out(c, db, user) for c in q.all()]


@router.post("", response_model=CourseOut)
def create_course(body: CourseCreate, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    if not body.title.strip():
        raise HTTPException(400, "请填写课程名称")
    student = db.query(User).get(body.student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    st, et = parse_dt(body.start_time), parse_dt(body.end_time)
    ensure_no_conflict(db, body.student_id, st, et, teacher_id=user.id)
    course = Course(teacher_id=user.id, student_id=body.student_id,
                    title=body.title.strip(), start_time=st,
                    end_time=et, location=body.location, note=body.note)
    db.add(course)
    ensure_binding(db, user.id, body.student_id, body.title.strip())
    db.commit()
    db.refresh(course)
    publish_to_students("course", [course.student_id])
    publish_to_teachers("student")
    return to_out(course, db, user)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, body: CourseCreate, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db, user)
    student = db.query(User).get(body.student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    new_start = parse_dt(body.start_time)
    new_end = parse_dt(body.end_time)
    ensure_no_conflict(db, body.student_id, new_start, new_end,
                       teacher_id=user.id, exclude_id=course.id)
    course.student_id = body.student_id
    course.title = body.title.strip()
    if new_start != course.start_time:
        course.reminded_at = None  # 改期后重置提醒标记，按新时间重新提醒
    course.start_time = new_start
    course.end_time = new_end
    course.location = body.location
    course.note = body.note
    ensure_binding(db, user.id, body.student_id, body.title.strip())
    db.commit()
    db.refresh(course)
    publish_to_students("course", [course.student_id])
    return to_out(course, db, user)


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db, user)
    student_id = course.student_id
    db.query(CourseFeedback).filter(CourseFeedback.course_id == course_id).delete()
    db.delete(course)
    db.commit()
    publish_to_students("course", [student_id])
    return {"ok": True}


@router.post("/{course_id}/feedback", response_model=CourseOut)
def add_feedback(course_id: int, body: CourseFeedbackCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    course = get_course_or_404(course_id, db, user)
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
                    user: User = Depends(require_teacher)):
    fb = db.query(CourseFeedback).get(feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    course = get_course_or_404(fb.course_id, db, user)
    db.delete(fb)
    db.commit()
    publish_to_students("course", [course.student_id])
    return {"ok": True}


# ===== 教师：AI 练习关注点来源 =====
@router.get("/feedback-source")
def feedback_source(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    """本人课程的反馈（扁平列表），供 AI 练习选择关注点来源"""
    from ..schemas import CourseFeedbackSourceOut
    rows = (db.query(CourseFeedback)
            .join(Course, CourseFeedback.course_id == Course.id)
            .filter(Course.teacher_id == user.id)
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
                          user: User = Depends(require_teacher)):
    """AI 润色扩写课程反馈：根据教师的简单输入生成更完整的反馈文案，供教师编辑确认"""
    raw = body.content.strip()
    if not raw:
        raise HTTPException(400, "请先填写反馈要点")
    ensure_ai_allowed(db, user)
    # AI 未配置时直接拦截并提示
    get_ai_config(db, user)
    prompt = (
        "你是一位经验丰富的辅导教师。请把下面的课程反馈要点润色扩写为一段通顺、专业、"
        "亲切的课堂学习反馈，面向家长/学生。保留原意，可补充常规教学建议，"
        "不要虚构具体成绩或事实，300 字以内，直接输出正文。\n"
        + (f"润色侧重：{body.hint.strip()}\n" if body.hint.strip() else "")
        + f"\n反馈要点：\n{raw}"
    )
    result = await chat(db, [{"role": "user", "content": prompt}], user=user)
    return PolishOut(content=result.strip())
