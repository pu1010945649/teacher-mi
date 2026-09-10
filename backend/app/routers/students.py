"""学生管理：注册/删除/师生绑定（多对多、按科目）/好友令牌由管理员维护；教师只能查看和编辑已绑定自己的学生"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin, require_staff, require_teacher
from ..database import get_db
from ..models import AssignmentTarget, Course, CourseFeedback, Feedback, \
    Submission, TeacherStudentLink, User
from ..schemas import StudentBinding, StudentCreate, StudentUpdate, UserOut
from ..services.events import publish_to_teachers

router = APIRouter(prefix="/api/students", tags=["students"])


def _teacher_names(db: Session) -> dict[int, str]:
    rows = db.query(User).filter(User.role.in_(["teacher", "admin"])).all()
    return {t.id: (t.real_name or t.username) for t in rows}


def get_bindings(db: Session, student_id: int) -> list[TeacherStudentLink]:
    return (db.query(TeacherStudentLink)
            .filter(TeacherStudentLink.student_id == student_id)
            .order_by(TeacherStudentLink.id).all())


def teacher_student_ids(db: Session, teacher_id: int) -> list[int]:
    """该教师绑定的全部学生 id"""
    rows = db.query(TeacherStudentLink.student_id)\
        .filter(TeacherStudentLink.teacher_id == teacher_id).all()
    return list({r[0] for r in rows})


def apply_bindings(db: Session, student: User, bindings: list[StudentBinding]):
    """重建学生的师生绑定，并把主归属（第一个绑定教师）同步到 users.teacher_id"""
    db.query(TeacherStudentLink).filter(TeacherStudentLink.student_id == student.id).delete()
    seen = set()
    for b in bindings:
        key = (b.teacher_id, b.subject.strip())
        if key in seen or not b.teacher_id:
            continue
        seen.add(key)
        db.add(TeacherStudentLink(teacher_id=b.teacher_id, student_id=student.id,
                                  subject=b.subject.strip()))
    if bindings:
        student.teacher_id = bindings[0].teacher_id


def to_out(u: User, names: dict[int, str], bindings: list[TeacherStudentLink] | None = None) -> UserOut:
    out = UserOut.model_validate(u)
    links = bindings if bindings is not None else []
    out.teacher_id = u.teacher_id
    out.teacher_name = "、".join(
        dict.fromkeys(names.get(l.teacher_id, "") for l in links if names.get(l.teacher_id)))
    out.bindings = [StudentBinding(teacher_id=l.teacher_id, subject=l.subject) for l in links]
    return out


@router.get("", response_model=list[UserOut])
def list_students(keyword: str = "", all: int = 0, db: Session = Depends(get_db),
                  user: User = Depends(require_staff)):
    """教师只看已绑定自己的学生（all 参数已废弃，保留兼容旧前端调用）；管理员看全部学生"""
    query = db.query(User).filter(User.role == "student")
    if user.role == "teacher":
        ids = teacher_student_ids(db, user.id)
        query = query.filter(User.id.in_(ids))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.real_name.like(like), User.username.like(like),
                                 User.student_no.like(like), User.class_name.like(like)))
    items = query.order_by(User.id.desc()).all()
    names = _teacher_names(db)
    links = {}
    if items:
        for l in (db.query(TeacherStudentLink)
                  .filter(TeacherStudentLink.student_id.in_([u.id for u in items]))
                  .order_by(TeacherStudentLink.id).all()):
            links.setdefault(l.student_id, []).append(l)
    result = []
    for u in items:
        out = to_out(u, names, links.get(u.id, []))
        if user.role == "teacher":
            out.pushplus_token = ""  # 好友令牌由管理员统一维护，不下发给教师
        result.append(out)
    return result


@router.post("", response_model=UserOut)
def create_student(body: StudentCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    username = validate_username(body.username.strip())
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(username=username, password_hash=hash_password(body.password), role="student",
                real_name=body.real_name, student_no=body.student_no, class_name=body.class_name,
                pushplus_token=body.pushplus_token.strip())
    db.add(user)
    db.flush()
    bindings = body.bindings or ([StudentBinding(teacher_id=body.teacher_id)]
                                 if body.teacher_id else [])
    for b in bindings:
        t = db.get(User, b.teacher_id)
        if not t or t.role not in ("teacher", "admin"):
            raise HTTPException(400, "归属教师不存在")
    apply_bindings(db, user, bindings)
    db.commit()
    db.refresh(user)
    publish_to_teachers("student")
    names = _teacher_names(db)
    return to_out(user, names, get_bindings(db, user.id))


@router.put("/{student_id}", response_model=UserOut)
def update_student(student_id: int, body: StudentUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_staff)):
    stu = db.get(User, student_id)
    if not stu or stu.role != "student":
        raise HTTPException(404, "学生不存在")
    if user.role == "teacher":
        if not db.query(TeacherStudentLink)\
                .filter(TeacherStudentLink.teacher_id == user.id,
                        TeacherStudentLink.student_id == stu.id).first():
            raise HTTPException(403, "只能编辑已绑定自己的学生")
        stu.real_name = body.real_name
        stu.student_no = body.student_no
        stu.class_name = body.class_name
        if body.password:
            stu.password_hash = hash_password(body.password)
    else:
        bindings = body.bindings or ([StudentBinding(teacher_id=body.teacher_id)]
                                     if body.teacher_id else [])
        for b in bindings:
            t = db.get(User, b.teacher_id)
            if not t or t.role not in ("teacher", "admin"):
                raise HTTPException(400, "归属教师不存在")
        apply_bindings(db, stu, bindings)
        stu.real_name = body.real_name
        stu.student_no = body.student_no
        stu.class_name = body.class_name
        stu.pushplus_token = body.pushplus_token.strip()
        if body.password:
            stu.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(stu)
    publish_to_teachers("student")
    names = _teacher_names(db)
    return to_out(stu, names, get_bindings(db, stu.id))


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    stu = db.get(User, student_id)
    if not stu or stu.role != "student":
        raise HTTPException(404, "学生不存在")
    # 级联清理该学生的全部关联数据
    db.query(TeacherStudentLink).filter(TeacherStudentLink.student_id == stu.id).delete()
    db.query(Feedback).filter(Feedback.teacher_id == stu.id).delete()
    db.query(CourseFeedback).filter(CourseFeedback.teacher_id == stu.id).delete()
    db.query(CourseFeedback).filter(CourseFeedback.course_id.in_(
        db.query(Course.id).filter(Course.student_id == stu.id))).delete(synchronize_session=False)
    db.query(Course).filter(Course.student_id == stu.id).delete()
    db.query(Feedback).filter(Feedback.submission_id.in_(
        db.query(Submission.id).filter(Submission.student_id == stu.id))).delete(synchronize_session=False)
    db.query(Submission).filter(Submission.student_id == stu.id).delete()
    db.query(AssignmentTarget).filter(AssignmentTarget.student_id == stu.id).delete()
    db.delete(stu)
    db.commit()
    publish_to_teachers("student")
    return {"ok": True}
