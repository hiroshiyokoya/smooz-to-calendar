# calendar_sync.py

import os
import sys
import json
import datetime
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fetch_reservations import parse_datetime #修正
from pytz import timezone
from authorize_once import load_credentials, authorize, save_credentials
from email.mime.text import MIMEText
import base64

# 定数
TOKEN_FILE = 'token.json'
CALENDAR_NAME = "Smooz"
SCOPES = ['https://www.googleapis.com/auth/calendar']
ALLOWED_STATUSES = {"購入済", "運休払戻済", "乗車変更購入済"}
JST = timezone('Asia/Tokyo')
NOTIFICATION_EMAIL = 'hyokoya@gmail.com'  # エラー通知の送信先メールアドレス

def send_error_notification(error_message):
    """エラーメッセージをGmailで送信する。

    Args:
        error_message (str): 送信するエラーメッセージ。
    """
    try:
        creds = load_credentials()
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = authorize()
                save_credentials(creds)

        service = build('gmail', 'v1', credentials=creds)

        # メールの作成
        message = MIMEText(error_message)
        message['to'] = NOTIFICATION_EMAIL
        message['from'] = creds.token_response.get('email', 'noreply@example.com')
        message['subject'] = 'カレンダー同期エラー通知'

        # メールの送信
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()

        print(f"✅ エラー通知を送信しました: {NOTIFICATION_EMAIL}")
    except Exception as e:
        print(f"❌ エラー通知の送信に失敗しました: {e}")

def authorize_google_calendar():
    """Google Calendar APIへのアクセスを認証する。

    Returns:
        googleapiclient.discovery.Resource: Google Calendar APIのサービスオブジェクト。

    Raises:
        RuntimeError: service_account.json が存在しない場合に発生。
        Exception: Google Calendar API の認証に失敗した場合に発生。
    """
    try:
        creds = load_credentials()
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = authorize()
                save_credentials(creds)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        error_message = f"Google Calendar API の認証に失敗しました: {e}"
        send_error_notification(error_message)
        raise Exception(error_message)

def get_calendar_id_by_name(service, name=CALENDAR_NAME):
    """指定された名前のカレンダーのIDを取得する。

    Args:
        service (googleapiclient.discovery.Resource): Google Calendar APIのサービスオブジェクト。
        name (str): 検索するカレンダーの名前。

    Returns:
        str: 指定された名前のカレンダーのID。

    Raises:
        ValueError: 指定された名前のカレンダーが見つからない場合に発生。
    """
    try:
        calendars = service.calendarList().list().execute()
        for cal in calendars["items"]:
            if cal["summary"] == name:
                return cal["id"]
        raise ValueError(f"カレンダー '{name}' が見つかりませんでした。")
    except Exception as e:
        raise Exception(f"カレンダーの検索に失敗しました。: {e}")

def extract_target_year_months(reservations):
    """予約情報から対象となる年月を抽出する。

    Args:
        reservations (list): 予約情報のリスト。

    Returns:
        set: 対象となる年月のセット (例: {"2023/10", "2023/11"})。
    """
    months = set()
    for r in reservations:
        try:
            ride_date = r.get("乗車日", "")
            # リストの場合は最初の要素を使用
            if isinstance(ride_date, list):
                ride_date = ride_date[0] if ride_date else ""
            ride_date = re.sub(r"[年月日（）]", "-", ride_date).strip("-")
            parts = ride_date.split("-")
            year_month = f"{parts[0]}/{int(parts[1])}"
            months.add(year_month)
        except Exception as e:
            print(f"年月抽出中にエラーが発生しました: {e}")
            continue
    return months

def delete_events_in_months(service, calendar_id, target_months):
    """指定された年月に対応するカレンダー内のイベントを削除する。

    Args:
        service (googleapiclient.discovery.Resource): Google Calendar APIのサービスオブジェクト。
        calendar_id (str): 削除対象のカレンダーID。
        target_months (set): 削除対象の年月セット。
    """
    print(f"🧹 カレンダー「{calendar_id}」内の対象月のイベントを削除します...")
    count = 0
    try:
        page_token = None
        while True:
            events = service.events().list(calendarId=calendar_id, pageToken=page_token).execute()
            for event in events.get('items', []):
                start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                if not start:
                    continue
                try:
                    dt = datetime.datetime.fromisoformat(start)
                    ym = f"{dt.year}/{dt.month}"
                    if ym in target_months:
                        service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                        count += 1
                except Exception as e:
                    print(f"イベント削除中にエラーが発生しました: {e}")
                    continue
            page_token = events.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        raise Exception(f"イベントの削除に失敗しました: {e}")
    print(f"✅ {count} 件のイベントを削除しました。")

def extract_event_details(reservation):
    """予約情報からイベントの詳細を抽出する。

    Args:
        reservation (dict): 予約情報の辞書。

    Returns:
        dict: イベントの詳細情報。
    """
    ride_date = reservation["乗車日"]
    # リストの場合は最初の要素を使用
    if isinstance(ride_date, list):
        ride_date = ride_date[0] if ride_date else ""
    start = parse_datetime(ride_date, reservation["出発時刻"]).astimezone(JST)
    end = parse_datetime(ride_date, reservation["到着時刻"]).astimezone(JST)

    # 号車と座席の処理
    car = reservation.get("号車", "")
    if isinstance(car, list):
        car = ", ".join(sorted(set(car)))  # 重複を除去してソート
    car = car.replace(" ", "")

    seat = reservation.get("座席", "")
    if isinstance(seat, list):
        seat = ", ".join(seat)
    seat = seat.replace(" ", "")

    # 列車名の処理
    train_name = reservation.get("列車名", "")
    if isinstance(train_name, list):
        train_name = train_name[0]
    train_name = train_name.replace(" ", "")

    # 出発駅と到着駅の処理
    departure = reservation.get("出発駅", "")
    if isinstance(departure, list):
        departure = departure[0]
    departure = departure.replace(" ", "")

    arrival = reservation.get("到着駅", "")
    if isinstance(arrival, list):
        arrival = arrival[0]
    arrival = arrival.replace(" ", "")

    # ステータスの処理
    status = reservation.get("ステータス", [])
    if isinstance(status, list):
        status = ", ".join(sorted(set(status)))  # 重複を除去してソート

    title = f"{departure}→{arrival} [{car} {seat}]"
    if "払戻済" in status:
        title = f"🚫 {title}"
    else:
        title = f"🚆 {title}"

    description = (
        f"列車名: {train_name}\n"
        f"号車: {car}\n"
        f"座席: {seat}\n"
        f"人数: 大人 {reservation['人数（大人）']} / 小児 {reservation['人数（小児）']}\n"
        f"金額: {reservation['金額']}\n"
        f"ステータス: {status}\n"
        f"購入番号: {reservation['購入番号']}\n"
    )

    return {
        'summary': title,
        'description': description,
        'location': departure + "駅",
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Tokyo'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Tokyo'}
    }

def sync_calendar(reservations, debug=False, clear=True):
    """予約情報をGoogleカレンダーに同期する。

    Args:
        reservations (list): 予約情報のリスト。
        debug (bool, optional): デバッグモードで実行するかどうか。Defaults to False.
        clear (bool, optional): カレンダーを事前に削除するかどうか。Defaults to True.
    """
    try:
        service = authorize_google_calendar()
        calendar_id = get_calendar_id_by_name(service, name=CALENDAR_NAME)

        if clear:
            target_months = extract_target_year_months(reservations)
            delete_events_in_months(service, calendar_id, target_months)

        for i, r in enumerate(reservations):
            print(f"\n🔍 予約情報 {i+1} 件目:")
            print(f"  乗車日: {r.get('乗車日')} (type: {type(r.get('乗車日'))})")
            print(f"  ステータス: {r.get('ステータス')} (type: {type(r.get('ステータス'))})")
            # ステータスがリストの場合は最初の要素を使用
            status = r.get("ステータス", [])
            if isinstance(status, list):
                status = status[0] if status else ""
            if status not in ALLOWED_STATUSES:
                print(f"  ⏭️ スキップ: ステータス {status} は対象外")
                continue
            try:
                event = extract_event_details(r)
                print(json.dumps(event, ensure_ascii=False, indent=2))
                created = service.events().insert(calendarId=calendar_id, body=event).execute()
                print(f"✅ 登録完了: {event['summary']}")
                print(f"  -> 登録されたイベントのURL: {created.get('htmlLink')}")
            except Exception as e:
                error_message = f"❌ イベント登録失敗: {e}"
                print(error_message)
                # 送信先メールアドレスを設定
                send_error_notification(error_message)

            if debug:
                print("🧪 デバッグモードなので、1件だけ登録して終了します。")
                break
    except Exception as e:
        error_message = f"⚠️ 同期中にエラーが発生しました。{e}"
        print(error_message)
        # 送信先メールアドレスを設定
        send_error_notification(error_message)

# CLI 用（手動実行など）
if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    clear_mode = "--clear" in sys.argv

    with open("reservations.json", "r", encoding="utf-8") as f:
        reservations = json.load(f)

    sync_calendar(reservations, debug=debug_mode, clear=clear_mode)
