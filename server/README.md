# WhatsApp Business Automation Backend

A powerful FastAPI backend for WhatsApp Business automation with AI-powered Message Control Protocols (MCPs).

## Features

### Core Functionality
- **WhatsApp Business API Integration**: Send/receive messages via Meta Cloud API
- **AI-Powered Responses**: Uses Google Gemini 2.0 Flash for intelligent replies
- **Vector Database**: ChromaDB for storing and searching message history
- **Real-time Communication**: Socket.IO for live message updates

### Message Control Protocols (MCPs)

#### 1. End Message MCP (`end_message_mcp`)
- Send messages using natural language commands
- Examples:
  - `send "Hello there!" to Harshit`
  - `send good morning message to Shubham`
- Resolves contact names to phone numbers using aliases

#### 2. Auto-Reply MCP (`auto_reply_mcp`)
- Automatically responds to incoming messages
- Uses conversation history + business description for context
- Generates professional, contextual replies using Gemini AI

<!-- Todo MCP removed -->
- Detects meeting information in messages
- Extracts dates, times, and meeting links
- Automatically creates todo items for meetings

#### 4. Meeting MCP (`meeting_mcp`)
- Generates Google Meet links for scheduled meetings
- Sends professional meeting invites via WhatsApp
- Integrates with Google Calendar

## Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**
   ```bash
   cp .env.example .env
   ```
   Fill in your API keys:
   - `GEMINI_API_KEY`: Google Gemini API key
   - `WHATSAPP_VERIFY_TOKEN`: WhatsApp webhook verification token
   - `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`: Google OAuth credentials

3. **Start the Server**
   ```bash
   python start_server.py
   ```
   Or using uvicorn directly:
   ```bash
   uvicorn main:socket_app --host localhost --port 4000 --reload
   ```

## API Endpoints

### Core Messaging
- `POST /api/send-message` - Send WhatsApp message
- `POST /api/generate-gemini-reply` - Generate AI response
- `POST /webhook` - WhatsApp webhook receiver
- `GET /webhook` - WhatsApp webhook verification

### MCP Endpoints
- `POST /api/mcp/send` - Process end_message_mcp commands
- `POST /api/auto-reply` - Trigger auto-reply manually
- `POST /api/schedule-meeting` - Schedule meeting with MCP

### Data Management
- `GET /api/conversations/{contact_id}` - Get conversation history
- `GET /api/contacts` - List all contacts
- `POST /api/search` - Search messages semantically
<!-- Todo endpoints removed -->

### Integrations
- `POST /api/create-google-meet` - Create Google Meet
- `GET /auth/google` - Get Google OAuth URL
- `POST /api/embedding` - Create text embeddings

## Configuration

### WhatsApp Setup
1. Create a WhatsApp Business account
2. Set up Meta Cloud API credentials
3. Configure webhook URL: `https://your-domain.com/webhook`
4. Use the verify token from your `.env` file

### Google Integration
1. Create Google Cloud Project
2. Enable Calendar API
3. Create OAuth 2.0 credentials
4. Add authorized redirect URI: `http://localhost:4000/auth/google/callback`

## Usage Examples

### Sending Messages via MCP
```python
# Frontend call
await api.mcpSend({
  WHATSAPP_TOKEN: "your_token",
  PHONE_NUMBER_ID: "your_number_id",
  aliases: {
    "harshit": "919876543210",
    "shubham": "919876543211"
  },
  command: "send 'Hello! How are you?' to Harshit"
})
```

### Auto-Reply Configuration
The auto-reply system automatically:
1. Receives incoming messages via webhook
2. Retrieves conversation history from vector database
3. Uses Gemini AI with business context to generate replies
4. Sends professional responses back to users

### Meeting Scheduling
```python
# Schedule a meeting
await api.scheduleMeeting({
  command: "schedule meeting with John at 2 PM tomorrow",
  contact_aliases: {"john": "919876543212"},
  google_tokens: your_google_tokens,
  whatsapp_token: "your_token",
  phone_number_id: "your_number_id"
})
```

## Architecture

```
Frontend (React) 
    ↓ Socket.IO / REST API
FastAPI Server
    ├── WhatsApp Service (Meta Cloud API)
    ├── Gemini Service (AI Processing)
    ├── Vector Service (ChromaDB)
    ├── Google Service (Calendar/Meet)
    └── MCP Services
        ├── End Message MCP
        ├── Auto-Reply MCP
        ├── Todo MCP
        └── Meeting MCP
```

## Data Storage

### Vector Database (ChromaDB)
- Stores all messages with metadata
- Enables semantic search across conversations
- Maintains sender/receiver relationships
- Supports conversation history retrieval

### Message Schema
```python
{
  "contact_id": "919876543210",
  "text": "Hello, how are you?",
  "sender": "919876543210",  # Phone number
  "receiver": "business_number",
  "timestamp": 1634567890000,
  "datetime": "2021-10-18T10:18:10"
}
```

## Security Notes

- Store API keys securely in environment variables
- Implement proper webhook signature validation in production
- Use HTTPS for all production deployments
- Validate and sanitize all user inputs
- Implement rate limiting for API endpoints

## Development

### Project Structure
```
server/
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── models.py            # Pydantic models
├── start_server.py      # Server startup script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── services/
    ├── whatsapp_service.py    # WhatsApp API integration
    ├── gemini_service.py      # Google Gemini AI
    ├── vector_service.py      # ChromaDB operations
    ├── google_service.py      # Google Calendar/Meet
    ├── mcp_services.py        # Basic MCPs
    └── advanced_mcp.py        # Advanced MCPs
```

### Adding New MCPs
1. Create new MCP class in `services/`
2. Implement `process_command()` method
3. Add endpoint in `main.py`
4. Update frontend integration

## Troubleshooting

### Common Issues
1. **ChromaDB Permissions**: Ensure write permissions to `./data/chromadb`
2. **WhatsApp Webhook**: Verify webhook URL is publicly accessible
3. **Google OAuth**: Check redirect URI configuration
4. **Gemini API**: Verify API key and quota limits

### Logs
Check server logs for detailed error information:
```bash
tail -f server.log
```