from pydantic import BaseModel, Field
from typing import Optional

class UserRoleAssign(BaseModel):
    role_id: Optional[int] = None
    role_key: Optional[str] = None
    scope: Optional[str] = None
