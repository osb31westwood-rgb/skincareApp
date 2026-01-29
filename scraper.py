import datetime
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. スプレッドシートの設定 ---
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("wired-armor-484415-p1-745fc3210ef5.json", scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open("Cosme Data")
    return sh.worksheet("カルテ")

# --- 2. ブラウザの設定 ---
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_multiline_input(prompt):
    print(f"\n{prompt} (貼り付け後、改行して 'q' とだけ打ってEnterで確定)")
    lines = []
    while True:
        line = input()
        if line.strip() == 'q':  # 'q' と打ったら入力終了
            break
        lines.append(line)
    return "\n".join(lines)

# --- 選択肢の設定（ここを編集すれば項目を増やせます） ---
GENRE_LIST = ["スキンケア", "メイクアップ", "ヘアケア", "ボディケア"]
ITEM_TYPE_LIST = ["導入美容液", "化粧水", "乳液", "クリーム", "美容液", "洗顔/クレンジング", "パック/マスク", "日焼け止め"]

def get_choice_input(prompt, choices):
    print(f"\n--- {prompt}を選択してください ---")
    for i, choice in enumerate(choices, 1):
        print(f"{i}: {choice}")
    
    while True:
        try:
            val = int(input(f"番号を入力 (1-{len(choices)}): "))
            if 1 <= val <= len(choices):
                return choices[val-1]
        except ValueError:
            pass
        print("正しい番号を入力してください。")

def manual_scrape_store(url): # genreを引数から外しました
    try:
        driver.get(url)
        print(f"\n==================================================")
        print(f"📄 処理中: {url}")
        
        # 1. ジャンル選択
        genre = get_choice_input("ジャンル", GENRE_LIST)
        
        # 2. アイテムタイプ選択
        item_type = get_choice_input("アイテムタイプ", ITEM_TYPE_LIST)
        
        # 3. 商品名（ここは手入力）
        name = input("\n3. 【商品名】を貼り付けてEnter: ")
        
        # 4. 全成分・商品説明（さっきの改行OKモード）
        ingredients = get_multiline_input("4. 【全成分】を貼り付けてください")
        description = get_multiline_input("5. 【公式情報（商品説明）】を貼り付けてください")

        # --- スプレッドシートへの書き込み ---
        today = datetime.date.today().strftime('%Y/%m/%d')
        row = [today, today, "自動取得データ", genre, item_type, name, ingredients, description, "", "", ""]
        
        sheet = get_sheet()
        sheet.append_row(row)
        print(f"\n✅ スプレッドシートへ登録完了！: {name}")

    except Exception as e:
        print(f"\n❌ エラー: {e}")

def manual_scrape_store(url, genre):
    try:
        driver.get(url)
        print(f"\n==================================================")
        print(f"📄 処理中: {url}")
        print(f"==================================================")

        # 改行対応の入力方式に変更
        name = input("\n1. 【商品名】を貼り付けてEnter: ")
        item_type = input("2. 【アイテムタイプ】を貼り付けてEnter: ")
        
        # ここから改行OKモード
        ingredients = get_multiline_input("3. 【全成分】を貼り付けてください")
        description = get_multiline_input("4. 【公式情報（商品説明）】を貼り付けてください")

        # --- スプレッドシートへの書き込み ---
        today = datetime.date.today().strftime('%Y/%m/%d')
        row = [today, today, "自動取得データ", genre, item_type, name, ingredients, description, "", "", ""]
        
        sheet = get_sheet()
        sheet.append_row(row)
        print(f"\n✅ スプレッドシートへ登録完了！: {name}")

    except Exception as e:
        print(f"\n❌ エラー: {e}")

# --- 3. 実行エリア ---
# 調べたいURLをここに並べてください
target_urls = [
    "https://sekkisei.jp/site/g/gPYAK/",
]

for url in target_urls:
    manual_scrape_store(url, "スキンケア")

print("\nすべて完了しました。")
driver.quit()