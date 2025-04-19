# calendar_sync.py

import os
import sys
import json
import datetime
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar']
ALLOWED_STATUSES = {"購入済", "運休払戻済", "乗車変更購入済"}

def authorize_google_calendar():
    if not os.path.exists('token.json'):
        raise RuntimeError("token.json が見つかりません。認証を先に実行してください。")

    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build('calendar', 'v3', credentials=creds)

def get_calendar_id_by_name(service, name="Smooz"):
    calendars = service.calendarList().list().execute()
    for cal in calendars["items"]:
        if cal["summary"] == name:
            return cal["id"]
    raise ValueError(f"カレンダー '{name}' が見つかりませんでした。")

def parse_datetime(date_str, time_str):
    date = re.sub(r"[年月日（）]", "-", date_str).strip("-").split("-")[0:3]
    date_str_clean = "-".join(date)
    time = re.sub(r"[^\d:]", "", time_str)
    return datetime.datetime.strptime(f"{date_str_clean} {time}", "%Y-%m-%d %H:%M")

def extract_target_year_months(reservations):
    months = set()
    for r in reservations:
        try:
            ride_date = re.sub(r"[年月日（）]", "-", r.get("乗車日", "")).strip("-")
            parts = ride_date.split("-")
            year_month = f"{parts[0]}/{int(parts[1])}"
            months.add(year_month)
        except:
            continue
    return months

def delete_events_in_months(service, calendar_id, target_months):
    print(f"🧹 カレンダー「{calendar_id}」内の対象月のイベントを削除します...")
    page_token = None
    count = 0
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
            except:
                continue
        page_token = events.get('nextPageToken')
        if not page_token:
            break
    print(f"✅ {count} 件のイベントを削除しました。")

def sync_calendar(reservations, debug=False, clear=True):
    service = authorize_google_calendar()
    calendar_id = get_calendar_id_by_name(service, name="Smooz")

    if clear:
        target_months = extract_target_year_months(reservations)
        delete_events_in_months(service, calendar_id, target_months)

    for i, r in enumerate(reservations):
        if r.get("ステータス") not in ALLOWED_STATUSES:
            continue

        try:
            start = parse_datetime(r["乗車日"], r["出発時刻"])
            end = parse_datetime(r["乗車日"], r["到着時刻"])

            car = r['号車'].replace(" ", "")
            title = f"{r['出発駅']}→{r['到着駅']} [{car} {r['座席']}]"
            if "払戻済" in r["ステータス"]:
                title = f"🚫 {title}"
            else:
                title = f"🚆 {title}"

            description = (
                f"列車名: {r['列車名']}\n"
                f"号車: {car}\n"
                f"座席: {r['座席']}\n"
                f"人数: 大人 {r['人数（大人）']} / 小児 {r['人数（小児）']}\n"
                f"金額: {r['金額']}\n"
                f"ステータス: {r['ステータス']}\n"
                f"購入番号: {r['購入番号']}\n"
            )

            event = {
                'summary': title,
                'description': description,
                'location': r['出発駅'] + "駅",
                'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Tokyo'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Tokyo'}
            }

            print(json.dumps(event, ensure_ascii=False, indent=2))
            try:
                created = service.events().insert(calendarId=calendar_id, body=event).execute()
                print(f"✅ 登録完了: {title}")
            except Exception as e:
                print(f"❌ イベント登録失敗: {e}")

            if debug:
                print("🧪 デバッグモードなので、1件だけ登録して終了します。")
                break
        except Exception as e:
            print(f"⚠️ スキップされた予約があります: {e}")

# CLI 用（手動実行など）
if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    clear_mode = "--clear" in sys.argv

    with open("reservations.json", "r", encoding="utf-8") as f:
        reservations = json.load(f)

    sync_calendar(reservations, debug=debug_mode, clear=clear_mode)
