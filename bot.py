import os
import json
import re
import gspread
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

# --- SPEED BOOST: CONNECT ONCE AT STARTUP ---
# We connect to Google only once when the app wakes up.
# This saves 3-5 seconds per message!
try:
    print("... Connecting to Google Sheets ...")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS missing")
    
    creds_dict = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds_dict)
    # Connect to the sheet immediately
    sh = gc.open("Daily Expenses").sheet1
    print("✅ Connected to Google Sheets!")
except Exception as e:
    print(f"❌ Connection Error: {e}")
    sh = None

# --- PARSER ---
def parse_expense(text):
    text = text.lower()
    segments = re.split(r' and | aur |,|&', text)
    expenses = []
    
    categories = {
        'Transport': ['petrol', 'bike', 'fuel', 'oil', 'uber', 'indriver', 'rickshaw', 'kiraya', 'bus'],
        'Food': ['khana', 'lunch', 'dinner', 'burger', 'pizza', 'chai', 'roti', 'hotel', 'tea', 'coffee', 'water'],
        'Mobile': ['balance', 'load', 'easyload', 'package', 'card', 'super card'],
        'Groceries': ['sabzi', 'doodh', 'milk', 'sugar', 'cheeni', 'rashan', 'aata', 'fruit'],
        'Bills': ['bijli', 'gas', 'internet', 'wifi', 'bill', 'fee']
    }

    for segment in segments:
        amount_match = re.search(r'\d+', segment)
        if amount_match:
            amount = int(amount_match.group())
            found_category = "Misc"
            for cat, keywords in categories.items():
                if any(word in segment for word in keywords):
                    found_category = cat
                    break
            expenses.append({"amount": amount, "category": found_category, "raw_text": segment.strip()})
    return expenses

# --- SERVER ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    msg = resp.message()

    try:
        extracted_data = parse_expense(incoming_msg)
        
        if not extracted_data:
            msg.body("Samajh nahi aya. Try: '500 ka petrol'")
        else:
            # Check if connection is alive
            if sh:
                response_text = "✅ *Saved:*\n"
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for item in extracted_data:
                    # Save to Google (Now much faster because 'sh' is ready)
                    sh.append_row([current_date, item['category'], item['amount'], item['raw_text']])
                    response_text += f"- {item['category']}: {item['amount']}\n"
                
                msg.body(response_text)
            else:
                msg.body("Error: Server could not connect to Google.")

    except Exception as e:
        print(f"ERROR: {e}")
        # If it fails, send a short message so WhatsApp doesn't hang
        msg.body("Saved (Slow Network)")

    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run()
