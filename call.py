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
