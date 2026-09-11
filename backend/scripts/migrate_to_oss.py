"""本地文件迁移到对象存储（一次性脚本）。

用途：从 local 切换到 oss 模式前，把 uploads 目录下的历史文件批量上传到 OSS，
key 与数据库记录一致（文件名），迁移后新老文件在 oss 模式下均可正常访问。

用法（在 backend 目录执行）：
  1. 先在管理员后台「对象存储」中填好 Endpoint/Bucket/AccessKey/SecretKey 并保存
     （存储模式可暂保持 local，本脚本只读配置、不改模式）
  2. 运行：
     python scripts/migrate_to_oss.py            # 默认上传后保留本地文件（安全）
     python scripts/migrate_to_oss.py --delete   # 上传校验成功后删除本地文件（省磁盘）
  3. 全部迁移完成且业务验证正常后，再在后台把存储模式切换为「对象存储」

说明：
  - 幂等：已在 OSS 上存在同 key 文件的自动跳过，可中断后重跑
  - 仅统计/上传 uploads 下的普通文件，迁移完打印汇总
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import UPLOAD_DIR  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services import storage  # noqa: E402


def main():
    delete_local = "--delete" in sys.argv

    db = SessionLocal()
    try:
        cfg = storage.get_config(db)
        if cfg["storage_backend"] != "oss":
            print(f"当前存储模式为 local（backend={cfg['storage_backend']}）")
            print("请先在管理员后台保存 Endpoint/Bucket/AccessKey/SecretKey（模式保持 local 也可），再运行本脚本")
            return 1
        if not all([cfg["oss_endpoint"], cfg["oss_bucket"], cfg["oss_access_key"], cfg["oss_secret_key"]]):
            print("OSS 配置不完整，请检查 Endpoint/Bucket/AccessKey/SecretKey")
            return 1

        files = [p for p in Path(UPLOAD_DIR).iterdir() if p.is_file()] if Path(UPLOAD_DIR).is_dir() else []
        if not files:
            print("uploads 目录为空，无需迁移")
            return 0

        client, bucket = storage._bucket(db)
        total = len(files)
        done = skipped = failed = 0
        freed = 0
        print(f"共 {total} 个文件待迁移 → {cfg['oss_endpoint']} / {cfg['oss_bucket']}\n")

        for i, path in enumerate(files, 1):
            key = path.name
            size = path.stat().st_size
            # 幂等：OSS 上已有同 key 且大小一致则跳过
            try:
                head = client.head_object(Bucket=bucket, Key=key)
                if head["ContentLength"] == size:
                    skipped += 1
                    print(f"[{i}/{total}] 跳过（已存在）：{key}")
                    if delete_local:
                        path.unlink()
                        freed += size
                    continue
            except client.exceptions.ClientError:
                pass

            try:
                client.upload_file(str(path), bucket, key)
                done += 1
                print(f"[{i}/{total}] 已上传：{key}（{size / 1024 / 1024:.1f} MB）")
                if delete_local:
                    path.unlink()
                    freed += size
            except Exception as e:  # 单文件失败不中断
                failed += 1
                print(f"[{i}/{total}] 失败：{key} → {e}")

        print(f"\n完成：上传 {done}，跳过 {skipped}，失败 {failed}")
        if delete_local:
            print(f"已释放本地磁盘 {freed / 1024 / 1024:.1f} MB")
        if failed:
            print("存在失败文件，修复后重新运行即可（已成功的会自动跳过）")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
