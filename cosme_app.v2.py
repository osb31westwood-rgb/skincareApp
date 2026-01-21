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
    genai.configure(api_key=st.secrets["AIzaSyDxw5AcNv3n6XoZSgLwAGF5-kcnbeuRR3Y"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# --- [中略: カラーパレットとCOLUMN_CONFIGは前回と同じ] ---
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
        "scores": ["発色の良さ", "質感の好み（ラメ・パール・ツヤ感・マット感）", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "クレンジングのしやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    }
}
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
 # 各機能の表示ロジック (分析系)
        if menu == "レーダーチャート比較":
            st.header("📊 スパイダーチャート分析")
            if not sub_df.empty:
                items = sub_df[conf["item_col"]].unique()
                selected_items = st.multiselect("4. 比較する商品を選択", items)
                if selected_items:
                    fig = go.Figure()
                    valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
                    for item in selected_items:
                        item_data = sub_df[sub_df[conf["item_col"]] == item][valid_scores].mean()
                        fig.add_trace(go.Scatterpolar(r=item_data.values, theta=valid_scores, fill='toself', name=item))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])))
                    st.plotly_chart(fig, width="stretch")
            else:
                st.info("条件に合うデータがありません。")

        elif menu == "分布図分析":
            st.header("📈 分析分布")
            if not sub_df.empty:
                valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
                x_ax = st.selectbox("横軸", valid_scores, index=0)
                y_ax = st.selectbox("縦軸", valid_scores, index=len(valid_scores)-1 if len(valid_scores)>1 else 0)
                fig = px.scatter(sub_df, x=x_ax, y=y_ax, color=COL_AGE, hover_name=conf["item_col"])
                st.plotly_chart(fig, width="stretch")

        elif menu == "AIポップ生成":
            st.header("📝 AI商品ポップ提案")
            if not sub_df.empty:
                items = sub_df[conf["item_col"]].unique()
                item_name = st.selectbox("商品を選択", items)
                if st.button("生成"):
                    valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
                    item_stats = sub_df[sub_df[conf["item_col"]] == item_name][valid_scores].mean()
                    best = item_stats.idxmax()
                    st.success(f"強み：{best}！ キャッチコピー案：『{best}を実感。』")

else:
    st.error("データの読み込みに失敗しました。")