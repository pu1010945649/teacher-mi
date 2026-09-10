"""应用设置：预置科目、PushPlus 推送配置、消息广播与登录日志（推送配置仅管理员，日志教师/管理员可查）"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_admin, require_staff
from ..config import SUBJECTS
from ..database import get_db
from ..models import AppSetting, LoginLog, User
from ..services import push_service

router = APIRouter(prefix="/api/settings", tags=["settings"])

SUBJECTS_KEY = "preset_subjects"  # AppSetting 中存预置科目（JSON 数组）


class PushPlusConfig(BaseModel):
    """token：发送方 Token（统一发送身份）；my_token：管理员自己的好友令牌（接收用）"""
    token: str = ""
    my_token: str = ""


class SubjectsConfig(BaseModel):
    subjects: list[str] = []


class BroadcastForm(BaseModel):
    audience: str = "all"  # all / teachers / students
    title: str
    content: str


def get_subjects(db: Session) -> list[str]:
    """预置科目：管理员配置存于 AppSetting，未配置时使用 config 默认值"""
    row = db.query(AppSetting).filter(AppSetting.key == SUBJECTS_KEY).first()
    if not row or not row.value.strip():
        return list(SUBJECTS)
    try:
        items = json.loads(row.value)
        return [s.strip() for s in items if isinstance(s, str) and s.strip()] or list(SUBJECTS)
    except Exception:
        return list(SUBJECTS)


@router.get("/subjects")
def read_subjects(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """预置科目列表（教师任教科目只能从中选择）"""
    return get_subjects(db)


@router.put("/subjects")
def update_subjects(body: SubjectsConfig, db: Session = Depends(get_db),
                    _: User = Depends(require_admin)):
    """保存预置科目（仅管理员），教师表单与学生绑定均从此读取"""
    items: list[str] = []
    for s in body.subjects:
        s = s.strip()
        if s and s not in items:
            items.append(s)
    if not items:
        raise HTTPException(400, "预置科目不能为空")
    value = json.dumps(items, ensure_ascii=False)
    row = db.query(AppSetting).filter(AppSetting.key == SUBJECTS_KEY).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=SUBJECTS_KEY, value=value))
    db.commit()
    return items


class PushPlusConfigOut(BaseModel):
    token_set: bool = False
    my_token_set: bool = False


@router.get("/pushplus", response_model=PushPlusConfigOut)
def get_pushplus(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return {
        "token_set": bool(push_service.get_sender_token(db)),
        "my_token_set": bool(user.pushplus_token),
    }


@router.put("/pushplus", response_model=PushPlusConfigOut)
def update_pushplus(body: PushPlusConfig, db: Session = Depends(get_db),
                    user: User = Depends(require_admin)):
    """保存推送配置（仅管理员）；两个 Token 留空均表示保持原值不变。
    所有消息统一通过该发送方 Token 推送；师生好友令牌由管理员在账号管理中维护。"""
    if body.token.strip():
        push_service.save_sender_token(db, body.token.strip())
    if body.my_token.strip():
        user.pushplus_token = body.my_token.strip()
        db.commit()
    return get_pushplus(db, user)


@router.post("/pushplus/test")
async def test_pushplus(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """发送测试消息到管理员自己的好友令牌"""
    if not push_service.get_sender_token(db):
        raise HTTPException(400, "请先保存发送方 Token")
    if not user.pushplus_token:
        raise HTTPException(400, "请先保存你的好友令牌（在 pushplus.plus 一对一推送中获取）")
    ok = await push_service.send_to_user(
        db, user, "Teacher-Mi 测试消息", "这是一条测试推送，收到说明 PushPlus 配置成功。")
    if not ok:
        raise HTTPException(400, "推送失败，请检查发送方 Token 与好友令牌是否正确、是否已建立好友关系")
    return {"ok": True}


@router.post("/broadcast")
async def broadcast(body: BroadcastForm, db: Session = Depends(get_db),
                    _: User = Depends(require_admin)):
    """管理员广播：全员或按角色推送（消息推送功能统一收在后台设置）"""
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(400, "标题和内容不能为空")
    if not push_service.get_sender_token(db):
        raise HTTPException(400, "请先在上方配置发送方 Token")
    if body.audience == "teachers":
        users = db.query(User).filter(User.role == "teacher").all()
    elif body.audience == "students":
        users = db.query(User).filter(User.role == "student").all()
    else:
        users = db.query(User).filter(User.role.in_(["teacher", "student"])).all()
    if not users:
        raise HTTPException(400, "没有可推送的接收人")
    sent, errors = await push_service.send_to_users_detail(
        db, users, f"【管理员通知】{title}", content)
    if not sent:
        detail = "；".join(dict.fromkeys(errors)) if errors else "推送全部失败"
        raise HTTPException(400, f"推送失败：{detail}")
    return {"ok": True, "count": len(sent), "sent_names": sent,
            "errors": errors}


@router.get("/login-logs")
def login_logs(page: int = 1, size: int = 20, db: Session = Depends(get_db),
               _: object = Depends(require_admin)):
    """登录日志分页列表（新记录在前）。含全部用户登录 IP，仅管理员可查"""
    page, size = max(1, page), min(100, max(1, size))
    q = db.query(LoginLog).order_by(LoginLog.created_at.desc(), LoginLog.id.desc())
    total = q.count()
    items = q.offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "items": [{
            "id": i.id, "username": i.username, "role": i.role, "ip": i.ip,
            "success": i.success, "created_at": i.created_at.isoformat(),
        } for i in items],
    }
