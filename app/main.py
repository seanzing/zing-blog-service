"""Main FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.config import app_config, settings

# Create FastAPI app
app = FastAPI(
    title="Zing Blog Generation Service",
    description="Automated blog content generation and Duda API integration",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("\n" + "="*60)
    print("🚀 Zing Blog Generation Service Starting...")
    print("="*60)
    print(f"Environment: {settings.environment}")
    print(f"Mode: {app_config.mode}")
    print(f"Model: {app_config.model}")
    print(f"Blogs per request: {app_config.number_of_blogs}")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("\n" + "="*60)
    print("👋 Zing Blog Generation Service Shutting Down...")
    print("="*60 + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_config.host,
        port=app_config.port,
        reload=True
    )
