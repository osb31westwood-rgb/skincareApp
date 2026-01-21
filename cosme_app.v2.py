import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. 基本設定 ---
st.set_page_config(page_title="CosmeInsight Pro v5", layout="wide")

# Gemini APIの初期化
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# スプレッドシート接続関数
def get_gspread_client():
    s_acc = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        s_acc,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(credentials)

# 定数・カラーパレット
COL_GENRE = "今回ご使用の商品のジャンルを選択してください。"
COL_AGE = "年齢"
COLOR_PALETTES = {
    "ナチュラル（自然派）": ["#a98467", "#adc178", "#dde5b6", "#6c584c", "#f0ead2"],
    "くすみカラー": ["#8e9775", "#e28e8e", "#94a7ae", "#a79c93", "#d4a5a5"],
    "ミルクカラー": ["#f3e9dc", "#c0d6df", "#d8e2dc", "#ffe5d9", "#fbfacd"],
    "パステルカラー": ["#ffb7b2", "#ffdac1", "#e2f0cb", "#b5ead7", "#c7ceea"],
    "ローズ系": ["#e5989b", "#ffb4a2", "#ffcdb2", "#b5838d", "#6d597a"]
}

# カラム設定（全ジャンル）
COLUMN_CONFIG = {
    "スキンケア商品（フェイスケア・ボディケア）": {
        "item_col": "今回ご使用の商品名を入力してください。",
        "type_col": "スキンケア商品を選択した方は種類を選択してください。",
        "concern_col_keyword": "肌悩み",
        "types": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア（ハンドクリーム）", "ボディウォッシュ（ボディソープ）", "ボディケア（ボディミスト・ボディクリーム・ボディオイル)", "その他"],
        "scores": ["肌なじみ・透明感", "しっとり感", "さらっと感", "肌への負担感のなさ・優しさ", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "ヘアケア商品": {
        "item_col": "今回ご使用の商品名を入力してください。.1",
        "type_col": "ヘアケア商品を選択した方は種類を選択してください。",
        "concern_col_keyword": "髪のお悩み",
        "types": ["シャンプー", "コンディショナー・トリートメント（洗い流すタイプ）", "アウトバストリートメント（ミスト・ミルク・オイルなど洗い流さないタイプ）", "スペシャルケア（ヘアマスク・頭皮クレンジングなど）", "スタイリング剤・整髪料（ワックス・ジェル・スプレーなど）", "その他（ヘアブラシ・ドライヤー・ヘアタイなど）"],
        "scores": ["指通り・まとまり", "ツヤ感", "地肌の刺激・洗い心地", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "コスメ商品（ベースメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.2",
        "type_col": "コスメ商品（ベースメイク）を選択した方は種類を選択してください。",
        "concern_col_keyword": "肌悩み",
        "types": ["日焼け止め・UVカット", "化粧下地（コントロールカラー・UV下地）", "パウダーファンデーション", "リキッドファンデーション", "クッションファンデーション", "BBクリーム・CCクリーム", "フェイスパウダー（ルース・プレスト）", "メイクキープ（フィックスミスト）その他"],
        "scores": ["伸びの良さ・密着感", "仕上がりの美しさ", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "肌への負担感の少なさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "コスメ商品（ポイントメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.3",
        "type_col": "コスメ商品（ポイントメイク）を選択した方は種類を選択してください。",
        "concern_col_keyword": "肌悩み",
        "types": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ・マスカラ下地", "リップ・口紅・グロス・ティント", "チーク", "ハイライト・シェーディング", "その他"],
        "scores": ["発色の良さ", "質感の好み（ラメ・パール・ツヤ感・マット感）", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "クレンジングのやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    }
}

# データ読み込み
@st.cache_data(ttl=300)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5HpURwDWt6S0KkQbiS8ugZksNm8yTokNeKE4X-oBHmLMubOvOKIsuU4q6_onLta2cd0brCBQc-cHA/pub?gid=1578087772&single=true&output=csv"
    try:
        data = pd.read_csv(url)
        data.columns = [str(c).strip() for c in data.columns]
        return data
    except:
        return None

df = load_data()

# サイドバー設定
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成", "商品POPカルテ"])
selected_theme = st.sidebar.selectbox("📊 配色テーマ", list(COLOR_PALETTES.keys()))
theme_colors = COLOR_PALETTES[selected_theme]

if df is not None:
    if menu == "QR生成":
        st.header("📲 アンケート回答用QR作成")
        q_genre = st.selectbox("ジャンルを選択", list(COLUMN_CONFIG.keys()))
        q_item = st.text_input("商品名を入力")
        if st.button("QRコードを発行"):
            params = urllib.parse.urlencode({"entry.500746217": q_genre, "entry.1507235458": q_item})
            full_url = f"https://docs.google.com/forms/d/e/1FAIpQLSdBubITUy2hWaM8z9Ryo4QV6qKF0A1cnUnFEM49E6tdf8JeXw/viewform?usp=pp_url&{params}"
            qr = qrcode.make(full_url)
            buf = BytesIO()
            qr.save(buf)
            st.image(buf.getvalue(), width=300)
            # 共通フィルタリング
    genre = st.sidebar.selectbox("分析ジャンル", list(COLUMN_CONFIG.keys()), key="main_g")
    conf = COLUMN_CONFIG[genre]
    sub_df = df[df[COL_GENRE] == genre].copy()

    if menu == "レーダーチャート比較":
        st.header(f"📊 スパイダー分析 ({selected_theme})")
        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        selected_items = st.multiselect("商品を選択", items)
        if selected_items:
            fig = go.Figure()
            valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
            for i, item in enumerate(selected_items):
                item_data = sub_df[sub_df[conf["item_col"]] == item][valid_scores].mean()
                color = theme_colors[i % len(theme_colors)]
                fig.add_trace(go.Scatterpolar(r=item_data.values, theta=valid_scores, fill='toself', name=item, line=dict(color=color), fillcolor=color, opacity=0.5))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    elif menu == "分布図分析":
        st.header(f"📈 分析分布 ({selected_theme})")
        valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
        x_ax = st.selectbox("横軸", valid_scores, index=0)
        y_ax = st.selectbox("縦軸", valid_scores, index=len(valid_scores)-1 if len(valid_scores)>1 else 0)
        fig = px.scatter(sub_df, x=x_ax, y=y_ax, color=COL_AGE, hover_name=conf["item_col"], color_discrete_sequence=theme_colors)
        st.plotly_chart(fig, use_container_width=True)

    elif menu == "AIポップ生成":
        st.header("✨ Gemini AI キャッチコピー案")
        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        item_name = st.selectbox("商品を選択", items)
        if st.button("AIコピーを生成"):
            stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
            best_point = stats.idxmax()
            prompt = f"商品名:{item_name}、顧客が最も評価した点:{best_point}。コスメ好きが思わず手に取る、Canvaで使えるポップ用コピーを3案提案して。"
            if model:
                with st.spinner("AIが考え中..."):
                    res = model.generate_content(prompt)
                    st.success("🤖 AIの提案")
                    st.write(res.text)
            else: st.warning("APIキー未設定です。")

    elif menu == "商品POPカルテ":
        st.header("📋 共有商品POPカルテ")
        with st.expander("📝 カルテを新規保存", expanded=True):
            creator = st.text_input("作成者名")
            item_name = st.selectbox("商品を選択", sorted(sub_df[conf["item_col"]].dropna().unique()))
            ai_copy = st.text_area("AIポップコピー案（メモ）")
            official_info = st.text_area("公式情報・成分など")
            if st.button("💾 スプレッドシートへ保存"):
                if creator and item_name:
                    try:
                        client = get_gspread_client()
                        sh = client.open("あなたのスプレッドシート名") # ←重要！
                        sheet = sh.worksheet("カルテ")
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        sheet.append_row([now, creator, item_name, ai_copy, official_info])
                        st.success("保存完了！")
                    except Exception as e: st.error(f"エラー: {e}")

        st.markdown("---")
        st.subheader("📚 過去のカルテ一覧")
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data") # ←重要！
            sheet = sh.worksheet("カルテ")
            records = sheet.get_all_records()
            if records:
                for i, row in enumerate(records):
                    with st.expander(f"{row['日付']} | {row['商品名']} ({row['作成者']})"):
                        st.write(f"**コピー:** {row['AIコピー']}")
                        st.write(f"**公式:** {row['公式情報']}")
                        if st.button("🗑️ 削除", key=f"del_{i}"):
                            sheet.delete_rows(i + 2)
                            st.rerun()
            else: st.info("データがありません。")
        except: st.write("データを読み込めませんでした。")
else:
    st.error("スプレッドシートの読み込みに失敗しました。")