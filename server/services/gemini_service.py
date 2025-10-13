import google.generativeai as genai
from typing import List
import logging
from config import settings

# Configure Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Prefer configured embedding model, fallback to a widely available default
        try:
            from config import settings
            self.embedding_model = getattr(settings, 'EMBEDDING_MODEL', None) or 'models/embedding-001'
        except Exception:
            self.embedding_model = 'models/embedding-001'
    
    async def generate_response(self, prompt: str) -> str:
        """Generate response using Gemini 2.5 Flash"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    async def create_embeddings(self, text: str) -> List[float]:
        """Create embeddings for text using Gemini embedding model"""
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text
            )
            # google-generativeai returns { 'embedding': { 'values': [...] } } in many versions
            emb = result.get('embedding') if isinstance(result, dict) else getattr(result, 'embedding', None)
            if isinstance(emb, dict) and 'values' in emb:
                return emb['values']
            # Some versions may already provide a list
            if isinstance(emb, list):
                return emb
            # As a last resort, try accessing attribute
            vals = getattr(emb, 'values', None)
            if isinstance(vals, list):
                return vals
            raise Exception('Unexpected embedding response shape')
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            # Fallback: deterministic local embedding using character hashing
            # This avoids 500s in development or when API key isn't set
            logger.warning("Falling back to local embedding (dev mode)")
            import math
            import hashlib
            h = hashlib.sha256((text or '').encode('utf-8')).digest()
            # Produce a fixed-length vector (e.g., 64 dims) from the hash
            dims = 64
            vec = [0.0] * dims
            for i, b in enumerate(h):
                vec[i % dims] += (b / 255.0)
            # Normalize
            norm = math.sqrt(sum(v*v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            return vec
    
    async def extract_meeting_info(self, message: str) -> dict:
        """Extract meeting information from message"""
        prompt = f"""
        Analyze this message and extract any meeting/appointment information:
        "{message}"
        
        Look for keywords like: meeting, schedule, appointment, call, meet, tomorrow, today, time, PM, AM, date
        
        Return ONLY a valid JSON object with these exact keys:
        - "has_meeting": true or false
        - "date": "YYYY-MM-DD" or null
        - "time": "HH:MM" or null  
        - "meeting_link": "link" or null
        - "description": "brief description" or null
        
        Example responses:
        {{"has_meeting": true, "date": "2025-10-13", "time": "14:00", "meeting_link": null, "description": "Meeting request"}}
        {{"has_meeting": false, "date": null, "time": null, "meeting_link": null, "description": null}}
        
        CRITICAL: Return ONLY the JSON object, no other text, no explanations, no markdown.
        """
        
        try:
            response = await self.generate_response(prompt)
            response = response.strip()
            
            # Clean up any potential formatting
            response = response.replace('```json', '').replace('```', '').strip()
            
            # Try to find JSON in the response
            import json
            import re
            
            # Look for JSON object pattern
            json_match = re.search(r'\{[^}]*"has_meeting"[^}]*\}', response)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            else:
                # Try parsing the whole response
                return json.loads(response)
                
        except Exception as e:
            logger.error(f"Meeting extraction error: {e}")
            logger.error(f"Response was: {response if 'response' in locals() else 'No response'}")
            
            # Fallback: simple keyword detection
            message_lower = message.lower()
            meeting_keywords = ['meeting', 'schedule', 'appointment', 'call', 'meet', 'book', 'reserve']
            time_keywords = ['tomorrow', 'today', 'pm', 'am', 'o\'clock', 'time', 'at']
            
            has_meeting_keyword = any(keyword in message_lower for keyword in meeting_keywords)
            has_time_keyword = any(keyword in message_lower for keyword in time_keywords)
            
            return {
                "has_meeting": has_meeting_keyword and has_time_keyword,
                "date": None,
                "time": None,
                "meeting_link": None,
                "description": "Meeting detected via keyword matching" if has_meeting_keyword and has_time_keyword else None
            }
    
    async def generate_meeting_invite(self, meeting_info: dict, contact_name: str = None) -> str:
        """Generate a professional meeting invite message"""
        date = meeting_info.get('date', 'TBD')
        time = meeting_info.get('time', 'TBD')
        link = meeting_info.get('meeting_link', '')
        formatted_date = meeting_info.get('formatted_date', date)
        formatted_time = meeting_info.get('formatted_time', time)
        
        prompt = f"""
        Someone asked for a meeting. Confirm it professionally but casually like a human would on WhatsApp.
        
        Details:
        - Date: {formatted_date}
        - Time: {formatted_time}
        - Meeting Link: {link}
        
        Write a quick, professional confirmation that sounds natural and human. 
        Be brief but include enthusiasm. DO NOT include the link in your response - it will be added separately.
        
        Good examples:
        ✅ "Perfect! I've scheduled our meeting for {formatted_date} at {formatted_time}. Looking forward to it!"
        ✅ "Great! Meeting confirmed for {formatted_date} at {formatted_time}. See you then!"
        ✅ "Sounds good! I've set up our meeting for {formatted_date} at {formatted_time}."
        
        Bad examples (don't do these):
        ❌ Including the meeting link in the message
        ❌ "Here's a meeting invite:" or similar meta-commentary
        ❌ Overly formal business language
        ❌ Too many details or explanations
        
        Write ONLY the confirmation message. Be human, brief, professional:
        """
        
        response = await self.generate_response(prompt)
        
        # Clean up any potential headers or prefixes
        response = response.strip()
        
        # Remove common prefixes more aggressively
        prefixes_to_remove = [
            "Here's a meeting invite:",
            "Meeting invitation:",
            "Invite message:",
            "Here's the invite:",
            "Meeting invite:",
            "Draft invite:",
            "Perfect! Here's what I'd send:",
            "I'd respond with:",
            "Here's a casual confirmation:",
            "Sure! Here's a quick",
            "Here's the confirmation:",
            "Meeting confirmation:",
            "Okay, here's a draft reply:",
            "Here's a professional confirmation:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()
                break
        
        # Remove quotes if the entire response is wrapped in them
        if (response.startswith('"') and response.endswith('"')) or (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        return response
        
        # If no link in response but we have one, add it
        if link and link not in response and 'http' not in response:
            response = f"{response}\n\nMeeting link: {link}"
        
        return response
    
    async def handle_meeting_request(self, message: str, contact_name: str, phone_number: str) -> dict:
        """Comprehensive meeting handling with Google Calendar and todo creation"""
        try:
            # Extract meeting information
            meeting_info = await self.extract_meeting_info(message)
            
            if not meeting_info.get("has_meeting", False):
                return {"is_meeting": False, "response": None}
            
            logger.info(f"Meeting detected: {meeting_info}")
            
            # Parse the meeting details
            from datetime import datetime, timedelta
            import re
            
            # Handle relative dates like "today", "tomorrow"
            if meeting_info.get("date"):
                meeting_date = meeting_info["date"]
            else:
                # Try to extract from message
                today = datetime.now()
                if "today" in message.lower():
                    meeting_date = today.strftime("%Y-%m-%d")
                elif "tomorrow" in message.lower():
                    tomorrow = today + timedelta(days=1)
                    meeting_date = tomorrow.strftime("%Y-%m-%d")
                else:
                    meeting_date = today.strftime("%Y-%m-%d")  # Default to today
            
            # Parse time
            meeting_time = meeting_info.get("time")
            if not meeting_time:
                # Try to extract time from message
                time_match = re.search(r'(\d{1,2})\s*(pm|am)', message.lower())
                if time_match:
                    hour = int(time_match.group(1))
                    is_pm = time_match.group(2) == 'pm'
                    if is_pm and hour != 12:
                        hour += 12
                    elif not is_pm and hour == 12:
                        hour = 0
                    meeting_time = f"{hour:02d}:00"
                else:
                    meeting_time = "17:00"  # Default to 5 PM
            
            # Create Google Calendar event and get meeting link
            try:
                from services.google_service import google_service
                
                # Prefer real calendar creation if tokens available
                tokens = google_service.get_saved_tokens()
                if tokens:
                    # Build RFC3339 timestamps in UTC (naive conversion assuming local time ~ UTC for simplicity)
                    start_rfc3339 = f"{meeting_date}T{meeting_time}:00Z"
                    # Default 60 minutes
                    from datetime import datetime as _dt
                    hours, minutes = map(int, meeting_time.split(':'))
                    # We won't compute exact end in UTC here; add 60 minutes to HH:MM
                    end_hours = hours + 1
                    end_rfc3339 = f"{meeting_date}T{end_hours:02d}:{minutes:02d}:00Z"
                    event_details = {
                        'summary': f"Meeting with {contact_name}",
                        'description': f"WhatsApp meeting request from {contact_name} ({phone_number})",
                        'start': start_rfc3339,
                        'end': end_rfc3339,
                        'attendees': []
                    }
                    created = await google_service.create_meeting(tokens, event_details)
                    meeting_link = created.get("meeting_link") or created.get("meet_link") or ""
                    event_id = created.get("event_id")
                else:
                    # Fallback: simulated business meeting
                    calendar_event = await google_service.create_business_meeting(
                        title=f"Meeting with {contact_name}",
                        start_date=meeting_date,
                        start_time=meeting_time,
                        duration_minutes=60,
                        description=f"WhatsApp meeting request from {contact_name} ({phone_number})"
                    )
                    meeting_link = calendar_event.get("meet_link", "")
                    event_id = calendar_event.get("event_id", "")
                
            except Exception as e:
                logger.error(f"Error creating calendar event: {e}")
                meeting_link = "https://meet.google.com/new"  # Fallback link
                event_id = None
            
            # Todo creation removed
            
            # Generate confirmation message
            meeting_info_with_link = {
                **meeting_info,
                "meeting_link": meeting_link,
                "date": meeting_date,
                "time": meeting_time,
                "formatted_date": self._format_date_for_message(meeting_date),
                "formatted_time": self._format_time_for_message(meeting_time)
            }
            
            confirmation_message = await self.generate_meeting_invite(
                meeting_info=meeting_info_with_link,
                contact_name=contact_name
            )
            
            # Enhance the message with professional details
            if meeting_link and meeting_link != "https://meet.google.com/new":
                # Format a professional meeting confirmation
                formatted_date = self._format_date_for_message(meeting_date)
                formatted_time = self._format_time_for_message(meeting_time)
                
                enhanced_message = f"{confirmation_message}\n\n📅 {formatted_date} at {formatted_time}\n🔗 {meeting_link}"
                
                return {
                    "is_meeting": True,
                    "response": enhanced_message,
                    "meeting_info": meeting_info_with_link,
                    "calendar_event_id": event_id
                }
            else:
                return {
                    "is_meeting": True,
                    "response": confirmation_message,
                    "meeting_info": meeting_info_with_link,
                    "calendar_event_id": event_id
                }
            
        except Exception as e:
            logger.error(f"Error handling meeting request: {e}")
            return {
                "is_meeting": False,
                "response": "Sure! Let me check my calendar and get back to you with the meeting details.",
                "error": str(e)
            }
    
    def _format_date_for_message(self, date_str: str) -> str:
        """Format date string for human-readable messages"""
        try:
            from datetime import datetime, timedelta
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now().date()
            
            if date_obj.date() == today:
                return "Today"
            elif date_obj.date() == today + timedelta(days=1):
                return "Tomorrow"
            else:
                return date_obj.strftime("%B %d, %Y")  # e.g., "December 15, 2024"
        except:
            return date_str
    
    def _format_time_for_message(self, time_str: str) -> str:
        """Format time string for human-readable messages"""
        try:
            from datetime import datetime
            time_obj = datetime.strptime(time_str, "%H:%M")
            return time_obj.strftime("%I:%M %p")  # e.g., "02:00 PM"
        except:
            return time_str
    
    async def generate_auto_reply(self, message: str, conversation_history: str, business_description: str) -> str:
        """Generate professional auto-reply based on context"""
        prompt = f"""
        Reply naturally like a real person would — short, clear, and human. 
        Generate a single response without any extra commentary or options.
        I'll simply copy your whole response and paste to customer chat as reply,
        so write a short 2-4 line reply without any single character other then a single reply
        (not even the single/double quotes around it.)
        You are texting back on WhatsApp. You work for: {business_description}
        Last messages:
        {conversation_history}
        They just said: "{message}"
        """
          
        response = await self.generate_response(prompt)
        
        # Clean up any potential headers or prefixes
        response = response.strip()
        
        # Remove common prefixes that might appear
        prefixes_to_remove = [
            "Here's a draft reply:",
            "Here's a reply:",
            "Draft reply:",
            "Reply:",
            "Response:",
            "Message:",
            "Okay, here's a draft reply:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()
                break
        
        # Remove markdown formatting
        import re
        # Remove bold (**text** or __text__)
        response = re.sub(r'\*\*(.*?)\*\*', r'\1', response)
        response = re.sub(r'__(.*?)__', r'\1', response)
        # Remove italic (*text* or _text_)
        response = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'\1', response)
        response = re.sub(r'(?<!_)_(?!_)([^_]+)_(?!_)', r'\1', response)
        # Remove any remaining asterisks used for emphasis
        response = re.sub(r'\*', '', response)
        
        # Remove quotes if the entire response is wrapped in them
        if (response.startswith('"') and response.endswith('"')) or (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        # Additional cleaning - remove any remaining quotes at the start/end
        response = response.strip('"').strip("'").strip()
        
        # Remove any "Option X" patterns and everything after
        response = re.sub(r'Option \d+.*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any numbered lists and everything after
        response = re.sub(r'^\d+\..*$', '', response, flags=re.MULTILINE | re.IGNORECASE)
        response = re.sub(r'\n\d+\..*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any analysis or explanation patterns
        response = re.sub(r'\n\s*\*\*Why.*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        response = re.sub(r'\n\s*I would recommend.*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        response = re.sub(r'\n\s*Good luck!.*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        response = re.sub(r'\n\s*\*.*?\*.*$', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any remaining meta-commentary
        response = re.sub(r'(Here\'s|Here are).*?:', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^.*?draft.*?:', '', response, flags=re.IGNORECASE)
        
        # Remove anything that looks like options or suggestions
        response = re.sub(r'(Option|Choice|Alternative).*?[:\-].*$', '', response, flags=re.MULTILINE | re.IGNORECASE)
        response = re.sub(r'\*\*.*?\*\*.*?:', '', response, flags=re.IGNORECASE)
        
        # Remove parenthetical explanations
        response = re.sub(r'\([^)]*\)', '', response)
        
        # If response starts with a number or option marker, take only the first line
        if re.match(r'^\d+\.', response.strip()):
            response = response.split('\n')[0]
            response = re.sub(r'^\d+\.\s*', '', response)
        
        # Take only the first sentence if there are multiple sentences with options
        if 'option' in response.lower() or 'choice' in response.lower():
            sentences = response.split('.')
            if sentences:
                response = sentences[0].strip() + '.'
        
        # Final aggressive quote removal
        while (response.startswith('"') and response.endswith('"')) or (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        return response.strip()

# Global instance
gemini_service = GeminiService()