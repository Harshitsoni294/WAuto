# WhatsApp Business Automation Platform

Full-stack example combining WhatsApp Cloud API, Google Gemini, and Google Calendar/Meet with a React client and Express backend.

## Prerequisites
- Node.js 18+
- WhatsApp Cloud API app and a test number
- Google Cloud project with Calendar API enabled, OAuth client (web) configured

## Setup (Windows PowerShell)

1. Backend
```powershell
cd server
copy .env.example .env
# edit .env and set GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, META_VERIFY_TOKEN
npm install
npm run dev
```

2. Frontend
```powershell
cd ../client
# optional: set VITE_SERVER_URL to your backend URL
ni .env -Type file -Value "VITE_SERVER_URL=http://localhost:4000"
npm install
npm run dev
```

Open http://localhost:5173

## Webhook
- Set your Meta Webhook URL to http://<public-url>/webhook (use ngrok or similar)
- Verify using the same token as META_VERIFY_TOKEN

## Google OAuth
- Visit http://localhost:4000/auth/google to consent
- Copy tokens from the callback page and paste into the client via future UI (or store in Local Storage via devtools)

## Notes
- All chats, contacts, vectors are stored locally in the browser. Backend holds no state.
- Backend proxies Gemini/Google calls and receives WhatsApp webhooks, emitting them to the client via socket.io.
