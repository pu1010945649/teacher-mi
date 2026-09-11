"""一次性回填：为无下发目标的历史作业物化目标（当前绑定发布老师的学生）"""
from app.database import SessionLocal
from app.models import Assignment, AssignmentTarget, TeacherStudentLink, User

db = SessionLocal()
n = 0
for a in db.query(Assignment).all():
    has = db.query(AssignmentTarget).filter(AssignmentTarget.assignment_id == a.id).first()
    if has:
        continue
    creator = db.get(User, a.created_by) if a.created_by else None
    if creator and creator.role == "teacher":
        ids = [r[0] for r in db.query(TeacherStudentLink.student_id)
               .filter(TeacherStudentLink.teacher_id == creator.id).all()]
        for sid in ids:
            db.add(AssignmentTarget(assignment_id=a.id, student_id=sid))
        n += 1
        print(f"assignment {a.id} 《{a.title}》 -> {len(ids)} targets")
db.commit()
print(f"backfilled {n} assignments")
db.close()
