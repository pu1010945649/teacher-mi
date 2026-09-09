import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Assignment, Feedback, Submission, User

router = APIRouter(prefix="/api/storage", tags=["storage"])

# 各表文件字段与业务分类的映射
_FILE_FIELDS = [
    (Assignment, "file_path", "作业附件"),
    (Submission, "file_path", "学生提交"),
    (Feedback, "file_path", "作业反馈附件"),
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


def _referenced_files(db: Session):
    """收集数据库中所有被引用的文件名（按分类）"""
    referenced = {}  # name -> 分类
    for model, field, label in _FILE_FIELDS:
        for (name,) in db.query(getattr(model, field)).filter(getattr(model, field) != "").all():
            referenced[os.path.basename(name)] = label
    return referenced


@router.get("/stats")
def storage_stats(db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    """存储使用统计：按业务分类统计占用空间，并列出数据库未引用的孤儿文件"""
    files = _scan_dir()
    referenced = _referenced_files(db)

    categories: dict[str, dict] = {}
    for _, _, label in _FILE_FIELDS:
        categories[label] = {"count": 0, "size": 0}
    orphans = []
    for name, size in files.items():
        label = referenced.get(name)
        if label:
            categories[label]["count"] += 1
            categories[label]["size"] += size
        else:
            orphans.append({"name": name, "size": size})

    missing = [name for name in referenced if name not in files]
    return {
        "total_size": sum(files.values()),
        "total_count": len(files),
        "categories": categories,
        "orphans": sorted(orphans, key=lambda x: -x["size"]),
        "orphan_size": sum(o["size"] for o in orphans),
        "missing_count": len(missing),  # 数据库有记录但文件已丢失（仅提示，不处理）
    }


@router.post("/cleanup")
def cleanup_orphans(db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    """清理孤儿文件：删除数据库中没有任何记录引用的上传文件（不影响正常业务数据）"""
    files = _scan_dir()
    referenced = _referenced_files(db)

    removed, freed = 0, 0
    for name, size in files.items():
        if name in referenced:
            continue
        try:
            os.remove(os.path.join(UPLOAD_DIR, name))
            removed += 1
            freed += size
        except OSError:
            pass
    return {"removed": removed, "freed": freed}
