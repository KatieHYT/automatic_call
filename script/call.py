import os
from twilio.rest import Client
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--call_to', type=str, required=True, help='e.g., +18668978264')
    parser.add_argument('--ngrok_url', type=str, default=None, help='this will change, if you do not serve your own service, ask for it.')
    args = parser.parse_args()

    # Find your Account SID and Auth Token at twilio.com/console
    # and set the environment variables. See http://twil.io/secure
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    client = Client(account_sid, auth_token)
    
    if args.ngrok_url is not None:
        remote_host_url = args.ngrok_url
        print(f"Using ngrok url from argparser: {remote_host_url}")
    else:
        remote_host_url = os.environ["REMOTE_HOST_URL"]
    
    call = client.calls.create(
                            #to='+14156054429',
                            to=args.call_to,
                            from_="+18668978264",
                            #from_='+18777495792',
                            url=f"https://{remote_host_url}/",
                        )
    
    print(call.sid)
