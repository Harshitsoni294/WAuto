import os
from pathlib import Path
from dotenv import load_dotenv

# Always load the .env from the server directory and override any existing env vars
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

def _normalize_origin(url: str) -> str:
    """Ensure an origin string includes scheme; return empty if falsy."""
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"

class Settings:
    # Server settings
    HOST = "localhost"
    PORT = 4000
    DEBUG = True
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # WhatsApp Cloud API
    # Support either WHATSAPP_VERIFY_TOKEN or META_VERIFY_TOKEN env names
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN") or os.getenv("META_VERIFY_TOKEN") or "whatsapp_verify_token"
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    # Google Calendar/Meet
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    
    # ChromaDB
    CHROMA_PERSIST_DIRECTORY = "./data/chromadb"
    
    # Vector Store
    EMBEDDING_MODEL = "models/embedding-001"
    
    # CORS configuration
    # Toggle to allow all origins (safe only for development)
    CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").strip().lower() in {"1", "true", "yes", "on"}

    # Base allowed origins for local dev
    _BASE_CORS = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite dev server (alternate port)
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]

    # Extra origins from env (comma-separated)
    _EXTRA = [o.strip() for o in os.getenv("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()]

    # Auto-include common platform URLs if provided via env
    _VERCEL_URL = _normalize_origin(os.getenv("VERCEL_URL", ""))
    _RENDER_EXTERNAL_URL = _normalize_origin(os.getenv("RENDER_EXTERNAL_URL", ""))

    _PLATFORM_ORIGINS = [o for o in [_VERCEL_URL, _RENDER_EXTERNAL_URL] if o]

    CORS_ORIGINS = list(dict.fromkeys(_BASE_CORS + _EXTRA + _PLATFORM_ORIGINS))

    # Public base URL for building OAuth redirects
    _RAW_BASE = os.getenv("SERVER_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:4000"
    # Ensure scheme is present and strip trailing slash
    BASE_URL = (_RAW_BASE if _RAW_BASE.startswith("http") else f"https://{_RAW_BASE}").rstrip("/")
    GOOGLE_REDIRECT_URI = f"{BASE_URL}/auth/google/callback"
    # Client application URL to redirect users after OAuth (frontend dev default)
    CLIENT_APP_URL = os.getenv("CLIENT_APP_URL", "http://localhost:5173").rstrip("/")

settings = Settings()