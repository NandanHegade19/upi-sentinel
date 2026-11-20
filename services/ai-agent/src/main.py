from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

MODEL_NAME = "all-MiniLM-L6-v2"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Loading embedding model: {MODEL_NAME}...")
    app.state.embedder = SentenceTransformer(MODEL_NAME)
    yield
    # Clean up state if necessary

app = FastAPI(title="UPI Sentinel AI Agent", lifespan=lifespan)

# CORS middleware block
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://upi-sentinel-oja8fx2pg-nandan-hegades-projects.vercel.app",
        "https://upi-sentinel-ui.vercel.app",
    ],
    allow_origin_regex=r"https://upi-sentinel-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows custom X-User-Role header through
)

from src.api.routes import router
from src.api.admin_routes import router as admin_router

app.include_router(router)
app.include_router(admin_router)