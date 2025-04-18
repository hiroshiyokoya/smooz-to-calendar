# authorize_once.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# 使用するスコープ：Googleカレンダー編集
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None

    # すでにtoken.jsonがある場合は再利用
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # 認証がなければ新しく取得
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        # creds = flow.run_local_server(port=0)
        creds = flow.run_local_server(port=0, open_browser=False)

        # 認証トークンを保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("✅ 認証完了！token.json を保存しました。")

if __name__ == '__main__':
    main()
