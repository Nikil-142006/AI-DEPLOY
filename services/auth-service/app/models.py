import uuid
from datetime import datetime

class User:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get("id") or kwargs.get("_id") or uuid.uuid4())
        self.email = kwargs.get("email")
        self.username = kwargs.get("username")
        self.hashed_password = kwargs.get("hashed_password")
        self.role = kwargs.get("role", "developer")
        self.is_active = kwargs.get("is_active", True)
        self.created_at = kwargs.get("created_at") or datetime.utcnow()
        self.updated_at = kwargs.get("updated_at") or datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self.id,
            "email": self.email,
            "username": self.username,
            "hashed_password": self.hashed_password,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"
