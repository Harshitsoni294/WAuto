import re
import logging
import json
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
            
            # Build contacts list (phone -> name) and send to Gemini so the LLM
            # can resolve ambiguous recipient names from the full contacts set.
            # We pass the display name exactly as stored locally (no lowercasing)
            contacts_for_prompt = []
            try:
                phone_to_name = contact_service.get_all_contacts()  # phone -> name
                seen = set()
                # Include up to 1000 contacts (can be adjusted). Preserve original display names.
                for phone, name in list(phone_to_name.items())[:1000]:
                    display_name = name if name else phone
                    pair = (display_name, phone)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    contacts_for_prompt.append({"name": display_name, "number": phone})
            except Exception:
                contacts_for_prompt = []

            # Build aliases mapping (name.lower() -> phone) for backwards-compatibility
            # with other components that expect an 'aliases' dict.
            # We include:
            # - full display name -> phone
            # - individual name tokens (first name, last name parts) -> phone
            # - this helps resolving short queries like "harshit" -> "Harshit Soni"
            aliases = {}
            try:
                for p, n in (phone_to_name or {}).items():
                    if not n:
                        continue
                    name_clean = n.strip()
                    key_full = name_clean.lower()
                    # prefer existing mapping (avoid overwriting existing aliases)
                    if key_full not in aliases:
                        aliases[key_full] = p

                    # Add tokens (split by whitespace/punctuation). Map first name token and any token not yet present
                    for token in re.split(r"[\s,.-]+", name_clean):
                        t = token.strip().lower()
                        if not t:
                            continue
                        if t not in aliases:
                            aliases[t] = p

                    # Also map the phone string itself (normalized) for quick lookup
                    aliases[p] = p
            except Exception:
                aliases = {}

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

            # Clean the response and try to parse JSON robustly. Gemini sometimes
            # returns no JSON (quota fallback or plain text). We try:
            # 1. Strip code fences
            # 2. json.loads directly
            # 3. Regex-extract a JSON object and parse that
            # 4. If the response looks like our quota fallback, return a clear failure
            response = (response or "").strip()
            if response.startswith('```json'):
                response = response[7:-3].strip()
            elif response.startswith('```'):
                response = response[3:-3].strip()

            message_info = None
            parse_error = None
            try:
                message_info = _json.loads(response)
            except Exception as e:
                parse_error = e
                logger.debug(f"Direct JSON parse failed for message extraction: {e}; response={response!r}")
                # Try to find a JSON object inside the response
                import re as _re
                m = _re.search(r'\{[\s\S]*\}', response)
                if m:
                    try:
                        message_info = _json.loads(m.group(0))
                    except Exception as e2:
                        logger.debug(f"Regex JSON extract failed: {e2}; extracted={m.group(0)!r}")

            # If we still couldn't parse, detect quota/fallback messages and return a helpful error
            if not message_info:
                # Common fallback text we return on quota errors
                fallback_indicators = ['temporarily unable to generate', 'quota', 'rate limit', 'unable to generate replies']
                low = (response or '').lower()
                if any(ind in low for ind in fallback_indicators):
                    logger.warning("Gemini returned a fallback/quota message while resolving recipient; aborting send_message flow.")
                    return {
                        "success": False,
                        "response": "Cannot send message right now: the AI reply service is temporarily unavailable (quota/limit). Please try again later.",
                        "action_type": "send_message_failed",
                        "details": {"raw_response": response}
                    }

                # Last resort: return parsing error to caller so UI can show a helpful message
                logger.error(f"Failed to parse Gemini response for send-message: {parse_error}; raw_response={response!r}")
                return {
                    "success": False,
                    "response": "I couldn't understand who to send the message to. Please specify the recipient explicitly.",
                    "action_type": "send_message_failed",
                    "details": {"parse_error": str(parse_error), "raw_response": response}
                }
            
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

            # Ensure we have a display name for the UI
            display_name = None
            try:
                if recipient_phone:
                    display_name = contact_service.get_contact_name(recipient_phone)
                if not display_name:
                    display_name = resolved_name or message_info.get('recipient_name')
            except Exception:
                display_name = resolved_name or message_info.get('recipient_name')

            # If MCP didn't actually send the message, try a direct WhatsApp send as a best-effort fallback
            if not mcp_result.get("success"):
                logger.warning(f"MCP failed to send message, attempting direct WhatsApp send. MCP result: {mcp_result}")
                try:
                    if recipient_phone and whatsapp_token and phone_number_id:
                        ws_result = await whatsapp_service.send_message(
                            phone_number_id=phone_number_id,
                            access_token=whatsapp_token,
                            to=recipient_phone,
                            message=professional_message
                        )
                        # ws_result may be None or a dict depending on implementation; normalize
                        ws_ok = isinstance(ws_result, dict) and ws_result.get('success') or (ws_result is None)
                        mcp_result['whatsapp_fallback'] = {'success': bool(ws_ok), 'raw': ws_result}
                    else:
                        mcp_result['whatsapp_fallback'] = {'success': False, 'raw': 'missing_credentials_or_recipient'}
                except Exception as ws_err:
                    logger.error(f"Direct WhatsApp send fallback failed: {ws_err}")
                    mcp_result['whatsapp_fallback'] = {'success': False, 'error': str(ws_err)}
            
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

            # Ensure meet_link is always defined to avoid UnboundLocalError when
            # different code-paths reference it before assignment.
            meet_link = ""

            # Build contacts list (phone -> name) and send to Gemini so the LLM
            # can resolve ambiguous recipient names from the full contacts set.
            contacts_for_prompt = []
            try:
                phone_to_name = contact_service.get_all_contacts()  # phone -> name
                seen = set()
                for phone, name in list(phone_to_name.items())[:1000]:
                    display_name = name if name else phone
                    pair = (display_name, phone)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    contacts_for_prompt.append({"name": display_name, "number": phone})
            except Exception:
                contacts_for_prompt = []

            contacts_json_str = json.dumps(contacts_for_prompt)

            # Extract meeting details using Gemini, and ask it to also choose a recipient
            # and draft a beautiful, personalized invite message
            prompt = f'''
            Extract meeting information from this request and resolve who to invite using the provided contacts list.
            Request: "{user_input}"

            Contacts (array of objects):
            {contacts_json_str}

            Return JSON with:
            {{
                "contact_name": "person to meet with (as mentioned)",
                "contact_number": "phone number if mentioned",
                "resolved_recipient_name": "a name from the Contacts list that best matches, or empty if none",
                "resolved_recipient_number": "the number from the Contacts list for the resolved name, or empty",
                "date": "YYYY-MM-DD format (use today's date: {today_str} if relative)",
                "time": "HH:MM format (24-hour)",
                "duration_minutes": 60,
                "title": "Meeting title",
                "draft_message": "A beautiful, warm, and professional WhatsApp message inviting them to the meeting. Be contextual and natural based on the user's request. Keep it friendly but professional. DO NOT include any placeholder like {{meet_link}} or <meeting_link> - we will add the actual link automatically.",
                "is_valid_request": true/false
            }}

            CRITICAL for draft_message:
            - Write a complete, beautiful message that reads naturally
            - Match the tone and context from the user's request
            - Be warm and personalized (use their name naturally)
            - DO NOT include placeholders like {{meet_link}} or <meeting_link>
            - The system will automatically append the Google Meet link after your message
            - Keep it 2-3 sentences, friendly and professional

            For relative dates:
            - "today" = {today_str}
            - "tomorrow" = {tomorrow_str}
            - Default time if not specified: 17:00 (5 PM)
            '''

            response = await gemini_service.generate_response(prompt)
            # Clean and parse response
            response = (response or "").strip()
            if response.startswith('```json'):
                response = response[7:-3]
            elif response.startswith('```'):
                response = response[3:-3]

            meeting_info = None
            try:
                meeting_info = json.loads(response)
            except Exception as e:
                # Try to regex-extract JSON
                import re as _re
                m = _re.search(r'\{[\s\S]*\}', response)
                if m:
                    try:
                        meeting_info = json.loads(m.group(0))
                    except Exception:
                        meeting_info = None
                if not meeting_info:
                    logger.error(f"Failed to parse meeting extraction from Gemini: {e}; raw={response!r}")
                    return {
                        "success": False,
                        "response": "I couldn't understand the meeting details. Please specify who and when.",
                        "action_type": "schedule_meeting_failed"
                    }
            
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

            # We'll build the response shown in the AI panel after we resolve the recipient
            response_msg = None

            # Determine the recipient: prefer Gemini's resolution if provided
            resolved_name = meeting_info.get('resolved_recipient_name') or ""
            resolved_number = meeting_info.get('resolved_recipient_number') or ""
            contact_name = meeting_info.get("contact_name") or ""
            contact_number = meeting_info.get("contact_number") or ""

            recipient_phone = None
            if resolved_number and str(resolved_number).strip():
                recipient_phone = str(resolved_number).strip()
            elif contact_number and contact_number.strip():
                recipient_phone = contact_number.strip()
            elif resolved_name:
                # try aliases / contact search
                recipient_phone = contact_service.search_contact_by_name(resolved_name) or contact_service.search_contact_by_name(contact_name) or resolved_name
            else:
                recipient_phone = contact_service.search_contact_by_name(contact_name) or contact_name

            # Prepare the invite message: use Gemini-provided draft and append the meet link
            draft = meeting_info.get('draft_message') or meeting_info.get('invite_message') or ''
            
            if draft and draft.strip():
                # Gemini provided a beautiful message - append the link cleanly
                invite = f"{draft.strip()}\n\nJoin: {meet_link}"
            else:
                # Fallback if no draft provided
                invite = f"Hi {contact_name}, I've scheduled our meeting on {formatted_date} at {formatted_time}.\n\nJoin: {meet_link}"

            # Also send the meeting invite to the contact on WhatsApp (best-effort)
            whatsapp_send_success = False
            try:
                if recipient_phone:
                    whatsapp_cfg = (user_context.get('whatsapp') or {}) if isinstance(user_context, dict) else {}
                    whatsapp_token = whatsapp_cfg.get('token') or settings.WHATSAPP_ACCESS_TOKEN or ""
                    phone_number_id = whatsapp_cfg.get('phone_number_id') or settings.WHATSAPP_PHONE_NUMBER_ID or ""
                    
                    logger.info(f"[MEETING] Attempting to send WhatsApp invite to {recipient_phone}")
                    logger.info(f"[MEETING] Token exists: {bool(whatsapp_token)}, Phone ID exists: {bool(phone_number_id)}")
                    
                    if whatsapp_token and phone_number_id:
                        ws_result = await whatsapp_service.send_message(
                            phone_number_id=phone_number_id,
                            access_token=whatsapp_token,
                            to=recipient_phone,
                            message=invite
                        )
                        logger.info(f"[MEETING] WhatsApp send result: {ws_result}")
                        # Optionally record ws_result in meeting_result for UI/debug
                        meeting_result = meeting_result or {}
                        meeting_result['whatsapp_sent'] = True
                        meeting_result['whatsapp_result'] = ws_result
                        whatsapp_send_success = True
                    else:
                        logger.warning(f"[MEETING] Missing WhatsApp credentials - cannot send invite")
                else:
                    logger.warning(f"[MEETING] No recipient phone - cannot send invite")
            except Exception as send_err:
                logger.error(f"[MEETING] Failed to send WhatsApp meeting invite: {send_err}", exc_info=True)
            
            # Resolve display name for UI (prefer contact_service mapping)
            try:
                display_name = contact_service.get_contact_name(recipient_phone) if recipient_phone else (resolved_name or contact_name)
            except Exception:
                display_name = resolved_name or contact_name

            # Build final response message shown to the user
            response_msg = f"✅ Meeting scheduled with {display_name}!\n\n"
            response_msg += f"📅 {formatted_date} at {formatted_time}\n"
            response_msg += f"🔗 {meet_link}\n"
            response_msg += f"📝 Added to your calendar"

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
                    "invite_message": invite,
                    "display_name": display_name,
                    "resolved_recipient_name": resolved_name,
                    "resolved_recipient_number": resolved_number
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