import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import qrcode
from io import BytesIO
import urllib.parse

# --- 1. 基本設定 ---
st.set_page_config(page_title="CosmeInsight Pro v3", layout="wide")

# セッション状態の初期化（カルテ保存用）
if "pop_charts" not in st.session_state:
    st.session_state.pop_charts = {}

COL_GENRE = "今回ご使用の商品のジャンルを選択してください。"
COL_AGE = "年齢"

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

# --- 3. メインメニュー ---
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成", "商品POPカルテ"])

if df is not None:
    if menu == "商品POPカルテ":
        st.header("📋 商品POPカルテ（制作指示書）")
        st.info("分析結果と画像を組み合わせて、Canva制作用の下書きを作ります。")

        # 1. 商品の選択
        genre = st.selectbox("ジャンルを選択", list(COLUMN_CONFIG.keys()))
        conf = COLUMN_CONFIG[genre]
        sub_df = df[df[COL_GENRE] == genre]
        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        item_name = st.selectbox("商品を選択", items)

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📷 ビジュアル設定")
            uploaded_file = st.file_uploader("商品の画像をアップロード", type=['png', 'jpg', 'jpeg'])
            if uploaded_file:
                st.image(uploaded_file, caption="使用する画像イメージ", width=300)
            
            official_desc = st.text_area("公式キャッチコピー・成分特徴", placeholder="例：ビタミンC配合で透明感アップ...")

        with col2:
            st.subheader("📊 分析データからの強み")
            # 商品の平均スコアを計算
            item_stats = sub_df[sub_df[conf["item_col"]] == item_name][conf["scores"]].mean()
            if not item_stats.empty:
                best_attr = item_stats.idxmax()
                st.success(f"顧客が感じた最大の魅力: **{best_attr}**")
                
                # AIポップ案の自動生成
                ai_copy = st.text_input("AIポップ案", value=f"お客様が選んだ『{best_attr}』の最高傑作。")
                
                # 色味や雰囲気の指定
                design_theme = st.select_slider("デザインの雰囲気", options=["可愛い", "ナチュラル", "シンプル", "高級感", "クール"])
                
                if st.button("カルテを保存"):
                    st.session_state.pop_charts[item_name] = {
                        "copy": ai_copy,
                        "desc": official_desc,
                        "theme": design_theme,
                        "best": best_attr
                    }
                    st.balloons()

        # 保存済みカルテの表示
        if st.session_state.pop_charts:
            st.markdown("---")
            st.subheader("📝 Canva制作メモ（保存済み）")
            for name, data in st.session_state.pop_charts.items():
                with st.expander(f"{name} の制作メモ"):
                    st.write(f"**【メインコピー】** {data['copy']}")
                    st.write(f"**【強みデータ】** {data['best']}")
                    st.write(f"**【公式情報】** {data['desc']}")
                    st.write(f"**【デザイン指示】** {data['theme']}な雰囲気で作成")

    elif menu == "QR生成":
        # (以前のQRコード生成ロジック)
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
            st.image(buf.getvalue(), width=300)

    else:
        # 分析系メニュー（チャート、分布図、AIポップ）
        # (ここには以前実装した共通フィルターと分析ロジックが入ります)
        genre = st.selectbox("1. ジャンルを選択", list(COLUMN_CONFIG.keys()), key=f"{menu}_g")
        conf = COLUMN_CONFIG[genre]
        selected_type = st.selectbox("2. 種類を選択", conf["types"], key=f"{menu}_t")
        sub_df = df[(df[COL_GENRE] == genre) & (df[conf["type_col"]] == selected_type)].copy()
        
        # ... (中略: レーダーチャート等の描画ロジック) ...
        if menu == "レーダーチャート比較":
            st.header("📊 スパイダーチャート分析")
            items = sub_df[conf["item_col"]].unique()
            selected_items = st.multiselect("商品を選択", items)
            if selected_items:
                fig = go.Figure()
                for item in selected_items:
                    item_data = sub_df[sub_df[conf["item_col"]] == item][conf["scores"]].mean()
                    fig.add_trace(go.Scatterpolar(r=item_data.values, theta=conf["scores"], fill='toself', name=item))
                st.plotly_chart(fig)
        
        # ※コードが長くなりすぎるため、他の分析メニューの詳細は以前のものを引き継いでください