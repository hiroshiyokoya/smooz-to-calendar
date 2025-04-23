# fetch_reservations.py

import time
import json
import jaconv
import re
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import os
from pytz import timezone

# 定数
SMOOZ_LOGIN_URL = "https://www.smooz.jp/Smooz/login.xhtml"
PURCHASE_HISTORY_LINK_TEXT = "購入履歴"
RESERVATIONS_FILE = "reservations.json"
LOGIN_FILE = "login.txt"
RETRY_COUNT = 3
WAIT_TIME = 10
SLEEP_TIME = 2
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"

def get_login_info(filename):
    """ログイン情報をファイルから読み込む。

    Args:
        filename (str): ログイン情報が記載されたファイル名。

    Returns:
        tuple: ユーザー名とパスワードのタプル。

    Raises:
        FileNotFoundError: ファイルが見つからない場合に発生。
        ValueError: ファイルの内容が不正な場合に発生。
    """
    try:
        with open(filename, "r") as f:
            username = f.readline().strip()
            password = f.readline().strip()
        if not username or not password:
            raise ValueError(f"ログイン情報が不正です: {filename}")
        return username, password
    except FileNotFoundError:
        raise FileNotFoundError(f"ログイン情報ファイルが見つかりません: {filename}")

def safe_text(el):
    """HTML要素から安全にテキストを取得する。"""
    return el.get_text(strip=True) if el else ""

def normalize_text(v):
    """テキストを正規化する。"""
    if not isinstance(v, str):
        return v
    v = jaconv.z2h(v, kana=False, ascii=True, digit=True)
    v = v.replace("\u00A0", " ")
    v = v.translate(str.maketrans({
        "（": "(",
        "）": ")",
        "　": " ",
        "‐": "-"
    }))
    return v

def normalize_reservation(reservation):
    """予約情報を正規化する。"""
    return {k: normalize_text(v) for k, v in reservation.items()}

def is_recent_month(value):
    """指定された値が直近の月かどうかを判定する。"""
    if value in ["currentMonth", "nextMonth"]:
        return True
    try:
        dt = datetime.strptime(value, "%Y%m%d")
        yyyymm = int(dt.strftime("%Y%m"))
        now = datetime.now()
        current_yyyymm = now.year * 100 + now.month
        return yyyymm >= (current_yyyymm - 1)
    except ValueError:
        return False

def login(driver, username, password):
    """Smoozにログインする。"""
    driver.get(SMOOZ_LOGIN_URL)
    time.sleep(SLEEP_TIME)

    try:
        driver.find_element(By.ID, "loginId").send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "submit").click()
        time.sleep(SLEEP_TIME * 2)
    except NoSuchElementException as e:
        raise ValueError("ログイン情報の入力項目が見つかりませんでした") from e

def navigate_to_purchase_history(driver):
    """購入履歴画面に遷移する。"""
    try:
        WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "menuBtn"))
        ).click()
        time.sleep(SLEEP_TIME / 2)

        WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, PURCHASE_HISTORY_LINK_TEXT))
        ).click()
        time.sleep(SLEEP_TIME + 1)
    except TimeoutException:
        raise TimeoutException("『購入履歴』リンクが見つかりませんでした")

def extract_reservation_details(block):
    """
    予約情報が記載されたHTMLブロックから予約詳細情報を抽出する。

    Args:
        block (bs4.element.Tag): 予約情報が記載されたHTMLブロック。

    Returns:
        dict: 抽出された予約詳細情報を含む辞書。
    """
    reservation = {
        "ステータス": "",
        "購入番号": safe_text(block.select_one('.contentItem')),
        "購入日時": safe_text(block.select_one('.catgory.item .value')),
        "乗車日": safe_text(block.select_one('.detailsArea .item:nth-of-type(1) .value')),
        "列車名": safe_text(block.select_one('.detailsArea .item:nth-of-type(2) .value')),
        "人数（大人）": safe_text(block.select_one('.detailsArea .item:nth-of-type(4) .value')),
        "人数（小児）": safe_text(block.select_one('.detailsArea .item:nth-of-type(5) .value')),
        "金額": safe_text(block.select_one('.detailsArea .item:nth-of-type(6) .value')),
        "号車": "",
        "座席": ""
    }

    stations = block.select('.detailsArea .item:nth-of-type(3) .station')
    if len(stations) >= 2:
        reservation["出発駅"] = safe_text(stations[0].select_one('.stationName'))
        reservation["出発時刻"] = safe_text(stations[0].select_one('.time'))
        reservation["到着駅"] = safe_text(stations[1].select_one('.stationName'))
        reservation["到着時刻"] = safe_text(stations[1].select_one('.time'))
    return reservation

def parse_datetime(date_str, time_str):
    """日付と時刻の文字列から datetime オブジェクトを生成する"""
    date = re.sub(r"[年月日（）]", "-", date_str).strip("-").split("-")[0:3]
    date_str_clean = "-".join(date)
    time = re.sub(r"[^\d:]", "", time_str)
    dt = datetime.strptime(f"{date_str_clean} {time}", "%Y-%m-%d %H:%M")
    return timezone('Asia/Tokyo').localize(dt)

def fetch_reservations_by_month(driver, month):
    """
    月を指定して予約情報を取得する。

    Args:
        driver (selenium.webdriver.Chrome): WebDriverインスタンス。
        month (str): 取得する予約情報の対象月 (例: "202310")。

    Returns:
        list: 予約情報のリスト。

    Raises:
        TimeoutException: ウェブ要素の検索にタイムアウトした場合に発生。
    """
    print(f"🔎 照会中: {month}")
    try:
        select = Select(WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.ID, "useInquiryDate"))
        ))
        select.select_by_value(month)

        WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable((By.ID, "displayBtn"))
        ).click()
        time.sleep(SLEEP_TIME + 1)
    except TimeoutException as e:
        raise TimeoutException(f"月を指定しての予約情報の取得に失敗しました: {month}") from e

    reservations = []
    while True:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        blocks = soup.select("div.pdg-10")

        current = None
        last_block = None

        for block in blocks:
            if block.select_one(".contentItem"):
                reservation = extract_reservation_details(block)
                current = reservation
                reservations.append(reservation)
            elif current:
                items = block.select(".item")
                for item in items:
                    label = safe_text(item.select_one(".name"))
                    value = safe_text(item.select_one(".value"))
                    if "号車" in label:
                        current["号車"] = value
                    elif "座席" in label:
                        current["座席"] = value

                sub_status_divs = block.select(".item.statusArea .status")
                sub_statuses = [safe_text(s) for s in sub_status_divs]
                if sub_statuses:
                    current["ステータス"] = " ".join(sub_statuses)

            last_block = block

        if current and current["ステータス"] == "" and last_block:
            sub_status_divs = last_block.select(".item.statusArea .status")
            sub_statuses = [safe_text(s) for s in sub_status_divs]
            if sub_statuses:
                current["ステータス"] = " ".join(sub_statuses)

        print(f"  -> {len(reservations)} 件取得")

        try:
            next_link = driver.find_element(By.ID, "next")
            next_url = urljoin(driver.current_url, next_link.get_attribute("href"))
            driver.get(next_url)
            time.sleep(SLEEP_TIME)
        except NoSuchElementException:
            break
    return reservations

def fetch_reservations():
    """
    Smoozから予約情報を取得する。

    Returns:
        list: 正規化された予約情報のリスト。
        None: エラーが発生した場合。
    """
    username, password = get_login_info(LOGIN_FILE)

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={USER_AGENT}")

    for retry in range(RETRY_COUNT):
        try:
            driver = webdriver.Chrome(options=options)
            login(driver, username, password)
            navigate_to_purchase_history(driver)

            select_element = WebDriverWait(driver, WAIT_TIME).until(
                EC.presence_of_element_located((By.ID, "useInquiryDate"))
            )
            select = Select(select_element)
            months = [option.get_attribute("value") for option in select.options if option.get_attribute("value") != "today"]
            months = [m for m in months if is_recent_month(m)]
            print(f"📅 対象月: {months}")

            all_reservations = []
            for month in months:
                reservations = fetch_reservations_by_month(driver, month)
                all_reservations.extend(reservations)

            normalized = [normalize_reservation(r) for r in all_reservations]
            return normalized

        except (ValueError, TimeoutException, WebDriverException) as e:
            print(f"❌ エラー発生 ({retry + 1}/{RETRY_COUNT}): {e}")
            if retry < RETRY_COUNT - 1:
                print("🔄 リトライします...")
                time.sleep(SLEEP_TIME)
            else:
                print("❌ リトライ回数を超えたため、処理を終了します")
                return None

        finally:
            driver.quit()

def save_reservations(reservations, filename):
    """予約情報をファイルに保存する。

    Args:
        reservations (list): 予約情報のリスト。
        filename (str): 保存するファイル名。
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(reservations, f, ensure_ascii=False, indent=2)
    print(f"✅ 合計 {len(reservations)} 件の予約を {filename} に保存しました。")

# 手動実行用（テストなど）
if __name__ == "__main__":
    reservations = fetch_reservations()
    if reservations:
        save_reservations(reservations, RESERVATIONS_FILE)
