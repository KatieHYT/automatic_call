import os
from twilio.rest import Client
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--call_to', type=str, required=True, help='e.g., +18668978264')
    args = parser.parse_args()

    # Find your Account SID and Auth Token at twilio.com/console
    # and set the environment variables. See http://twil.io/secure
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    client = Client(account_sid, auth_token)
    
    remote_host_url = os.environ["REMOTE_HOST_URL"]
    
    call = client.calls.create(
                            #to='+14156054429',
                            to=args.call_to,
                            from_="+18668978264",
                            #from_='+18777495792',
                            url=f"https://{remote_host_url}/",
                        )
    
    print(call.sid)
