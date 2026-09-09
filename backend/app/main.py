from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text

from .auth import hash_password, verify_password
from .database import Base, SessionLocal, engine
from .models import AiConfig, User
from .routers import ai, assignments, auth, courses, events, feedback, students, submissions, tasks, worksheets
from .services import task_worker

DEFAULT_ADMIN = ("admin", "teachermi")

# 旧库轻量迁移：为新表新增的列补 ALTER TABLE
MIGRATIONS = [
    "ALTER TABLE assignments ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN annotation TEXT DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE worksheets ADD COLUMN status VARCHAR(20) DEFAULT 'pending'",
    "ALTER TABLE worksheets ADD COLUMN published_at DATETIME",
    "ALTER TABLE worksheets ADD COLUMN published_as_assignment_id INTEGER",
]


def migrate():
    with engine.begin() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
            except Exception:
                pass  # 列已存在则跳过


def seed():
    """初始化默认教师账号与 AI 配置行"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == DEFAULT_ADMIN[0], User.role == "teacher").first()
        if not admin:
            db.add(User(username=DEFAULT_ADMIN[0], password_hash=hash_password(DEFAULT_ADMIN[1]),
                        role="teacher", real_name="教师"))
        elif verify_password("admin123", admin.password_hash):
            # 旧库仍是旧默认密码，同步为新默认密码
            admin.password_hash = hash_password(DEFAULT_ADMIN[1])
        if not db.query(AiConfig).first():
            db.add(AiConfig())
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    Base.metadata.create_all(engine)
    seed()
    task_worker.start_worker()
    yield
    task_worker.stop_worker()


app = FastAPI(title="Teacher-Mi 智能教学助手", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health", include_in_schema=False)
def health():
    """容器健康检查端点（供 Docker HEALTHCHECK / 编排探针使用）"""
    return {"ok": True}

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(assignments.router)
app.include_router(submissions.router)
app.include_router(feedback.router)
app.include_router(ai.router)
app.include_router(worksheets.router)
app.include_router(tasks.router)
app.include_router(courses.router)
app.include_router(events.router)

# 若存在前端构建产物，则由后端直接托管（Docker 单容器部署用）
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        file = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(file):
            return FileResponse(file)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
