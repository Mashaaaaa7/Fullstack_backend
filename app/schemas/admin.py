from pydantic import BaseModel
from app.models import UserRole

class RoleUpdate(BaseModel):
    role: UserRole