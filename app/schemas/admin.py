from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from enum import Enum

class UserRoleEnum(str, Enum):
    user = "user"
    admin = "admin"

class UserOut(BaseModel):
    user_id: int
    email: str
    role: UserRoleEnum
    created_at: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PaginatedUsersResponse(BaseModel):
    success: bool
    total: int
    page: int
    limit: int
    items: List[UserOut]

class RoleUpdate(BaseModel):
    role: UserRoleEnum