import os
from pathlib import Path
from dotenv import load_dotenv

# Always load the .env from the server directory and override any existing env vars
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

class Settings:
    # Server settings
    HOST = "localhost"
    PORT = 4000
    DEBUG = True
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # WhatsApp Cloud API
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "whatsapp_verify_token")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    # Google Calendar/Meet
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    # Time zone for calendar events (IANA tz database name)
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    
    # ChromaDB
    CHROMA_PERSIST_DIRECTORY = "./data/chromadb"
    
    # Vector Store
    EMBEDDING_MODEL = "models/embedding-001"
    
    # Cors
    CORS_ORIGINS = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite dev server (alternate port)
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000"
    ]

settings = Settings()