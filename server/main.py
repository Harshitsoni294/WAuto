from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import socketio
import uvicorn
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import our services
from config import settings

# First try to import and configure services
try:
    from services.whatsapp_service import whatsapp_service
    from services.gemini_service import gemini_service
    from services.vector_service import vector_service
    from services.google_service import google_service
    from services.mcp_services import end_message_mcp, auto_reply_mcp
    from services.advanced_mcp import meeting_mcp
    from services.contact_service import contact_service
    from models import *
    print("✅ All services imported successfully!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Socket.IO setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=True,
    engineio_logger=True
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting WhatsApp Business Automation Server")
    yield
    # Shutdown
    logger.info("Shutting down server")

# Create FastAPI app
app = FastAPI(
    title="WhatsApp Business Automation API",
    description="Backend for WhatsApp Business automation with AI-powered MCPs",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio, app)

# Socket.IO events
@sio.event
async def connect(sid, environ, auth):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

# API Routes

@app.get("/")
async def root():
    return {"message": "WhatsApp Business Automation API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test basic functionality
        return {
            "status": "healthy",
            "services": {
                "api": "operational",
                "vector_db": "operational",
                "whatsapp": "operational"
            },
            "endpoints": {
                "send_message": "/api/send-message",
                "gemini_reply": "/api/generate-gemini-reply", 
                "mcp_send": "/api/mcp/send",
                "webhook": "/webhook"
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/debug/google-oauth")
async def debug_google_oauth():
    return {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": "http://localhost:4000/auth/google/callback"
    }

@app.post("/api/send-message")
async def send_message(request: SendMessageRequest):
    """Send a WhatsApp message"""
    try:
        result = await whatsapp_service.send_message(
            phone_number_id=request.PHONE_NUMBER_ID,
            access_token=request.WHATSAPP_TOKEN,
            to=request.to,
            message=request.text
        )
        
        # Store the message in vector database
        await vector_service.add_message(
            contact_id=request.to,
            text=request.text,
            sender=request.PHONE_NUMBER_ID,
            receiver=request.to,
            timestamp=None
        )
        
        # Also process for meeting-related actions on outgoing messages
        try:
            contact_name = request.to
            meeting_result = await gemini_service.handle_meeting_request(
                message=request.text,
                contact_name=contact_name,
                phone_number=request.to
            )
            if meeting_result.get("is_meeting"):
                await sio.emit('meeting_confirmed', {
                    'from': request.PHONE_NUMBER_ID,
                    'contact_name': contact_name,
                    'message': meeting_result.get("response"),
                    'meeting_info': meeting_result.get("meeting_info"),
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error processing outgoing meeting logic: {e}")

        return result
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-gemini-reply")
async def generate_gemini_reply(request: GeminiReplyRequest):
    """Generate a response using Gemini AI"""
    try:
        response = await gemini_service.generate_response(request.prompt)
        return {"text": response}
    except Exception as e:
        logger.error(f"Error generating Gemini reply: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embedding")
async def create_embedding(request: EmbeddingRequest):
    """Create embeddings for text"""
    try:
        embedding = await gemini_service.create_embeddings(request.text)
        return {"embedding": embedding}
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create-google-meet")
async def create_google_meet(request: GoogleMeetRequest):
    """Create a Google Meet meeting"""
    try:
        result = await google_service.create_meeting(request.tokens.dict(), request.event.dict())
        return {"meetLink": result["meeting_link"], **result}
    except Exception as e:
        logger.error(f"Error creating Google Meet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mcp/send")
async def mcp_send(request: MCPSendRequest):
    """Process MCP send command"""
    try:
        result = await end_message_mcp.process_command(
            command=request.command,
            aliases=request.aliases,
            whatsapp_token=request.WHATSAPP_TOKEN,
            phone_number_id=request.PHONE_NUMBER_ID
        )
        return result
    except Exception as e:
        logger.error(f"Error in MCP send: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WhatsApp Webhook endpoints
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    """Verify WhatsApp webhook"""
    try:
        challenge = whatsapp_service.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
        return PlainTextResponse(challenge)
    except ValueError as e:
        logger.error(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receive WhatsApp webhook messages"""
    try:
        payload = await request.json()
        logger.info(f"Received webhook payload: {payload}")
        
        # Parse the webhook payload
        message_data = whatsapp_service.parse_webhook_payload(payload)
        
        if message_data:
            # Emit to connected clients
            await sio.emit('newMessage', payload)
            
            # Process with auto-reply MCP if needed
            # Note: This would need additional configuration for auto-reply settings
            # For now, we'll just log and emit the message
            contact_name = message_data.get('contact_name', message_data['from'])
            logger.info(f"Message from {contact_name} ({message_data['from']}): {message_data['text']}")
            
            # Store the incoming message
            await vector_service.add_message(
                contact_id=message_data['from'],
                text=message_data['text'],
                sender=message_data['from'],
                receiver="business",  # This should be your business phone number
                timestamp=message_data.get('timestamp')
            )
            
            # Todo processing removed
            
            # Handle meeting requests comprehensively
            meeting_result = await gemini_service.handle_meeting_request(
                message=message_data['text'],
                contact_name=contact_name,
                phone_number=message_data['from']
            )
            
            if meeting_result.get("is_meeting", False):
                logger.info(f"Meeting handled: {meeting_result}")
                
                # Emit to UI
                await sio.emit('meeting_confirmed', {
                    'from': message_data['from'],
                    'contact_name': contact_name,
                    'message': meeting_result.get("response"),
                    'meeting_info': meeting_result.get("meeting_info"),
                    'timestamp': datetime.now().isoformat()
                })
                
                # If WhatsApp credentials are configured, send confirmation to user
                if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
                    try:
                        send_res = await whatsapp_service.send_message(
                            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
                            access_token=settings.WHATSAPP_ACCESS_TOKEN,
                            to=message_data['from'],
                            message=meeting_result.get("response")
                        )
                        # Store in vector DB
                        await vector_service.add_message(
                            contact_id=message_data['from'],
                            text=meeting_result.get("response"),
                            sender=settings.WHATSAPP_PHONE_NUMBER_ID,
                            receiver=message_data['from'],
                            timestamp=message_data.get('timestamp')
                        )
                        logger.info(f"Meeting confirmation sent via WhatsApp: {send_res}")
                    except Exception as send_err:
                        logger.error(f"Failed to send meeting confirmation: {send_err}")

                logger.info(f"Meeting confirmation sent: {meeting_result.get('response')}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

# Auto-reply endpoint for manual triggering
@app.post("/api/auto-reply")
async def trigger_auto_reply(request: AutoReplyRequest):
    """Manually trigger auto-reply for a message"""
    try:
        result = await auto_reply_mcp.process_incoming_message(
            from_number=request.from_number,
            message_text=request.message_text,
            business_description=request.business_description,
            whatsapp_token=request.whatsapp_token,
            phone_number_id=request.phone_number_id,
            auto_reply_enabled=request.auto_reply_enabled,
            contact_auto_reply_settings=request.contact_auto_reply_settings
        )
        return result
    except Exception as e:
        logger.error(f"Error in auto-reply: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Todo endpoints removed

# Meeting endpoints
@app.post("/api/schedule-meeting")
async def schedule_meeting(request: ScheduleMeetingRequest):
    """Schedule a meeting and send invite"""
    try:
        result = await meeting_mcp.process_meeting_request(
            command=request.command,
            contact_aliases=request.contact_aliases,
            google_tokens=request.google_tokens,
            whatsapp_token=request.whatsapp_token,
            phone_number_id=request.phone_number_id
        )
        return result
    except Exception as e:
        logger.error(f"Error scheduling meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Conversation history endpoints
@app.get("/api/conversations/{contact_id}")
async def get_conversation_history(contact_id: str, limit: int = 50):
    """Get conversation history for a contact"""
    try:
        history = await vector_service.get_conversation_history(contact_id, limit)
        return {"conversation": history}
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contacts")
async def get_all_contacts():
    """Get list of all contacts"""
    try:
        contacts = await vector_service.get_all_contacts()
        return {"contacts": contacts}
    except Exception as e:
        logger.error(f"Error getting contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Contact name management endpoints
@app.get("/api/contacts/names")
async def get_contact_names():
    """Get all contact name mappings"""
    try:
        contact_names = contact_service.get_all_contacts()
        return {"contact_names": contact_names}
    except Exception as e:
        logger.error(f"Error getting contact names: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/contacts/{phone_number}/name")
async def set_contact_name(phone_number: str, request: Dict[str, str]):
    """Set or update contact name"""
    try:
        name = request.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        
        contact_service.set_contact_name(phone_number, name)
        return {"status": "success", "phone_number": phone_number, "name": name}
    except Exception as e:
        logger.error(f"Error setting contact name: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/contacts/{phone_number}/name")
async def remove_contact_name(phone_number: str):
    """Remove custom contact name (revert to phone number)"""
    try:
        contact_service.remove_contact_name(phone_number)
        return {"status": "success", "phone_number": phone_number}
    except Exception as e:
        logger.error(f"Error removing contact name: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/contacts/{phone_number}/name")
async def get_contact_name(phone_number: str):
    """Get contact name for specific phone number"""
    try:
        name = contact_service.get_contact_name(phone_number)
        return {"phone_number": phone_number, "name": name}
    except Exception as e:
        logger.error(f"Error getting contact name: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Vector search endpoint
@app.post("/api/search")
async def search_messages(request: SearchMessagesRequest):
    """Search for similar messages"""
    try:
        results = await vector_service.search_similar_messages(
            query_text=request.query,
            contact_id=request.contact_id,
            n_results=request.n_results
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Auth endpoints
@app.get("/auth/google")
async def google_auth():
    """Get Google OAuth URL"""
    try:
        auth_url = google_service.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error getting Google auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/google/callback")
async def google_auth_callback(code: str):
    """Handle Google OAuth callback"""
    try:
        tokens = google_service.exchange_code_for_tokens(code)
        # Persist tokens for server-side scheduled actions
        try:
            google_service.save_tokens(tokens)
        except Exception as e:
            logger.error(f"Failed to persist Google tokens: {e}")
        return {"tokens": tokens}
    except Exception as e:
        logger.error(f"Error in Google auth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# AI Agent endpoints
@app.post("/api/ai-agent/chat")
async def ai_agent_chat(request: dict):
    """Chat with AI agent"""
    try:
        from services.context import ai_agent_context
        
        user_input = request.get("message", "")
        user_context = request.get("context", {})
        
        if not user_input.strip():
            return {"success": False, "error": "Message cannot be empty"}
        
        result = await ai_agent_context.process_user_input(user_input, user_context)
        
        # Emit to Socket.IO for real-time updates
        await sio.emit('ai_agent_response', {
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in AI agent chat: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/ai-agent/history")
async def get_ai_agent_history():
    """Get AI agent conversation history"""
    try:
        from services.context import ai_agent_context
        
        history = ai_agent_context.get_conversation_history()
        return {"success": True, "history": history}
        
    except Exception as e:
        logger.error(f"Error getting AI agent history: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/ai-agent/clear-history")
async def clear_ai_agent_history():
    """Clear AI agent conversation history"""
    try:
        from services.context import ai_agent_context
        
        success = ai_agent_context.clear_conversation_history()
        
        # Emit to Socket.IO for real-time updates
        await sio.emit('ai_agent_history_cleared', {
            'timestamp': datetime.now().isoformat()
        })
        
        return {"success": success}
        
    except Exception as e:
        logger.error(f"Error clearing AI agent history: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(
        "main:socket_app",  # Use socket_app instead of app
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )