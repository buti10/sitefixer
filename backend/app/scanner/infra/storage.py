# scanner/infra/storage.py
import json, uuid
from ..common.errors import NotFound
from app.extensions import redis_conn

SESSION_TTL = 1800  # 30 min

class RedisSessionStore:
    def put(self, host, username, password, ttl=SESSION_TTL):
        sid = str(uuid.uuid4())
        key = f"sftp:{sid}"
        data = json.dumps({"host": host, "username": username, "password": password})
        redis_conn.setex(key, ttl, data)
        return sid

    def get(self, sid, refresh=True):
        key = f"sftp:{sid}"
        raw = redis_conn.get(key)
        if not raw:
            raise NotFound("sid")
        if refresh:
            redis_conn.expire(key, SESSION_TTL)
        return json.loads(raw)

    def pop(self, sid):
        key = f"sftp:{sid}"
        if not redis_conn.delete(key):
            raise NotFound("sid")
        return True

Sessions = RedisSessionStore()
