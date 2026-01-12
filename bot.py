import os
import json
import re
import gspread
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

# --- GOOGLE SHEETS SETUP (MODERN METHOD) ---
def get_sheet():
    # Load credentials from the environment variable
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if not creds_json:
        print("CRITICAL ERROR: GOOGLE_CREDENTIALS not found.")
        return None

    creds_dict = json.loads(creds_json)
    
    # NEW: Connect using gspread's built-in tool
    # This automatically handles the correct permissions (Scopes)
    client = gspread.service_account_from_dict(creds_dict)
    
    return client.open("Daily Expenses").sheet1

# --- LOGIC: ROMAN URDU PARSER ---
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
            
            expenses.append({
                "amount": amount,
                "category": found_category,
                "raw_text": segment.strip()
            })
    return expenses

# --- WHATSAPP SERVER ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    msg = resp.message()

    try:
        extracted_data = parse_expense(incoming_msg)
        
        if not extracted_data:
            msg.body("Samajh nahi aya. Try saying: '500 ka petrol' or '200 ki chai'.")
        else:
            sheet = get_sheet()
            if sheet:
                response_text = "✅ *Saved:*\n"
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for item in extracted_data:
                    sheet.append_row([current_date, item['category'], item['amount'], item['raw_text']])
                    response_text += f"- {item['category']}: {item['amount']}\n"
                msg.body(response_text)
            else:
                msg.body("Error: Database connection failed.")

    except Exception as e:
        print(f"ERROR: {e}")
        msg.body(f"System Error: {str(e)}")

    return str(resp)

if __name__ == "__main__":
    app.run()
