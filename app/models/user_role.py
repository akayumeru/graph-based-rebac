from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class UserRoleAssign(BaseModel):
    role_id: Optional[int] = None
    role_key: Optional[str] = None
    scope: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    can_delete_posts: Optional[bool] = None
    max_posts_per_day: Optional[int] = None
   