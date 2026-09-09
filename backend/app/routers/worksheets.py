import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Submission, User, Worksheet
from ..schemas import WorksheetGenerate, WorksheetOut
from ..services.ai_service import chat, parse_json_object
from ..services.pdf_service import build_pdf

router = APIRouter(prefix="/api/worksheets", tags=["worksheets"])

PROMPT = (
    "你是一位经验丰富的教师。请根据学生的学习记录，针对其薄弱环节生成一份个性化练习作业。\n"
    '以 JSON 返回：{{"title": "练习标题", "content": "练习内容"}}。\n'
    "content 为纯文本：用「一、二、三」分节（如 一、选择题 / 二、填空题 / 三、解答题），"
    "每题单独一行并用数字编号，共 6-10 题，难度围绕学生掌握较差的知识点。\n"
    "只返回 JSON，不要其他内容。\n\n学生姓名：{name}\n教师补充关注点：{focus}\n\n学习记录：\n{records}"
)


def to_out(item: Worksheet, student: User | None) -> WorksheetOut:
    out = WorksheetOut.model_validate(item)
    out.student_name = (student.real_name or student.username) if student else ""
    out.has_pdf = bool(item.pdf_path)
    return out


def collect_records(db: Session, student: User) -> str:
    subs = db.query(Submission).filter(Submission.student_id == student.id).all()
    lines = []
    for sub in subs:
        fb = sub.feedback
        score = fb.score if fb else "未批改"
        comment = fb.content if fb else ""
        excerpt = (sub.content or "")[:150]
        lines.append(f"- 作业《{sub.assignment.title}》得分：{score}；教师评语：{comment}；提交摘要：{excerpt}")
    return "\n".join(lines) if lines else "（暂无记录）"


@router.post("/generate", response_model=WorksheetOut)
async def generate(body: WorksheetGenerate, db: Session = Depends(get_db),
                   teacher: User = Depends(require_teacher)):
    student = db.get(User, body.student_id)
    if not student or student.role != "student":
        raise HTTPException(404, "学生不存在")
    if not collect_records(db, student).strip():
        raise HTTPException(400, "该学生暂无学习记录，无法生成个性化练习")

    prompt = PROMPT.format(name=student.real_name or student.username,
                           focus=body.focus or "无",
                           records=collect_records(db, student))
    result = await chat(db, [{"role": "user", "content": prompt}])
    data = parse_json_object(result)
    title = str(data.get("title") or f"{student.real_name or student.username} 个性化练习")
    content = str(data.get("content") or result).strip()

    pdf_name = f"{uuid.uuid4().hex}_ws.pdf"
    build_pdf(title, content, os.path.join(UPLOAD_DIR, pdf_name))
    ws = Worksheet(student_id=student.id, created_by=teacher.id, title=title,
                   content=content, pdf_path=pdf_name)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return to_out(ws, student)


@router.get("", response_model=list[WorksheetOut])
def list_worksheets(student_id: int = 0, db: Session = Depends(get_db),
                    _: User = Depends(require_teacher)):
    query = db.query(Worksheet).order_by(Worksheet.id.desc())
    items = query.filter(Worksheet.student_id == student_id).all() if student_id else query.all()
    students = {s.id: s for s in db.query(User).filter(User.role == "student")}
    return [to_out(item, students.get(item.student_id)) for item in items]


@router.get("/my", response_model=list[WorksheetOut])
def my_worksheets(db: Session = Depends(get_db), student: User = Depends(require_student)):
    items = db.query(Worksheet).filter(Worksheet.student_id == student.id).all()
    return [to_out(item, student) for item in items]


@router.get("/{worksheet_id}/pdf")
def download_pdf(worksheet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ws = db.get(Worksheet, worksheet_id)
    if not ws:
        raise HTTPException(404, "练习不存在")
    if user.role == "student" and ws.student_id != user.id:
        raise HTTPException(403, "无权下载他人练习")
    path = os.path.join(UPLOAD_DIR, ws.pdf_path)
    if not ws.pdf_path or not os.path.exists(path):
        raise HTTPException(404, "PDF 文件已丢失")
    return FileResponse(path, filename=f"practice_{ws.id}.pdf")
