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

@router.get("/{user_id}/has-permission/{perm_key}")
def has_permission(
        user_id: str,
        perm_key: str,
        at: Optional[datetime] = Query(None),
        scope: Optional[str] = Query(None)
) -> Dict[str, Any]:
    params = {"user_id": user_id, "perm_key": perm_key}

    query = """
    MATCH path = (u:User {user_id: $user_id})-[hr:HAS_ROLE]->(dr:Role)-[:ROLE_INHERITS*0..]->(r:Role)-[:ROLE_HAS_PERMISSION]->(p:Permission {key: $perm_key})
    """

    conditions = []
    if at:
        conditions.append(
            "(hr.valid_from IS NULL OR hr.valid_from <= $at) AND (hr.valid_until IS NULL OR hr.valid_until >= $at)")
        params["at"] = at
    if scope:
        conditions.append("hr.scope = $scope")
        params["scope"] = scope

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
    RETURN DISTINCT 
        r.key AS via_role,
        properties(hr) AS params
    """

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()

            if not results:
                return {
                    "has": False,
                    "via_roles": [],
                    "params_list": []
                }

            serialized_results = []
            for r in results:
                serialized = {}
                for key, value in r.items():
                    serialized[key] = serialize_neo4j_data(value)
                serialized_results.append(serialized)

            via_roles = list(set(r["via_role"] for r in serialized_results))
            params_list = [r["params"] for r in serialized_results]

            return {
                "has": True,
                "via_roles": via_roles,
                "params_list": params_list
            }

    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")


@router.get("/{user_id}/decision/role/{role_key}")
def decision_role(
        user_id: str,
        role_key: str,
        at: Optional[datetime] = Query(None),
        scope: Optional[str] = Query(None),
        max_depth: int = Query(5, ge=1, le=10),
        limit_paths: int = Query(3, ge=1, le=10)
) -> Dict[str, Any]:
    params = {"user_id": user_id, "role_key": role_key, "max_depth": max_depth}

    query = """
    MATCH path = shortestPath((u:User {user_id: $user_id})-[*1..]->(r:Role {key: $role_key}))
    WHERE length(path) <= $max_depth
    """

    conditions = []
    if at:
        conditions.append(
            "all(rel IN relationships(path) WHERE (rel.valid_from IS NULL OR rel.valid_from <= $at) AND (rel.valid_until IS NULL OR rel.valid_until >= $at))")
        params["at"] = at
    if scope:
        conditions.append("all(rel IN relationships(path) WHERE rel.scope = $scope)")
        params["scope"] = scope

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += f"""
    WITH path, length(path) AS depth
    ORDER BY depth ASC
    LIMIT {limit_paths}
    RETURN 
        [n IN nodes(path) | {{id: elementId(n), labels: labels(n), props: properties(n)}}] AS nodes,
        [rel IN relationships(path) | {{type: type(rel), props: properties(rel)}}] AS edges,
        depth AS path_length,
        CASE WHEN length(path) > 0 THEN True ELSE False END AS granted
    """

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()

            if not results:
                return {"granted": False, "paths": []}

            serialized_results = []
            for r in results:
                serialized = {}
                for key, value in r.items():
                    serialized[key] = serialize_neo4j_data(value)
                serialized_results.append(serialized)

            return {
                "granted": True,
                "paths": [
                    {
                        "nodes": r["nodes"],
                        "edges": r["edges"],
                        "path_length": r["path_length"]
                    } for r in serialized_results
                ]
            }
    except Exception as e:
        raise HTTPException(500, detail=f"Decision path error: {str(e)}")


@router.get("/{user_id}/decision/permission/{perm_key}")
def decision_permission(
        user_id: str,
        perm_key: str,
        at: Optional[datetime] = Query(None),
        scope: Optional[str] = Query(None),
        max_depth: int = Query(5, ge=1, le=10),
        limit_paths: int = Query(3, ge=1, le=10)
) -> Dict[str, Any]:
    params = {"user_id": user_id, "perm_key": perm_key, "max_depth": max_depth}

    query = """
    MATCH path = shortestPath((u:User {user_id: $user_id})-[*1..]->(p:Permission {key: $perm_key}))
    WHERE length(path) <= $max_depth
    """

    conditions = []
    if at:
        conditions.append(
            "all(rel IN relationships(path) WHERE (rel.valid_from IS NULL OR rel.valid_from <= $at) AND (rel.valid_until IS NULL OR rel.valid_until >= $at))")
        params["at"] = at
    if scope:
        conditions.append("all(rel IN relationships(path) WHERE rel.scope = $scope)")
        params["scope"] = scope

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += f"""
    WITH path, length(path) AS depth
    ORDER BY depth ASC
    LIMIT {limit_paths}
    RETURN 
        [n IN nodes(path) | {{id: elementId(n), labels: labels(n), props: properties(n)}}] AS nodes,
        [rel IN relationships(path) | {{type: type(rel), props: properties(rel)}}] AS edges,
        depth AS path_length,
        CASE WHEN length(path) > 0 THEN True ELSE False END AS granted
    """

    try:
        with driver.session() as session:
            results = session.run(query, **params).data()

            if not results:
                return {"granted": False, "paths": []}

            serialized_results = []
            for r in results:
                serialized = {}
                for key, value in r.items():
                    serialized[key] = serialize_neo4j_data(value)
                serialized_results.append(serialized)

            return {
                "granted": True,
                "paths": [
                    {
                        "nodes": r["nodes"],
                        "edges": r["edges"],
                        "path_length": r["path_length"]
                    } for r in serialized_results
                ]
            }
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")