from contextlib import asynccontextmanager
import os
import random
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text

from . import config
from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import AiConfig, AppSetting, TeacherStudentLink, User
from .routers import (ai, announcements, assignments, auth, courses, events, feedback,
                      reports, settings, storage, students, submissions, tasks, teachers)
from .services import task_worker
from .services import reminder_service

DEFAULT_ADMIN = ("admin", "teachermi")

# 旧库轻量迁移：为新表新增的列补 ALTER TABLE
MIGRATIONS = [
    "ALTER TABLE assignments ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN subject VARCHAR(50) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN video_filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN video_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN annotation TEXT DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE submissions ADD COLUMN attempt INTEGER DEFAULT 1",
    "ALTER TABLE worksheet_tasks ADD COLUMN assignment_id INTEGER",
    "ALTER TABLE worksheet_tasks ADD COLUMN title TEXT DEFAULT ''",
    "ALTER TABLE worksheet_tasks ADD COLUMN content TEXT DEFAULT ''",
    "ALTER TABLE worksheet_tasks ADD COLUMN pdf_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE worksheet_tasks ADD COLUMN course_feedback_ids TEXT DEFAULT '[]'",
    "ALTER TABLE users ADD COLUMN pushplus_token VARCHAR(200) DEFAULT ''",
    "ALTER TABLE users ADD COLUMN ai_enabled BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN teacher_id INTEGER",
    "ALTER TABLE users ADD COLUMN subject VARCHAR(50) DEFAULT ''",
    "ALTER TABLE ai_config ADD COLUMN user_id INTEGER DEFAULT 0",
    "ALTER TABLE courses ADD COLUMN reminded_at DATETIME",
]


def migrate():
    with engine.begin() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
            except Exception:
                pass  # 列已存在则跳过


def seed():
    """初始化默认管理员账号与 AI 配置行"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == DEFAULT_ADMIN[0]).first()
        if not admin:
            # 默认管理员账号：负责教师账号、AI 设置与日志管理
            db.add(User(username=DEFAULT_ADMIN[0], password_hash=hash_password(DEFAULT_ADMIN[1]),
                        role="admin", real_name="管理员"))
        elif admin.role == "teacher":
            # 老库升级：内置 admin 账号提升为管理员角色
            admin.role = "admin"
        if admin.real_name in ("", "教师"):
            # 内置管理员账号统一显示"管理员"（旧库可能残留原教师姓名）
            admin.real_name = "管理员"
        db.flush()  # 确保 admin.id 可用
        # JWT 签名密钥：优先环境变量；未设置则首次生成随机密钥并持久化到 AppSetting（重启不掉线）
        if os.environ.get("TEACHER_MI_SECRET_KEY"):
            config.SECRET_KEY = os.environ["TEACHER_MI_SECRET_KEY"]
        else:
            row = db.query(AppSetting).filter(AppSetting.key == "jwt_secret").first()
            if row and row.value:
                config.SECRET_KEY = row.value
            else:
                import secrets as _secrets
                value = _secrets.token_hex(32)
                if row:
                    row.value = value
                else:
                    db.add(AppSetting(key="jwt_secret", value=value))
                db.flush()
                config.SECRET_KEY = value
        # 旧数据回填：把 users.teacher_id 的单一归属迁移为师生绑定记录（科目为空）
        if not db.query(TeacherStudentLink).first():
            for s in db.query(User).filter(User.role == "student",
                                           User.teacher_id.isnot(None)).all():
                db.add(TeacherStudentLink(teacher_id=s.teacher_id, student_id=s.id, subject=""))
        # 旧版学生账号（3 个字母，不符合现有 4-20 位字母开头规则）自动追加 3 位数字后缀
        pattern = re.compile(r"^[A-Za-z]{3}$")
        taken = {row[0] for row in db.query(User.username).all()}
        for s in db.query(User).filter(User.role == "student").all():
            if not pattern.match(s.username or ""):
                continue
            base = s.username
            # 用学号/手机号等已有信息尽量保持可读性：随机不冲突的 3 位数字
            for _ in range(100):
                cand = f"{base}{random.randint(100, 999)}"
                if cand not in taken:
                    taken.add(cand)
                    s.username = cand
                    break
            else:
                # 100 次仍冲突则扩展为 4 位
                for _ in range(1000):
                    cand = f"{base}{random.randint(1000, 9999)}"
                    if cand not in taken:
                        taken.add(cand)
                        s.username = cand
                        break
        db.flush()
        # 遗留全局 AI 配置（user_id=0）划归管理员，作为各教师的默认回退配置
        legacy_cfg = db.query(AiConfig).filter(AiConfig.user_id == 0).first()
        if legacy_cfg:
            if not db.query(AiConfig).filter(AiConfig.user_id == admin.id).first():
                legacy_cfg.user_id = admin.id
            else:
                db.delete(legacy_cfg)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    Base.metadata.create_all(engine)
    seed()
    task_worker.start_worker()
    reminder_service.start_reminder()
    yield
    reminder_service.stop_reminder()
    task_worker.stop_worker()


app = FastAPI(title="Teacher-Mi 智能教学助手", lifespan=lifespan)
# 前后端分离部署时在环境变量配置前端地址；同源部署（单容器）无需跨域
_origins = [o.strip() for o in os.environ.get("TEACHER_MI_CORS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])


@app.get("/health", include_in_schema=False)
def health():
    """容器健康检查端点（供 Docker HEALTHCHECK / 编排探针使用）"""
    return {"ok": True}

app.include_router(auth.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(assignments.router)
app.include_router(submissions.router)
app.include_router(feedback.router)
app.include_router(ai.router)
app.include_router(tasks.router)
app.include_router(courses.router)
app.include_router(reports.router)
app.include_router(settings.router)
app.include_router(events.router)
app.include_router(storage.router)
app.include_router(announcements.router)

# 若存在前端构建产物，则由后端直接托管（Docker 单容器部署用）
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        # 防路径穿越：解析后的真实路径必须仍位于前端目录内
        file = os.path.realpath(os.path.join(FRONTEND_DIST, full_path))
        if full_path and file.startswith(os.path.realpath(FRONTEND_DIST) + os.sep)\
                and os.path.isfile(file):
            # 带哈希的静态资源可长缓存
            return FileResponse(file, headers={"Cache-Control": "public, max-age=604800"})
        # index.html 不缓存，确保发新版后浏览器立即拿到新入口
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"),
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
