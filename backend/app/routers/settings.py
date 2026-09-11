"""应用设置：预置科目、PushPlus 推送配置、消息广播与登录日志（推送配置仅管理员，日志教师/管理员可查）"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import require_admin, require_staff
from ..config import SUBJECTS
from ..database import get_db, SessionLocal
from ..models import AppSetting, LoginLog, User
from ..services import push_service, storage

router = APIRouter(prefix="/api/settings", tags=["settings"])

SUBJECTS_KEY = "preset_subjects"  # AppSetting 中存预置科目（JSON 数组）


class PushPlusConfig(BaseModel):
    """token：发送方 Token（统一发送身份）；my_token：管理员自己的好友令牌（接收用）；
    传入掩码表示未修改；传空表示删除对应配置"""
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
    token_mask: str = ""  # 脱敏后的发送方 Token，不出明文
    my_token_mask: str = ""  # 脱敏后的管理员好友令牌，不出明文


def _mask(v: str) -> str:
    return v[:6] + "****" + v[-4:] if len(v) > 10 else ("****" if v else "")


@router.get("/pushplus", response_model=PushPlusConfigOut)
def get_pushplus(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    sender = push_service.get_sender_token(db) or ""
    return {
        "token_set": bool(sender),
        "my_token_set": bool(user.pushplus_token),
        "token_mask": _mask(sender),
        "my_token_mask": _mask(user.pushplus_token or ""),
    }


@router.put("/pushplus", response_model=PushPlusConfigOut)
def update_pushplus(body: PushPlusConfig, db: Session = Depends(get_db),
                    user: User = Depends(require_admin)):
    """保存推送配置（仅管理员）。传入掩码表示未修改；清空表示删除对应 Token。
    所有消息统一通过该发送方 Token 推送；师生好友令牌由管理员在账号管理中维护。"""
    sender = push_service.get_sender_token(db)
    token = body.token.strip()
    if not token:  # 清空 = 删除发送方 Token
        push_service.save_sender_token(db, "")
    elif not (sender and token == _mask(sender)):  # 掩码未变则不动
        push_service.save_sender_token(db, token)
    my = body.my_token.strip()
    if not my:  # 清空 = 删除管理员好友令牌
        user.pushplus_token = ""
    elif not (user.pushplus_token and my == _mask(user.pushplus_token)):
        user.pushplus_token = my
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


# ---------- 对象存储设置（local/oss 双模式，默认 local） ----------

class StorageConfig(BaseModel):
    """backend：local=本地磁盘（默认），oss=S3 兼容对象存储（阿里云OSS/腾讯COS/MinIO等）；
    secret_key 留空表示保持原密钥不变"""
    backend: str = "local"
    endpoint: str = ""
    bucket: str = ""
    access_key: str = ""
    secret_key: str = ""


@router.get("/storage")
def get_storage(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    cfg = storage.get_config(db)
    return {"backend": cfg["storage_backend"], "endpoint": cfg["oss_endpoint"],
            "bucket": cfg["oss_bucket"], "access_key": cfg["oss_access_key"],
            "secret_set": bool(cfg["oss_secret_key"])}


@router.put("/storage")
def update_storage(body: StorageConfig, db: Session = Depends(get_db),
                   _: User = Depends(require_admin)):
    """保存存储配置（仅管理员）。切到 oss 前建议先点「测试连接」验证；
    切换后新上传走 OSS，历史本地文件仍在磁盘上（如需迁云用迁移脚本）"""
    backend = body.backend if body.backend in ("local", "oss") else "local"
    if backend == "oss" and not all([body.endpoint.strip(), body.bucket.strip(),
                                     body.access_key.strip()]):
        raise HTTPException(400, "启用对象存储需填写 Endpoint、Bucket、AccessKey")
    storage.save_config(db, {"storage_backend": backend, "oss_endpoint": body.endpoint,
                             "oss_bucket": body.bucket, "oss_access_key": body.access_key,
                             "oss_secret_key": body.secret_key})
    return get_storage(db)


@router.post("/storage/test")
def test_storage(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """测试对象存储连通性：上传-读取-删除一个临时对象"""
    if not storage.is_oss(db):
        raise HTTPException(400, "当前为本地存储模式，请先选择对象存储并保存")
    try:
        storage.test_connection(db)
    except Exception as e:
        raise HTTPException(400, f"连接失败：{e}")
    return {"ok": True}


# ---------- 历史数据一键迁移（后台线程执行，进度可查） ----------

_MIGRATE_STATE = {"running": False, "total": 0, "done": 0, "skipped": 0, "failed": 0,
                  "errors": [], "finished": False}
# 本地老文件迁移到 OSS 后不删除，保留为回退副本


def _do_migrate():
    import threading
    state = _MIGRATE_STATE

    def run():
        from pathlib import Path
        from ..config import UPLOAD_DIR
        db = SessionLocal()
        try:
            files = sorted(Path(UPLOAD_DIR).glob("*"))
            files = [p for p in files if p.is_file()]
            state.update(running=True, total=len(files), done=0, skipped=0,
                         failed=0, errors=[], finished=False)
            client, bucket = storage._bucket(db)
            for i, path in enumerate(files, 1):
                key = path.name
                size = path.stat().st_size
                try:
                    head = client.head_object(Bucket=bucket, Key=key)
                    if head["ContentLength"] == size:  # 已存在且一致，跳过（幂等可重跑）
                        state["skipped"] += 1
                        continue
                except client.exceptions.ClientError:
                    pass
                try:
                    client.upload_file(str(path), bucket, key)
                    state["done"] += 1
                except Exception as e:
                    state["failed"] += 1
                    if len(state["errors"]) < 10:
                        state["errors"].append(f"{key}: {e}")
            state["finished"] = True
        except Exception as e:
            state["failed"] += 1
            state["errors"].append(f"迁移中断: {e}")
            state["finished"] = True
        finally:
            state["running"] = False
            db.close()

    threading.Thread(target=run, daemon=True).start()


@router.post("/storage/migrate")
def start_migrate(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """一键迁移：把 uploads 本地历史文件全部上传到 OSS（本地文件保留不删）。
    后台线程执行，接口立即返回；进度通过 GET /settings/storage/migrate 查询"""
    if not storage.is_oss(db):
        raise HTTPException(400, "当前为本地存储模式，请先切换到对象存储再迁移")
    if _MIGRATE_STATE["running"]:
        return {"started": False, **{k: _MIGRATE_STATE[k] for k in
                                     ("total", "done", "skipped", "failed", "finished")}}
    _do_migrate()
    return {"started": True, "total": 0, "done": 0, "skipped": 0, "failed": 0, "finished": False}


@router.get("/storage/migrate")
def migrate_progress(_: User = Depends(require_admin)):
    """查询迁移进度（轮询用）"""
    s = _MIGRATE_STATE
    return {"running": s["running"], "total": s["total"], "done": s["done"],
            "skipped": s["skipped"], "failed": s["failed"],
            "finished": s["finished"], "errors": s["errors"]}


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
