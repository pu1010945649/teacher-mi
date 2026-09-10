from datetime import datetime, timedelta, timezone
import re

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# 行业主流账号规则：4-20 位，字母开头，仅含字母/数字/下划线
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,19}$")


def validate_username(username: str) -> str:
    """校验并返回用户名（教师/学生等账号统一规则）"""
    if not USERNAME_RE.match(username or ""):
        raise HTTPException(400, "用户名需 4-20 位，以字母开头，仅含字母、数字、下划线")
    return username


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def get_current_user(request: Request, token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效，请重新登录")
    if not token and request.method == "GET":
        # 文件下载等场景（img/a/window.open 无法携带请求头）允许 GET 请求用 ?token= 查询参数鉴权
        token = request.query_params.get("token")
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise credentials_error
    user = db.get(User, user_id)
    if not user:
        raise credentials_error
    return user


def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要教师权限")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """教师或管理员均可访问（管理端页面会调用的通用接口）"""
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要教师权限")
    return user


def ensure_ai_allowed(user: User) -> None:
    """教师使用 AI 受管理员权限控制（users.ai_enabled），管理员不受限"""
    if user.role == "teacher" and not user.ai_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "管理员未开放你的 AI 使用权限，请联系管理员开启")


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要学生权限")
    return user
