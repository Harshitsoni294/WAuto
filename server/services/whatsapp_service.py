import requests
import logging
from typing import Dict, Any
from config import settings
from .contact_service import contact_service

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
    
    async def send_message(self, phone_number_id: str, access_token: str, to: str, message: str) -> Dict[str, Any]:
        """Send a WhatsApp message using Meta Cloud API"""
        url = f"{self.base_url}/{phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"WhatsApp API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise Exception(f"Failed to send WhatsApp message: {str(e)}")
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> str:
        """Verify WhatsApp webhook"""
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return challenge
        raise ValueError("Invalid webhook verification")
    
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse incoming WhatsApp webhook payload"""
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            
            if not messages:
                return None
            
            message = messages[0]
            from_number = message.get("from")
            message_id = message.get("id")
            timestamp = message.get("timestamp")
            
            # Extract contact name from webhook if available
            contacts = value.get("contacts", [])
            webhook_name = None
            if contacts:
                contact = contacts[0]
                profile = contact.get("profile", {})
                webhook_name = profile.get("name")
            
            # Update contact name using contact service
            contact_name = contact_service.update_contact_from_webhook(from_number, webhook_name)
            
            # Extract message content
            text_content = None
            if "text" in message:
                text_content = message["text"]["body"]
            elif "button" in message:
                text_content = message["button"]["text"]
            elif "interactive" in message:
                interactive = message["interactive"]
                if "button_reply" in interactive:
                    text_content = interactive["button_reply"]["title"]
                elif "list_reply" in interactive:
                    text_content = interactive["list_reply"]["title"]
            
            return {
                "from": from_number,
                "contact_name": contact_name,
                "message_id": message_id,
                "timestamp": int(timestamp) if timestamp else None,
                "text": text_content or "[Non-text message]",
                "raw_message": message
            }
        except Exception as e:
            logger.error(f"Error parsing webhook payload: {e}")
            return None

# Global instance
whatsapp_service = WhatsAppService()