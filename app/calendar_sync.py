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

# 定数
TOKEN_FILE = 'token.json'
CALENDAR_NAME = "Smooz"
SCOPES = ['https://www.googleapis.com/auth/calendar']
ALLOWED_STATUSES = {"購入済", "運休払戻済", "乗車変更購入済"}
JST = timezone('Asia/Tokyo')

def authorize_google_calendar():
    """Google Calendar APIへのアクセスを認証する。

    Returns:
        googleapiclient.discovery.Resource: Google Calendar APIのサービスオブジェクト。

    Raises:
        RuntimeError: token.json が存在しない場合に発生。
        Exception: Google Calendar API の認証に失敗した場合に発生。
    """
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(f"{TOKEN_FILE} が見つかりません。認証を先に実行してください。")

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        raise Exception(f"Google Calendar API の認証に失敗しました: {e}")

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
            ride_date = re.sub(r"[年月日（）]", "-", r.get("乗車日", "")).strip("-")
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
    start = parse_datetime(reservation["乗車日"], reservation["出発時刻"]).astimezone(JST)
    end = parse_datetime(reservation["乗車日"], reservation["到着時刻"]).astimezone(JST)
    car = reservation['号車'].replace(" ", "")
    title = f"{reservation['出発駅']}→{reservation['到着駅']} [{car} {reservation['座席']}]"
    if "払戻済" in reservation["ステータス"]:
        title = f"🚫 {title}"
    else:
        title = f"🚆 {title}"

    description = (
        f"列車名: {reservation['列車名']}\n"
        f"号車: {car}\n"
        f"座席: {reservation['座席']}\n"
        f"人数: 大人 {reservation['人数（大人）']} / 小児 {reservation['人数（小児）']}\n"
        f"金額: {reservation['金額']}\n"
        f"ステータス: {reservation['ステータス']}\n"
        f"購入番号: {reservation['購入番号']}\n"
    )

    return {
        'summary': title,
        'description': description,
        'location': reservation['出発駅'] + "駅",
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
            if r.get("ステータス") not in ALLOWED_STATUSES:
                continue
            try:
                event = extract_event_details(r)
                print(json.dumps(event, ensure_ascii=False, indent=2))
                created = service.events().insert(calendarId=calendar_id, body=event).execute()
                print(f"✅ 登録完了: {event['summary']}")
                print(f"  -> 登録されたイベントのURL: {created.get('htmlLink')}")
            except Exception as e:
                print(f"❌ イベント登録失敗: {e}")

            if debug:
                print("🧪 デバッグモードなので、1件だけ登録して終了します。")
                break
    except Exception as e:
        print(f"⚠️ 同期中にエラーが発生しました。{e}")

# CLI 用（手動実行など）
if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    clear_mode = "--clear" in sys.argv

    with open("reservations.json", "r", encoding="utf-8") as f:
        reservations = json.load(f)

    sync_calendar(reservations, debug=debug_mode, clear=clear_mode)
