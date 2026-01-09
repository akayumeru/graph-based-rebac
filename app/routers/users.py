from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.user import UserCreate, User
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])

def serialize_neo4j_data(data):
    """Сериализация Neo4j типов данных"""
    if isinstance(data, Neo4jDateTime):
        return data.to_native().isoformat()
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: serialize_neo4j_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_neo4j_data(item) for item in data]
    return data

@router.post("", response_model=User, status_code=201)
def create_user(user: UserCreate):
    try:
        with driver.session() as session:
            result = session.run(
                """
                CREATE (u:User {user_id: $user_id, name: $name})
                RETURN elementId(u) AS id, u.user_id AS user_id, u.name AS name
                """,
                user_id=user.user_id,
                name=user.name
            ).single()

            return User(id=result["id"], user_id=result["user_id"], name=result["name"])
    except Exception as e:
        if "ConstraintValidationFailed" in str(e) or "already exists" in str(e).lower():
            raise HTTPException(409, detail=f"User with user_id '{user.user_id}' already exists")
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[User])
def list_users(user_id: Optional[str] = Query(None), name: Optional[str] = Query(None)):
    query = "MATCH (u:User)"
    params = {}
    conditions = []

    if user_id:
        conditions.append("u.user_id CONTAINS $user_id")
        params["user_id"] = user_id
    if name:
        conditions.append("u.name CONTAINS $name")
        params["name"] = name

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " RETURN elementId(u) AS id, u.user_id AS user_id, u.name AS name"

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()
            serialized_results = [serialize_neo4j_data(r) for r in results]
            return [User(**r) for r in serialized_results]
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("/{user_id}", response_model=User)
def get_user(user_id: str):
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {user_id: $user_id})
                RETURN elementId(u) AS id, u.user_id AS user_id, u.name AS name
                """,
                user_id=user_id
            ).single()

            if not result:
                raise HTTPException(404, detail="User not found")

            serialized = serialize_neo4j_data(dict(result))
            return User(**serialized)
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str):
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {user_id: $user_id})
                DETACH DELETE u
                RETURN count(u) AS deleted
                """,
                user_id=user_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="User not found")
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")