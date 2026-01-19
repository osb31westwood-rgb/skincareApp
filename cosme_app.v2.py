import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse

# --- 1. 基本設定 ---
st.set_page_config(page_title="最新版CosmeInsight Pro", layout="wide")

COL_GENRE = "今回ご使用の商品のジャンルを選択してください。"
COL_AGE = "年齢" # スプレッドシートの年齢列名

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
        "scores": ["指通り・まとまり", "ツヤ感", "地肌の刺激・洗い心地", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
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
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return None

df = load_data()

# --- 3. メインUI ---
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成"])

if df is not None:
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

    else:
        # --- 共通の多段階フィルタリング ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 詳細フィルター")
        
        genre = st.selectbox("1. ジャンルを選択", list(COLUMN_CONFIG.keys()), key=f"{menu}_g")
        conf = COLUMN_CONFIG[genre]
        selected_type = st.selectbox("2. 種類を選択", conf["types"], key=f"{menu}_t")
        
        # 基礎絞り込み
        sub_df = df[(df[COL_GENRE] == genre) & (df[conf["type_col"]] == selected_type)].copy()
        
        # 年齢フィルター (サイドバーに配置)
        if COL_AGE in df.columns:
            age_list = sorted(df[COL_AGE].dropna().unique())
            selected_ages = st.sidebar.multiselect("👥 年齢層で絞り込む", age_list, default=age_list, key=f"{menu}_age")
            sub_df = sub_df[sub_df[COL_AGE].isin(selected_ages)]

        # お悩みフィルター
        if not sub_df.empty:
            all_concerns = []
            for row in sub_df[conf["concern_col"]].dropna():
                all_concerns.extend([c.strip() for c in str(row).split(',')])
            unique_concerns = sorted(list(set(all_concerns)))
            
            selected_concern = st.multiselect(f"3. {conf['concern_col']}で絞り込む", unique_concerns, key=f"{menu}_c")
            
            if selected_concern:
                sub_df = sub_df[sub_df[conf["concern_col"]].apply(lambda x: any(c in str(x) for c in selected_concern))]

        # --- 各機能の表示 ---
        if menu == "レーダーチャート比較":
            st.header("📊 スパイダーチャート分析")
            if not sub_df.empty:
                items = sub_df[conf["item_col"]].unique()
                selected_items = st.multiselect("4. 比較する商品を選択", items)
                if selected_items:
                    fig = go.Figure()
                    for item in selected_items:
                        item_data = sub_df[sub_df[conf["item_col"]] == item][conf["scores"]].mean()
                        fig.add_trace(go.Scatterpolar(r=item_data.values, theta=conf["scores"], fill='toself', name=item))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])))
                    st.plotly_chart(fig, width="stretch")
            else:
                st.info("条件に合うデータがありません。")

        elif menu == "分布図分析":
            st.header("📈 お悩み×満足度の分布")
            if not sub_df.empty:
                x_ax = st.selectbox("横軸を選択", conf["scores"], index=0)
                y_ax = st.selectbox("縦軸を選択", conf["scores"], index=len(conf["scores"])-1)
                fig = px.scatter(sub_df, x=x_ax, y=y_ax, color=COL_AGE, hover_name=conf["item_col"], 
                                 title=f"{genre} の分布分析", size_max=15)
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("条件に合うデータがありません。")

        elif menu == "AIポップ生成":
            st.header("📝 AI商品ポップ提案")
            if not sub_df.empty:
                items = sub_df[conf["item_col"]].unique()
                item_name = st.selectbox("4. 商品を選択", items)
                if st.button("提案を生成"):
                    item_stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
                    best = item_stats.idxmax()
                    
                    concern_txt = f"{', '.join(selected_concern)}に悩む" if selected_concern else ""
                    age_txt = f"{', '.join(map(str, selected_ages))}" if len(selected_ages) < len(age_list) else "幅広い世代"
                    
                    st.success(f"**【{item_name}】のPOP提案**\n\n"
                               f"ターゲット：{age_txt}の{concern_txt}お客様へ\n"
                               f"訴求ポイント：圧倒的な「{best}」\n\n"
                               f"キャッチコピー：『{age_txt}が選んだ、{best}の決定版。』")
            else:
                st.info("条件に合うデータがありません。")
else:
    st.error("データの読み込みに失敗しました。")