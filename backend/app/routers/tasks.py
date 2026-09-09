import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import get_db
from ..models import User, WorksheetTask
from ..schemas import WorksheetTaskCreate, WorksheetTaskOut, WorksheetTaskSettings
from ..services import task_worker

router = APIRouter(prefix="/api/worksheet-tasks", tags=["worksheet-tasks"])


def to_out(task: WorksheetTask) -> WorksheetTaskOut:
    out = WorksheetTaskOut.model_validate(task)
    out.student_name = (task.student.real_name or task.student.username) if task.student else ""
    return out


@router.post("", response_model=list[WorksheetTaskOut])
def create_tasks(body: WorksheetTaskCreate, db: Session = Depends(get_db),
                 teacher: User = Depends(require_teacher)):
    student_ids = list(dict.fromkeys(body.student_ids))  # 去重保序
    if not student_ids:
        raise HTTPException(400, "请选择至少一名学生")
    for sid in student_ids:
        s = db.get(User, sid)
        if not s or s.role != "student":
            raise HTTPException(400, f"学生 {sid} 不存在")

    tasks = []
    for sid in student_ids:
        ids = body.submission_ids.get(str(sid), [])
        tasks.append(WorksheetTask(
            student_id=sid, created_by=teacher.id, focus=body.focus,
            submission_ids=json.dumps(ids) if ids else "[]"))
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
    task = db.get(WorksheetTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status != "pending":
        raise HTTPException(400, "仅排队中的任务可取消")
    task.status = "canceled"
    task.finished_at = __import__("datetime").datetime.now()
    db.commit()
    return to_out(task)


@router.get("/settings", response_model=WorksheetTaskSettings)
def get_settings(_: User = Depends(require_teacher)):
    return {"concurrency": task_worker.get_concurrency()}


@router.put("/settings", response_model=WorksheetTaskSettings)
def update_settings(body: WorksheetTaskSettings, _: User = Depends(require_teacher)):
    return {"concurrency": task_worker.set_concurrency(body.concurrency)}
