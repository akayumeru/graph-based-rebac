from fastapi import APIRouter, HTTPException, Body
from typing import Dict
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime

router = APIRouter(prefix="/roles", tags=["roles-relations"])

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

@router.post("/{role_id}/permissions")
def add_permission_to_role(role_id: str, body: Dict = Body(...)):  
    perm_id = body.get("permission_id")
    perm_key = body.get("permission_key")

    if not (perm_id or perm_key or role_id):
        raise HTTPException(400, detail="Provide 'permission_id' or 'permission_key'")

    try:
        with driver.session() as session:
            role = session.run(
                "MATCH (r:Role {key: $key}) RETURN elementId(r) AS id",
                key=role_id
            ).single()
            if not role:
                raise HTTPException(404, detail="Role not found")
            role_id = role["id"]
            if perm_key:
                perm = session.run(
                    "MATCH (p:Permission {key: $key}) RETURN elementId(p) AS id",
                    key=perm_key
                ).single()
                if not perm:
                    raise HTTPException(404, detail="Permission not found")
                perm_id = perm["id"]

            session.run(
                """
                MATCH (r:Role) WHERE elementId(r) = $role_id
                MATCH (p:Permission) WHERE elementId(p) = $perm_id
                MERGE (r)-[:ROLE_HAS_PERMISSION]->(p)
                """,
                role_id=role_id, perm_id=perm_id
            )

        return {"status": "Permission added to role", "role_id": role_id, "perm_id": perm_id}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{role_id}/permissions/{perm_id}")
def remove_permission_from_role(role_id: str, perm_id: str):  
    try:
        with driver.session() as session:
            role = session.run(
                "MATCH (r:Role {key: $key}) RETURN elementId(r) AS id",
                key=role_id
            ).single()
            if not role:
                raise HTTPException(404, detail="Role not found")
            role_id = role["id"]
            perm = session.run(
                "MATCH (p:Permission {key: $key}) RETURN elementId(p) AS id",
                key=perm_id
            ).single()
            if not perm:
                raise HTTPException(404, detail="Permission not found")
            perm_id = perm["id"]
            result = session.run(
                """
                MATCH (r:Role)-[rel:ROLE_HAS_PERMISSION]->(p:Permission)
                WHERE elementId(r) = $role_id AND elementId(p) = $perm_id
                DELETE rel
                RETURN count(rel) AS deleted
                """,
                role_id=role_id, perm_id=perm_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="Permission not linked to this role")

        return {"status": "permission removed from role"}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.post("/{child_id}/parents")
def add_parent_role(child_id: str, body: Dict = Body(...)):  
    parent_id = body.get("parent_id")
    parent_key = body.get("parent_key")

    if not (parent_id or parent_key):
        raise HTTPException(400, detail="Provide 'parent_id' or 'parent_key'")

    try:
        with driver.session() as session:
            if parent_key:
                parent = session.run(
                    "MATCH (r:Role {key: $key}) RETURN elementId(r) AS id",
                    key=parent_key
                ).single()
                if not parent:
                    raise HTTPException(404, detail="Parent role not found")
                parent_id = parent["id"]

            cycle = session.run(
                """
                MATCH path = (parent:Role)-[:ROLE_INHERITS*]->(child:Role)
                WHERE elementId(parent) = $parent_id AND elementId(child) = $child_id
                RETURN count(path) > 0 AS has_cycle
                """,
                parent_id=parent_id, child_id=child_id
            ).single()["has_cycle"]

            if cycle:
                raise HTTPException(409, detail="Inheritance cycle detected")

            session.run(
                """
                MATCH (child:Role) WHERE elementId(child) = $child_id
                MATCH (parent:Role) WHERE elementId(parent) = $parent_id
                MERGE (child)-[:ROLE_INHERITS]->(parent)
                """,
                child_id=child_id, parent_id=parent_id
            )

        return {"status": "parent role added"}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{child_id}/parents/{parent_id}")
def remove_parent_role(child_id: str, parent_id: str):  
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (child:Role)-[rel:ROLE_INHERITS]->(parent:Role)
                WHERE elementId(child) = $child_id AND elementId(parent) = $parent_id
                DELETE rel
                RETURN count(rel) AS deleted
                """,
                child_id=child_id, parent_id=parent_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="Inheritance relation not found")

        return {"status": "parent role removed"}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.get("/{role_id}/permissions")
def get_role_permissions(
    role_id: str, 
    mode: str = "direct"
):
    try:
        with driver.session() as session:
            role = session.run(
                "MATCH (r:Role {key: $key}) RETURN elementId(r) AS id",
                key=role_id
            ).single()
            if not role:
                raise HTTPException(404, detail="Role not found")
            role_id = role["id"]
            if mode == "direct":
                query = """
                MATCH (r:Role)-[:ROLE_HAS_PERMISSION]->(p:Permission)
                WHERE elementId(r) = $role_id
                RETURN elementId(p) AS id, p.key AS key, p.description AS description
                """
            else:  
                query = """
                MATCH (r:Role)-[:ROLE_INHERITS*0..]->(parent:Role)-[:ROLE_HAS_PERMISSION]->(p:Permission)
                WHERE elementId(r) = $role_id
                RETURN DISTINCT elementId(p) AS id, p.key AS key, p.description AS description
                """

            results = session.run(query, role_id=role_id).data()
            
        
            serialized_results = []
            for r in results:
                serialized = {}
                for key, value in r.items():
                    serialized[key] = serialize_neo4j_data(value)
                serialized_results.append(serialized)
            
            return serialized_results
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")