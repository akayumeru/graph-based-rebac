from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError, ServiceUnavailable, SessionExpired
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RBAC Neo4j API")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
    auth=(
        os.getenv("NEO4J_USERNAME", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "ktrwbz123")
    )
)

def init_neo4j_schema():
    try:
        with driver.session() as session:
            constraints = [
                "CREATE CONSTRAINT role_key IF NOT EXISTS FOR (r:Role) REQUIRE r.key IS UNIQUE",
                "CREATE CONSTRAINT permission_key IF NOT EXISTS FOR (p:Permission) REQUIRE p.key IS UNIQUE",
                "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE"
            ]
            for cypher in constraints:
                try:
                    session.run(cypher)
                except ClientError as e:
                    if "already exists" not in str(e).lower():
                        raise e
        print("Neo4j schema initialized successfully")
    except (ServiceUnavailable, SessionExpired, Exception) as e:
        print(f"Warning: Could not initialize Neo4j schema on startup: {str(e)}")
        print("→ Make sure Neo4j is running (docker compose up -d)")

@app.on_event("startup")
async def startup_event():
    init_neo4j_schema()

@app.on_event("shutdown")
def shutdown_event():
    driver.close()

@app.get("/health")
def health_check():
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 AS status")
            record = result.single()
            if record and record["status"] == 1:
                return {
                    "status": "ok",
                    "neo4j": "connected",
                    "message": "Neo4j доступен"
                }
        raise RuntimeError("Не удалось получить ответ от Neo4j")
    except (ServiceUnavailable, SessionExpired) as e:
        raise HTTPException(
            status_code=503,
            detail=f"Neo4j недоступен: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка проверки здоровья: {str(e)}"
        )

from app.routers import users

app.include_router(users.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )