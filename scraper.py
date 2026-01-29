import time
import datetime
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- 1. スプレッドシートの設定 ---
def get_sheet():
    # 既存の認証ファイル（json）のパスを指定してください
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("wired-armor-484415-p1-745fc3210ef5.json", scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open("Cosme Data")
    return sh.worksheet("カルテ")

# --- 2. ブラウザの設定 ---
options = webdriver.ChromeOptions()
# options.add_argument('--headless') # 動きを見たい場合はコメントアウト
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def scrape_and_store(url, genre):
    try:
        driver.get(url)
        time.sleep(3)

        # サイト構造に合わせて取得（コーセー系共通クラス名を想定）
        name = driver.find_element(By.TAG_NAME, "h1").text
        
        # アイテムタイプ（カテゴリ）
        try:
            item_type = driver.find_element(By.CLASS_NAME, "p-product-detail__category").text
        except:
            item_type = "未分類"

        # 公式情報（商品説明）
        description = driver.find_element(By.CLASS_NAME, "p-product-detail__description").text

        # 全成分（ボタンをクリックして取得）
        try:
            target_btn = driver.find_element(By.XPATH, "//*[contains(text(), '全成分')]")
            driver.execute_script("arguments[0].click();", target_btn)
            time.sleep(1)
            ingredients = driver.find_element(By.CLASS_NAME, "p-product-detail__ingredients").text
        except:
            ingredients = "取得失敗（手動確認）"

        # --- スプレッドシートへの書き込みデータ作成 ---
        today = datetime.date.today().strftime('%Y/%m/%d')
        # 列順: [新規, 更新, 作成者, ジャンル, アイテムタイプ, 商品名, 全成分, 公式情報, AIコピー, メモ, 画像URL]
        row = [
            today,            # 新規
            today,            # 更新
            "自動取得データ",   # 作成者 ★ご指定通り
            genre,            # ジャンル
            item_type,        # アイテムタイプ
            name,             # 商品名
            ingredients,      # 全成分
            description,      # 公式情報
            "",               # AIコピー（空欄）
            "",               # メモ（空欄）
            ""                # 画像URL（空欄）
        ]
        
        sheet = get_sheet()
        sheet.append_row(row)
        print(f"✅ 登録完了: {name}")

    except Exception as e:
        print(f"❌ エラー ({url}): {e}")

# --- 3. 実行エリア ---
# ここにプレディアBLUEなどの商品URLをリストアップしてください
target_urls = [
    "https://sekkisei.jp/site/g/gPYAK/", # 例
    # 他のURLをここに並べる
]

for url in target_urls:
    scrape_and_store(url, "スキンケア")

driver.quit()