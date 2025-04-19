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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup

import os

# USERNAME = os.environ["SMOOZ_USER"]
# PASSWORD = os.environ["SMOOZ_PASS"]

def safe_text(el):
    return el.get_text(strip=True) if el else ""

def normalize_reservation(reservation):
    def normalize_text(v):
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
    return {k: normalize_text(v) for k, v in reservation.items()}

def is_recent_month(value):
    if value in ["currentMonth", "nextMonth"]:
        return True
    try:
        dt = datetime.strptime(value, "%Y%m%d")
        yyyymm = int(dt.strftime("%Y%m"))
        now = datetime.now()
        current_yyyymm = now.year * 100 + now.month
        return yyyymm >= (current_yyyymm - 1)
    except:
        return False

def fetch_reservations():
    with open("login.txt", "r") as f:
        USERNAME = f.readline().strip()
        PASSWORD = f.readline().strip()

    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.smooz.jp/Smooz/login.xhtml")
        time.sleep(2)

        driver.find_element(By.ID, "loginId").send_keys(USERNAME)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.ID, "submit").click()
        time.sleep(4)

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "menuBtn"))
        ).click()
        time.sleep(1)

        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "購入履歴"))
            ).click()
            time.sleep(3)
        except TimeoutException:
            print("⚠ 『購入履歴』リンクが見つかりませんでした")

        all_reservations = []

        select_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "useInquiryDate"))
        )
        select = Select(select_element)
        months = [option.get_attribute("value") for option in select.options if option.get_attribute("value") != "today"]
        months = [m for m in months if is_recent_month(m)]
        print(f"📅 対象月: {months}")

        for month in months:
            print(f"🔎 照会中: {month}")

            select = Select(WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "useInquiryDate"))
            ))
            select.select_by_value(month)

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "displayBtn"))
            ).click()
            time.sleep(3)

            while True:
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                blocks = soup.select("div.pdg-10")

                reservations = []
                current = None
                last_block = None

                for block in blocks:
                    if block.select_one(".contentItem"):
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
                all_reservations.extend(reservations)

                try:
                    next_link = driver.find_element(By.ID, "next")
                    next_url = urljoin(driver.current_url, next_link.get_attribute("href"))
                    driver.get(next_url)
                    time.sleep(2)
                except NoSuchElementException:
                    break

        normalized = [normalize_reservation(r) for r in all_reservations]
        return normalized

    finally:
        driver.quit()

# 手動実行用（テストなど）
if __name__ == "__main__":
    reservations = fetch_reservations()
    with open("reservations.json", "w", encoding="utf-8") as f:
        json.dump(reservations, f, ensure_ascii=False, indent=2)
    print(f"✅ 合計 {len(reservations)} 件の予約を reservations.json に保存しました。")
