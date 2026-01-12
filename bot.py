from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    # Basic logic: Just reply "Hello"
    resp = MessagingResponse()
    resp.message("Testing! I am alive.")
    
    # Return as XML
    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run()
