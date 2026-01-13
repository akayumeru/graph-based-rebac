from pydantic import BaseModel, Field
from typing import Optional

class RoleCreate(BaseModel):
    key: str = Field(..., min_length=1, description="Уникальный ключ роли")
    description: Optional[str] = Field(None, description="Описание роли")

class Role(RoleCreate):
    id: str = Field(..., description="Element ID узла в Neo4j")  