import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import ensure_ai_allowed, get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, Course, CourseFeedback, Submission, TeacherStudentLink, User, \
    WeeklyReport
from ..schemas import WeeklyReportEdit, WeeklyReportGenerate, WeeklyReportOut
from ..services import storage
from ..services.ai_service import chat, parse_json_object
from ..services.events import publish_to_students

router = APIRouter(prefix="/api/weekly-reports", tags=["weekly-reports"])

FILE_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

PROMPT = (
    "你是一位经验丰富的教师，请根据学生本周的学习记录（作业提交与批改情况、每节课的教师反馈与学生回复），"
    "撰写一份发给家长/学生的学习周报。\n"
    '以 JSON 返回：{{"title": "周报标题", "content": "周报正文"}}。\n'
    "content 为纯文本，用「一、二、三」分节，建议包含：本周学习内容概览、作业完成情况、"
    "课堂表现与进步亮点、存在的不足、下周学习建议。语气亲切鼓励、客观具体，500 字以内。\n"
    "只返回 JSON，不要其他内容。\n\n学生姓名：{name}\n周起始：{week_start}\n\n学习记录：\n{records}"
)


def to_out(r: WeeklyReport, db: Session | None = None) -> WeeklyReportOut:
    out = WeeklyReportOut.model_validate(r)
    out.student_name = (r.student.real_name or r.student.username) if r.student else ""
    # 推送老师与科目（教师端绑定科目 / 学生端取绑定该发布老师的科目）
    creator = r.created_by and db.get(User, r.created_by) if db else None
    out.teacher_name = (creator.real_name or creator.username) if creator else ""
    if db and creator:
        link = (db.query(TeacherStudentLink)
                .filter(TeacherStudentLink.teacher_id == r.created_by,
                        TeacherStudentLink.student_id == r.student_id).first())
        out.subject = (link.subject or "").strip() if link else ""
    return out


def get_report(db: Session, report_id: int, teacher: User | None = None) -> WeeklyReport:
    r = db.get(WeeklyReport, report_id)
    if not r:
        raise HTTPException(404, "周报不存在")
    if teacher is not None and r.created_by != teacher.id:
        raise HTTPException(403, "无权操作他人创建的周报")
    return r


def collect_week_records(db: Session, student: User, week_start: str,
                         teacher: User) -> str:
    """汇集学生一周内该教师的数据：课程、作业批改与课程反馈。
    隔离规则：作业仅取该教师下发的；课程仅取该教师排的；绑定科目非空时再按科目过滤"""
    start = datetime.strptime(week_start, "%Y-%m-%d")
    end = start + timedelta(days=7)
    lines = []

    # 绑定科目（师生绑定按科目隔离）：非空时仅取该科目的课程与作业
    link = (db.query(TeacherStudentLink)
            .filter(TeacherStudentLink.teacher_id == teacher.id,
                    TeacherStudentLink.student_id == student.id).first())
    subject = (link.subject or "").strip() if link else ""

    courses = (db.query(Course)
               .filter(Course.student_id == student.id,
                       Course.teacher_id == teacher.id,
                       Course.start_time >= start, Course.start_time < end)
               .order_by(Course.start_time).all())
    if subject:
        courses = [c for c in courses if (c.title or "").strip() == subject]
    course_ids = [c.id for c in courses]
    fbs = (db.query(CourseFeedback)
           .filter(CourseFeedback.course_id.in_(course_ids))
           .all()) if course_ids else []
    fb_by_course = {}
    for fb in fbs:
        fb_by_course.setdefault(fb.course_id, []).append(fb)
    for c in courses:
        lines.append(f"- 课程《{c.title}》{c.start_time.strftime('%m-%d %H:%M')}")
        for fb in fb_by_course.get(c.id, []):
            reply = f"；学生回复：{fb.reply}" if fb.reply else ""
            lines.append(f"  教师反馈：{fb.content}{reply}")

    subs = (db.query(Submission)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .filter(Submission.student_id == student.id,
                    Assignment.created_by == teacher.id,
                    Submission.submitted_at >= start, Submission.submitted_at < end)
            .order_by(Submission.submitted_at).all())
    if subject:
        subs = [s for s in subs
                if (s.assignment.subject or "").strip() == subject]
    for s in subs:
        fb = s.feedback
        score = f"得分 {fb.score:g}" if fb and fb.score is not None else "未批改"
        comment = f"；教师评语：{fb.content}" if fb and fb.content else ""
        lines.append(f"- 作业《{s.assignment.title if s.assignment else '已删'}》"
                     f"第 {s.attempt} 次提交，{score}{comment}")

    return "\n".join(lines)


@router.get("", response_model=list[WeeklyReportOut])
def list_reports(student_id: int | None = None, status: str = "",
                 db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    q = db.query(WeeklyReport).filter(WeeklyReport.created_by == user.id)\
        .order_by(WeeklyReport.id.desc())
    if student_id:
        q = q.filter(WeeklyReport.student_id == student_id)
    if status:
        q = q.filter(WeeklyReport.status == status)
    return [to_out(r, db) for r in q.limit(200).all()]


@router.post("/generate", response_model=WeeklyReportOut)
async def generate_report(body: WeeklyReportGenerate, db: Session = Depends(get_db),
                          teacher: User = Depends(require_teacher)):
    """汇集学生一周的学习记录，AI 生成周报草稿（同周已有草稿则重新生成覆盖）"""
    ensure_ai_allowed(db, teacher)
    student = db.get(User, body.student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    if not db.query(TeacherStudentLink)\
            .filter(TeacherStudentLink.teacher_id == teacher.id,
                    TeacherStudentLink.student_id == student.id).first():
        raise HTTPException(403, "只能为已绑定自己的学生生成周报")
    try:
        datetime.strptime(body.week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "week_start 需为 YYYY-MM-DD 格式的周一日期")

    existing = (db.query(WeeklyReport)
                .filter(WeeklyReport.student_id == student.id,
                        WeeklyReport.created_by == teacher.id,
                        WeeklyReport.week_start == body.week_start)
                .first())
    if existing and existing.status == "sent":
        raise HTTPException(400, "该周周报已发送，如需修改请删除后重新生成")

    records = collect_week_records(db, student, body.week_start, teacher)
    if not records:
        raise HTTPException(400, f"{student.real_name or student.username} 本周暂无课程反馈和作业记录，请先在排课/批改中录入反馈")
    prompt = PROMPT.format(name=student.real_name or student.username,
                           week_start=body.week_start, records=records)
    result = await chat(db, [{"role": "user", "content": prompt}], user=teacher)
    data = parse_json_object(result)
    title = str(data.get("title") or f"{student.real_name or student.username} 学习周报")
    content = str(data.get("content") or result).strip()

    if existing:
        existing.title, existing.content = title, content
        existing.created_at = datetime.now()
        r = existing
    else:
        r = WeeklyReport(student_id=student.id, created_by=teacher.id,
                         week_start=body.week_start, title=title, content=content)
        db.add(r)
    db.commit()
    db.refresh(r)
    return to_out(r, db)


@router.post("/upload", response_model=WeeklyReportOut)
async def upload_report(student_id: int = Form(...), week_start: str = Form(...),
                        title: str = Form(""), file: UploadFile = File(...),
                        db: Session = Depends(get_db),
                        teacher: User = Depends(require_teacher)):
    """教师手工上传周报文件（PDF/Word/Excel/图片），生成草稿后发送给学生"""
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(400, "学生不存在")
    if not db.query(TeacherStudentLink)\
            .filter(TeacherStudentLink.teacher_id == teacher.id,
                    TeacherStudentLink.student_id == student.id).first():
        raise HTTPException(403, "只能为已绑定自己的学生上传周报")
    try:
        datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "week_start 需为 YYYY-MM-DD 格式的周一日期")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in FILE_EXT:
        raise HTTPException(400, "仅支持 pdf/doc/docx/xls/xlsx/png/jpg/jpeg 格式")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小不能超过 20MB")

    existing = (db.query(WeeklyReport)
                .filter(WeeklyReport.student_id == student.id,
                        WeeklyReport.created_by == teacher.id,
                        WeeklyReport.week_start == week_start)
                .first())
    if existing and existing.status == "sent":
        raise HTTPException(400, "该周周报已发送，如需重发请删除后重新上传")

    # 覆盖上传：先删旧文件
    if existing and existing.file_path:
        storage.delete(db, existing.file_path)
    safe_name = f"{uuid.uuid4().hex}_weekly{ext}"
    storage.save(db, safe_name, data)

    name = student.real_name or student.username
    title = title.strip() or f"{name} 学习周报"
    if existing:
        existing.title, existing.file_name, existing.file_path = title, file.filename, safe_name
        existing.created_at = datetime.now()
        r = existing
    else:
        r = WeeklyReport(student_id=student.id, created_by=teacher.id,
                         week_start=week_start, title=title, content="",
                         file_name=file.filename, file_path=safe_name)
        db.add(r)
    db.commit()
    db.refresh(r)
    return to_out(r, db)


@router.get("/{report_id}/file")
def report_file(report_id: int, download: int = 0,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """周报文件在线查看/下载：仅报告所属学生、创建教师与管理员"""
    r = get_report(db, report_id)
    if user.role == "student" and r.student_id != user.id:
        raise HTTPException(403, "无权查看他人周报")
    if user.role == "teacher" and r.created_by != user.id:
        raise HTTPException(403, "无权查看他人创建的周报")
    if not r.file_path:
        raise HTTPException(404, "该周报没有文件")
    if storage.is_oss(db):
        url = storage.signed_url(db, r.file_path, ttl=600,
                                 download_name=r.file_name if download else "")
        if url:
            return RedirectResponse(url)
        raise HTTPException(500, "对象存储未配置完整，请在后台设置中检查")
    path = os.path.join(UPLOAD_DIR, r.file_path)
    if not os.path.exists(path):
        raise HTTPException(404, "文件已丢失")
    if download:
        return FileResponse(path, filename=r.file_name)
    import mimetypes
    mime = mimetypes.guess_type(r.file_name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=mime)  # 无 filename 时浏览器内联预览


@router.put("/{report_id}", response_model=WeeklyReportOut)
def edit_report(report_id: int, body: WeeklyReportEdit, db: Session = Depends(get_db),
                teacher: User = Depends(require_teacher)):
    """教师编辑周报草稿"""
    r = get_report(db, report_id, teacher)
    if r.status == "sent":
        raise HTTPException(400, "已发送的周报不能编辑")
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(400, "标题和内容不能为空")
    r.title, r.content = title, content
    db.commit()
    db.refresh(r)
    return to_out(r, db)


@router.post("/{report_id}/send", response_model=WeeklyReportOut)
def send_report(report_id: int, db: Session = Depends(get_db),
                teacher: User = Depends(require_teacher)):
    """教师确认发送，学生端消息中心可见"""
    r = get_report(db, report_id, teacher)
    if r.status == "sent":
        raise HTTPException(400, "该周报已发送")
    r.status = "sent"
    r.sent_at = datetime.now()
    db.commit()
    db.refresh(r)
    publish_to_students("message", [r.student_id])
    return to_out(r, db)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db),
                  teacher: User = Depends(require_teacher)):
    r = get_report(db, report_id, teacher)
    storage.delete(db, r.file_path)
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.get("/my", response_model=list[WeeklyReportOut])
def my_reports(db: Session = Depends(get_db), user: User = Depends(require_student)):
    """学生端消息中心：已发送给我的学习周报"""
    rows = (db.query(WeeklyReport)
            .filter(WeeklyReport.student_id == user.id, WeeklyReport.status == "sent")
            .order_by(WeeklyReport.sent_at.desc()).limit(100).all())
    return [to_out(r, db) for r in rows]
