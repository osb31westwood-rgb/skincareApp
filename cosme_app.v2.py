import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse
import google.generativeai as genai

# --- 1. 基本設定 ---
st.set_page_config(page_title="CosmeInsight Pro v5 (AI Connect)", layout="wide")

# Gemini APIの初期化
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# --- [中略: カラーパレットとCOLUMN_CONFIGは前回と同じ] ---
COLOR_PALETTES = {
    "ナチュラル（自然派）": ["#a98467", "#adc178", "#dde5b6", "#6c584c", "#f0ead2"],
    "くすみカラー": ["#8e9775", "#e28e8e", "#94a7ae", "#a79c93", "#d4a5a5"],
    "ミルクカラー": ["#f3e9dc", "#c0d6df", "#d8e2dc", "#ffe5d9", "#fbfacd"],
    "パステルカラー": ["#ffb7b2", "#ffdac1", "#e2f0cb", "#b5ead7", "#c7ceea"],
    "ローズ系": ["#e5989b", "#ffb4a2", "#ffcdb2", "#b5838d", "#6d597a"]
}

# (以前のCOLUMN_CONFIGをここに貼り付けてください)

# --- 2. データ読み込み ---
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

# --- 3. メインUI ---
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成", "商品POPカルテ"])

selected_theme = st.sidebar.selectbox("📊 配色テーマ", list(COLOR_PALETTES.keys()))
theme_colors = COLOR_PALETTES[selected_theme]

if df is not None:
    # --- 共通フィルタリング ---
    genre = st.sidebar.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="main_g")
    conf = COLUMN_CONFIG[genre]
    sub_df = df[df[COL_GENRE] == genre].copy()

    # --- AIポップ生成（Gemini連携版） ---
    if menu == "AIポップ生成":
        st.header("✨ Gemini AI キャッチコピー生成")
        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        item_name = st.selectbox("分析する商品を選択", items)

        if st.button("AIにキャッチコピーを考えてもらう"):
            # 分析データの抽出
            stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
            best_point = stats.idxmax()
            best_score = round(stats.max(), 1)
            
            prompt = f"""
            あなたはコスメ専門のコピーライターです。
            以下のアンケート結果に基づき、店頭POPで使える魅力的なキャッチコピーを3案提案してください。
            
            商品名: {item_name}
            最も評価された点: {best_point} (5点満点中 {best_score}点)
            
            条件:
            - 1案目は20文字以内の短いキャッチコピー
            - 2案目はターゲットの悩みに寄り添ったコピー
            - 3案目は思わず手に取りたくなるワクワクするコピー
            - 専門用語を使いすぎず、親しみやすい日本語で。
            """

            if model:
                try:
                    with st.spinner("Geminiが思考中..."):
                        response = model.generate_content(prompt)
                        st.success("🤖 Geminiからの提案")
                        st.markdown(response.text)
                except Exception as e:
                    st.error(f"AIエラーが発生しました: {e}")
            else:
                st.warning("APIキーが設定されていません。定型文を表示します。")
                st.info(f"【{item_name}】の強み：{best_point}！ 『もう手放せない、圧倒的な{best_point}を。』")

    # --- [レーダーチャートや分布図のロジックをここに維持] ---

else:
    st.error("データの読み込みに失敗しました。")