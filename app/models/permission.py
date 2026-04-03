from pydantic import BaseModel, Field
from typing import Optional

class PermissionCreate(BaseModel):
    key: str = Field(..., min_length=1)
    description: Optional[str] = None

class Permission(PermissionCreate):
    id: str