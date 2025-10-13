import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from services.gemini_service import gemini_service
from services.vector_service import vector_service
from services.google_service import google_service
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class MeetingMCP:
    """Message Control Protocol for generating meeting links and sending invites"""
    
    def __init__(self):
        self.name = "meeting_mcp"
        self.description = "Generate meeting links and send meeting invites"
    
    async def process_meeting_request(
        self,
        command: str,
        contact_aliases: Dict[str, str],
        google_tokens: Dict[str, Any],
        whatsapp_token: str,
        phone_number_id: str
    ) -> Dict[str, Any]:
        """
        Process meeting scheduling command
        Example: "schedule meeting with John at 2 PM tomorrow"
        """
        try:
            # Parse the meeting request
            meeting_details = await self._parse_meeting_command(command)
            
            if not meeting_details["success"]:
                return meeting_details
            
            # Create Google Meet event
            event_details = {
                "summary": meeting_details.get("title", "Meeting"),
                "description": meeting_details.get("description", ""),
                "start": meeting_details["start_time"],
                "end": meeting_details["end_time"],
                "attendees": []
            }
            
            meeting_result = await google_service.create_meeting(google_tokens, event_details)
            
            # Generate professional invite message
            invite_message = await gemini_service.generate_meeting_invite(
                meeting_info={
                    "date": meeting_details["date"],
                    "time": meeting_details["time"],
                    "meeting_link": meeting_result["meeting_link"]
                },
                contact_name=meeting_details.get("contact_name")
            )
            
            # Send invite if contact specified
            sent_to = None
            if meeting_details.get("contact_name"):
                contact_id = self._resolve_contact(meeting_details["contact_name"], contact_aliases)
                if contact_id:
                    await whatsapp_service.send_message(
                        phone_number_id=phone_number_id,
                        access_token=whatsapp_token,
                        to=contact_id,
                        message=invite_message
                    )
                    
                    # Store the sent message
                    await vector_service.add_message(
                        contact_id=contact_id,
                        text=invite_message,
                        sender=phone_number_id,
                        receiver=contact_id,
                        timestamp=None
                    )
                    
                    sent_to = meeting_details["contact_name"]
            
            return {
                "success": True,
                "meeting_created": True,
                "meeting_link": meeting_result["meeting_link"],
                "event_id": meeting_result["event_id"],
                "invite_message": invite_message,
                "sent_to": sent_to,
                "meeting_details": meeting_details
            }
            
        except Exception as e:
            logger.error(f"Error in meeting_mcp: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _parse_meeting_command(self, command: str) -> Dict[str, Any]:
        """Parse meeting scheduling command using AI"""
        prompt = f"""
        Parse this meeting scheduling command and extract information:
        "{command}"
        
        Return a JSON object with:
        - success: boolean
        - title: string (meeting title/subject)
        - contact_name: string (person to meet with, if mentioned)
        - date: string (YYYY-MM-DD format)
        - time: string (HH:MM format, 24-hour)
        - start_time: string (ISO format datetime)
        - end_time: string (ISO format datetime, assume 30 min duration)
        - description: string (brief description)
        
        If the command doesn't contain valid meeting information, return {{"success": false, "error": "reason"}}.
        Only return valid JSON, no other text.
        
        Current date/time context: {datetime.now().isoformat()}
        """
        
        try:
            response = await gemini_service.generate_response(prompt)
            import json
            return json.loads(response.strip())
        except Exception as e:
            logger.error(f"Error parsing meeting command: {e}")
            return {
                "success": False,
                "error": "Failed to parse meeting command"
            }
    
    def _resolve_contact(self, name: str, aliases: Dict[str, str]) -> Optional[str]:
        """Resolve contact name to contact ID using aliases"""
        name_lower = name.lower().strip()
        
        # Direct lookup
        if name_lower in aliases:
            return aliases[name_lower]
        
        # Fuzzy search in aliases
        for alias, contact_id in aliases.items():
            if name_lower in alias or alias in name_lower:
                return contact_id
        
        return None

meeting_mcp = MeetingMCP()