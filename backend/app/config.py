from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent

GMAIL_CREDENTIALS_PATH = BACKEND_DIR / os.getenv("GMAIL_CREDENTIALS_PATH", "./secrets/credentials.json")
GMAIL_TOKEN_PATH = BACKEND_DIR / os.getenv("GMAIL_TOKEN_PATH", "./secrets/token.json")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:devpassword@localhost:5433/inbox_relief"
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6335")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
