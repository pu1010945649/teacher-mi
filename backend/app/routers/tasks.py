import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, AssignmentTarget, Course, CourseFeedback, Submission, User, WorksheetTask
from ..schemas import (WorksheetTaskCreate, WorksheetTaskEdit, WorksheetTaskOut,
                       WorksheetTaskSettings)
from ..services import task_worker
from ..services.ai_service import get_ai_config
from ..services.events import publish_to_students

router = APIRouter(prefix="/api/worksheet-tasks", tags=["worksheet-tasks"])


def to_out(task: WorksheetTask) -> WorksheetTaskOut:
    out = WorksheetTaskOut.model_validate(task)
    out.student_name = (task.student.real_name or task.student.username) if task.student else ""
    return out


def get_task(db: Session, task_id: int) -> WorksheetTask:
    task = db.get(WorksheetTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.post("", response_model=list[WorksheetTaskOut])
def create_tasks(body: WorksheetTaskCreate, db: Session = Depends(get_db),
                 teacher: User = Depends(require_teacher)):
    student_ids = list(dict.fromkeys(body.student_ids))  # 去重保序
    if not student_ids:
        raise HTTPException(400, "请选择至少一名学生")
    # AI 未配置时直接拦截，避免任务创建后才失败
    get_ai_config(db)
    for sid in student_ids:
        s = db.get(User, sid)
        if not s or s.role != "student":
            raise HTTPException(400, f"学生 {sid} 不存在")

    # 必须选择关注点来源：至少一名学生勾选了课程反馈或作业批改
    if not any(body.course_feedback_ids.values()) and not any(body.submission_ids.values()):
        raise HTTPException(400, "请先选择关注点来源（课程反馈或作业批改记录）")

    # 校验每个学生是否至少有课程反馈或作业记录可供参考
    for sid in student_ids:
        s = db.get(User, sid)
        has_fb = (db.query(CourseFeedback).join(Course, CourseFeedback.course_id == Course.id)
                  .filter(Course.student_id == sid).first() is not None)
        has_sub = db.query(Submission).filter(Submission.student_id == sid).first() is not None
        if not has_fb and not has_sub:
            name = s.real_name or s.username
            raise HTTPException(400, f"学生 {name} 暂无课程反馈和作业记录，无法生成个性化练习，请先在排课/批改中录入反馈")

    tasks = []
    for sid in student_ids:
        ids = body.submission_ids.get(str(sid), [])
        fb_ids = body.course_feedback_ids.get(str(sid), [])
        # 校验来源记录必须属于该学生，不能混入他人信息
        bad_fb = [i for i in fb_ids if not db.query(CourseFeedback).join(
            Course, CourseFeedback.course_id == Course.id).filter(
            CourseFeedback.id == i, Course.student_id == sid).first()]
        if bad_fb:
            raise HTTPException(400, f"课程反馈 {bad_fb} 不属于所选学生，请重新选择")
        bad_sub = [i for i in ids if not db.get(Submission, i) or db.get(Submission, i).student_id != sid]
        if bad_sub:
            raise HTTPException(400, f"作业批改记录 {bad_sub} 不属于所选学生，请重新选择")
        tasks.append(WorksheetTask(
            student_id=sid, created_by=teacher.id,
            submission_ids=json.dumps(ids) if ids else "[]",
            course_feedback_ids=json.dumps(fb_ids) if fb_ids else "[]"))
    db.add_all(tasks)
    db.commit()
    for t in tasks:
        db.refresh(t)
        task_worker.enqueue(t.id)
    return [to_out(t) for t in tasks]


@router.get("", response_model=list[WorksheetTaskOut])
def list_tasks(status: str = "", limit: int = 50, db: Session = Depends(get_db),
               _: User = Depends(require_teacher)):
    q = db.query(WorksheetTask).order_by(WorksheetTask.id.desc())
    if status:
        q = q.filter(WorksheetTask.status == status)
    return [to_out(t) for t in q.limit(min(limit, 200)).all()]


@router.post("/{task_id}/cancel", response_model=WorksheetTaskOut)
def cancel_task(task_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    task = get_task(db, task_id)
    if task.status not in ("pending", "running"):
        raise HTTPException(400, "仅排队中/生成中的任务可取消")
    task.status = "canceled"
    task.finished_at = datetime.now()
    db.commit()
    return to_out(task)


@router.put("/{task_id}", response_model=WorksheetTaskOut)
def edit_task(task_id: int, body: WorksheetTaskEdit, db: Session = Depends(get_db),
              _: User = Depends(require_teacher)):
    """教师编辑生成结果草稿（下发前），并重建 PDF"""
    task = get_task(db, task_id)
    if task.status != "generated":
        raise HTTPException(400, "仅待确认的练习可编辑")
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(400, "标题和内容不能为空")
    task.title, task.content = title, content
    pdf_name = f"{uuid.uuid4().hex}_ws.pdf"
    task_worker.build_pdf(title, content, os.path.join(UPLOAD_DIR, pdf_name))
    if task.pdf_path:
        old = os.path.join(UPLOAD_DIR, task.pdf_path)
        if os.path.exists(old):
            os.remove(old)
    task.pdf_path = pdf_name
    db.commit()
    db.refresh(task)
    return to_out(task)


@router.post("/{task_id}/publish", response_model=WorksheetTaskOut)
def publish_task(task_id: int, db: Session = Depends(get_db),
                 teacher: User = Depends(require_teacher)):
    """确认下发：创建学生作业（PDF 作为附件）并通知学生"""
    task = get_task(db, task_id)
    if task.status != "generated":
        raise HTTPException(400, "仅待确认的练习可下发")
    assignment = Assignment(
        title=f"[个性化练习] {task.title}",
        description=task.content,
        created_by=teacher.id,
        filename=f"{task.title}.pdf",
        file_path=task.pdf_path,
    )
    db.add(assignment)
    db.flush()
    db.add(AssignmentTarget(assignment_id=assignment.id, student_id=task.student_id))
    task.assignment_id = assignment.id
    task.status = "done"
    task.finished_at = datetime.now()
    db.commit()
    publish_to_students("assignment", [task.student_id])
    return to_out(task)


@router.post("/{task_id}/reject", response_model=WorksheetTaskOut)
def reject_task(task_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    """驳回生成结果，不下发"""
    task = get_task(db, task_id)
    if task.status != "generated":
        raise HTTPException(400, "仅待确认的练习可驳回")
    task.status = "rejected"
    task.finished_at = datetime.now()
    db.commit()
    return to_out(task)


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    """删除任务记录及草稿 PDF；已下发的作业不受影响"""
    task = get_task(db, task_id)
    if task.pdf_path and task.status != "done":
        path = os.path.join(UPLOAD_DIR, task.pdf_path)
        if os.path.exists(path):
            os.remove(path)  # 已下发的 PDF 归作业附件，不删
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.get("/settings", response_model=WorksheetTaskSettings)
def get_settings(_: User = Depends(require_teacher)):
    return {"concurrency": task_worker.get_concurrency()}


@router.put("/settings", response_model=WorksheetTaskSettings)
def update_settings(body: WorksheetTaskSettings, _: User = Depends(require_teacher)):
    return {"concurrency": task_worker.set_concurrency(body.concurrency)}
