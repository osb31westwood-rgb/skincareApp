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
import datetime
import time
from streamlit_option_menu import option_menu

# --- パスワード認証機能 ---
def check_password():
    """パスワードが正しいかチェックする関数"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # すでに認証済みなら何もしない
    if st.session_state["password_correct"]:
        return True

    # パスワード入力画面の表示
    st.title("🔐 Sachika専用ツール")
    st.write("このアプリを使用するには合言葉が必要です。")
    
    password_input = st.text_input("パスワードを入力してください", type="password")
    
    # 秘密の合言葉（好きな文字に変えてください）
    SECRET_PASSWORD = st.secrets.get("APP_PASSWORD", "fs11710n") 

    if st.button("ログイン"):
        if password_input == SECRET_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    
    return False

# --- パスワードチェックを実行 ---
if not check_password():
    st.stop()

# --- ログイン成功時の演出（ここを修正） ---
if "login_celebrated" not in st.session_state:
    placeholder = st.empty() # 消去可能なメッセージ箱を作成
    placeholder.success("🔐 ログイン成功！ツールを起動します...")
    time.sleep(1.5) # 1.5秒だけ表示
    placeholder.empty() # メッセージを消す
    st.session_state["login_celebrated"] = True # 二回目以降は出さない
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

# ここです！
def get_gspread_client():
    s_acc = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        s_acc,
        # ここに "https://www.googleapis.com/auth/drive" が入っていればOKです！
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(credentials)

from googleapiclient.http import MediaIoBaseUpload
import io
from googleapiclient.discovery import build

import requests
import base64

def upload_to_imgbb(uploaded_file):
    """ImgBBに画像をアップロードして直リンクを返す"""
    try:
        api_key = st.secrets["IMGBB_API_KEY"]
        url = "https://api.imgbb.com/1/upload"
        
        # 画像をbase64形式に変換
        image_data = base64.b64encode(uploaded_file.getvalue())
        
        data = {
            "key": api_key,
            "image": image_data,
        }
        
        # アップロード実行
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            # 成功したら画像のURLを返す
            return response.json()["data"]["url"]
        else:
            st.error(f"ImgBBアップロード失敗: {response.text}")
            return None
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        return None

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
category_data = {
    "スキンケア（フェイス・ボディ）": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア", "ボディウォッシュ", "ボディケア", "その他"],
    "ヘアケア商品": ["シャンプー", "コンディショナー・トリートメント", "アウトバストリートメント", "スペシャルケア", "スタイリング剤", "その他"],
    "ベースメイク": ["日焼け止め・UV", "化粧下地", "ファンデーション", "BB・CCクリーム", "フェイスパウダー", "その他"],
    "ポイントメイク": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ", "リップ・口紅", "チーク", "その他"]
}
# ジャンル別カラム・ID設定
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
with st.sidebar:
    st.title("💄 Sachika's Cosme")
    
    # アイコン付きメニューの設定
    menu = option_menu(
        menu_title=None,  # カテゴリ分けを自前でするのでここはNone
        options=[
            "📲 アンケートQR生成", 
            "✨ AIポップ作成", 
            "📋 商品カルテ編集", 
            "📚 商品カルテ一覧", 
            "📈 アンケート分析"
        ],
        icons=["qr-code-scan", "magic", "pencil-square", "collection", "bar-chart-line", "graph-up"],
        menu_icon="cast",
        default_index=0,
    

        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "#90C6C8", "font-size": "18px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#90C6C8"
            ""},
        }
    )

    st.markdown("---")


    if df is not None:
    # --- 共通の絞り込みフィルター ---
        with st.expander("⚙️ データ絞り込み", expanded=True): # 最初は見せるためにTrueにしてみましょう
           selected_theme = st.selectbox("📊 分析グラフのカラー", list(COLOR_PALETTES.keys()))
           theme_colors = COLOR_PALETTES[selected_theme]
        
           genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="main_g")
           conf = COLUMN_CONFIG[genre]
        
            # フィルター適用のロジックをここに全部書く
           sub_df = df[df[COL_GENRE] == genre].copy()
        
           types = sorted(sub_df[conf["type_col"]].dropna().unique())
           selected_types = st.multiselect("アイテムタイプ", types, default=types)
        
           ages = sorted(sub_df[COL_AGE].unique())
           selected_ages = st.multiselect("年代", ages, default=ages)
        
           genders = ["女性", "男性", "回答しない／その他"]
           selected_genders = st.multiselect("性別", genders, default=genders)

           # フィルタ適用
           sub_df = sub_df[
            (sub_df[COL_AGE].isin(selected_ages)) & 
            (sub_df[conf["type_col"]].isin(selected_types)) &
            (sub_df["性別"].isin(selected_genders))
           ]
           # 条件を一つずつ & (かつ) でつなげます


    # --- 各メニュー機能 ---
if menu == "📲 アンケートQR生成":
        st.header("📲 アンケート回答用QR作成")
        q_genre = st.selectbox("ジャンル", list(COLUMN_CONFIG.keys()), key="qr_g")
        q_type = st.selectbox("アイテムタイプを選択", COLUMN_CONFIG[q_genre]["types"], key="qr_t")
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
elif menu == "✨ AIポップ作成":
        st.header("✨ AIポップ案制作")

        # 1. NGワード辞書の読み込みと編集機能（サイドバー）
        ng_dict = load_ng_words()
        
        with st.sidebar.expander("🚫 NGワード辞書を編集"):
            new_word = st.text_input("追加する単語", placeholder="例：最高", key="add_ng_word")
            new_reason = st.text_input("理由/言い換え案", placeholder="例：最大級表現はNG", key="add_ng_reason")
            
            if st.button("➕ 辞書に追加", key="btn_add_ng"):
                if new_word and new_reason:
                    try:
                        client = get_gspread_client()
                        sh = client.open("Cosme Data")
                        sheet_ng = sh.worksheet("NGワード辞書")
            
                       # 現在の日時を取得
                        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
                       # [NGワード, 理由, 更新日時] の順で追加
                        sheet_ng.append_row([new_word, new_reason, now])
            
                        st.success(f"「{new_word}」を追加しました！")
                        st.cache_data.clear() 
                        st.rerun()
                    except Exception as e: st.error(f"追加失敗: {e}")

            st.markdown("---")
            st.write("📝 現在の登録リスト")
            for word, reason in ng_dict.items():
                col_w, col_d = st.columns([3, 1])
                col_w.write(f"**{word}**")
                if col_d.button("🗑️", key=f"del_ng_{word}"):
                    try:
                        client = get_gspread_client()
                        sh = client.open("Cosme Data")
                        sheet_ng = sh.worksheet("NGワード辞書")
                        cell = sheet_ng.find(word)
                        if cell:
                            sheet_ng.delete_rows(cell.row)
                            st.success("削除完了")
                            st.cache_data.clear()
                            st.rerun()
                    except: st.error("削除失敗")

        # 2. 商品データの取得（真っ白回避）
        survey_items = set()
        if not sub_df.empty and conf["item_col"] in sub_df.columns:
            survey_items = set(sub_df[conf["item_col"]].dropna().unique())

        saved_records = []
        saved_items = set()
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_k = sh.worksheet("カルテ")
            saved_records = sheet_k.get_all_records()
            saved_items = {row.get('商品名', '') for row in saved_records if row.get('商品名')}
        except: pass
        
        all_items = sorted(list(survey_items | saved_items))
        if not all_items:
            st.info("💡 現在、商品データが登録されていません。")
            st.stop()

        selected_item = st.selectbox("制作する商品を選択", all_items, key="ai_pop_selectbox")
        
        ## 1. まず変数の中身をリセット
        saved_info = ""
        current_row_idx = None

        # 2. saved_records（スプレッドシートの中身）を1行ずつチェック
        for i, row in enumerate(saved_records):
            # 商品名が一致するかチェック
            if str(row.get('商品名')) == str(selected_item):
                saved_info = row.get('公式情報', '')
                current_row_idx = i + 2  # 行番号を保存
                break  # 見つかったらループ終了

        # 3. もし見つからなかった、あるいは公式情報が空だった場合の処理
        if not saved_info:
            saved_info = "（カルテに公式情報が登録されていません）"


        # 3. メインレイアウト（2カラム）
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # ★ 商品名と画像を横に並べて表示
            title_col, img_preview_col = st.columns([2, 1])
            with title_col:
                st.subheader("📖 商品情報・指示")
            
            # 選択中の商品の画像URLを取得
            # --- ここから差し替え ---
            import pandas as pd
            df_temp = pd.DataFrame(saved_records)
            
            # 選択中の商品名に一致する行を探す
            item_row = df_temp[df_temp["商品名"] == selected_item]

            with img_preview_col:
                if not item_row.empty:
                    # 「画像URL」列が存在するか確認
                    if "画像URL" in item_row.columns:
                        # 一番新しいデータ（最後の行）のURLを取得
                        img_url = item_row.iloc[-1]["画像URL"]
                        
                        # URLがちゃんと入っているかチェック
                        if pd.notna(img_url) and str(img_url).startswith("http"):
                            st.image(img_url, use_container_width=True)
                        else:
                            st.caption("🖼️ 画像はまだ登録されていません")
                    else:
                        st.error("⚠️ スプレッドシートに「画像URL」列がありません")
                else:
                    st.caption("🔍 商品データが見つかりません")
            # --- ここまで差し替え ---

            input_info = st.text_area(
                "カルテからの引継ぎ情報", 
                value=saved_info, 
                height=150, 
                key=f"input_info_{selected_item}" # キーに商品名を含めることで、商品を変えた時に中身を強制更新する
            )
            human_hint = st.text_input("AIへの追加指示", placeholder="例：30代向け、上品に", key="input_hint")
            run_generate = st.button("🚀 AIポップコピーを生成", key="btn_generate_ai_pop")
        with col2:
            st.subheader("📊 顧客の声（分析結果）")
            
            # --- 1. 性別フィルターの設置 ---
            gender_target = st.radio(
                "ターゲット層を選択",
                ["全て", "女性", "男性", "回答しない／その他"],
                horizontal=True,
                key="gender_filter_radio"
            )

            # --- 2. データの絞り込みロジック ---
            # 選択した商品で絞り込み
            item_all_data = sub_df[sub_df[conf["item_col"]] == selected_item]
            
            # 性別でさらに絞り込み
            if gender_target != "全て":
                # アンケートデータの列名が「性別」であることを前提としています
                target_df = item_all_data[item_all_data["性別"] == gender_target]
            else:
                target_df = item_all_data

            # スコアの平均を計算
            item_stats = target_df[conf["scores"]].mean()

            # --- 3. グラフとヒントの表示 ---
            if not item_stats.dropna().empty:
                st.info(f"【{gender_target}】評価トップ: {item_stats.idxmax()}")
                import plotly.graph_objects as go

                # --- 修正ポイント：最後と最初をつなげる ---
                # 値のリストの最後に、最初の値を付け加える
                r_values = list(item_stats.values)
                r_values.append(r_values[0])
                
                # 項目のリストの最後に、最初の項目名を付け加える
                theta_values = list(conf["scores"])
                theta_values.append(theta_values[0])

                fig_spy = go.Figure(go.Scatterpolar(
                    r=r_values,           # 修正後のリストを使用
                    theta=theta_values,   # 修正後のリストを使用
                    fill='toself', 
                    line_color=theme_colors[0] if 'theme_colors' in locals() else 'pink' # 先ほどの配色を反映
                ))
                # --- ここまで ---

                fig_spy.update_layout(
                    height=250, 
                    margin=dict(l=30, r=30, t=20, b=20), 
                    polar=dict(radialaxis=dict(visible=True, range=[0, 5]))
                )
                st.plotly_chart(fig_spy, use_container_width=True)
                
                # AIへのヒントに性別情報を追加
                analysis_hint = f"顧客分析（{gender_target}）: {item_stats.idxmax()}が特に評価されています。"
            else:
                st.warning(f"⚠️ {gender_target}の回答データがありません")
                analysis_hint = f"{gender_target}向けに、商品の魅力を新規提案してください。"

        # 4. 生成処理と薬機法チェック
        if run_generate:
            if model:
                with st.spinner("AIが画像と情報を分析して生成中..."):
                    try:
                        # --- 画像解析の準備 ---
                        image_data = None
                        if img_url:
                            try:
                                import requests
                                from PIL import Image
                                import io
                                # img_urlから画像をダウンロード
                                img_res = requests.get(img_url)
                                image_data = Image.open(io.BytesIO(img_res.content))
                            except:
                                st.warning("画像の読み込みに失敗したため、テキストのみで生成します。")

                        # --- プロンプトの構築 ---
                        # --- プロンプトの構築（ジャンルとタイプを追加） ---
                        # saved_recordsから現在の商品のジャンルとタイプを特定
                        current_item_data = next((row for row in saved_records if str(row.get('商品名')) == str(selected_item)), {})
                        item_genre = current_item_data.get('ジャンル', '不明')
                        item_type = current_item_data.get('アイテムタイプ', '不明')

                        prompt = f"""
                        あなたはこの化粧品を販売するプロのPOPライターです。
                        {'添付画像からパッケージの色味やデザインの雰囲気を読み取り、' if image_data else ''}
                        以下の情報と顧客分析を組み合わせて、思わず手に取りたくなる店頭POP用キャッチコピーを3案提案してください。

                        【最重要】薬機法（化粧品広告ガイドライン）を遵守し、治療効果や「最高」等の誇大表現は避けてください。
                        商品名: {selected_item}
                        カテゴリー: {item_genre} （{item_type}） # ←ここを追加！
                        特徴: {input_info}
                        要望: {human_hint}
                        ターゲット層: {gender_target}
                        分析結果: {analysis_hint}
                        
                        【出力ルール】:
                        - {item_type}としての役割（保湿、発色、香りなど）を活かした表現にすること
                        - パッケージの雰囲気に合う言葉選びをすること
                        - ターゲットの心に刺さる強い言葉を1つ入れること
                        """

                        # --- Geminiへのリクエスト (画像があればリスト形式で渡す) ---
                        if image_data:
                            res = model.generate_content([prompt, image_data])
                        else:
                            res = model.generate_content(prompt)
                            
                        st.session_state["generated_copy"] = res.text
                    except Exception as e: 
                        st.error(f"生成エラー: {e}")
            else:
                st.error("APIキーが設定されていません。")
                
            st.success("🤖 AI提案のコピー")
            st.write(st.session_state["generated_copy"])
            
            st.subheader("📝 採用案をカルテに保存")
            final_choice = st.text_area("採用・編集後のテキスト", value=st.session_state["generated_copy"], height=100)
            
            if st.button("💾 この内容をカルテに保存する", key="btn_save_karte"):
                if current_row_idx:
                    try:
                        headers = sheet_k.row_values(1)
                        if "ポップ案" in headers:
                            col_idx = headers.index("ポップ案") + 1
                            sheet_k.update_cell(current_row_idx, col_idx, final_choice)
                            st.balloons()
                            st.success(f"「{selected_item}」のカルテに保存しました！")
                        else: st.error("「ポップ案」列が見つかりません。")
                    except Exception as e: st.error(f"保存失敗: {e}")
                else: st.warning("先に「商品カルテ編集」からこの商品を登録してください。")

elif menu == "📋 商品カルテ編集":
        st.header("📋 商品カルテ：編集・管理")
        
        # カテゴリーデータの定義
        category_data = {
            "スキンケア（フェイス・ボディ）": ["洗顔・クレンジング", "導入液・ブースター", "化粧水", "美容液（セラム・パック）", "乳液・フェイスクリーム", "アイクリーム・パーツケア", "オールインワン", "ハンドケア", "ボディウォッシュ", "ボディケア", "その他"],
            "ヘアケア商品": ["シャンプー", "コンディショナー・トリートメント", "アウトバストリートメント", "スペシャルケア", "スタイリング剤", "その他"],
            "ベースメイク": ["日焼け止め・UV", "化粧下地", "ファンデーション", "BB・CCクリーム", "フェイスパウダー", "その他"],
            "ポイントメイク": ["アイシャドウ", "アイライナー", "アイブロウ", "マスカラ", "リップ・口紅", "チーク", "その他"]
        }

        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()
            df_karte = pd.DataFrame(records) if records else pd.DataFrame()

            mode = st.radio("作業を選択してください", ["既存データから選んで編集", "新規カルテ作成"], horizontal=True)

            # 初期値のリセット
            target_item_name, official_info_val, memo_val, author_val, current_img_url = "", "", "", "", ""
            base_date, current_gen, current_type = "", "", ""

            if mode == "既存データから選んで編集" and not df_karte.empty:
                item_list = [n for n in df_karte["商品名"].unique() if n]
                selected_name = st.selectbox("編集する商品を選択", item_list, key="edit_item_select")
                latest_row = df_karte[df_karte["商品名"] == selected_name].iloc[-1]
                
                target_item_name = selected_name
                official_info_val = latest_row.get("公式情報", "")
                memo_val = latest_row.get("メモ", "")
                author_val = latest_row.get("作成者", "")
                base_date = latest_row.get("新規", "")
                current_img_url = latest_row.get("画像URL", "")
                current_gen = latest_row.get("ジャンル", "")
                current_type = latest_row.get("アイテムタイプ", "")

            st.markdown("---")
            st.markdown("### 📝 カルテ入力")
            
            # --- 入力エリア ---
            col_info1, col_info2, col_info3 = st.columns([2, 2, 1])
            with col_info1:
                # 既存データがある場合はその値を初期値にする
                gen_idx = list(category_data.keys()).index(current_gen) if current_gen in category_data else 0
                main_cat = st.selectbox("✨ ジャンル", list(category_data.keys()), index=gen_idx)
            with col_info2:
                types = category_data[main_cat]
                type_idx = types.index(current_type) if current_type in types else 0
                sub_cat = st.selectbox("🏷️ アイテムタイプ", types, index=type_idx)
            with col_info3:
                edit_author = st.text_input("✍️ 作成者", value=author_val)

            edit_item_name = st.text_input("🎁 商品名", value=target_item_name)

            col_text1, col_text2 = st.columns(2)
            with col_text1:
                edit_official_info = st.text_area("📖 公式情報（特徴・成分など）", value=official_info_val, height=150)
            with col_text2:
                edit_memo = st.text_area("💡 スタッフメモ・備考", value=memo_val, height=150)

            # --- 画像エリア ---
            st.subheader("📸 商品画像")
            delete_image = False
            if current_img_url:
                st.image(current_img_url, caption="現在登録されている画像", width=200)
                delete_image = st.checkbox("🗑️ この画像を削除する")
            
            uploaded_file = st.file_uploader("新しい画像を選択（上書き）", type=["jpg", "jpeg", "png"])

            # --- 保存ボタン ---
            if st.button("💾 カルテ内容を保存・更新", key="save_karte_edit"):
                if not edit_item_name:
                    st.error("商品名を入力してください。")
                else:
                    with st.spinner("データを保存中..."):
                        # 時間設定
                        now_jst = datetime.datetime.now() + datetime.timedelta(hours=9)
                        now_str = now_jst.strftime("%Y-%m-%d %H:%M:%S")
                        final_base_date = base_date if mode == "既存データから選んで編集" and base_date else now_str

                        # 画像URL決定
                        if delete_image:
                            new_image_url = ""
                        elif uploaded_file:
                            res_url = upload_to_imgbb(uploaded_file)
                            new_image_url = res_url if res_url else current_img_url
                        else:
                            new_image_url = current_img_url

                        # 保存データ A～K列
                        new_row = [
                            final_base_date,    # A: 新規
                            now_str,            # B: 更新
                            edit_author,        # C: 作成者
                            main_cat,           # D: ジャンル
                            sub_cat,            # E: アイテムタイプ
                            edit_item_name,     # F: 商品名
                            "",                 # G: AIコピー
                            edit_official_info, # H: 公式情報
                            "",                 # I: ポップ案
                            edit_memo,          # J: メモ
                            new_image_url       # K: 画像URL
                        ]

                        # スプレッドシート更新
                        all_records = sheet_karte.get_all_records()
                        df_all = pd.DataFrame(all_records)
                        
                        if not df_all.empty and edit_item_name in df_all["商品名"].values:
                            row_index = df_all[df_all["商品名"] == edit_item_name].index[0] + 2
                            # A列(新規日)を維持
                            new_row[0] = str(df_all.loc[df_all["商品名"] == edit_item_name, "新規"].values[0])
                            sheet_karte.update(range_name=f"A{row_index}:K{row_index}", values=[new_row])
                            st.success(f"「{edit_item_name}」を更新しました！")
                        else:
                            sheet_karte.append_row(new_row)
                            st.success(f"「{edit_item_name}」を新規登録しました！")

                        st.balloons()
                        st.rerun()

        except Exception as e:
            st.error(f"システムエラーが発生しました: {e}")

elif menu == "📚 商品カルテ一覧":
        st.header("📋 登録済み商品カルテ一覧")
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()

            if records:
                df_karte = pd.DataFrame(records)
                st.subheader("📊 全商品アーカイブ")
                
                # --- 表に表示する列にジャンルとタイプを追加 ---
                # A:新規 B:更新 C:作成者 D:ジャンル E:アイテムタイプ F:商品名 G:AIコピー H:公式情報 I:ポップ案 J:メモ K:画像URL
                cols = ["新規", "更新", "作成者", "ジャンル", "アイテムタイプ", "商品名", "ポップ案"]
                display_cols = [c for c in cols if c in df_karte.columns]
                st.dataframe(df_karte[display_cols], use_container_width=True)

                st.markdown("---")
                st.subheader("🔍 商品別・詳細アーカイブ")
                item_list = [n for n in df_karte["商品名"].unique() if n]
                
                if item_list:
                    target_item = st.selectbox("詳しく見たい商品を選択", item_list, key="karte_pro_select")
                    item_data = df_karte[df_karte["商品名"] == target_item].iloc[-1]
                    
                    c1, c2, c3 = st.columns([1, 1.2, 1.2])
                    
                    with c1:
                        st.write("📸 **商品画像**")
                        img_url = item_data.get("画像URL", "")
                        if img_url:
                            st.image(img_url, use_container_width=True, caption=target_item)
                        else:
                            st.info("画像なし")

                    with c2:
                        # --- カテゴリー情報を目立たせて表示 ---
                        st.markdown(f"### 🏷️ {target_item}")
                        gen = item_data.get('ジャンル', '---')
                        typ = item_data.get('アイテムタイプ', '---')
                        st.markdown(f"**分類:** `{gen}` / `{typ}`") # バッジっぽく表示
                        
                        st.info(f"**📖 公式情報:**\n\n{item_data.get('公式情報', '未登録')}")
                        st.warning(f"**📝 スタッフメモ:**\n\n{item_data.get('メモ', 'なし')}")
                    
                    with c3:
                        st.success(f"**🤖 AI提案コピー:**\n\n{item_data.get('AIコピー', '未登録')}")
                        st.success(f"**✨ 決定ポップ案:**\n\n{item_data.get('ポップ案', '未作成')}")
                        st.caption(f"作成者: {item_data.get('作成者', '---')}")
                        st.caption(f"最終更新: {item_data.get('更新', '---')}")
            else:
                st.info("まだカルテが登録されていません。")

        except Exception as e:
            st.error(f"表示エラー: {e}")
            
            
elif menu == "📈 アンケート分析":
    st.header("📊 アンケートデータ詳細分析")
    
    if sub_df.empty:
        st.warning("⚠️ 現在の絞り込み条件に一致するデータがありません。")
    else:
        # メインのタブを3つに分割
        tab1, tab2, tab3 = st.tabs(["📈 スコア分析", "🗣️ 全体の感想・不満分析", "🔍 その他項目の内訳確認"])

        # --- Tab 1: スコア分析（チャート・分布図） ---
        with tab1:
            st.subheader("📊 多角的な評価分析")
            target_items = sorted(sub_df[conf["item_col"]].dropna().unique())
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                selected_analysis_item = st.selectbox("分析する商品を選択", target_items, key="ans_item_select")
            with col_sel2:
                gender_target = st.radio("表示対象", ["全て", "女性", "男性", "回答しない／その他"], horizontal=True, key="ans_gender_radio")

            item_data = sub_df[sub_df[conf["item_col"]] == selected_analysis_item]
            if gender_target != "全て":
                item_data = item_data[item_data["性別"] == gender_target]

            chart_col, dist_col = st.columns([1, 1])
            with chart_col:
                st.write("📌 平均評価（バランス）")
                item_stats = item_data[conf["scores"]].mean()
                if not item_stats.dropna().empty:
                    import plotly.graph_objects as go
                    r_values = list(item_stats.values) + [item_stats.values[0]]
                    theta_values = list(conf["scores"]) + [conf["scores"][0]]
                    fig_spy = go.Figure(go.Scatterpolar(r=r_values, theta=theta_values, fill='toself', 
                                                       line_color=theme_colors[0] if 'theme_colors' in locals() else 'pink'))
                    fig_spy.update_layout(height=300, margin=dict(l=20,r=20,t=20,b=20), polar=dict(radialaxis=dict(visible=True, range=[0, 5])))
                    st.plotly_chart(fig_spy, use_container_width=True)
                else: st.warning("データ不足")

            with dist_col:
                st.write("📌 評価のバラツキ（分布）")
                dist_data = item_data[conf["scores"]].melt(var_name="項目", value_name="スコア")
                if not dist_data.empty:
                    import plotly.express as px
                    fig_dist = px.box(dist_data, x="項目", y="スコア", points="all",
                                     color_discrete_sequence=[theme_colors[0]] if 'theme_colors' in locals() else ['pink'])
                    fig_dist.update_layout(height=300, margin=dict(l=20,r=20,t=20,b=20), yaxis=dict(range=[0, 5.5]))
                    st.plotly_chart(fig_dist, use_container_width=True)

            if not item_stats.dropna().empty:
                max_val = item_stats.max()
                top_scores = item_stats[item_stats == max_val].index.tolist()
                st.success(f"💡 分析ヒント: この商品は **{' ・ '.join(top_scores)}** が最も評価されています。")

        # --- Tab 2: 感想・不満分析（全件・絞り込み） ---
        with tab2:
            st.subheader("🗣️ 全ジャンル・全アイテムの生の声")
            feedback_col = "ご感想やご不満点がございましたら、ご自由にご入力ください。"
            
            # --- 修正ポイント：商品名の列を自動特定 ---
            item_col_name = conf["item_col"] # 設定ファイルから正しい列名を取得
            
            # データがあるか確認
            voice_base_df = sub_df[sub_df[feedback_col].fillna("").str.strip() != ""]

            with st.expander("🛠️ 詳細フィルタで声を絞り込む", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    # ここで商品名の列を指定
                    item_options = sorted(voice_base_df[item_col_name].unique()) if not voice_base_df.empty else []
                    f_items = st.multiselect("特定の商品", item_options, key="v_f_items")
                    f_word = st.text_input("キーワード検索", placeholder="例：ベタつく", key="v_f_word")
                with c2:
                    # 肌悩みも列があるか確認してから
                    skin_col = "肌悩み"
                    skin_options = sorted(voice_base_df[skin_col].dropna().unique()) if skin_col in voice_base_df.columns else []
                    f_skin = st.multiselect("肌悩み", skin_options, key="v_f_skin")
                    f_gender = st.multiselect("性別（追加）", ["女性", "男性", "回答しない／その他"], key="v_f_gender")

            # --- フィルタ適用 ---
            f_df = voice_base_df.copy()
            if f_items: 
                f_df = f_df[f_df[item_col_name].isin(f_items)]
            if f_skin: 
                f_df = f_df[f_df["肌悩み"].isin(f_skin)]
            if f_gender: 
                f_df = f_df[f_df["性別"].isin(f_gender)]
            if f_word: 
                f_df = f_df[f_df[feedback_col].str.contains(f_word, na=False)]

            st.write(f"📈 該当件数: **{len(f_df)}** 件")
            st.markdown("---")

            # --- 本文表示エリア ---
            if not f_df.empty:
                for idx, row in f_df.iterrows():
                    # 1件ずつ枠（カード）で囲って表示
                    with st.container(border=True):
                        # ヘッダー情報を横並びにする
                        meta_col1, meta_col2 = st.columns([3, 1])
                        with meta_col1:
                            st.markdown(f"**📍 {row[item_col_name]}**")
                        with meta_col2:
                            st.caption(f"{row['性別']} | {row['年代']}")
                        
                        # 肌悩みがあれば表示
                        if "肌悩み" in row and pd.notna(row["肌悩み"]):
                            st.caption(f"悩み: {row['肌悩み']}")
                        
                        # 本文をドーンと表示
                        st.write(row[feedback_col])
            else:
                # フィルタで誰もいなくなった場合
                st.info("🔍 条件に一致する「声」が見つかりませんでした。フィルタを緩めてみてください。")
                
        # --- Tab 3: その他（分類漏れ）確認 ---
        with tab3:
            st.subheader("🔍 その他項目の内訳確認")
            other_col = "商品のアイテムタイプにて『その他』を選んだ方は入力してください。"
            st.caption("ジャンルやタイプで『その他』を選んだ方の記述内容です。")
            
            # 「その他」の列に記入がある行を抽出
            others_df = sub_df[sub_df[other_col].fillna("").str.strip() != ""]
            
            if not others_df.empty:
                st.dataframe(
                    others_df[["商品名", "性別", "年代", other_col]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("現在、分類不能なデータ（その他）はありません。")