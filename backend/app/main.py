from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import AiConfig, User
from .routers import ai, assignments, auth, feedback, students, submissions, worksheets

DEFAULT_ADMIN = ("admin", "admin123")

# 旧库轻量迁移：为新表新增的列补 ALTER TABLE
MIGRATIONS = [
    "ALTER TABLE assignments ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE assignments ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN annotation TEXT DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN filename VARCHAR(255) DEFAULT ''",
    "ALTER TABLE feedbacks ADD COLUMN file_path VARCHAR(255) DEFAULT ''",
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
        if not db.query(User).filter(User.role == "teacher").first():
            db.add(User(username=DEFAULT_ADMIN[0], password_hash=hash_password(DEFAULT_ADMIN[1]),
                        role="teacher", real_name="教师"))
        if not db.query(AiConfig).first():
            db.add(AiConfig())
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(title="Teacher-Mi 智能教学助手", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(assignments.router)
app.include_router(submissions.router)
app.include_router(feedback.router)
app.include_router(ai.router)
app.include_router(worksheets.router)

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
