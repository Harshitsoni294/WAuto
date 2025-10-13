from pydantic import BaseModel
from typing import Dict, Any, Optional, List

# Request models
class SendMessageRequest(BaseModel):
    WHATSAPP_TOKEN: str
    PHONE_NUMBER_ID: str
    to: str
    text: str

class GeminiReplyRequest(BaseModel):
    prompt: str

class EmbeddingRequest(BaseModel):
    text: str

class GoogleTokens(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_expiry: Optional[str] = None
    scopes: Optional[List[str]] = None

class GoogleMeetEvent(BaseModel):
    summary: str
    description: Optional[str] = ""
    start: str  # ISO format datetime
    end: str    # ISO format datetime
    attendees: Optional[List[str]] = []

class GoogleMeetRequest(BaseModel):
    tokens: GoogleTokens
    event: GoogleMeetEvent

class MCPSendRequest(BaseModel):
    WHATSAPP_TOKEN: str
    PHONE_NUMBER_ID: str
    aliases: Dict[str, str]
    command: str

class AutoReplyRequest(BaseModel):
    from_number: str
    message_text: str
    business_description: str
    whatsapp_token: str
    phone_number_id: str
    auto_reply_enabled: bool = True
    contact_auto_reply_settings: Optional[Dict[str, bool]] = None

class UpdateTodoStatusRequest(BaseModel):
    status: str

class ScheduleMeetingRequest(BaseModel):
    command: str
    contact_aliases: Dict[str, str]
    google_tokens: Dict[str, Any]
    whatsapp_token: str
    phone_number_id: str

class SearchMessagesRequest(BaseModel):
    query: str
    contact_id: Optional[str] = None
    n_results: int = 5