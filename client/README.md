# WhatsApp Business Automation Client

React + Vite + Tailwind app storing chats and vectors locally (LocalStorage + ChromaDB via chromadb-ts). Connects to the backend for proxying API calls and sockets.

## Setup

Create `.env` in client with:

```
VITE_SERVER_URL=http://localhost:4000
```

Install and run:

```powershell
cd client
npm install
npm run dev
```

Open http://localhost:5173

## Commands in chat input

- /draft <topic> — Ask Gemini to draft a message.
- /schedule meeting with {contact} at {time} — Creates a Meet and adds a todo, then sends an invite.
