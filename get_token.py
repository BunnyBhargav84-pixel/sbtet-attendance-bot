from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def generate():
    flow = InstalledAppFlow.from_client_secrets_file('G_credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("SUCCESS: 'token.json' has been created in your folder!")

if __name__ == '__main__':
    generate()
