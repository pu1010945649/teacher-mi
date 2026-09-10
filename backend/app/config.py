import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_URL = f"sqlite:///{os.environ.get('TEACHER_MI_DB', os.path.join(BASE_DIR, 'teacher_mi.db'))}"

# JWT 签名密钥：生产环境建议用环境变量 TEACHER_MI_SECRET_KEY 覆盖；
# 未设置时 main.seed() 会在启动时自动生成随机密钥并持久化到数据库（不再使用下面的默认值）
SECRET_KEY = os.environ.get("TEACHER_MI_SECRET_KEY", "teacher-mi-secret-key-change-me-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 12

os.makedirs(UPLOAD_DIR, exist_ok=True)

# 统一科目口径：教师任教科目只能从这里选择，保证绑定/划拨时按科目匹配不出歧义
SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "政治",
            "科学", "信息技术", "编程"]
