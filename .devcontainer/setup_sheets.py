import gspread
import gspread
import json
import streamlit as st
from google.oauth2.service_account import Credentials

def get_gspread_client():
    # GitHubのSecrets（Streamlit経由）からJSONを読み込む
    # st.secrets["gcp_service_account"] の名前は自分の設定に合わせてね！
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    
    # 権限の範囲（スコープ）を設定
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # 認証情報を作成
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    # スプレッドシートのクライアントを返却
    return gspread.authorize(creds)

# 使い方
# client = get_gspread_client()
# spreadsheet = client.open_by_key("スプレッドシートのID")
# 1. 接続の準備（既に認証済みの spreadsheet オブジェクトを使っている前提だよ）
# spreadsheet = client.open("スプレッドシート名") 
client = get_gspread_client()
spreadsheet = client.open("Cosme Data")
# --- 2. データの定義（姉ちゃんの今のコードから抜粋） ---
GENRE_ID_MAP = {
    "スキンケア商品（フェイスケア・ボディケア）": 10,
    "ヘアケア商品": 20,
    "コスメ商品（ベースメイク）": 30,
    "コスメ商品（ポイントメイク）": 40
}

# 姉ちゃんの COLUMN_CONFIG をそのまま使うよ
# (長いから一部省略して書いてるけど、実際のコードのやつをそのまま読み込ませればOK！)
# COLUMN_CONFIG = { ... }
COLUMN_CONFIG = {
    "スキンケア商品（フェイスケア・ボディケア）": {
        "item_col": "今回ご使用の商品名を入力してください。",
        "type_col": "スキンケア商品を選択した方はアイテムタイプを選択してください。",
        "form_id": "entry.1030688450",
        "scores": ["肌なじみ・透明感", "しっとり感", "さらっと感", "肌への負担感のなさ・優しさ", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア（ハンドクリーム）", "ボディウォッシュ（ボディソープ）", "ボディケア（ボディミスト・ボディクリーム・ボディオイル)", "その他"]
    },
    "ヘアケア商品": {
        "item_col": "今回ご使用の商品名を入力してください。.1",
        "type_col": "ヘアケア商品を選択した方はアイテムタイプを選択してください。",
        "form_id": "entry.279505478",
        "scores": ["指通り・まとまり", "ツヤ感", "肌への負担感のなさ・優しさ", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["シャンプー", "コンディショナー・トリートメント", "アウトバストリートメント", "スペシャルケア", "スタイリング剤", "その他"]
    },
    "コスメ商品（ベースメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.2",
        "type_col": "コスメ商品（ベースメイク）を選択した方はアイテムタイプを選択してください。",
        "form_id": "entry.997470046",
        "scores": ["伸びの良さ・密着感", "仕上がりの美しさ", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "肌への負担感の少なさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["日焼け止め・UV", "化粧下地", "ファンデーション", "BB・CCクリーム", "フェイスパウダー", "その他"]
    },
    "コスメ商品（ポイントメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.3",
        "type_col": "コスメ商品（ポイントメイク）を選択した方はアイテムタイプを選択してください。",
        "form_id": "entry.948471097",
        "scores": ["発色の良さ", "質感の好み", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "クレンジングのやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ", "リップ・口紅", "チーク", "その他"]
    }
}
# --- 3. シートの準備（初期化） ---
SHEET_NAME = "商品構成"
try:
    config_sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="100", cols="10")
except:
    config_sheet = spreadsheet.worksheet(SHEET_NAME)
    config_sheet.clear() # 一旦真っさらにして書き直す

# --- 4. データの整形（ここがヘビ使いの腕の見せ所！） ---
# ヘッダー（見出し）
rows_to_upload = [["ジャンルID", "タイプID", "ジャンル名", "アイテムタイプ", "評価項目リスト", "フォームID"]]

for genre_name, config in COLUMN_CONFIG.items():
    # ジャンルIDを取得（見つからない場合はとりあえず 0）
    genre_id = GENRE_ID_MAP.get(genre_name, 0)
    
    for i, t_name in enumerate(config["types"]):
        # 基本は 1, 2, 3... と連番を振る
        # 姉ちゃんのこだわり「その他」は特別に 99 番にする！
        if t_name == "その他":
            type_id = 99
        else:
            type_id = i + 1
            
        # 評価項目のリスト ['肌なじみ', 'しっとり'] を '肌なじみ,しっとり' という文字に変換
        score_str = ",".join(config["scores"])
        
        # 1行分のデータを作成
        rows_to_upload.append([
            genre_id, 
            type_id, 
            genre_name, 
            t_name, 
            score_str, 
            config["form_id"]
        ])

# --- 5. スプレッドシートへ一括書き込み！ ---
# リストのサイズに合わせて範囲を自動計算（A1 から F の末尾まで）
target_range = f"A1:F{len(rows_to_upload)}"
config_sheet.update(target_range, rows_to_upload)

print(f"✨ 成功！『{SHEET_NAME}』シートに全データを引っ越したよ！")
print(f"✅ ジャンルIDの割り当て完了")
print(f"✅ 『その他』を ID:99 に固定完了")
print(f"✅ 評価項目をカンマ区切りで保存完了")