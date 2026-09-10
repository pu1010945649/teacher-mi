"""公告管理：管理员发布/关闭，教师端与学生端顶部展示栏读取"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Announcement, User

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    content: str


class AnnouncementOut(BaseModel):
    id: int
    content: str
    is_active: bool
    created_by_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


def _creator_name(db: Session, a: Announcement) -> str:
    u = db.get(User, a.created_by) if a.created_by else None
    return (u.real_name or u.username) if u else ""


@router.get("/active", response_model=AnnouncementOut | None)
def get_active(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前启用的公告（所有登录用户可读，顶部展示栏用）"""
    a = db.query(Announcement).filter(Announcement.is_active.is_(True))\
        .order_by(Announcement.id.desc()).first()
    if not a:
        return None
    out = AnnouncementOut.model_validate(a)
    out.created_by_name = _creator_name(db, a)
    return out


@router.get("", response_model=list[AnnouncementOut])
def list_all(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """公告历史列表（管理员）"""
    items = db.query(Announcement).order_by(Announcement.id.desc()).all()
    outs = [AnnouncementOut.model_validate(a) for a in items]
    for a, o in zip(items, outs):
        o.created_by_name = _creator_name(db, a)
    return outs


@router.post("", response_model=AnnouncementOut)
def publish(body: AnnouncementCreate, db: Session = Depends(get_db),
            user: User = Depends(require_admin)):
    """发布公告：新公告生效，历史公告自动停用（展示栏始终只显示最新一条）"""
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "公告内容不能为空")
    if len(content) > 500:
        raise HTTPException(400, "公告内容不能超过 500 字")
    for old in db.query(Announcement).filter(Announcement.is_active.is_(True)).all():
        old.is_active = False
    a = Announcement(content=content, created_by=user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    out = AnnouncementOut.model_validate(a)
    out.created_by_name = _creator_name(db, a)
    return out


@router.put("/{ann_id}/toggle", response_model=AnnouncementOut)
def toggle(ann_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """管理员开启/关闭公告展示"""
    a = db.get(Announcement, ann_id)
    if not a:
        raise HTTPException(404, "公告不存在")
    if not a.is_active:
        for old in db.query(Announcement).filter(
                Announcement.is_active.is_(True), Announcement.id != a.id).all():
            old.is_active = False
    a.is_active = not a.is_active
    db.commit()
    db.refresh(a)
    out = AnnouncementOut.model_validate(a)
    out.created_by_name = _creator_name(db, a)
    return out


@router.delete("/{ann_id}")
def delete(ann_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    a = db.get(Announcement, ann_id)
    if not a:
        raise HTTPException(404, "公告不存在")
    db.delete(a)
    db.commit()
    return {"ok": True}
