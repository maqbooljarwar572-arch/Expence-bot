import os
import json
import re
import gspread
import requests
import threading
from flask import Flask, request

app = Flask(__name__)

# --- CONFIGURATION ---
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
PHONE_ID = os.environ.get("META_PHONE_ID")
VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "my_secret_password")

# --- SEND MESSAGE FUNCTION (Meta API) ---
def send_whatsapp_message(to_number, message_text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    requests.post(url, headers=headers, json=data)

# --- WORKER: SAVE & REPLY ---
def process_message(incoming_msg, sender_phone):
    try:
        # 1. Connect to Google
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            return

        creds_dict = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("Daily Expenses").sheet1
        
        # 2. Logic
        text = incoming_msg.lower()
        segments = re.split(r' and | aur |,|&', text)
        
        categories = {
            'Transport': ['petrol', 'bike', 'fuel', 'oil', 'uber', 'indriver', 'rickshaw', 'kiraya', 'bus'],
            'Food': ['khana', 'lunch', 'dinner', 'burger', 'pizza', 'chai', 'roti', 'hotel', 'tea', 'coffee', 'water'],
            'Mobile': ['balance', 'load', 'easyload', 'package', 'card', 'super card'],
            'Groceries': ['sabzi', 'doodh', 'milk', 'sugar', 'cheeni', 'rashan', 'aata', 'fruit'],
            'Bills': ['bijli', 'gas', 'internet', 'wifi', 'bill', 'fee']
        }
        
        current_date = "2024-01-01" # Simplified date for safety
        saved_items = []

        for segment in segments:
            amount_match = re.search(r'\d+', segment)
            if amount_match:
                amount = int(amount_match.group())
                found_category = "Misc"
                for cat, keywords in categories.items():
                    if any(word in segment for word in keywords):
                        found_category = cat
                        break
                
                sh.append_row([current_date, found_category, amount, segment.strip()])
                saved_items.append(f"{found_category}: {amount}")

        # 3. Reply
        if saved_items:
            send_whatsapp_message(sender_phone, "✅ Saved: " + ", ".join(saved_items))
        else:
            send_whatsapp_message(sender_phone, "Samajh nahi aya. Try '500 ka petrol'")

    except Exception as e:
        print(f"Error: {e}")

# --- WEBHOOK (The Door) ---
@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp_webhook():
    # Verify Connection (Facebook checks this first)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return 'Forbidden', 403

    # Receive Message
    if request.method == 'POST':
        data = request.get_json()
        try:
            if data.get('entry') and data['entry'][0]['changes'][0]['value'].get('messages'):
                msg_data = data['entry'][0]['changes'][0]['value']['messages'][0]
                sender = msg_data['from']
                text = msg_data['text']['body']
                
                thread = threading.Thread(target=process_message, args=(text, sender))
                thread.start()
        except:
            pass
        return 'OK', 200

if __name__ == "__main__":
    app.run(port=10000)
