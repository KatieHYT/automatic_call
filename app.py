from flask import Flask, request
from twilio.twiml.voice_response import Gather, VoiceResponse, Say

app = Flask(__name__)

@app.route('/voice', methods=['POST'])
def voice():
    response = VoiceResponse()

    gather = Gather(input='speech', action='/handle-user-input', method='POST')
    gather.say("Hello KT. Please say something after the beep.")
    response.append(gather)

    return str(response)

@app.route('/handle-user-input', methods=['POST'])
def handle_user_input():
    response = VoiceResponse()

    user_input = request.form.get('SpeechResult')

    if user_input:
        response.say("You said: " + user_input)
        response.say("Good night, KT!")

    return str(response)

@app.route('/call-status', methods=['POST'])
def call_status():
    call_sid = request.form['CallSid']
    call_status = request.form['CallStatus']

    print(f"Call SID: {call_sid}, Status: {call_status}")

    # Here, you can perform actions based on the call status, such as logging, updating a database, etc.

    return 'OK'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=2000)

