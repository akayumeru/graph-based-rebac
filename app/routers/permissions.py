from fastapi import APIRouter, HTTPException
from app.models.permission import PermissionCreate, Permission
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime

router = APIRouter(prefix="/permissions", tags=["permissions"])

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

@router.post("", response_model=Permission, status_code=201)
def create_permission(perm: PermissionCreate):
    try:
        with driver.session() as session:
            result = session.run(
                """
                CREATE (p:Permission {key: $key, description: $description})
                RETURN elementId(p) AS id, p.key AS key, p.description AS description
                """,
                key=perm.key,
                description=perm.description
            ).single()

            return Permission(id=result["id"], key=result["key"], description=result["description"])
    except Exception as e:
        if "ConstraintValidationFailed" in str(e) or "already exists" in str(e).lower():
            raise HTTPException(409, detail=f"Permission with key '{perm.key}' already exists")
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("/{perm_id}", response_model=Permission)
def get_permission(perm_id: str):  
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (p:Permission) WHERE elementId(p) = $id "
                "RETURN elementId(p) AS id, p.key AS key, p.description AS description",
                id=perm_id
            ).single()

            if not result:
                raise HTTPException(404, detail="Permission not found")

            serialized = serialize_neo4j_data(dict(result))
            return Permission(**serialized)
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{perm_id}", status_code=204)
def delete_permission(perm_id: str): 
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (p:Permission) WHERE elementId(p) = $id "
                "DETACH DELETE p "
                "RETURN count(p) AS deleted",
                id=perm_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="Permission not found")
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")