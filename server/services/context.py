import re
import logging
from typing import Dict, Any
from services.gemini_service import gemini_service
from services.contact_service import contact_service
from services.mcp_services import end_message_mcp
from services.whatsapp_service import whatsapp_service
from config import settings
from services.google_service import google_service

logger = logging.getLogger(__name__)

class AIAgentContext:
    """AI Agent that understands user intent and executes appropriate actions"""
    
    def __init__(self):
        self.name = "ai_agent_context"
        self.conversation_history = []
    
    async def process_user_input(self, user_input: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process user input and determine the appropriate action
        """
        try:
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "message": user_input,
                "timestamp": self._get_timestamp()
            })
            
            # Analyze intent using Gemini
            intent_analysis = await self._analyze_intent(user_input)
            
            # Route to appropriate handler based on intent
            result = await self._route_action(intent_analysis, user_input, user_context or {})
            
            # Add agent response to history
            self.conversation_history.append({
                "role": "agent",
                "message": result.get("response", "Action completed"),
                "timestamp": self._get_timestamp(),
                "action_type": result.get("action_type"),
                "details": result.get("details", {})
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI agent context: {e}")
            error_response = f"Sorry, I encountered an error: {str(e)}"
            self.conversation_history.append({
                "role": "agent",
                "message": error_response,
                "timestamp": self._get_timestamp(),
                "action_type": "error"
            })
            return {
                "success": False,
                "response": error_response,
                "action_type": "error"
            }
    
    async def _analyze_intent(self, user_input: str) -> Dict[str, Any]:
        """Use Gemini to analyze user intent"""
        prompt = f'''
        Analyze this user input and determine the intent. Respond with JSON only.
        
        User input: "{user_input}"
        
        Possible intents:
        1. "send_message" - wants to send a message to someone (mentions name/number)
        2. "schedule_meeting" - wants to schedule a meeting with someone
    3. "general_chat" - general conversation or questions
        
        Look for:
        - Names or phone numbers (indicates send_message or schedule_meeting)
        - Meeting/appointment keywords (schedule_meeting)
        - Questions or general statements (general_chat)
        
        Return JSON format:
        {{
            "intent": "send_message|schedule_meeting|general_chat",
            "confidence": 0.8,
            "extracted_info": {{
                "contact_name": "name if mentioned",
                "contact_number": "number if mentioned", 
                "message_content": "message to send if applicable",
                "meeting_details": "meeting info if applicable"
            }}
        }}
        '''
        
        try:
            response = await gemini_service.generate_response(prompt)
            # Clean response and parse JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:-3]
            elif response.startswith('```'):
                response = response[3:-3]
            
            import json
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error analyzing intent: {e}")
            # Fallback intent analysis
            return self._fallback_intent_analysis(user_input)
    
    def _fallback_intent_analysis(self, user_input: str) -> Dict[str, Any]:
        """Fallback intent analysis using regex patterns"""
        user_lower = user_input.lower()
        
        # Check for send message patterns
        send_patterns = [r'send.*to\s+(\w+)', r'message.*(\w+)', r'tell.*(\w+)']
        for pattern in send_patterns:
            if re.search(pattern, user_lower):
                return {
                    "intent": "send_message",
                    "confidence": 0.7,
                    "extracted_info": {"message_content": user_input}
                }
        
        # Check for meeting patterns
        meeting_patterns = [r'meeting.*with', r'schedule.*meeting', r'meet.*with', r'appointment']
        for pattern in meeting_patterns:
            if re.search(pattern, user_lower):
                return {
                    "intent": "schedule_meeting",
                    "confidence": 0.7,
                    "extracted_info": {"meeting_details": user_input}
                }
        
        return {
            "intent": "general_chat",
            "confidence": 0.5,
            "extracted_info": {}
        }
    
    async def _route_action(self, intent_analysis: Dict[str, Any], user_input: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Route to appropriate action handler"""
        intent = intent_analysis.get("intent", "general_chat")
        extracted_info = intent_analysis.get("extracted_info", {})
        
        if intent == "send_message":
            return await self._handle_send_message(user_input, extracted_info, user_context)
        elif intent == "schedule_meeting":
            return await self._handle_schedule_meeting(user_input, extracted_info, user_context)
        else:
            return await self._handle_general_chat(user_input, extracted_info)
    
    async def _handle_send_message(self, user_input: str, extracted_info: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle sending message to someone"""
        try:
            import json as _json
            
            # Build aliases map name->phone (lowercase names) early so we can share with Gemini for fuzzy resolution
            aliases: Dict[str, str] = {}
            ctx_aliases = (user_context.get('aliases') or {}) if isinstance(user_context, dict) else {}
            if ctx_aliases:
                aliases.update({str(k).lower(): str(v) for k, v in ctx_aliases.items()})
            else:
                try:
                    phone_to_name = contact_service.get_all_contacts()  # phone -> name
                    for phone, name in phone_to_name.items():
                        if name:
                            aliases[name.lower()] = phone
                    for phone in phone_to_name.keys():
                        aliases[phone.lower()] = phone
                except Exception:
                    pass

            # Prepare a compact contacts list for the prompt: name->number pairs (up to 150 entries)
            contacts_for_prompt = []
            seen_pairs = set()
            # extract likely human names (non-numeric keys) from aliases
            for key, val in list(aliases.items())[:1000]:
                # key is lowercased; keep as-is for matching
                if any(ch.isalpha() for ch in key):
                    pair = (key, val)
                    if pair not in seen_pairs:
                        contacts_for_prompt.append({"name": key, "number": val})
                        seen_pairs.add(pair)
                # also include raw numbers as self-maps to help the model
                elif key.isdigit():
                    pair = (key, key)
                    if pair not in seen_pairs:
                        contacts_for_prompt.append({"name": key, "number": key})
                        seen_pairs.add(pair)
                if len(contacts_for_prompt) >= 150:
                    break
            contacts_json_str = _json.dumps(contacts_for_prompt)

            # Use Gemini to extract proper message and resolve recipient using provided contacts list
            prompt = f'''
            Extract message sending information from this request and resolve the recipient using the provided contacts list.
            Request: "{user_input}"
            
            Contacts (array of objects):
            {contacts_json_str}
            
            Rules:
            - Prefer the closest matching contact name from the provided list (handle typos like "Jhon" -> "john").
            - If multiple possible matches, choose the most likely one by string similarity.
            - If a phone number is explicitly provided in the request, use it.
            - If you cannot determine a recipient, set is_valid_request=false.
            
            Return JSON with:
            {{
                "recipient_name": "name string extracted from the user request (as written)",
                "recipient_number": "phone number if explicitly in the request (else empty)",
                "resolved_recipient_name": "a name from the Contacts list that best matches, or empty if none",
                "resolved_recipient_number": "the number from the Contacts list for the resolved name, or empty",
                "message_to_send": "the actual message content to send",
                "is_valid_request": true/false
            }}
            '''
            
            response = await gemini_service.generate_response(prompt)
            
            # Clean and parse response
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:-3]
            elif response.startswith('```'):
                response = response[3:-3]
            
            message_info = _json.loads(response)
            
            if not message_info.get("is_valid_request", False):
                return {
                    "success": False,
                    "response": "I couldn't understand who you want to send a message to. Please specify a name or number.",
                    "action_type": "send_message_failed"
                }
            
            # Get professional message version
            professional_message = await self._make_message_professional(message_info.get("message_to_send", ""))

            # Determine WhatsApp credentials (prefer user_context)
            whatsapp_cfg = (user_context.get('whatsapp') or {}) if isinstance(user_context, dict) else {}
            whatsapp_token = whatsapp_cfg.get('token') or settings.WHATSAPP_ACCESS_TOKEN or ""
            phone_number_id = whatsapp_cfg.get('phone_number_id') or settings.WHATSAPP_PHONE_NUMBER_ID or ""
            if not whatsapp_token or not phone_number_id:
                return {
                    "success": False,
                    "response": "WhatsApp credentials are not configured on the server.",
                    "action_type": "send_message_failed"
                }

            # Resolve recipient phone for frontend update
            # Resolve recipient phone with priority to Gemini's resolution
            recipient_phone = None
            resolved_name = str(message_info.get("resolved_recipient_name", "") or "").strip()
            resolved_number = str(message_info.get("resolved_recipient_number", "") or "").strip()
            explicit_number = str(message_info.get("recipient_number", "") or "").strip()

            if resolved_number:
                recipient_phone = resolved_number
            elif resolved_name:
                recipient_phone = aliases.get(resolved_name.lower())
            if not recipient_phone:
                # fallback to mapping original extracted recipient_name or explicit number
                recipient_phone = (
                    aliases.get(str(message_info.get("recipient_name", "")).lower())
                    or explicit_number
                    or None
                )

            # Try to send via MCP (correct API)
            target_for_command = resolved_name or message_info.get("recipient_name", "") or (recipient_phone or "")
            send_command = f'send "{professional_message}" to {target_for_command}'
            mcp_result = await end_message_mcp.process_command(
                command=send_command,
                aliases=aliases,
                whatsapp_token=whatsapp_token,
                phone_number_id=phone_number_id
            )
            
            if mcp_result.get("success"):
                return {
                    "success": True,
                    "response": f"✅ Message sent to {message_info.get('recipient_name')}: {professional_message}",
                    "action_type": "send_message",
                    "details": {
                        "recipient": resolved_name or message_info.get("recipient_name"),
                        "recipient_phone": recipient_phone,
                        "message": professional_message,
                        "mcp_response": mcp_result
                    }
                }
            else:
                return {
                    "success": False,
                    "response": f"❌ Failed to send message to {message_info.get('recipient_name')}: {mcp_result.get('error', 'Unknown error')}",
                    "action_type": "send_message_failed",
                    "details": mcp_result
                }
                
        except Exception as e:
            logger.error(f"Error handling send message: {e}")
            return {
                "success": False,
                "response": f"Error sending message: {str(e)}",
                "action_type": "send_message_failed"
            }
    
    async def _handle_schedule_meeting(self, user_input: str, extracted_info: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scheduling a meeting"""
        try:
            # Compute dynamic dates for prompt context
            from datetime import datetime, timedelta
            today_str = datetime.now().strftime('%Y-%m-%d')
            tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

            # Extract meeting details using Gemini
            prompt = f'''
            Extract meeting information from this request:
            "{user_input}"
            
            Return JSON with:
            {{
                "contact_name": "person to meet with",
                "contact_number": "phone number if mentioned",
                "date": "YYYY-MM-DD format (use today's date: {today_str} if relative)",
                "time": "HH:MM format (24-hour)",
                "duration_minutes": 60,
                "title": "Meeting title",
                "is_valid_request": true/false
            }}
            
            For relative dates:
            - "today" = {today_str}
            - "tomorrow" = {tomorrow_str}
            - Default time if not specified: 17:00 (5 PM)
            '''
            
            response = await gemini_service.generate_response(prompt)
            import json
            # Clean and parse response
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:-3]
            elif response.startswith('```'):
                response = response[3:-3]

            meeting_info = json.loads(response)
            
            if not meeting_info.get("is_valid_request", False):
                return {
                    "success": False,
                    "response": "I couldn't understand the meeting details. Please specify who, when, and what time.",
                    "action_type": "schedule_meeting_failed"
                }
            
            # Create Google Meet link
            # Prefer real meeting creation if google tokens provided by client
            meeting_result = None
            try:
                ctx_google = (user_context.get('google_tokens') or {}) if isinstance(user_context, dict) else {}
                if ctx_google and isinstance(ctx_google, dict) and ctx_google.get('access_token'):
                    from datetime import datetime, timedelta
                    start_dt = f"{meeting_info.get('date')}T{meeting_info.get('time')}:00Z"
                    # 60 mins default
                    t = meeting_info.get('time') or '17:00'
                    hh, mm = map(int, t.split(':'))
                    end_hh = (hh + 1) % 24
                    end_dt = f"{meeting_info.get('date')}T{end_hh:02d}:{mm:02d}:00Z"
                    event_details = {
                        'summary': meeting_info.get('title', f"Meeting with {meeting_info.get('contact_name', 'Unknown')}"),
                        'description': f"Meeting scheduled via AI agent with {meeting_info.get('contact_name', 'Unknown')}",
                        'start': start_dt,
                        'end': end_dt,
                        'attendees': []
                    }
                    meeting_result = await google_service.create_meeting(ctx_google, event_details)
                    # normalize key name for downstream
                    if 'meeting_link' in meeting_result and 'meet_link' not in meeting_result:
                        meeting_result['meet_link'] = meeting_result['meeting_link']
                else:
                    raise ValueError('No google tokens')
            except Exception:
                # Fallback to business meeting creator (will create real if saved tokens exist else instant/new)
                meeting_result = await google_service.create_business_meeting(
                    title=meeting_info.get("title", f"Meeting with {meeting_info.get('contact_name', 'Unknown')}"),
                    start_date=meeting_info.get("date"),
                    start_time=meeting_info.get("time"),
                    duration_minutes=meeting_info.get("duration_minutes", 60),
                    description=f"Meeting scheduled via AI agent with {meeting_info.get('contact_name', 'Unknown')}"
                )
            
            # Create calendar event (placeholder/side-effect)
            await self._create_calendar_event(
                f"Meeting with {meeting_info.get('contact_name')} ({meeting_info.get('contact_number', 'No number')})",
                f"{meeting_info.get('date')} at {meeting_info.get('time')} - {meeting_info.get('title', 'Meeting')}",
                meeting_info
            )
            
            meet_link = meeting_result.get("meet_link", "")
            formatted_date = self._format_date_readable(meeting_info.get("date"))
            formatted_time = self._format_time_readable(meeting_info.get("time"))

            # Build response shown in AI panel
            response_msg = f"✅ Meeting scheduled with {meeting_info.get('contact_name')}!\n\n"
            response_msg += f"📅 {formatted_date} at {formatted_time}\n"
            response_msg += f"🔗 {meet_link}\n"
            response_msg += f"📝 Added to your calendar"

            # Build invite message and resolve a recipient phone for frontend reflection
            contact_name = meeting_info.get("contact_name") or ""
            contact_number = meeting_info.get("contact_number") or ""
            recipient_phone = None
            if contact_number and contact_number.strip():
                recipient_phone = contact_number.strip()
            else:
                # Try resolve by name, fallback to name (frontend will try map name->id if needed)
                recipient_phone = contact_service.search_contact_by_name(contact_name) or contact_name

            invite = f"Hi {contact_name}, I've scheduled our meeting on {formatted_date} at {formatted_time}. Here's the Google Meet link: {meet_link}"

            # Also send the meeting invite to the contact on WhatsApp (best-effort)
            try:
                if recipient_phone:
                    whatsapp_cfg = (user_context.get('whatsapp') or {}) if isinstance(user_context, dict) else {}
                    whatsapp_token = whatsapp_cfg.get('token') or settings.WHATSAPP_ACCESS_TOKEN or ""
                    phone_number_id = whatsapp_cfg.get('phone_number_id') or settings.WHATSAPP_PHONE_NUMBER_ID or ""
                    if whatsapp_token and phone_number_id:
                        await whatsapp_service.send_message(
                            phone_number_id=phone_number_id,
                            access_token=whatsapp_token,
                            to=recipient_phone,
                            message=invite
                        )
            except Exception as send_err:
                logger.error(f"Failed to send WhatsApp meeting invite: {send_err}")
            
            return {
                "success": True,
                "response": response_msg,
                "action_type": "schedule_meeting",
                "details": {
                    "meeting_info": meeting_info,
                    "meeting_result": meeting_result,
                    "calendar_added": True,
                    # Extra fields for frontend reflection in chat UI
                    "recipient_phone": recipient_phone,
                    "invite_message": invite
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling schedule meeting: {e}")
            return {
                "success": False,
                "response": f"Error scheduling meeting: {str(e)}",
                "action_type": "schedule_meeting_failed"
            }
    
    # Removed: add_todo handler and related helpers
    
    async def _handle_general_chat(self, user_input: str, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general conversation"""
        try:
            # Generate conversational response
            conversation_context = self._get_recent_conversation()
            
            prompt = f'''
            You are a helpful AI assistant for a WhatsApp business automation system.
            
            Recent conversation:
            {conversation_context}
            
            User just said: "{user_input}"
            
            Respond naturally and helpfully. You can:
            - Answer questions about the system
            - Provide help with commands
            - Have general conversation
            - Suggest actions they can take
            
            Keep responses concise and friendly.
            '''
            
            response = await gemini_service.generate_response(prompt)
            
            return {
                "success": True,
                "response": response,
                "action_type": "general_chat"
            }
            
        except Exception as e:
            logger.error(f"Error handling general chat: {e}")
            return {
                "success": True,
                "response": "I'm here to help! You can ask me to send messages or schedule meetings.",
                "action_type": "general_chat"
            }
    
    async def _make_message_professional(self, message: str) -> str:
        """Make message more professional using Gemini"""
        try:
            prompt = f'''
            Make this message more professional and polite, but keep it natural for WhatsApp:
            "{message}"
            
            Return only the improved message, nothing else.
            '''
            
            response = await gemini_service.generate_response(prompt)
            return response.strip().strip('"\'')
        except:
            return message
    
    # Removed: _add_todo_item (todos removed)
    
    async def _create_calendar_event(self, title: str, description: str, meeting_info: Dict[str, Any]) -> bool:
        """Create calendar event for meeting"""
        try:
            # This would integrate with Google Calendar
            # For now, log the action
            logger.info(f"Would create calendar event: {title} on {meeting_info.get('date')} at {meeting_info.get('time')}")
            return True
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return False
    
    # Removed: _create_calendar_event_for_todo (todos removed)
    
    def _format_date_readable(self, date_str: str) -> str:
        """Format date for human reading"""
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%B %d, %Y")
        except:
            return date_str
    
    def _format_time_readable(self, time_str: str) -> str:
        """Format time for human reading"""
        try:
            from datetime import datetime
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.strftime("%I:%M %p")
        except:
            return time_str
    
    def _get_recent_conversation(self) -> str:
        """Get recent conversation for context"""
        if not self.conversation_history:
            return "No previous conversation."
        
        recent = self.conversation_history[-6:]  # Last 6 messages
        formatted = []
        for msg in recent:
            role = msg["role"].upper()
            formatted.append(f"{role}: {msg['message']}")
        
        return "\n".join(formatted)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_conversation_history(self) -> list:
        """Get full conversation history"""
        return self.conversation_history
    
    def clear_conversation_history(self) -> bool:
        """Clear conversation history"""
        self.conversation_history = []
        return True

# Global instance
ai_agent_context = AIAgentContext()