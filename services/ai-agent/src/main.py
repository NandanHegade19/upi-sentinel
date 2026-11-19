from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import os

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
        "http://localhost:3000", "http://localhost:5173",
        "https://upi-sentinel-oja8fx2pg-nandan-hegades-projects.vercel.app",
        "https://upi-sentinel-ui.vercel.app"],
    allow_origin_regex=r"https://upi-sentinel-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # This allows custom X-User-Role header through
)

from src.api.routes import router
app.include_router(router)
