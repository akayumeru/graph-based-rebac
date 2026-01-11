from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.role import RoleCreate, Role
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime

router = APIRouter(prefix="/roles", tags=["roles"])

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

@router.post("", response_model=Role, status_code=201)
def create_role(role: RoleCreate):
    try:
        with driver.session() as session:
            result = session.run(
                """
                CREATE (r:Role {key: $key, description: $description})
                RETURN elementId(r) AS id, r.key AS key, r.description AS description
                """,
                key=role.key,
                description=role.description
            ).single()

            return Role(id=result["id"], key=result["key"], description=result["description"])
    except Exception as e:
        if "ConstraintValidationFailed" in str(e) or "already exists" in str(e).lower():
            raise HTTPException(409, detail=f"Role with key '{role.key}' already exists")
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("", response_model=List[Role])
def list_roles(key: Optional[str] = Query(None), description: Optional[str] = Query(None)):
    query = "MATCH (r:Role)"
    params = {}
    conditions = []

    if key:
        conditions.append("r.key CONTAINS $key")
        params["key"] = key
    if description:
        conditions.append("r.description CONTAINS $description")
        params["description"] = description

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " RETURN elementId(r) AS id, r.key AS key, r.description AS description"

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()
            serialized_results = [serialize_neo4j_data(r) for r in results]
            return [Role(**r) for r in serialized_results]
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("/{role_id}", response_model=Role)
def get_role(role_id: str): 
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (r:Role) WHERE elementId(r) = $id
                RETURN elementId(r) AS id, r.key AS key, r.description AS description
                """,
                id=role_id
            ).single()

            if not result:
                raise HTTPException(404, detail="Role not found")

            serialized = serialize_neo4j_data(dict(result))
            return Role(**serialized)
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: str):  
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (r:Role) WHERE elementId(r) = $id
                DETACH DELETE r
                RETURN count(r) AS deleted
                """,
                id=role_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="Role not found")
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")