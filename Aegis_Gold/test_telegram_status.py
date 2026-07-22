#!/usr/bin/env python3
"""
Test Telegram Status Command - Check Confidence Display
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_status_command():
    """Send /status command to bot"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "/status",
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ /status command sent successfully")
            print("Check Telegram for confidence display")
            print("\nExpected format:")
            print("🟢 EURUSD: XX% (TRENDING_UP) - Confidence too low...")
            print("🟡 XAUUSD: XX% (RANGING) - Entry parameters not met...")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Sending /status command to test confidence display...")
    send_status_command()