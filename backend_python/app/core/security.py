"""安全工具: 密码哈希、JWT 签发与校验"""
import bcrypt
import jwt as pyjwt
from datetime import datetime, timezone, timedelta
from ..config import settings


def hash_password(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(sub: str, username: str, role: str) -> str:
    """签发 JWT access token — payload 包含用户ID/用户名/角色/过期时间"""
    payload = {
        "sub": sub,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_EXPIRES_IN),
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT token，无效则抛出异常"""
    return pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
