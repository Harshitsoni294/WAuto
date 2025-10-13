import re
import logging
from typing import Dict, Any, Optional
from services.whatsapp_service import whatsapp_service
from services.vector_service import vector_service
from services.gemini_service import gemini_service
from services.contact_service import contact_service

logger = logging.getLogger(__name__)

class EndMessageMCP:
    """Message Control Protocol for sending messages to contacts by name"""
    
    def __init__(self):
        self.name = "end_message_mcp"
        self.description = "Send messages to contacts using natural language commands"
    
    async def process_command(
        self, 
        command: str, 
        aliases: Dict[str, str], 
        whatsapp_token: str, 
        phone_number_id: str
    ) -> Dict[str, Any]:
        """
        Process natural language command to send message
        Examples:
        - "send hello to Harshit"
        - "send 'Good morning!' to Shubham"
        - "sent meeting reminder to John"
        """
        try:
            # Parse the command using regex patterns
            message_text, recipient_name = self._parse_send_command(command)
            
            if not message_text or not recipient_name:
                return {
                    "success": False,
                    "error": "Could not parse command. Use format: 'send \"message\" to ContactName'"
                }
            
            # Find the contact using aliases
            contact_id = self._resolve_contact(recipient_name, aliases)
            
            if not contact_id:
                return {
                    "success": False,
                    "error": f"Contact '{recipient_name}' not found in aliases"
                }
            
            # Send the message via WhatsApp
            result = await whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                access_token=whatsapp_token,
                to=contact_id,
                message=message_text
            )
            
            # Store the sent message in vector database
            await vector_service.add_message(
                contact_id=contact_id,
                text=message_text,
                sender=phone_number_id,  # Our business number
                receiver=contact_id,
                timestamp=None  # Will use current timestamp
            )
            
            logger.info(f"Message sent to {recipient_name} ({contact_id}): {message_text}")
            
            return {
                "success": True,
                "message": f"Message sent to {recipient_name}",
                "recipient": recipient_name,
                "contact_id": contact_id,
                "text": message_text,
                "whatsapp_response": result
            }
            
        except Exception as e:
            logger.error(f"Error in end_message_mcp: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_send_command(self, command: str) -> tuple[Optional[str], Optional[str]]:
        """Parse natural language send command"""
        command = command.strip()
        
        # Pattern 1: send "message" to Name
        pattern1 = r'^(?:send|sent)\s+"(.*?)"\s+to\s+(.+)$'
        match = re.match(pattern1, command, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1), match.group(2).strip()
        
        # Pattern 2: send 'message' to Name
        pattern2 = r"^(?:send|sent)\s+'(.*?)'\s+to\s+(.+)$"
        match = re.match(pattern2, command, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1), match.group(2).strip()
        
        # Pattern 3: send message to Name (without quotes)
        pattern3 = r'^(?:send|sent)\s+(.+?)\s+to\s+(.+)$'
        match = re.match(pattern3, command, re.IGNORECASE)
        if match:
            message_part = match.group(1).strip()
            recipient_part = match.group(2).strip()
            # Make sure we don't capture "to" as part of message
            return message_part, recipient_part
        
        return None, None
    
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
        
        # If no alias found, try the name as-is (might be a phone number)
        return name if name else None

# Auto-reply MCP
class AutoReplyMCP:
    """Message Control Protocol for automatic replies"""
    
    def __init__(self):
        self.name = "auto_reply_mcp"
        self.description = "Generate and send automatic replies using AI"
    
    async def process_incoming_message(
        self,
        from_number: str,
        message_text: str,
        business_description: str,
        whatsapp_token: str,
        phone_number_id: str,
        auto_reply_enabled: bool = True,
        contact_auto_reply_settings: Dict[str, bool] = None
    ) -> Dict[str, Any]:
        """Process incoming message and send auto-reply if enabled"""
        try:
            # Store incoming message
            await vector_service.add_message(
                contact_id=from_number,
                text=message_text,
                sender=from_number,
                receiver=phone_number_id,
                timestamp=None
            )
            
            # Determine contact name early for downstream use
            contact_name = contact_service.get_contact_name(from_number) or from_number

            # Check for meeting information in incoming messages and create todos
            await self._process_incoming_meeting_info(message_text, from_number, contact_name)
            
            # Check if auto-reply is enabled globally and for this contact
            if not auto_reply_enabled:
                return {"success": True, "auto_reply_sent": False, "reason": "Auto-reply disabled globally"}
            
            if contact_auto_reply_settings and contact_auto_reply_settings.get(from_number) is False:
                return {"success": True, "auto_reply_sent": False, "reason": "Auto-reply disabled for contact"}

            # First: detect and handle meeting requests comprehensively
            meeting_result = await gemini_service.handle_meeting_request(
                message=message_text,
                contact_name=contact_name,
                phone_number=from_number
            )
            if meeting_result.get("is_meeting"):
                ai_reply = meeting_result.get("response")
            else:
                # Get conversation history
                conversation_history = await vector_service.get_conversation_history(from_number, limit=50)
                # Format conversation for AI
                formatted_history = self._format_conversation_history(conversation_history, phone_number_id)
                # Generate AI reply
                ai_reply = await gemini_service.generate_auto_reply(
                    message=message_text,
                    conversation_history=formatted_history,
                    business_description=business_description
                )
            
            # Send the reply
            result = await whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                access_token=whatsapp_token,
                to=from_number,
                message=ai_reply
            )
            
            # Store the sent reply
            await vector_service.add_message(
                contact_id=from_number,
                text=ai_reply,
                sender=phone_number_id,
                receiver=from_number,
                timestamp=None
            )
            
            logger.info(f"Auto-reply sent to {from_number}: {ai_reply}")
            
            return {
                "success": True,
                "auto_reply_sent": True,
                "reply_text": ai_reply,
                "whatsapp_response": result
            }
            
        except Exception as e:
            logger.error(f"Error in auto_reply_mcp: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_conversation_history(self, history: list, our_number: str) -> str:
        """Format conversation history for AI prompt"""
        if not history:
            return "No previous conversation."
        
        formatted = []
        for msg in history:
            sender_label = "ME" if msg["sender"] == our_number else "THEM"
            timestamp = msg.get("datetime", "")
            formatted.append(f"{sender_label} [{timestamp}]: {msg['text']}")
        
        return "\n".join(formatted)

    async def _process_incoming_meeting_info(self, message_text: str, from_number: str, contact_name: str):
        """Process incoming message for meeting information and create calendar events (todos removed)"""
        try:
            # Check if message contains meeting information
            meeting_keywords = [
                'meeting', 'meet', 'appointment', 'call', 'zoom', 'teams', 
                'google meet', 'skype', 'conference', 'discussion', 'session'
            ]
            
            message_lower = message_text.lower()
            has_meeting_keyword = any(keyword in message_lower for keyword in meeting_keywords)
            
            if not has_meeting_keyword:
                return
            
            # Check for meeting links
            import re
            meeting_link_patterns = [
                r'https://meet\.google\.com/[a-z-]+',
                r'https://zoom\.us/j/\d+',
                r'https://teams\.microsoft\.com/[^\s]+',
                r'https://[^\s]*meet[^\s]*',
            ]
            
            meeting_links = []
            for pattern in meeting_link_patterns:
                links = re.findall(pattern, message_text, re.IGNORECASE)
                meeting_links.extend(links)
            
            # Extract date and time information
            date_time_info = await self._extract_datetime_from_message(message_text)
            
            if meeting_links or date_time_info.get('has_datetime'):
                # Try to create calendar event if we have date/time
                if date_time_info.get('has_datetime'):
                    try:
                        await self._create_calendar_event_from_message(
                            f"Meeting with {contact_name}", f"Message: {message_text}", date_time_info, meeting_links
                        )
                    except Exception as e:
                        logger.error(f"Error creating calendar event from message: {e}")
                
        except Exception as e:
            logger.error(f"Error processing incoming meeting info: {e}")

    async def _extract_datetime_from_message(self, message_text: str) -> dict:
        """Extract date and time information from message"""
        try:
            # Use Gemini to extract date/time info
            prompt = f'''
            Extract date and time information from this message:
            "{message_text}"
            
            Return JSON with:
            {{
                "has_datetime": true/false,
                "date": "YYYY-MM-DD format if found",
                "time": "HH:MM format if found",
                "relative_date": "today/tomorrow/etc if mentioned",
                "confidence": 0.0-1.0
            }}
            
            Today is 2025-10-12. Look for:
            - Specific dates (Dec 15, 15th December, etc.)
            - Relative dates (today, tomorrow, next week)
            - Times (3pm, 15:00, three o'clock)
            '''
            
            response = await gemini_service.generate_response(prompt)
            
            # Clean and parse response
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:-3]
            elif response.startswith('```'):
                response = response[3:-3]
            
            import json
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"Error extracting datetime from message: {e}")
            return {"has_datetime": False}
    
    async def _create_calendar_event_from_message(self, title: str, description: str, 
                                                 date_time_info: dict, meeting_links: list):
        """Create calendar event from message information"""
        try:
            if not date_time_info.get('has_datetime'):
                return
            
            from services.google_service import google_service
            from datetime import datetime, timedelta
            
            # Parse date and time
            date_str = date_time_info.get('date')
            time_str = date_time_info.get('time', '17:00')  # Default to 5 PM
            
            if not date_str:
                # Use relative date
                from datetime import date
                today = date.today()
                if date_time_info.get('relative_date') == 'tomorrow':
                    target_date = today + timedelta(days=1)
                    date_str = target_date.strftime('%Y-%m-%d')
                else:
                    date_str = today.strftime('%Y-%m-%d')
            
            # Create calendar event
            calendar_result = await google_service.create_business_meeting(
                title=title,
                start_date=date_str,
                start_time=time_str,
                duration_minutes=60,
                description=f"{description}\n\nAuto-created from WhatsApp message"
            )
            
            logger.info(f"Created calendar event from message: {title}")
            return calendar_result
            
        except Exception as e:
            logger.error(f"Error creating calendar event from message: {e}")
            raise

# Global instances
end_message_mcp = EndMessageMCP()
auto_reply_mcp = AutoReplyMCP()