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

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    try:
        # 使えるモデルをリストアップして、flashが含まれるものを探す
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 'gemini-1.5-flash' があればそれを、なければリストの最初を使う
        target_model = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
        model = genai.GenerativeModel(target_model)
        # st.write(f"DEBUG: 選択されたモデル: {target_model}") # 動作確認用
    except Exception as e:
        st.error(f"モデルリスト取得エラー: {e}")
        model = genai.GenerativeModel('gemini-1.5-flash') # 失敗したらデフォルト
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
    "ナチュラルカラー": ["#a98467", "#adc178", "#dde5b6", "#6c584c", "#f0ead2"],
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
        "scores": ["指通り・まとまり", "ツヤ感", "肌への負担感のなさ・優しさ", "ダメージ補修・翌朝の髪の状態", "香りの好み", "パッケージのときめき・使いやすさ", "リピート欲・おすすめ度"],
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
menu = st.sidebar.radio("機能を選択", ["QR生成", "レーダーチャート比較", "分布図分析", "AIポップ生成", "商品カルテ編集","商品カルテ一覧"])
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
            
            # QRコード生成
            qr = qrcode.make(full_url)
            buf = BytesIO()
            qr.save(buf, format="PNG") # フォーマットを指定
            byte_im = buf.getvalue()

            # 表示
            st.image(byte_im, width=300, caption="スマホで読み取って回答")
            
            # --- ここから追加・修正 ---
            st.markdown("#### 📄 このURLをコピー")
            st.code(full_url, language="text") # クリックでコピー可能

            st.download_button(
                label="📥 QRコードを画像として保存",
                data=byte_im,
                file_name=f"QR_{q_item}.png",
                mime="image/png",
                key="download_qr"
            )
            # ------------------------
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
        st.header("✨ AIポップ制作")

        # 1. データの安全な読み込み
        survey_items = set()
        if not sub_df.empty and conf["item_col"] in sub_df.columns:
            survey_items = set(sub_df[conf["item_col"]].dropna().unique())

        saved_records = []
        saved_items = set()
        
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            saved_records = sheet_karte.get_all_records()
            
            # シートから「商品名」列のデータを安全に取り出す
            if saved_records:
                saved_items = {row.get('商品名') for row in saved_records if row.get('商品名')}
        except Exception as e:
            st.error(f"スプレッドシートの読み込みに失敗しました。シート名や列名を確認してください: {e}")

        all_items = sorted(list(survey_items | saved_items))

        # データが1件もない場合は、真っ白回避のためにここで止める
        if not all_items:
            st.info("💡 現在、商品データが登録されていません。")
            st.warning("スプレッドシートの『カルテ』シートに『商品名』を入力するか、アンケートを回答してください。")
            st.stop() 

        selected_item = st.selectbox("制作する商品を選択", all_items)

        # 2. 選択された商品の情報を抽出
        saved_info = ""
        current_row_idx = None
        for i, row in enumerate(saved_records):
            if str(row.get('商品名')) == str(selected_item):
                saved_info = row.get('公式情報', '') # 「公式情報」列から取得
                current_row_idx = i + 2
                break

        # --- 以下、入力エリアと生成ボタン ---
        st.markdown("---")
        input_info = st.text_area("商品情報（公式情報から引用）", value=saved_info, height=150)
        human_hint = st.text_input("AIへの追加指示（例：ギフト向け、20代後半、しっとり感強調）")
        
        if st.button("🚀 AIポップコピーを生成"):
            # (ここに前回の生成処理を入れる)
            pass

        ng_dict = load_ng_words()
        
        # 商品リストとカルテデータの取得（修正版）
        survey_items = set(sub_df[conf["item_col"]].dropna().unique())
        saved_records = []
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            saved_records = sheet_karte.get_all_records()
        except Exception as e:
            st.warning(f"カルテの読み込みを待機中、またはエラー: {e}")
            saved_records = [] # エラーが起きても空のリストを入れる

        # データが1件もない場合の回避
        if saved_records:
            saved_items = {row.get('商品名', '') for row in saved_records if '商品名' in row}
        else:
            saved_items = set()
            # 1. 商品リストとカルテデータの取得
        survey_items = set(sub_df[conf["item_col"]].dropna().unique())
        saved_records = []
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data") # ★スプレッドシート名を確認
            sheet_karte = sh.worksheet("カルテ")
            saved_records = sheet_karte.get_all_records()
        except Exception as e:
            st.error(f"データ連携エラー: {e}")
        
        saved_items = {row.get('商品名', '') for row in saved_records if row.get('商品名')}
        all_items = sorted(list(survey_items | saved_items))
        selected_item = st.selectbox("制作する商品を選択", all_items, key="ai_pop_selectbox")
        
        # 既存情報の抽出
        saved_info = ""
        current_row_idx = None
        for i, row in enumerate(saved_records):
            if row['商品名'] == selected_item:
                saved_info = row['公式情報']
                current_row_idx = i + 2 # ヘッダーの分+1
                break

        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📖 商品情報・指示")
            input_info = st.text_area("カルテからの引継ぎ情報", value=saved_info, height=150)
            human_hint = st.text_input("AIへの追加指示", placeholder="例：30代向け、上品に")
            run_generate = st.button("🚀 AIポップコピーを生成", key="btn_generate_ai_pop")

        with col2:
            st.subheader("📊 顧客の声（分析結果）")
            item_stats = sub_df[sub_df[conf["item_col"]] == selected_item][conf["scores"]].mean()
            if not item_stats.dropna().empty:
                st.info(f"評価トップ: {item_stats.idxmax()}")
                fig_spy = go.Figure(go.Scatterpolar(r=item_stats.values, theta=conf["scores"], fill='toself'))
                fig_spy.update_layout(height=250, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_spy, use_container_width=True)
                analysis_hint = f"分析結果: {item_stats.idxmax()}が高評価。"
            else:
                st.warning("アンケートデータがありません")
                analysis_hint = "新商品として魅力を提案してください。"

        # 2. 生成と保存の処理
        if run_generate:
            if model:
                with st.spinner("AIが薬機法を考慮して生成中..."):
                    try:
                        res = model.generate_content(f"商品:{selected_item}\n特徴:{input_info}\n要望:{human_hint}\n分析:{analysis_hint}\n薬機法を守って3案提案して。")
                        # 生成結果を一時保存（session_state）
                        st.session_state["generated_copy"] = res.text
                    except Exception as e:
                        st.error(f"生成エラー: {e}")
            else:
                st.error("APIキーが設定されていません。")

        # 3. 生成された結果の表示と保存ボタン
        if "generated_copy" in st.session_state:
            st.markdown("---")
            st.success("🤖 AI提案のコピー")
            st.write(st.session_state["generated_copy"])
            
            # --- 【重要】保存ボタンの設置 ---
            st.subheader("📝 採用案をカルテに保存")
            final_choice = st.text_area("採用する案をここにコピー＆ペースト（または編集）してください", 
                                        value=st.session_state["generated_copy"], height=100)
            
            if st.button("💾 この内容をカルテに保存する", key="btn_save_karte"):
                if current_row_idx:
                    try:
                        # 「ポップ案」がスプレッドシートの何列目にあるか指定（例: 3列目など）
                        # カラム名を検索して自動で列を特定
                        headers = sheet_karte.row_values(1)
                        if "ポップ案" in headers:
                            col_idx = headers.index("ポップ案") + 1
                            sheet_karte.update_cell(current_row_idx, col_idx, final_choice)
                            st.balloons()
                            st.success(f"「{selected_item}」のカルテにポップ案を保存しました！")
                        else:
                            st.error("スプレッドシートに「ポップ案」という列が見つかりません。")
                    except Exception as e:
                        st.error(f"保存失敗: {e}")
                else:
                    st.warning("この商品はカルテに登録されていないため、保存できません。先にカルテ作成をしてください。")

    elif menu == "商品カルテ編集":
        st.header("📋 商品カルテ：編集・管理")

        try:
            # 1. スプレッドシートからの読み込み
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()
            df_karte = pd.DataFrame(records) if records else pd.DataFrame()

            # 2. モード選択：新規 or 既存
            mode = st.radio("作業を選択してください", ["既存データから選んで編集", "新規カルテ作成"], horizontal=True)

            # 初期値の準備
            target_item_name = ""
            official_info_val = ""
            memo_val = ""

            if mode == "既存データから選んで編集":
                if not df_karte.empty and "商品名" in df_karte.columns:
                    item_list = [n for n in df_karte["商品名"].unique() if n]
                    selected_name = st.selectbox("編集する商品を選択", item_list, key="edit_item_select")
                    
                    # 選択した商品の最新データを取得
                    latest_row = df_karte[df_karte["商品名"] == selected_name].iloc[-1]
                    target_item_name = selected_name
                    official_info_val = latest_row.get("公式情報", "")
                    # 「メモ」という列がある前提（なければ空）
                    memo_val = latest_row.get("メモ", "") 
                else:
                    st.warning("既存データがありません。「新規カルテ作成」を選んでください。")
            
            st.markdown("---")
            
            # 3. 入力エリア（新規・既存共通）
            st.subheader(f"🖋️ {mode}")
            
            edit_item_name = st.text_input("商品名", value=target_item_name)
            edit_official_info = st.text_area("公式情報（特徴・成分など）", value=official_info_val, height=150)
            edit_memo = st.text_area("スタッフメモ・備考（ターゲット層や接客のヒント）", value=memo_val, height=100)

            if st.button("💾 カルテ内容を保存・更新", key="save_karte_edit"):
                if not edit_item_name:
                    st.error("商品名を入力してください。")
                else:
                    import datetime
                    new_row = [
                        str(datetime.date.today()), # 日付
                        "スタッフ",                 # 作成者（仮）
                        edit_item_name,             # 商品名
                        "",                         # AIコピー（ここでは空）
                        edit_official_info,         # 公式情報
                        "",                         # ポップ案（ここでは空）
                        edit_memo                   # メモ（スプレッドシートに列を増やしてください）
                    ]
                    sheet_karte.append_row(new_row)
                    st.success(f"「{edit_item_name}」の情報を保存しました！")
                    st.balloons()

            # 4. 全体の一覧も下に見えるようにしておく
            if not df_karte.empty:
                with st.expander("📂 現在のカルテ一覧を表示"):
                    st.dataframe(df_karte, use_container_width=True)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            
    elif menu == "商品カルテ一覧":
        st.header("📋 登録済み商品カルテ一覧")

        try:
            # 1. スプレッドシートからの読み込み
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()

            if not records:
                st.info("💡 まだカルテにデータが登録されていません。AIポップ生成から保存してください。")
                st.stop()

            import pandas as pd
            df_karte = pd.DataFrame(records)

            # 2. メインのカルテ一覧表示
            st.subheader("📊 全商品アーカイブ")
            # 必要な列を並び替え（スプレッドシートの項目名に合わせる）
            cols = ["日付", "作成者", "商品名", "AIコピー", "ポップ案"]
            display_cols = [c for c in cols if c in df_karte.columns]
            st.dataframe(df_karte[display_cols], use_container_width=True)

            # 3. 特定商品の「深掘り」表示機能（ここが大事！）
            st.markdown("---")
            st.subheader("🔍 商品別・詳細アーカイブ")
            
            # 商品名リストを取得
            item_list = [n for n in df_karte["商品名"].unique() if n]
            
            if item_list:
                target_item = st.selectbox("詳しく見たい商品を選択してください", item_list, key="karte_pro_select")
                
                # 選択された商品の最新データを取得
                item_data = df_karte[df_karte["商品名"] == target_item].iloc[-1] # 一番下の（最新の）データ

                # デザインされたカード形式で表示
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown(f"### 🏷️ {target_item}")
                    st.write(f"**最終更新:** {item_data.get('日付', '不明')}")
                    st.write(f"**担当者:** {item_data.get('作成者', '不明')}")
                    st.info(f"**公式・基本情報:**\n\n{item_data.get('公式情報', '未登録')}")
                
                with c2:
                    st.success(f"**✨ AIが提案したコピー（原文）:**\n\n{item_data.get('AIコピー', '未登録')}")
                    st.warning(f"**✍️ 最終決定したポップ案:**\n\n{item_data.get('ポップ案', '未作成')}")
                    
                    # 編集のアドバイスなどを出すことも可能
                    st.caption("※この内容はスプレッドシートから直接修正することも可能です。")

            else:
                st.warning("有効な商品名が見つかりません。")

        except Exception as e:
            st.error(f"表示エラーが発生しました。")
            st.code(f"Error: {e}")