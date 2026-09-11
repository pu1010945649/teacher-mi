"""统一文件存储抽象层：local（本地磁盘）与 oss（任意 S3 兼容对象存储）双模式。

模式与连接配置存于 AppSetting（管理员后台设置），默认 local，行为与改造前完全一致。
业务层只调 save/delete/signed_url/is_oss，不感知底层实现；换 OSS 厂家只需改 endpoint。
"""
import os
from functools import lru_cache
from urllib.parse import quote

from ..config import UPLOAD_DIR

# AppSetting 中的配置键
KEYS = ("storage_backend", "oss_endpoint", "oss_bucket", "oss_access_key", "oss_secret_key")
DEFAULTS = {k: "" for k in KEYS}
DEFAULTS["storage_backend"] = "local"


def get_config(db) -> dict:
    """从 AppSetting 读取存储配置（缺失项用默认值）"""
    from ..models import AppSetting
    cfg = dict(DEFAULTS)
    for k in KEYS:
        row = db.query(AppSetting).filter(AppSetting.key == k).first()
        if row and row.value.strip():
            cfg[k] = row.value.strip()
    return cfg


def save_config(db, cfg: dict):
    """保存存储配置；密钥传空字符串表示不修改"""
    from ..models import AppSetting
    for k in KEYS:
        val = (cfg.get(k) or "").strip()
        if k == "oss_secret_key" and not val:  # 留空 = 沿用原密钥
            continue
        row = db.query(AppSetting).filter(AppSetting.key == k).first()
        if row:
            row.value = val
        else:
            db.add(AppSetting(key=k, value=val))
    db.commit()


def is_oss(db) -> bool:
    return get_config(db)["storage_backend"] == "oss"


@lru_cache(maxsize=4)
def _client(endpoint: str, ak: str, sk: str):
    """S3 客户端（按连接参数缓存，阿里云OSS/腾讯COS/MinIO 等兼容端点通用）"""
    import boto3
    return boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=ak, aws_secret_access_key=sk,
        region_name="us-east-1",
    )


def _bucket(db) -> tuple:
    cfg = get_config(db)
    return _client(cfg["oss_endpoint"], cfg["oss_access_key"], cfg["oss_secret_key"]), cfg["oss_bucket"]


# ---------- 业务接口 ----------

def save(db, key: str, data: bytes):
    """写入文件。key 建议带业务前缀分目录，如 video/xxx.mp4、submission/xxx.pdf"""
    if is_oss(db):
        client, bucket = _bucket(db)
        client.put_object(Bucket=bucket, Key=key, Body=data)
        return
    path = os.path.join(UPLOAD_DIR, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def delete(db, key: str):
    """删除文件；key 为空或文件不存在时静默跳过"""
    if not key:
        return
    if is_oss(db):
        try:
            client, bucket = _bucket(db)
            client.delete_object(Bucket=bucket, Key=key)
        except Exception:
            pass
        return
    path = os.path.join(UPLOAD_DIR, key)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def signed_url(db, key: str, ttl: int = 600, download_name: str = "") -> str:
    """签名 URL：oss 模式返回带过期时间的直链（支持 Range 拖动进度条）；
    local 模式返回空串，业务层自行走本地文件响应。"""
    if not is_oss(db):
        return ""
    client, bucket = _bucket(db)
    params = {}
    if download_name:
        params["ResponseContentDisposition"] = \
            f"attachment; filename*=UTF-8''{quote(download_name)}"
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key, **params}, ExpiresIn=ttl)


def exists(db, key: str) -> bool:
    if not key:
        return False
    if is_oss(db):
        try:
            client, bucket = _bucket(db)
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False
    return os.path.exists(os.path.join(UPLOAD_DIR, key))


def test_connection(db) -> str:
    """管理员测试连接：上传-读取-删除一个临时对象，抛异常时返回错误信息"""
    import uuid
    client, bucket = _bucket(db)
    key = f"_connect_test/{uuid.uuid4().hex}.txt"
    client.put_object(Bucket=bucket, Key=key, Body=b"ok")
    client.get_object(Bucket=bucket, Key=key)["Body"].read()
    client.delete_object(Bucket=bucket, Key=key)
    return ""
