from fastapi import FastAPI

from .core.config import settings

app = FastAPI(
    title=settings.project_name, openapi_url=f"{settings.api_v1_str}/openapi.json"
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
