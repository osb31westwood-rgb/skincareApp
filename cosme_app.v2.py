import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse

# --- 1. 基本設定 ---
# 2026年最新仕様に合わせた設定
st.set_page_config(page_title="最新版CosmeInsight Pro", layout="wide")

COL_GENRE = "今回ご使用の商品のジャンルを選択してください。"

COLUMN_CONFIG = {
    "スキンケア商品（フェイスケア・ボディケア）": {
        "item_col": "今回ご使用の商品名を入力してください。",
        "type_col": "スキンケア商品を選択した方は種類を選択してください。",
        "concern_col": "肌悩み（※複数選択可）",
        "types": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア（ハンドクリーム）", "ボディウォッシュ（ボディソープ）", "ボディケア（ボディミスト・ボディクリーム・ボディオイル)", "その他"],
        "scores": ["肌なじみ・透明感", "しっとり感", "さらっと感", "肌への負担感のなさ・優しさ", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "ヘアケア商品": {
        "item_col": "今回ご使用の商品名を入力してください。.1",
        "type_col": "ヘアケア商品を選択した方は種類を選択してください。",
        "concern_col": "髪のお悩み（※複数選択可）",
        "types": ["シャンプー", "コンディショナー・トリートメント（洗い流すタイプ）", "アウトバストリートメント（ミスト・ミルク・オイルなど洗い流さないタイプ）", "スペシャルケア（ヘアマスク・頭皮クレンジングなど）", "スタイリング剤・整髪料（ワックス・ジェル・スプレーなど）", "その他（ヘアブラシ・ドライヤー・ヘアタイなど）"],
        "scores": ["指通り・まとまり", "ツヤ感", "肌への負担感」のなさ・優しさ", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "コスメ商品（ベースメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.2",
        "type_col": "コスメ商品（ベースメイク）を選択した方は種類を選択してください。",
        "concern_col": "肌悩み（※複数選択可）",
        "types": ["日焼け止め・UVカット", "化粧下地（コントロールカラー・UV下地）", "パウダーファンデーション", "リキッドファンデーション", "クッションファンデーション", "BBクリーム・CCクリーム", "フェイスパウダー（ルース・プレスト）", "メイクキープ（フィックスミスト）その他"],
        "scores": ["伸びの良さ・密着感", "仕上がりの美しさ", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "肌への負担感の少なさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    },
    "コスメ商品（ポイントメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.3",
        "type_col": "コスメ商品（ポイントメイク）を選択した方は種類を選択してください。",
        "concern_col": "肌悩み（※複数選択可）",
        "types": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ・マスカラ下地", "リップ・口紅・グロス・ティント", "チーク", "ハイライト・シェーディング", "その他"],
        "scores": ["発色の良さ", "質感の好み（ラメ・パール・ツヤ感・マット感）", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "クレンジングのしやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    }
}

# --- 2. データ読み込み ---
@st.cache_data(ttl=300)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5HpURwDWt6S0KkQbiS8ugZksNm8yTokNeKE4X-oBHmLMubOvOKIsuU4q6_onLta2cd0brCBQc-cHA/pub?gid=1578087772&single=true&output=csv"
    try:
        return pd.read_csv(url)
    except:
        return None

df = load_data()

# --- 3. メインUI ---
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成"])

if df is not None:
    # (1) QR生成
    if menu == "QR生成":
        st.header("📲 アンケート回答用QR作成")
        q_genre = st.selectbox("ジャンルを選択", list(COLUMN_CONFIG.keys()))
        q_type = st.selectbox("種類を選択", COLUMN_CONFIG[q_genre]["types"])
        q_item = st.text_input("商品名を入力")
        if st.button("QRコードを発行"):
            params = urllib.parse.urlencode({"entry.500746217": q_genre, "entry.1507235458": q_item})
            full_url = f"https://docs.google.com/forms/d/e/1FAIpQLSdBubITUy2hWaM8z9Ryo4QV6qKF0A1cnUnFEM49E6tdf8JeXw/viewform?usp=pp_url&{params}"
            qr = qrcode.make(full_url)
            buf = BytesIO()
            qr.save(buf)
            st.image(buf.getvalue(), width="stretch")

    # (2) レーダーチャート
    elif menu == "レーダーチャート比較":
        st.header("📊 スパイダーチャート分析")
        genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="r_g")
        conf = COLUMN_CONFIG[genre]
        selected_type = st.selectbox("種類（小分類）", conf["types"], key="r_t")
        sub_df = df[(df[COL_GENRE] == genre) & (df[conf["type_col"]] == selected_type)].copy()
        
        if not sub_df.empty:
            items = sub_df[conf["item_col"]].unique()
            selected_items = st.multiselect("商品を選択", items)
            if selected_items:
                fig = go.Figure()
                for item in selected_items:
                    item_data = sub_df[sub_df[conf["item_col"]] == item][conf["scores"]].mean()
                    fig.add_trace(go.Scatterpolar(r=item_data.values, theta=conf["scores"], fill='toself', name=item))
                st.plotly_chart(fig, width="stretch")

    # (3) 分布図分析
    elif menu == "分布図分析":
        st.header("📈 お悩み×満足度の分布")
        genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="d_g")
        conf = COLUMN_CONFIG[genre]
        selected_type = st.selectbox("種類", conf["types"], key="d_t")
        sub_df = df[(df[COL_GENRE] == genre) & (df[conf["type_col"]] == selected_type)]
        if not sub_df.empty:
            x_ax = st.selectbox("横軸", conf["scores"], index=0)
            y_ax = st.selectbox("縦軸", conf["scores"], index=len(conf["scores"])-1)
            fig = px.scatter(sub_df, x=x_ax, y=y_ax, color="年齢", hover_name=conf["item_col"])
            st.plotly_chart(fig, width="stretch")

    # (4) AIポップ生成
    elif menu == "AIポップ生成":
        st.header("📝 AI商品ポップ提案")
        genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="a_g")
        conf = COLUMN_CONFIG[genre]
        selected_type = st.selectbox("種類", conf["types"], key="a_t")
        sub_df = df[(df[COL_GENRE] == genre) & (df[conf["type_col"]] == selected_type)]
        items = sub_df[conf["item_col"]].unique()
        if len(items) > 0:
            item_name = st.selectbox("商品", items)
            if st.button("提案を生成"):
                item_stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
                best = item_stats.idxmax()
                st.success(f"【{item_name}】の強み：{best}！ キャッチコピー案：『もう手放せない、圧倒的な{best}を。』")
else:
    st.error("データの読み込みに失敗しました。")