import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_URL = f"sqlite:///{os.environ.get('TEACHER_MI_DB', os.path.join(BASE_DIR, 'teacher_mi.db'))}"

SECRET_KEY = "teacher-mi-secret-key-change-me-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 12

os.makedirs(UPLOAD_DIR, exist_ok=True)
