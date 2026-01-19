import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse  # これが必要でした！

# --- 1. 基本設定 ---
st.set_page_config(page_title="CosmeInsight Pro", layout="wide")

COLUMN_CONFIG = {
    "スキンケア商品（フェイスケア・ボディケア）": {
        "item_col": "今回ご使用の商品名を入力してください。",
        "type_col": "スキンケア商品を選択した方は種類を選択してください。",
        "concern_col": "肌悩み（※複数選択可）",
        "types": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア（ハンドクリーム）", "ボディウォッシュ（ボディソープ）", "ボディケア（ボディミスト・ボディクリーム・ボディオイル)", "その他"],
        "scores": ["肌なじみ・透明感", "しっとり感", "さらっと感", "刺激のなさ・優しさ", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
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
    },
    "その他": {
        "item_col": "今回ご使用の商品名を入力してください。.4",
        "type_col": "商品の種類を入力してください。",
        "concern_col": "肌悩み（※複数選択可）",
        "types": ["その他"],
        "scores": ["使用感のよさ（テクスチャーや使い心地）", "仕上がりの満足度", "持続性・キープ力", "肌当たり・優しさ", "クレンジング・手入れのしやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"]
    }
}

# --- 2. データ読み込み ---
@st.cache_data(ttl=300)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5HpURwDWt6S0KkQbiS8ugZksNm8yTokNeKE4X-oBHmLMubOvOKIsuU4q6_onLta2cd0brCBQc-cHA/pub?gid=1578087772&single=true&output=csv"
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        return None

df = load_data()

# --- 3. メインUI ---
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成"])

# --- 4. 各メニューの処理 ---

# (1) QR生成機能
if menu == "QR生成":
    st.header("📲 アンケート回答用QR作成")
    st.info("お客様が読み取ると、商品情報が自動入力された状態でアンケートが開きます。")

    q_genre = st.selectbox("1. ジャンルを選択", list(COLUMN_CONFIG.keys()))
    q_type = st.selectbox("2. 種類を選択", COLUMN_CONFIG[q_genre]["types"])
    q_item = st.text_input("3. 商品名を入力（例：雪肌精 化粧水）")

    if st.button("アンケート用QRコードを発行"):
        if not q_item:
            st.error("商品名を入力してください！")
        else:
            base_url = "https://docs.google.com/forms/d/e/1FAIpQLSdBubITUy2hWaM8z9Ryo4QV6qKF0A1cnUnFEM49E6tdf8JeXw/viewform?usp=pp_url"
            
            # entry IDの割り当て
            params = {
                "entry.500746217": q_genre,
                "entry.1507235458": q_item
            }
            if q_genre == "スキンケア商品（フェイスケア・ボディケア）":
                params["entry.1030688450"] = q_type
            elif q_genre == "ヘアケア商品":
                params["entry.279505478"] = q_type
            elif q_genre == "コスメ商品（ベースメイク）":
                params["entry.997470046"] = q_type
            elif q_genre == "コスメ商品（ポイントメイク）":
                params["entry.948471097"] = q_type

            query_string = urllib.parse.urlencode(params)
            full_url = f"{base_url}&{query_string}"

            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(full_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = BytesIO()
            img.save(buf)
            st.divider()
            st.subheader(f"【{q_type}】{q_item}")
            st.image(buf.getvalue(), caption="店頭POPに貼り付けて使用してください")
            st.code(full_url, language="text")

# (2) レーダーチャート比較
elif menu == "レーダーチャート比較":
    st.header("📊 スパイダーチャート分析")
    if df is not None:
        genre = st.selectbox("分析ジャンル", list(COLUMN_CONFIG.keys()))
        conf = COLUMN_CONFIG[genre]
        sub_df = df[df["今回ご使用の商品のジャンルを選択してください。"] == genre].copy()
        
        analysis_mode = st.radio("分析軸を選んでください", ["商品ごとに比較", "年代別に比較", "お悩み別に比較"])

        if analysis_mode == "商品ごとに比較":
            items = sub_df[conf["item_col"]].unique()
            selected_items = st.multiselect("商品を選択", items)
            if selected_items:
                fig = go.Figure()
                for item in selected_items:
                    item_data = sub_df[sub_df[conf["item_col"]] == item][conf["scores"]].mean()
                    fig.add_trace(go.Scatterpolar(r=item_data.values, theta=conf["scores"], fill='toself', name=item))
                st.plotly_chart(fig, use_container_width=True)

        elif analysis_mode == "年代別に比較":
            item_names = sub_df[conf["item_col"]].unique()
            if len(item_names) > 0:
                item_name = st.selectbox("分析したい商品を選択", item_names)
                target_df = sub_df[sub_df[conf["item_col"]] == item_name]
                available_ages = sorted(target_df["年齢"].unique())
                selected_ages = st.multiselect("比較する年代を選択", available_ages, default=available_ages)
                
                fig = go.Figure()
                for age in selected_ages:
                    age_data = target_df[target_df["年齢"] == age][conf["scores"]].mean()
                    fig.add_trace(go.Scatterpolar(r=age_data.values, theta=conf["scores"], fill='toself', name=f"{age}"))
                st.plotly_chart(fig, use_container_width=True)

        elif analysis_mode == "お悩み別に比較":
            item_names = sub_df[conf["item_col"]].unique()
            if len(item_names) > 0:
                item_name = st.selectbox("分析したい商品を選択", item_names)
                target_df = sub_df[sub_df[conf["item_col"]] == item_name]
                concern_col = conf["concern_col"]
                all_concerns = []
                for c in target_df[concern_col].dropna():
                    all_concerns.extend([x.strip() for x in str(c).split(',')])
                unique_concerns = sorted(list(set(all_concerns)))
                selected_concerns = st.multiselect("比較するお悩みを選択", unique_concerns)
                
                if selected_concerns:
                    fig = go.Figure()
                    for concern in selected_concerns:
                        concern_df = target_df[target_df[concern_col].str.contains(concern, na=False)]
                        concern_data = concern_df[conf["scores"]].mean()
                        fig.add_trace(go.Scatterpolar(r=concern_data.values, theta=conf["scores"], fill='toself', name=f"悩み：{concern}"))
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("データが読み込めていません。")

# (3) 分布図分析
elif menu == "分布図分析":
    st.header("📈 お悩み×満足度の分布")
    if df is not None:
        genre = st.selectbox("分析ジャンル", list(COLUMN_CONFIG.keys()))
        conf = COLUMN_CONFIG[genre]
        sub_df = df[df["今回ご使用の商品のジャンルを選択してください。"] == genre]
        if not sub_df.empty:
            x_axis = st.selectbox("横軸（項目）", conf["scores"], index=0)
            y_axis = st.selectbox("縦軸（項目）", conf["scores"], index=len(conf["scores"])-1)
            fig = px.scatter(sub_df, x=x_axis, y=y_axis, color="年齢", hover_name=conf["item_col"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("このジャンルのデータはまだありません。")

# (4) AIポップ生成
elif menu == "AIポップ生成":
    st.header("📝 AI商品ポップ提案")
    if df is not None:
        genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="pop_genre")
        conf = COLUMN_CONFIG[genre]
        sub_df = df[df["今回ご使用の商品のジャンルを選択してください。"] == genre]
        item_names = sub_df[conf["item_col"]].unique()
        
        if len(item_names) > 0:
            item_name = st.selectbox("ポップを作りたい商品", item_names)
            item_stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
            best_feature = item_stats.idxmax()
            
            st.subheader(f"🔍 {item_name} の分析結果")
            st.write(f"この商品の最大の強みは **「{best_feature}」** です！")
            tone = st.select_slider("雰囲気", options=["信頼感（プロ風）", "親しみやすい", "おしゃれ・エモい", "インパクト重視"])
            
            if st.button("キャッチコピー案を生成"):
                if tone == "信頼感（プロ風）":
                    st.info(f"【案】データが証明する実力。{best_feature}に妥協したくないあなたへ。")
                elif tone == "親しみやすい":
                    st.success(f"【案】スタッフも驚いた！{item_name}で毎日がもっと楽しくなる。")
                elif tone == "おしゃれ・エモい":
                    st.warning(f"【案】光を味方に。{best_feature}が導く、新しい私。")
                else:
                    st.error(f"【案】リピート確定！？この「{best_feature}」は事件です。")
        else:
            st.write("まだ分析対象の商品データがありません。")