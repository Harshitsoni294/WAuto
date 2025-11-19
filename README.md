# WAuto

WAuto is a powerful automation tool built on the **Meta (Facebook) WhatsApp Business API** that helps businesses streamline communication, automate responses, and schedule meetings with the help of AI.

This repository contains both client and server code, designed to deliver a seamless experience for managing WhatsApp business interactions through intelligent automation.

---

## 🚀 Features

### **🤖 AI‑Powered Automations**

* **Automatic replies** to customer messages based on intent.
* **AI agent–powered messaging** for personalized, smart interactions.
* **AI‑based meeting scheduling** directly through WhatsApp.

### **📅 Google Calendar Integration**

* Automatically schedules meetings.
* Generates **unique meeting links** for each client.
* Syncs events and reminders with Google Calendar.

### **💬 WhatsApp Business Account Management**

* Integrates directly with **Facebook Business API**.
* Allows WhatsApp Business Account operations via your Facebook Developer App.
* Ensures secure, scalable, and reliable message delivery.

---

## 🛠️ Tech Stack

* **WhatsApp Business API (Meta/Facebook)**
* **Node.js / Python backend** (based on repo structure)
* **React / Next.js frontend** (assuming typical structure)
* **Google Calendar API**
* **AI / NLP services**

---

## 📦 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/Harshitsoni294/WAuto.git
cd WAuto
```

### 2. Configure environment variables

You will need credentials for:

* Facebook Developer App (WhatsApp Business)
* Google Cloud Calendar API
* AI service keys

3. Install dependencies

```bash
cd server
pip install -r requirements.txt

cd ../client
npm install
```

### 4. Run development servers

```bash
# backend
python main.py
# frontend
npm run dev
```

---

## ⚙️ How It Works

1. **Customer sends a WhatsApp message** → Webhook triggers server.
2. Server processes using **AI agent** → Generates smart response.
3. If the user requests scheduling:

   * AI parses date/time.
   * Event is created in **Google Calendar**.
   * A **unique meeting link** is generated.
4. Customer receives confirmation message automatically.

---

## 🌐 Deployment

This project includes configs for:

* **Vercel** (frontend)
* **Render** (backend)

Just connect the repo to these platforms and deploy.

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

##

---

## ✨ Author

Developed by **Harshit Soni**.
