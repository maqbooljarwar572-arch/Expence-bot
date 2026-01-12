import os
import json
import re
import gspread
import threading
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

# --- BACKGROUND WORKER ---
def save_to_google_background(incoming_msg):
    try:
        # Connect to Google (Inside the thread so it doesn't block the reply)
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            print("Error: No Credentials")
            return

        creds_dict = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("Daily Expenses").sheet1
        
        # Parse logic
        text = incoming_msg.lower()
        segments = re.split(r' and | aur |,|&', text)
        
        categories = {
            'Transport': ['petrol', 'bike', 'fuel', 'oil', 'uber', 'indriver', 'rickshaw', 'kiraya', 'bus'],
            'Food': ['khana', 'lunch', 'dinner', 'burger', 'pizza', 'chai', 'roti', 'hotel', 'tea', 'coffee', 'water'],
            'Mobile': ['balance', 'load', 'easyload', 'package', 'card', 'super card'],
            'Groceries': ['sabzi', 'doodh', 'milk', 'sugar', 'cheeni', 'rashan', 'aata', 'fruit'],
            'Bills': ['bijli', 'gas', 'internet', 'wifi', 'bill', 'fee']
        }
        
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for segment in segments:
            amount_match = re.search(r'\d+', segment)
            if amount_match:
                amount = int(amount_match.group())
                found_category = "Misc"
                for cat, keywords in categories.items():
                    if any(word in segment for word in keywords):
                        found_category = cat
                        break
                
                # Save to Sheet
                sh.append_row([current_date, found_category, amount, segment.strip()])
                print(f"Saved: {found_category} - {amount}")

    except Exception as e:
        print(f"Background Error: {e}")

# --- SERVER ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    
    # 1. Start the "Heavy Lifting" in the background
    # This runs separate from the main reply
    thread = threading.Thread(target=save_to_google_background, args=(incoming_msg,))
    thread.start()

    # 2. Reply to WhatsApp IMMEDIATELY (Beating the 15s timer)
    resp = MessagingResponse()
    resp.message("✅ Received! Saving in background...")
    
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run()
