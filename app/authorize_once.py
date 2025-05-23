# authorize_once.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 定数
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send'
]
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

def load_credentials():
    """token.json が存在する場合は、そこから認証情報を読み込む。

    Returns:
        google.oauth2.credentials.Credentials: 認証情報。token.json が存在しない場合は None。
    """
    if os.path.exists(TOKEN_FILE):
        return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return None

def authorize():
    """Google Calendar APIへの認証を実行する。

    Returns:
        google.oauth2.credentials.Credentials: 認証情報。

    Raises:
        FileNotFoundError: credentials.json が見つからない場合に発生。
        Exception: 認証処理中にエラーが発生した場合に発生。
    """
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(f"'{CREDENTIALS_FILE}' が見つかりません。")

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        return flow.run_local_server(port=0, open_browser=False)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"{e}")
    except Exception as e:
        raise Exception(f"認証中にエラーが発生しました: {e}")

def save_credentials(creds):
    """認証情報を token.json に保存する。

    Args:
        creds (google.oauth2.credentials.Credentials): 認証情報。
    """
    try:
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    except Exception as e:
        raise Exception(f"認証情報の保存中にエラーが発生しました: {e}")
    print(f"✅ 認証完了！'{TOKEN_FILE}' を保存しました。")

def main():
    """Google Calendar API の認証を行うメイン処理。"""
    creds = load_credentials()

    # token.json がないか、認証情報が無効な場合は、新しく認証を行う
    if not creds or not creds.valid:
        creds = authorize()

    save_credentials(creds)

if __name__ == '__main__':
    main()
