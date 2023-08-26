import os
from twilio.rest import Client

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

remote_host_url = os.environ["REMOTE_HOST_URL"]

call = client.calls.create(
                        to='+14156054429',
                        from_='+18777495792',
                        url=f"https://{remote_host_url}/twiml",
                    )

print(call.sid)
