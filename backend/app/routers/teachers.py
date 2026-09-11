"""教师账号管理（仅管理员）：教师账号增改、AI 使用权限控制、好友令牌维护、旧数据按科目认领"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin, validate_username
from ..database import get_db
from ..models import (Assignment, Course, CourseFeedback, Feedback, TeacherStudentLink, User,
                      WeeklyReport, WorksheetTask)
from ..schemas import StudentBinding
from .settings import get_subjects

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


class TeacherCreate(BaseModel):
    username: str
    password: str
    real_name: str = ""
    subject: str = ""  # 任教科目（学生绑定时自动读取）
    pushplus_token: str = ""  # 好友令牌（接收推送用，管理员统一维护）


class TeacherUpdate(BaseModel):
    """密码留空表示不修改"""
    real_name: str = ""
    subject: str = ""  # 任教科目
    password: str = ""
    ai_enabled: bool = True
    pushplus_token: str = ""  # 留空表示不修改


class TeacherTransfer(BaseModel):
    """换老师：数据移交的目标教师"""
    target_id: int


class TeacherOut(BaseModel):
    id: int
    username: str
    real_name: str
    subject: str
    ai_enabled: bool
    pushplus_token_mask: str = ""  # 脱敏后的好友令牌，不出明文
    created_at: str


def mask_secret(v: str) -> str:
    return v[:6] + "****" + v[-4:] if len(v) > 10 else ("****" if v else "")


def to_out(t: User) -> TeacherOut:
    return TeacherOut(id=t.id, username=t.username, real_name=t.real_name, subject=t.subject,
                      ai_enabled=t.ai_enabled,
                      pushplus_token_mask=mask_secret(t.pushplus_token or ""),
                      created_at=t.created_at.isoformat())


@router.get("", response_model=list[TeacherOut])
def list_teachers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [to_out(t) for t in db.query(User).filter(User.role == "teacher")
            .order_by(User.id).all()]


@router.post("", response_model=TeacherOut)
def create_teacher(body: TeacherCreate, db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    username = validate_username(body.username.strip())
    if not username or not body.password:
        raise HTTPException(400, "用户名和密码不能为空")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "用户名已存在")
    subject = body.subject.strip()
    subjects = get_subjects(db)
    if subject and subject not in subjects:
        raise HTTPException(400, f"任教科目必须是预置科目之一：{'、'.join(subjects)}")
    t = User(username=username, password_hash=hash_password(body.password),
             role="teacher", real_name=body.real_name.strip(), subject=subject,
             pushplus_token=body.pushplus_token.strip())
    db.add(t)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.put("/{teacher_id}", response_model=TeacherOut)
def update_teacher(teacher_id: int, body: TeacherUpdate, db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    t = db.get(User, teacher_id)
    if not t or t.role != "teacher":
        raise HTTPException(404, "教师不存在")
    subject = body.subject.strip()
    subjects = get_subjects(db)
    if subject and subject not in subjects:
        raise HTTPException(400, f"任教科目必须是预置科目之一：{'、'.join(subjects)}")
    t.real_name = body.real_name.strip()
    t.subject = subject
    t.ai_enabled = body.ai_enabled
    if body.password:  # 留空表示不修改密码
        t.password_hash = hash_password(body.password)
    token = body.pushplus_token.strip()
    if not token:  # 清空 = 删除令牌
        t.pushplus_token = ""
    elif not (t.pushplus_token and token == mask_secret(t.pushplus_token)):  # 掩码未变则不动
        t.pushplus_token = token
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.get("/adopt-preview")
def adopt_preview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """按科目认领前的预览：未归属学生列表、托管课程数据按科目分组、其余托管数据量、可选教师列表"""
    admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
    admin_id = admin.id if admin else 0
    orphans = db.query(User).filter(User.role == "student", User.teacher_id.is_(None))\
        .order_by(User.id).all()

    # 托管课程按科目（课程名）分组
    groups: dict[str, dict] = {}
    for c in db.query(Course).filter(Course.teacher_id == admin_id).all():
        g = groups.setdefault(c.title, {"subject": c.title, "courses": 0, "course_feedbacks": 0})
        g["courses"] += 1
    for fb in db.query(CourseFeedback).filter(CourseFeedback.teacher_id == admin_id).all():
        course = db.get(Course, fb.course_id)
        if course:
            g = groups.setdefault(course.title,
                                  {"subject": course.title, "courses": 0, "course_feedbacks": 0})
            g["course_feedbacks"] += 1

    teachers = db.query(User).filter(User.role == "teacher").order_by(User.id).all()
    return {
        "teachers": [{"id": t.id, "name": t.real_name or t.username,
                      "subject": t.subject} for t in teachers],
        "orphan_students": [{"id": s.id, "name": s.real_name or s.username,
                             "class_name": s.class_name} for s in orphans],
        "subject_groups": sorted(groups.values(), key=lambda g: g["subject"]),
        "others": {
            "assignments": db.query(Assignment).filter(Assignment.created_by == admin_id).count(),
            "feedbacks": db.query(Feedback).filter(Feedback.teacher_id == admin_id).count(),
            "worksheet_tasks": db.query(WorksheetTask).filter(WorksheetTask.created_by == admin_id).count(),
            "weekly_reports": db.query(WeeklyReport).filter(WeeklyReport.created_by == admin_id).count(),
        },
    }


class AdoptBinding(BaseModel):
    """未归属学生的绑定方案"""
    student_id: int
    bindings: list[StudentBinding] = []


class AdoptSubject(BaseModel):
    """某科目的托管数据接收教师"""
    subject: str
    teacher_id: int


class TeacherAdoptIn(BaseModel):
    """按科目认领：学生绑定方案 + 科目数据分配 + 其余托管数据接收教师"""
    students: list[AdoptBinding] = []
    subjects: list[AdoptSubject] = []
    others_teacher_id: int | None = None


@router.post("/adopt")
def adopt_legacy(body: TeacherAdoptIn, db: Session = Depends(get_db),
                 _: User = Depends(require_admin)):
    """旧版升级按科目认领：
    1) 未归属学生按管理员方案绑定多个教师（每个绑定含科目）；
    2) 托管课程与课堂反馈按科目拆分划拨给对应教师；
    3) 其余托管数据（作业/批改/练习/周报）整体划给指定教师。
    适用于单教师旧版升级到多教师后，同一学生的课程数据需按科目隔离的场景。"""
    admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
    admin_id = admin.id if admin else 0

    def valid_teacher(tid: int | None) -> User | None:
        if not tid:
            return None
        t = db.get(User, tid)
        return t if t and t.role in ("teacher", "admin") else None

    for sb in body.students:
        for b in sb.bindings:
            if not valid_teacher(b.teacher_id):
                raise HTTPException(400, "绑定的教师不存在")

    moved_students = 0
    for sb in body.students:
        stu = db.get(User, sb.student_id)
        if not stu or stu.role != "student":
            continue
        db.query(TeacherStudentLink).filter(TeacherStudentLink.student_id == stu.id).delete()
        seen = set()
        for b in sb.bindings:
            key = (b.teacher_id, b.subject.strip())
            if key in seen:
                continue
            seen.add(key)
            db.add(TeacherStudentLink(teacher_id=b.teacher_id, student_id=stu.id,
                                      subject=b.subject.strip()))
        if sb.bindings:
            stu.teacher_id = sb.bindings[0].teacher_id
        else:
            stu.teacher_id = None
        moved_students += 1

    subject_map = {s.subject.strip(): s.teacher_id for s in body.subjects if s.subject.strip()}
    moved = {"courses": 0, "course_feedbacks": 0}
    for c in db.query(Course).filter(Course.teacher_id == admin_id).all():
        target_id = subject_map.get(c.title.strip())
        if target_id:
            moved["course_feedbacks"] += db.query(CourseFeedback)\
                .filter(CourseFeedback.course_id == c.id)\
                .update({CourseFeedback.teacher_id: target_id}, synchronize_session=False)
            c.teacher_id = target_id
            moved["courses"] += 1
            # 排过课即建立绑定；但学生与该教师已有任意绑定时不再追加——
            # 旧课程标题是自由文本（如 统计/统计与概率/一对一），按标题逐条建绑定
            # 会导致同一教师出现多条科目绑定（绑定膨胀），且管理员方案绑定优先
            if not db.query(TeacherStudentLink)\
                    .filter(TeacherStudentLink.teacher_id == target_id,
                            TeacherStudentLink.student_id == c.student_id).first():
                db.add(TeacherStudentLink(teacher_id=target_id, student_id=c.student_id,
                                          subject=c.title.strip()))

    others = valid_teacher(body.others_teacher_id)
    counts = {
        "students": moved_students,
        "courses": moved["courses"],
        "course_feedbacks": moved["course_feedbacks"],
        "assignments": 0, "feedbacks": 0, "worksheet_tasks": 0, "weekly_reports": 0,
    }
    if others:
        counts["assignments"] = db.query(Assignment).filter(Assignment.created_by == admin_id)\
            .update({Assignment.created_by: others.id}, synchronize_session=False)
        counts["feedbacks"] = db.query(Feedback).filter(Feedback.teacher_id == admin_id)\
            .update({Feedback.teacher_id: others.id}, synchronize_session=False)
        counts["worksheet_tasks"] = db.query(WorksheetTask).filter(WorksheetTask.created_by == admin_id)\
            .update({WorksheetTask.created_by: others.id}, synchronize_session=False)
        counts["weekly_reports"] = db.query(WeeklyReport).filter(WeeklyReport.created_by == admin_id)\
            .update({WeeklyReport.created_by: others.id}, synchronize_session=False)
    db.commit()
    return {"ok": True, "moved": counts}


@router.get("/{teacher_id}/transfer-preview")
def transfer_preview(teacher_id: int, db: Session = Depends(get_db),
                     _: User = Depends(require_admin)):
    """移交数据前的预览：统计该教师名下学生与教学数据量，供选择接收教师"""
    t = db.get(User, teacher_id)
    if not t or t.role != "teacher":
        raise HTTPException(404, "教师不存在")
    others = db.query(User).filter(User.role == "teacher", User.id != t.id)\
        .order_by(User.id).all()
    return {
        "teacher_name": t.real_name or t.username,
        "students": db.query(TeacherStudentLink).filter(TeacherStudentLink.teacher_id == t.id).count(),
        "assignments": db.query(Assignment).filter(Assignment.created_by == t.id).count(),
        "courses": db.query(Course).filter(Course.teacher_id == t.id).count(),
        "course_feedbacks": db.query(CourseFeedback).filter(CourseFeedback.teacher_id == t.id).count(),
        "feedbacks": db.query(Feedback).filter(Feedback.teacher_id == t.id).count(),
        "worksheet_tasks": db.query(WorksheetTask).filter(WorksheetTask.created_by == t.id).count(),
        "weekly_reports": db.query(WeeklyReport).filter(WeeklyReport.created_by == t.id).count(),
        "targets": [{"id": o.id, "name": o.real_name or o.username} for o in others],
    }


@router.post("/{teacher_id}/transfer")
def transfer_data(teacher_id: int, body: TeacherTransfer, db: Session = Depends(get_db),
                  _: User = Depends(require_admin)):
    """换老师：把该教师名下的学生和全部教学数据整体移交给另一位教师（原账号不受影响，可随后删除）"""
    t = db.get(User, teacher_id)
    if not t or t.role != "teacher":
        raise HTTPException(404, "教师不存在")
    target = db.get(User, body.target_id)
    if not target or target.role != "teacher":
        raise HTTPException(400, "接收教师不存在")
    if target.id == t.id:
        raise HTTPException(400, "不能移交给本人")

    moved = {
        "students": db.query(TeacherStudentLink).filter(TeacherStudentLink.teacher_id == t.id)
            .update({TeacherStudentLink.teacher_id: target.id}, synchronize_session=False),
        "assignments": db.query(Assignment).filter(Assignment.created_by == t.id)
            .update({Assignment.created_by: target.id}, synchronize_session=False),
        "courses": db.query(Course).filter(Course.teacher_id == t.id)
            .update({Course.teacher_id: target.id}, synchronize_session=False),
        "course_feedbacks": db.query(CourseFeedback).filter(CourseFeedback.teacher_id == t.id)
            .update({CourseFeedback.teacher_id: target.id}, synchronize_session=False),
        "feedbacks": db.query(Feedback).filter(Feedback.teacher_id == t.id)
            .update({Feedback.teacher_id: target.id}, synchronize_session=False),
        "worksheet_tasks": db.query(WorksheetTask).filter(WorksheetTask.created_by == t.id)
            .update({WorksheetTask.created_by: target.id}, synchronize_session=False),
        "weekly_reports": db.query(WeeklyReport).filter(WeeklyReport.created_by == t.id)
            .update({WeeklyReport.created_by: target.id}, synchronize_session=False),
    }
    # 主归属同步：原主教师换成接收教师
    db.query(User).filter(User.role == "student", User.teacher_id == t.id)\
        .update({User.teacher_id: target.id}, synchronize_session=False)
    db.commit()
    return {"ok": True, "moved": moved, "target_name": target.real_name or target.username}


@router.delete("/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    """教师离职：删除账号，但保留学生与其学习数据以便后续关联新教师。
    - 名下学生解除归属（teacher_id 置空），可在「教师账号 → 认领旧数据」或「学生管理」中重新分配
    - 教学数据（作业/课程/反馈/批改/练习/周报）移交管理员托管，同样可通过认领划归新教师
    - 学生的提交、批改反馈等学习记录全部保留，不受教师离职影响"""
    t = db.get(User, teacher_id)
    if not t or t.role != "teacher":
        raise HTTPException(404, "教师不存在")
    admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()
    if not admin:
        raise HTTPException(400, "系统缺少管理员账号，无法托管数据")

    # 删除该教师的全部绑定；仍有其他教师绑定的学生保留，仅重置其主归属
    links = db.query(TeacherStudentLink).filter(TeacherStudentLink.teacher_id == t.id).all()
    affected = {l.student_id for l in links}
    for l in links:
        db.delete(l)
    for sid in affected:
        rest = db.query(TeacherStudentLink).filter(TeacherStudentLink.student_id == sid)\
            .order_by(TeacherStudentLink.id).first()
        stu = db.get(User, sid)
        if stu:
            stu.teacher_id = rest.teacher_id if rest else None
    moved = {
        "students": len(affected),
        "assignments": db.query(Assignment).filter(Assignment.created_by == t.id)
            .update({Assignment.created_by: admin.id}, synchronize_session=False),
        "courses": db.query(Course).filter(Course.teacher_id == t.id)
            .update({Course.teacher_id: admin.id}, synchronize_session=False),
        "course_feedbacks": db.query(CourseFeedback).filter(CourseFeedback.teacher_id == t.id)
            .update({CourseFeedback.teacher_id: admin.id}, synchronize_session=False),
        "feedbacks": db.query(Feedback).filter(Feedback.teacher_id == t.id)
            .update({Feedback.teacher_id: admin.id}, synchronize_session=False),
        "worksheet_tasks": db.query(WorksheetTask).filter(WorksheetTask.created_by == t.id)
            .update({WorksheetTask.created_by: admin.id}, synchronize_session=False),
        "weekly_reports": db.query(WeeklyReport).filter(WeeklyReport.created_by == t.id)
            .update({WeeklyReport.created_by: admin.id}, synchronize_session=False),
    }
    db.delete(t)
    db.commit()
    return {"ok": True, "moved": moved}
