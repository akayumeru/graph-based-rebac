from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime

router = APIRouter(prefix="/users", tags=["checks"])

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

@router.get("/{user_id}/has-role/{role_key}")
def has_role(
    user_id: str,
    role_key: str,
    at: Optional[datetime] = Query(None, description="Дата проверки (по умолчанию сейчас)"),
    scope: Optional[str] = Query(None, description="Scope для фильтра"),
    aggregate: bool = Query(False, description="Вернуть все совпадающие пути вместо ближайшего")
) -> Dict[str, Any]:
    params = {"user_id": user_id, "role_key": role_key}

    query = """
    MATCH path = (u:User {user_id: $user_id})-[hr:HAS_ROLE]->(dr:Role)-[:ROLE_INHERITS*0..]->(r:Role {key: $role_key})
    """

    conditions = []
    if at:
        conditions.append("(hr.valid_from IS NULL OR hr.valid_from <= $at) AND (hr.valid_until IS NULL OR hr.valid_until >= $at)")
        params["at"] = at
    if scope:
        conditions.append("hr.scope = $scope")
        params["scope"] = scope

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
    RETURN DISTINCT 
        r.key AS role_key,
        properties(hr) AS params,
        length(path) AS depth
    ORDER BY depth ASC
    """

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()

            if not results:
                return {"has": False, "params": None, "params_list": []}

           
            serialized_results = []
            for r in results:
                serialized = {}
                for key, value in r.items():
                    serialized[key] = serialize_neo4j_data(value)
                serialized_results.append(serialized)

            if aggregate:
                return {
                    "has": True,
                    "params_list": [r["params"] for r in serialized_results],
                    "via_roles": list(set(r["role_key"] for r in serialized_results))
                }
            else:
                nearest = min(serialized_results, key=lambda x: x["depth"])
                return {
                    "has": True,
                    "params": nearest["params"]
                }

    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")
