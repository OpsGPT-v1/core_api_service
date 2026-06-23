import logging

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit_logs, auth, incidents, internal, knowledge_base, projects, users
from app.core.config import settings
from app.db.database import init_db
from app.db.seed import seed_default_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpsGPT Core API Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(incidents.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(audit_logs.router)
api_router.include_router(internal.router)

app.include_router(api_router)
app.include_router(api_router, prefix="/api/core")


@app.on_event("startup")
def startup() -> None:
    initialized = init_db()
    if initialized:
        seed_default_users()
    else:
        logger.error("Core API started without confirmed database initialization")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "core-api-service"}
