from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.models.user_role import UserRoleAssign
from app.main import driver
from neo4j.time import DateTime as Neo4jDateTime

router = APIRouter(prefix="/users", tags=["user-roles"])

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

@router.post("/{user_id}/roles")
def assign_role_to_user(user_id: str, assign: UserRoleAssign):
    role_id = assign.role_id
    if assign.role_key:
        with driver.session() as session:
            role = session.run(
                "MATCH (r:Role {key: $key}) RETURN elementId(r) AS id",
                key=assign.role_key
            ).single()
            if not role:
                raise HTTPException(404, detail="Role not found")
            role_id = role["id"]

    if not role_id:
        raise HTTPException(400, detail="Provide 'role_id' or 'role_key'")

    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (u:User {user_id: $user_id})
                MATCH (r:Role) WHERE elementId(r) = $role_id
                MERGE (u)-[hr:HAS_ROLE {
                    scope: $scope,
                    valid_from: $valid_from,
                    valid_until: $valid_until,
                    can_delete_posts: $can_delete_posts,
                    max_posts_per_day: $max_posts_per_day
                }]->(r)
                """,
                user_id=user_id,
                role_id=role_id,
                scope=assign.scope,
                valid_from=assign.valid_from,
                valid_until=assign.valid_until,
                can_delete_posts=assign.can_delete_posts,
                max_posts_per_day=assign.max_posts_per_day
            )
        return {"status": "role assigned"}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")

@router.delete("/{user_id}/roles/{role_id}")
def remove_role_from_user(user_id: str, role_id: str):  
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {user_id: $user_id})-[hr:HAS_ROLE]->(r:Role)
                WHERE elementId(r) = $role_id
                DELETE hr
                RETURN count(hr) AS deleted
                """,
                user_id=user_id, role_id=role_id
            ).single()

            if result["deleted"] == 0:
                raise HTTPException(404, detail="Role not assigned to this user")

        return {"status": "role removed"}
    except Exception as e:
        raise HTTPException(500, detail=f"Database error: {str(e)}")
