from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import Base, engine
from .routers import auth, crawl, documents, ai, groups, notifications

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(crawl.router)
app.include_router(documents.router)
app.include_router(ai.router)
app.include_router(groups.router)
app.include_router(notifications.router)

# Expose generated PDFs for download
pdf_dir = Path(settings.pdf_output_dir)
pdf_dir.mkdir(parents=True, exist_ok=True)
app.mount("/pdfs", StaticFiles(directory=pdf_dir), name="pdfs")


@app.get("/health")
def health_check():
    return {"status": "ok"}
