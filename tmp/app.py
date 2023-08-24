import logging
from flask import Flask, request
from flask_sockets import Sockets
from twilio.twiml.voice_response import Gather, VoiceResponse, Say
from twilio.twiml.voice_response import Gather, VoiceResponse, Say, Start

app = Flask(__name__)
sockets = Sockets(app)

#@app.route('/voice', methods=['POST'])
#def voice():
#    #response = VoiceResponse()
#    #response.say("Hi, can I bring dog to your place?")
#    #gather = Gather(input='speech', action='/handle-user-input', speechTimeout="auto", speechModel="phone_call", method="POST")
#    #response.append(gather)
#    #response.redirect('/handle-user-input')
#    #return str(response)

@app.route("/incoming-voice", methods=["POST"])
def incoming_voice():
    #app.logger.info("Connection accepted")
    response = VoiceResponse()
    #print("????????????????")
    start = Start()
    start.stream(
        name='Example Audio Stream', url='2394-140-112-41-151.ngrok-free.app/media'
    )
    response.say("I'm sorry, I didn't quite catch that.")
    response.append(start)
    return str(response)

@sockets.route('/media')
def echo(ws):
    app.logger.info("Connection accepted")
    # A lot of messages will be sent rapidly. We'll stop showing after the first one.
    has_seen_media = False
    message_count = 0
    while not ws.closed:
        message = ws.receive()
        if message is None:
            app.logger.info("No message received...")
            continue

        # Messages are a JSON encoded string
        data = json.loads(message)

        # Using the event type you can determine what type of message you are receiving
        if data['event'] == "connected":
            app.logger.info("Connected Message received: {}".format(message))
        if data['event'] == "start":
            app.logger.info("Start Message received: {}".format(message))
        if data['event'] == "media":
            if not has_seen_media:
                app.logger.info("Media message: {}".format(message))
                payload = data['media']['payload']
                app.logger.info("Payload is: {}".format(payload))
                chunk = base64.b64decode(payload)
                app.logger.info("That's {} bytes".format(len(chunk)))
                app.logger.info("Additional media messages from WebSocket are being suppressed....")
                has_seen_media = True
        if data['event'] == "closed":
            app.logger.info("Closed Message received: {}".format(message))
            break
        message_count += 1

    app.logger.info("Connection closed. Received a total of {} messages".format(message_count))


@app.route('/handle-user-input', methods=['POST'])
def handle_user_input():
    response = VoiceResponse()

    user_input = request.form.get('SpeechResult')

    if user_input:
        response.say("You said: " + user_input)
        response.say("Good night, KT!")
    else:
        response = VoiceResponse()
        response.say("I'm sorry, I didn't quite catch that.")
        gather = Gather(input='speech', action='/handle-user-input', speechTimeout="auto", speechModel="phone_call", method="POST")
        response.append(gather)
        response.redirect('/handle-user-input')

    return str(response)

@app.route('/call-status', methods=['POST'])
def call_status():
    call_sid = request.form['CallSid']
    call_status = request.form['CallStatus']

    print(f"Call SID: {call_sid}, Status: {call_status}")

    # Here, you can perform actions based on the call status, such as logging, updating a database, etc.

    return 'OK'

if __name__ == '__main__':
    HTTP_SERVER_PORT=2000
    #app.run(debug=True, host='0.0.0.0', port=HTTP_SERVER_PORT)

    app.logger.setLevel(logging.DEBUG)
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(('', HTTP_SERVER_PORT), app, handler_class=WebSocketHandler)
    print("Server listening on: http://localhost:" + str(HTTP_SERVER_PORT))
    server.serve_forever()

