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
    model = genai.GenerativeModel('models/gemini-1.5-flash')
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

# ジャンル別カラム・ID設定
COLUMN_CONFIG = {
    "スキンケア商品（フェイスケア・ボディケア）": {
        "item_col": "今回ご使用の商品名を入力してください。",
        "type_col": "スキンケア商品を選択した方は種類を選択してください。",
        "form_id": "entry.1030688450",
        "scores": ["肌なじみ・透明感", "しっとり感", "さらっと感", "肌への負担感のなさ・優しさ", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア（ハンドクリーム）", "ボディウォッシュ（ボディソープ）", "ボディケア（ボディミスト・ボディクリーム・ボディオイル)", "その他"]
    },
    "ヘアケア商品": {
        "item_col": "今回ご使用の商品名を入力してください。.1",
        "type_col": "ヘアケア商品を選択した方は種類を選択してください。",
        "form_id": "entry.279505478",
        "scores": ["指通り・まとまり", "ツヤ感", "地肌の刺激・洗い心地", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["シャンプー", "コンディショナー・トリートメント", "アウトバストリートメント", "スペシャルケア", "スタイリング剤", "その他"]
    },
    "コスメ商品（ベースメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.2",
        "type_col": "コスメ商品（ベースメイク）を選択した方は種類を選択してください。",
        "form_id": "entry.997470046",
        "scores": ["伸びの良さ・密着感", "仕上がりの美しさ", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "肌への負担感の少なさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["日焼け止め・UV", "化粧下地", "ファンデーション", "BB・CCクリーム", "フェイスパウダー", "その他"]
    },
    "コスメ商品（ポイントメイク）": {
        "item_col": "今回ご使用の商品名を入力してください。.3",
        "type_col": "コスメ商品（ポイントメイク）を選択した方は種類を選択してください。",
        "form_id": "entry.948471097",
        "scores": ["発色の良さ", "質感の好み", "崩れにくさ・キープ力", "保湿力・乾燥しにくさ", "クレンジングのやすさ", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
        "types": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ", "リップ・口紅", "チーク", "その他"]
    }
}

# 2. データ読み込み
@st.cache_data(ttl=300)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5HpURwDWt6S0KkQbiS8ugZksNm8yTokNeKE4X-oBHmLMubOvOKIsuU4q6_onLta2cd0brCBQc-cHA/pub?gid=1578087772&single=true&output=csv"
    try:
        data = pd.read_csv(url)
        data.columns = [str(c).strip() for c in data.columns]
        return data
    except: return None
    # --- 【新設】NGワード辞書の読み込み ---
@st.cache_data(ttl=300)
def load_ng_words():
    try:
        client = get_gspread_client()
        sh = client.open("Cosme Data") # ★ご自身のシート名に
        sheet = sh.worksheet("NGワード辞書")
        records = sheet.get_all_records()
        # { "NGワード": "理由" } という辞書形式に変換
        return {row['NGワード']: row['理由'] for row in records if row['NGワード']}
    except:
        return {}

df = load_data()

# サイドバー基本設定
st.sidebar.title("💄 Cosme Management")
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成", "商品POPカルテ"])
selected_theme = st.sidebar.selectbox("📊 配色テーマ", list(COLOR_PALETTES.keys()))
theme_colors = COLOR_PALETTES[selected_theme]

if df is not None:
    # --- 共通フィルタリング ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 データを絞り込む")
    
    genre = st.sidebar.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="main_g")
    conf = COLUMN_CONFIG[genre]
    sub_df = df[df[COL_GENRE] == genre].copy()
    
    # 【復活】種類別絞り込み
    types = sorted(sub_df[conf["type_col"]].dropna().unique())
    selected_types = st.sidebar.multiselect("種類を選択", types, default=types)
    
    # 【復活】年代絞り込み
    ages = sorted(sub_df[COL_AGE].unique())
    selected_ages = st.sidebar.multiselect("年代を選択", ages, default=ages)
    

    # フィルタ適用
    sub_df = sub_df[
        (sub_df[COL_AGE].isin(selected_ages)) & 
        (sub_df[conf["type_col"]].isin(selected_types))
    ]
    # --- 各メニュー機能 ---
    if menu == "QR生成":
        st.header("📲 アンケート回答用QR作成")
        q_genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="qr_g")
        q_type = st.selectbox("種類を選択", COLUMN_CONFIG[q_genre]["types"], key="qr_t")
        q_item = st.text_input("商品名を入力", key="qr_i")
        
        if st.button("QRコードを発行"):
            type_id = COLUMN_CONFIG[q_genre]["form_id"]
            params = urllib.parse.urlencode({"entry.500746217": q_genre, type_id: q_type, "entry.1507235458": q_item})
            full_url = f"https://docs.google.com/forms/d/e/1FAIpQLSdBubITUy2hWaM8z9Ryo4QV6qKF0A1cnUnFEM49E6tdf8JeXw/viewform?usp=pp_url&{params}"
            qr = qrcode.make(full_url)
            buf = BytesIO()
            qr.save(buf)
            st.image(buf.getvalue(), width=300, caption="スマホで読み取って回答")
            st.write(f"URL: [回答リンク]({full_url})")

    elif menu == "レーダーチャート比較":
        st.header(f"📊 スパイダー分析 ({selected_theme})")
        
        # --- 【新機能】グリッド切り替えスイッチ ---
        col_chart1, col_chart2 = st.columns([2, 1])
        with col_chart2:
            st.write("🔧 チャート設定")
            show_grid = st.toggle("グリッド線を表示", value=True)
            show_axis = st.toggle("軸ラベルを表示", value=True)

        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        selected_items = st.multiselect("比較する商品を選択", items)
        
        if selected_items:
            fig = go.Figure()
            valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
            
            for i, item in enumerate(selected_items):
                item_data = sub_df[sub_df[conf["item_col"]] == item][valid_scores].mean()
                color = theme_colors[i % len(theme_colors)]
                fig.add_trace(go.Scatterpolar(
                    r=item_data.values, 
                    theta=valid_scores, 
                    fill='toself', 
                    name=item, 
                    line=dict(color=color), 
                    fillcolor=color, 
                    opacity=0.5
                ))
            
            # --- スイッチの状態を反映 ---
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=show_grid, # グリッド（円）の表示
                        range=[0, 5],
                        showticklabels=show_axis # 数字ラベルの表示
                    ),
                    angularaxis=dict(
                        visible=show_grid, # スポーク（放射状の線）の表示
                        showticklabels=show_axis # 項目名の表示
                    )
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

    elif menu == "分布図分析":
        st.header(f"📈 分析分布 ({selected_theme})")
        valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
        x_ax = st.selectbox("横軸", valid_scores, index=0)
        y_ax = st.selectbox("縦軸", valid_scores, index=len(valid_scores)-1 if len(valid_scores)>1 else 0)
        fig = px.scatter(sub_df, x=x_ax, y=y_ax, color=COL_AGE, hover_name=conf["item_col"], color_discrete_sequence=theme_colors)
        st.plotly_chart(fig, use_container_width=True)

    elif menu == "AIポップ生成":
        st.header("✨ AI×人間 共同ポップ制作（薬機法チェック付）")

        # 1. 辞書・商品データの読み込み
        ng_dict = load_ng_words()
        
        # 商品リストの作成
        survey_items = set(sub_df[conf["item_col"]].dropna().unique())
        saved_records = []
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet = sh.worksheet("カルテ")
            saved_records = sheet.get_all_records()
        except: pass
        
        saved_items = {row['商品名'] for row in saved_records}
        all_items = sorted(list(survey_items | saved_items))
        
        selected_item = st.selectbox("制作する商品を選択", all_items)
        
        # カルテから情報取得
        saved_info = ""
        for row in saved_records:
            if row['商品名'] == selected_item:
                saved_info = row['公式情報']
                break

        st.markdown("---")
        
        # 2. 編集・分析エリア
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📖 商品情報・指示")
            input_info = st.text_area("カルテからの引継ぎ情報", value=saved_info, height=150)
            human_hint = st.text_input("AIへの追加指示", placeholder="例：30代向けに上品に")
            
            # 生成ボタンを左側に配置
            run_generate = st.button("🚀 AIポップコピーを生成")

        with col2:
            st.subheader("📊 顧客の声（分析視覚化）")
            item_stats = sub_df[sub_df[conf["item_col"]] == selected_item][conf["scores"]].mean()
            
            if not item_stats.dropna().empty:
                tab1, tab2 = st.tabs(["スパイダー", "分布推移"])
                
                with tab1:
                    # スパイダーチャート
                    fig_spy = go.Figure(go.Scatterpolar(
                        r=item_stats.values,
                        theta=conf["scores"],
                        fill='toself',
                        line=dict(color=theme_colors[0])
                    ))
                    fig_spy.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                        height=300, margin=dict(l=40, r=40, t=20, b=20),
                        paper_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_spy, use_container_width=True)
                
                with tab2:
                    # 分布図（簡易表示：全データの中での位置づけ）
                    fig_scat = px.scatter(
                        sub_df, x=conf["scores"][0], y=conf["scores"][-1],
                        color_discrete_sequence=[theme_colors[1]],
                        opacity=0.3
                    )
                    # 選択中の商品だけ強調
                    this_item = sub_df[sub_df[conf["item_col"]] == selected_item]
                    fig_scat.add_trace(go.Scatter(
                        x=this_item[conf["scores"][0]], y=this_item[conf["scores"][-1]],
                        mode='markers', marker=dict(color='red', size=12, symbol='star'),
                        name='この商品'
                    ))
                    fig_scat.update_layout(height=300, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(fig_scat, use_container_width=True)
                
                analysis_hint = f"顧客分析結果: {item_stats.idxmax()}が最高評価です。"
            else:
                st.info("アンケートデータなし（新商品として生成）")
                analysis_hint = "新商品としての魅力を提案してください。"

        # 3. AI生成実行
        if run_generate:
            prompt = f"商品名:{selected_item}\n特徴:{input_info}\n分析:{analysis_hint}\n要望:{human_hint}\n薬機法を守り、魅力的なコピーを3案出して。"
            
            if model:
                with st.spinner("生成中..."):
                    res = model.generate_content(prompt)
                    generated_text = res.text
                    
                    # 薬機法チェック
                    st.markdown("---")
                    st.subheader("⚠️ 薬機法チェック結果")
                    found_ng = False
                    for word, reason in ng_dict.items():
                        if word in generated_text:
                            st.error(f"**NGワード検知: 「{word}」** → {reason}")
                            found_ng = True
                    if not found_ng: st.success("NGワードは見つかりませんでした。")
                    
                    st.markdown("---")
                    st.success("🤖 AI提案")
                    st.write(generated_text)
            else:
                st.error("APIキー未設定です。")

    elif menu == "商品POPカルテ":
        st.header("📋 共有商品POPカルテ")
        with st.expander("📝 カルテを新規保存", expanded=True):
            
            # --- 【修正ポイント】商品名の選択方法を切り替えられるようにする ---
            items_list = sorted(sub_df[conf["item_col"]].dropna().unique())
            input_method = st.radio("商品の入力方法", ["既存のデータから選ぶ", "新しい商品を直接入力する"], horizontal=True)
            
            if input_method == "既存のデータから選ぶ" and items_list:
                target_item = st.selectbox("商品を選択", items_list, key="kt_item_select")
            else:
                target_item = st.text_input("商品名を入力（新商品など）", key="kt_item_input")
            
            ai_copy = st.text_area("AIポップコピー案（メモ）")
            official_info = st.text_area("公式情報・成分・画像URLなど")

            creator = st.text_input("作成者名")
            
            if st.button("💾 保存実行"):
                if creator and target_item:
                    try:
                        client = get_gspread_client()
                        # ★ここをご自身のスプレッドシート名に書き換えてください
                        sh = client.open("Cosme Data") 
                        sheet = sh.worksheet("カルテ")
                        sheet.append_row([
                            datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            creator, 
                            target_item, 
                            ai_copy, 
                            official_info
                        ])
                        st.success(f"「{target_item}」の情報を保存しました！")
                    except Exception as e: 
                        st.error(f"保存失敗: {e}")
                else:
                    st.warning("作成者名と商品名を入力してください。")