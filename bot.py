import os
import json
import re
import gspread
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

# --- GOOGLE SHEETS SETUP (UPDATED SCOPES) ---
def get_sheet():
    # UPDATED: We now use the modern 'spreadsheets' scope instead of 'feeds'
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if not creds_json:
        raise Exception("Google Credentials not found in Environment Variables.")
        
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Make sure the sheet name is exactly "Daily Expenses"
    return client.open("Daily Expenses").sheet1

# --- LOGIC: UNDERSTAND ROMAN URDU ---
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
            response_text = "✅ *Saved:*\n"
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for item in extracted_data:
                sheet.append_row([current_date, item['category'], item['amount'], item['raw_text']])
                response_text += f"- {item['category']}: {item['amount']}\n"
            
            msg.body(response_text)

    except Exception as e:
        # This will now print the full error details if something breaks
        error_message = f"Error aya hai: {e}"
        print(error_message) # Print to Render logs
        msg.body(error_message)

    return str(resp)

if __name__ == "__main__":
    app.run()
