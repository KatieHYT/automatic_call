#from twilio.rest import Client
#
## Your Twilio Account SID and Auth Token
#account_sid = 'AC3af075b86d82096251b059536575eb8c'
#auth_token = 'e547a2b0504b9e868db89084b47507ea'
#
## Create a Twilio client
#client = Client(account_sid, auth_token)
#
## Make the outbound call
#call = client.calls.create(
#    to='+14156054429',  # Replace with KT's phone number
#    from_='+18777495792',  # Replace with your Twilio phone number
#    twiml='<Response><Say>Ahoy, World!</Say></Response>',
#    #url='https://2394-140-112-41-151.ngrok-free.app/voice'  # Replace with your Ngrok URL
#)
#
#print("Call SID:", call.sid)
#
#
# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client


# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

call = client.calls.create(
                        to='+14156054429',
                        from_='+18777495792',
                        url="https://2394-140-112-41-151.ngrok-free.app/twiml",
                    )

print(call.sid)
