from pydantic import BaseModel, Field
from typing import Optional

class UserCreate(BaseModel):
    user_id: str = Field(..., min_length=1, description="Уникальный идентификатор пользователя (строка)")
    name: Optional[str] = Field(None, description="Имя или ник пользователя")

class User(UserCreate):
    id: str = Field(..., description="Element ID узла в Neo4j")  