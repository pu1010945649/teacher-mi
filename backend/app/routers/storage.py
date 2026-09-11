"""存储管理：教师可查看自己名下文件的存储统计；孤儿文件清理仅管理员"""
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_staff
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, Feedback, Submission, User, WeeklyReport, WorksheetTask

router = APIRouter(prefix="/api/storage", tags=["storage"])

# 各表文件字段与业务分类的映射（凡存文件名的字段都要登记，否则会被误判为孤儿文件）
_FILE_FIELDS = [
    (Assignment, "file_path", "作业附件"),
    (Assignment, "video_path", "讲解视频"),
    (Submission, "file_path", "学生提交"),
    (Feedback, "file_path", "作业反馈附件"),
    (WeeklyReport, "file_path", "学习周报"),
    (WorksheetTask, "pdf_path", "AI练习PDF"),
]


def _scan_dir():
    """扫描 uploads 目录，返回 {文件名: 字节数}"""
    files = {}
    if os.path.isdir(UPLOAD_DIR):
        with os.scandir(UPLOAD_DIR) as it:
            for entry in it:
                if entry.is_file():
                    try:
                        files[entry.name] = entry.stat().st_size
                    except OSError:
                        pass
    return files


def _referenced_files(db: Session, teacher: User | None = None):
    """收集数据库中被引用的文件名（按分类）；teacher 传入时只统计其名下数据"""
    referenced = {}  # name -> 分类
    for model, field, label in _FILE_FIELDS:
        q = db.query(getattr(model, field)).filter(getattr(model, field) != "")
        if teacher is not None:
            if model is Assignment:
                q = q.filter(Assignment.created_by == teacher.id)
            elif model is Submission:
                q = q.join(Assignment, Submission.assignment_id == Assignment.id)\
                    .filter(Assignment.created_by == teacher.id)
            elif model is Feedback:
                q = q.join(Submission, Feedback.submission_id == Submission.id)\
                    .join(Assignment, Submission.assignment_id == Assignment.id)\
                    .filter(Assignment.created_by == teacher.id)
            elif model is WeeklyReport:
                q = q.filter(WeeklyReport.created_by == teacher.id)
            elif model is WorksheetTask:
                q = q.filter(WorksheetTask.created_by == teacher.id)
        for (name,) in q.all():
            referenced[os.path.basename(name)] = label
    return referenced


@router.get("/stats")
def storage_stats(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """存储使用统计：按业务分类统计本人名下文件占用；管理员额外返回孤儿文件与全量数据"""
    files = _scan_dir()
    mine_only = user.role != "admin"
    referenced = _referenced_files(db, user if mine_only else None)

    categories: dict[str, dict] = {}
    for _, _, label in _FILE_FIELDS:
        categories[label] = {"count": 0, "size": 0}
    my_size = 0
    orphans = []
    matched = set()
    for name, size in files.items():
        label = referenced.get(name)
        if label:
            matched.add(name)
            categories[label]["count"] += 1
            categories[label]["size"] += size
            my_size += size
        elif not mine_only:
            orphans.append({"name": name, "size": size})

    if mine_only:
        return {
            "total_size": my_size,  # 名下文件总占用
            "total_count": len(matched),
            "categories": categories,
            "orphans": [],
            "orphan_size": 0,
            "missing_count": 0,
            "mine_only": True,
        }

    missing = [name for name in referenced if name not in files]
    return {
        "total_size": sum(files.values()),
        "total_count": len(files),
        "categories": categories,
        "orphans": sorted(orphans, key=lambda x: -x["size"]),
        "orphan_size": sum(o["size"] for o in orphans),
        "missing_count": len(missing),  # 数据库有记录但文件已丢失（仅提示，不处理）
        "mine_only": False,
    }


@router.post("/cleanup")
def cleanup_orphans(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """清理孤儿文件（仅管理员）：删除数据库中没有任何记录引用的上传文件（不影响正常业务数据）"""
    files = _scan_dir()
    referenced = _referenced_files(db)

    removed_names, freed = [], 0
    for name, size in files.items():
        if name in referenced:
            continue
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
            removed_names.append(name)
            freed += size
        except OSError:
            pass
    return {"removed": len(removed_names), "freed": freed, "removed_names": removed_names}
