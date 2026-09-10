from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import LoginLog, User
from ..schemas import ChangePassword, LoginRequest, TokenResponse
from ..services.crypto_service import decrypt_payload, get_public_key

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ===== 登录防破解参数 =====
FAIL_WINDOW_MIN = 10       # 失败统计窗口（分钟）
USERNAME_MAX_FAILS = 5     # 同一账号窗口内最大失败次数（防止单账号密码爆破）
IP_MAX_FAILS = 20          # 同一 IP 窗口内最大失败次数（防止撞库遍历账号）
LOCK_MINUTES = 15          # 触发后的锁定时长（自最后一次失败起算）
MIN_PASSWORD_LEN = 6       # 新密码最小长度


def client_ip(request: Request) -> str:
    """取真实客户端 IP（反代/容器场景优先 X-Forwarded-For）"""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _reject_locked(db: Session, username: str, ip: str):
    """防破解检查：账号/IP 近期失败过多则拒绝登录，返回剩余锁定分钟数"""
    now = datetime.now()
    since = now - timedelta(minutes=FAIL_WINDOW_MIN)
    checks = [(LoginLog.username, username, USERNAME_MAX_FAILS, "该账号"),
              (LoginLog.ip, ip, IP_MAX_FAILS, "当前网络")]
    for col, val, limit, label in checks:
        if not val:
            continue
        row = (db.query(func.count(), func.max(LoginLog.created_at))
               .filter(LoginLog.success == False,  # noqa: E712
                       LoginLog.created_at >= since, col == val).one())
        cnt, last = int(row[0] or 0), row[1]
        if cnt >= limit and last and now - last < timedelta(minutes=LOCK_MINUTES):
            remain = int((timedelta(minutes=LOCK_MINUTES) - (now - last))\
                         .total_seconds() // 60) + 1
            raise HTTPException(429, f"登录尝试次数过多，{label}已被临时锁定，"
                                     f"请约 {remain} 分钟后重试")


@router.get("/public-key", response_class=PlainTextResponse)
def public_key(db: Session = Depends(get_db)):
    """登录加密公钥（私钥保存在服务端数据库）"""
    return get_public_key(db)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = body.username.strip()
    ip = client_ip(request)
    # 防破解：先检查锁定状态，再校验密码
    _reject_locked(db, username, ip)
    # 密码为 RSA 加密密文，在此解密后才做校验（校验完全在服务端完成）
    try:
        password = decrypt_payload(db, body.password)
    except ValueError as e:
        db.add(LoginLog(username=username, ip=ip, success=False))
        db.commit()
        raise HTTPException(400, str(e))
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        db.add(LoginLog(username=username, ip=ip, success=False))
        db.commit()
        # 记录后立即重新检查，本次即反馈锁定状态（而不是等下一次）
        try:
            _reject_locked(db, username, ip)
        except HTTPException:
            raise
        # 统一提示，不暴露账号是否存在
        raise HTTPException(401, "用户名或密码错误")
    db.add(LoginLog(username=user.username, role=user.role, ip=ip, success=True))
    db.commit()
    token = create_access_token(user.id, user.role)
    return TokenResponse(token=token, role=user.role, real_name=user.real_name,
                         username=user.username)


@router.post("/change-password")
def change_password(body: ChangePassword, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """验证原密码后修改为新密码，教师和学生通用；新旧密码均为加密密文"""
    try:
        old_password = decrypt_payload(db, body.old_password)
        new_password = decrypt_payload(db, body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 防错：新密码强度校验
    if len(new_password) < MIN_PASSWORD_LEN:
        raise HTTPException(400, f"新密码至少 {MIN_PASSWORD_LEN} 位")
    if new_password.strip() != new_password:
        raise HTTPException(400, "新密码首尾不能包含空格")
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(400, "原密码错误")
    if old_password == new_password:
        raise HTTPException(400, "新密码不能与原密码相同")
    user.password_hash = hash_password(new_password)
    db.commit()
    return {"ok": True}
