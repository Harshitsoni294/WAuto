#!/usr/bin/env python3
"""
WhatsApp Business Automation Server Startup Script
"""

import uvicorn
from config import settings

if __name__ == "__main__":
    print("Starting WhatsApp Business Automation Server...")
    print(f"Server will run on {settings.HOST}:{settings.PORT}")
    print(f"Debug mode: {settings.DEBUG}")
    
    uvicorn.run(
        "main:socket_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )