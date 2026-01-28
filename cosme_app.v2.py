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

# --- 1. 定数・カラーパレットの定義 (最初に書く！) ---
COL_GENRE = "ジャンル"
COL_AGE = "年齢"
COL_GENDER = "性別"

COLOR_PALETTES = {
    "ナチュラルカラー": ["#a98467", "#adc178", "#dde5b6", "#6c584c", "#f0ead2"],
    "くすみカラー": ["#8e9775", "#e28e8e", "#94a7ae", "#a79c93", "#d4a5a5"],
    "ミルクカラー": ["#f3e9dc", "#c0d6df", "#d8e2dc", "#ffe5d9", "#fbfacd"],
    "パステルカラー": ["#ffb7b2", "#ffdac1", "#e2f0cb", "#b5ead7", "#c7ceea"],
    "ローズ系": ["#e5989b", "#ffb4a2", "#ffcdb2", "#b5838d", "#6d597a"]
}

# --- 2. 関数の定義 (読み込み処理の準備) ---

def load_config_from_sheet(spreadsheet):
    """商品構成シートから設定を読み込む"""
    sheet = spreadsheet.worksheet("商品構成")
    data = sheet.get_all_records()
    new_config = {}
    
    for row in data:
        genre = row["ジャンル名"]
        if genre not in new_config:
            new_config[genre] = {
                "item_col": "商品名",
                "type_col": "アイテムタイプ",
                "form_id": row["フォームID"],
                "scores": [s.strip() for s in row["評価項目リスト"].split(",")],
                "types": []
            }
        new_config[genre]["types"].append(row["アイテムタイプ"])
    return new_config

@st.cache_data(ttl=300)
def load_data():
    """アンケート結果を読み込み、列名を短い名前にリネームする"""
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT5HpURwDWt6S0KkQbiS8ugZksNm8yTokNeKE4X-oBHmLMubOvOKIsuU4q6_onLta2cd0brCBQc-cHA/pub?gid=1578087772&single=true&output=csv"
    try:
        data = pd.read_csv(url)
        # 列名の前後の空白を削除
        data.columns = [str(c).strip() for c in data.columns]
        
        # 長い質問文を短いIDに変換するマップ
        COL_MAP = {
            "今回ご使用の商品のジャンルを選択してください。": "ジャンル",
            "スキンケア商品を選択した方はアイテムタイプを選択してください。": "アイテムタイプ",
            "ヘアケア商品を選択した方はアイテムタイプを選択してください。": "アイテムタイプ",
            "コスメ商品（ベースメイク）を選択した方はアイテムタイプを選択してください。": "アイテムタイプ",
            "コスメ商品（ポイントメイク）を選択した方はアイテムタイプを選択してください。": "アイテムタイプ",
            "今回ご使用の商品名を入力してください。": "商品名",
            "ご感想やご不満点がございましたら、ご自由にご入力ください。": "感想",
            "今回の商品は購入されましたか？": "購入状況",
            "最近、ご自身が置かれている環境で気になることはありますか？": "環境変化",
            "ライフスタイルでストレス・睡眠・食生活など、気になることはありますか？": "ライフスタイル",
            "肌のお悩み（※複数選択可）": "肌悩み"
        }

        # 枝番（.1, .2など）を処理してリネームを適用
        new_cols = []
        for col in data.columns:
            base_name = col.split('.')[0].strip()
            new_cols.append(COL_MAP.get(base_name, col))
        
        data.columns = new_cols
         # --- ここで強制お掃除 ---
        for c in ["商品名", "肌悩み", "アイテムタイプ", "感想"]:
            if c in data.columns and isinstance(data[c], pd.DataFrame):
                data[c] = data[c].bfill(axis=1).iloc[:, 0]
        data = data.loc[:, ~data.columns.duplicated()].copy()
        # ----------------------
        return data
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return None

# --- 3. 実際の実行プロセス ---

# クライアント・スプレッドシートの準備
client = get_gspread_client()
spreadsheet = client.open("Cosme Data")

# 定義した関数を使ってデータを読み込む
COLUMN_CONFIG = load_config_from_sheet(spreadsheet)
df = load_data()
# --- 【修正後】ここにお掃除コードを入れる ---
if df is not None:
    # 統合したい列名のリスト
    cols_to_fix = ["商品名", "肌悩み", "アイテムタイプ", "感想"]

    for col_name in cols_to_fix:
        if col_name in df.columns:
            target_cols = df[col_name]
            # 同じ名前の列が複数（DataFrame）ある場合のみ処理
            if isinstance(target_cols, pd.DataFrame):
                # 横方向に見て空欄を埋め、1本にまとめる
                df[col_name] = target_cols.bfill(axis=1).iloc[:, 0]
    
    # まとめた後、重複した古い列を削除して「1つだけ」残す
    df = df.loc[:, ~df.columns.duplicated()].copy()
# ----------------------------------------------

# この後にメニュー選択 (if menu == ...) や分析コードが続く
# ------------------------------------------------
    
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
            "🧪 成分マスタ編集",
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
        
           # 254行目付近の修正
           type_col_name = conf.get("type_col", "アイテムタイプ")

           if type_col_name in sub_df.columns:
            # --- 修正：複数列あっても1つにまとめてユニーク値を取得 ---
               target_data = sub_df[type_col_name]
               if isinstance(target_data, pd.DataFrame):
                # 複数列ある場合は縦に積み上げて1列にする
                combined_series = target_data.stack()
               else:
                # 1列だけならそのまま
                combined_series = target_data
            
               types = sorted(combined_series.dropna().unique())
               selected_types = st.multiselect("アイテムタイプ", types)
            # --------------------------------------------------
           else:
             st.warning(f"⚠️ 列 '{type_col_name}' がデータに見つかりません。")
             st.write("現在の列名:", sub_df.columns.tolist())
             selected_types = []

        # 年代の選択
        ages = sorted(sub_df[COL_AGE].unique())
        selected_ages = st.multiselect("年代", ages, default=ages)

        genders = ["女性", "男性", "回答しない／その他"]
        selected_genders = st.multiselect("性別", genders, default=genders)

          # --- フィルタ適用（1つずつ順番に絞り込む） ---

# 1. 年齢で絞り込む
if selected_ages:
    sub_df = sub_df[sub_df[COL_AGE].isin(selected_ages)]

# 2. アイテムタイプで絞り込む（列が存在し、かつ選択されている場合のみ）
type_col = "アイテムタイプ"
if type_col in sub_df.columns:
    if selected_types:
        sub_df = sub_df[sub_df[type_col].isin(selected_types)]

# 3. 性別で絞り込む
if selected_genders:
    sub_df = sub_df[sub_df["性別"].isin(selected_genders)]


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
            # --- 384行目付近の修正 ---
            item_col_name = conf["item_col"]
            target_item_data = sub_df[item_col_name]

            if isinstance(target_item_data, pd.DataFrame):
               # 複数列（商品名が5つなど）ある場合、すべてを1列にまとめてからユニーク値を取る
               survey_items = set(target_item_data.stack().dropna().unique())
            else:
                # 1列だけの場合
                survey_items = set(target_item_data.dropna().unique())
                # -------------------------

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
            # --- 487行目の修正：商品詳細データの抽出 ---
            item_col = conf["item_col"]
            target_item_col = sub_df[item_col]

            # 複数列（商品名）のどこかに、選択された商品名がある行を探す
            if isinstance(target_item_col, pd.DataFrame):
               # 横方向に見て、どれか1列でも一致すればTrueにする
               mask = (target_item_col == selected_item).any(axis=1)
            else:
                # 1列しかな\い場合は普通に比較
                mask = (target_item_col == selected_item)

            item_all_data = sub_df[mask].copy()
            # ----------------------------------------
            
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

# --- 商品カルテ編集・新規作成セクション ---
elif menu == "📋 商品カルテ編集":
    st.header("📋 商品カルテ：編集・管理")

    try:
        # スプレッドシートへの接続
        client = get_gspread_client()
        sh = client.open("Cosme Data")
        sheet_karte = sh.worksheet("カルテ")
        
        # データを取得して DataFrame に変換
        records = sheet_karte.get_all_records()
        
        # ★ここで確実に df_karte を定義する！
        if records:
            df_karte = pd.DataFrame(records)
        else:
            # データが1件もない場合の空の器を作る（列名だけ定義）
            df_karte = pd.DataFrame(columns=[
                "新規", "更新", "作成者", "ジャンル", "アイテムタイプ", 
                "商品名", "全成分", "公式情報", "AIコピー/ポップ案", "メモ", "画像URL"
            ])

        mode = st.radio("作業を選択してください", ["既存データから選んで編集", "新規カルテ作成"], horizontal=True)

        # --- ★重要：ここで全ての変数に初期値をセットする（エラー防止） ---
        target_item_name = ""
        official_info_val = ""
        memo_val = ""
        author_val = st.session_state.get("user_name", "") # ログイン名があれば入れる
        base_date = ""
        current_img_url = ""
        current_gen = ""
        current_type = ""
        current_ingredients = ""
        latest_row = {} # 空の辞書として初期化

        # 既存編集の場合のみ、上記に値を上書きする
        if mode == "既存データから選んで編集" and not df_karte.empty:
            item_list = [n for n in df_karte["商品名"].unique() if n]
            if item_list:
                selected_name = st.selectbox("編集する商品を選択", item_list, key="edit_item_select")
                
                # 選択された商品の最新行を取得
                target_rows = df_karte[df_karte["商品名"] == selected_name]
                if not target_rows.empty:
                    latest_row = target_rows.iloc[-1]
                    
                    target_item_name = selected_name
                    official_info_val = latest_row.get("公式情報", "")
                    memo_val = latest_row.get("メモ", "")
                    author_val = latest_row.get("作成者", "")
                    base_date = latest_row.get("新規", "")
                    current_img_url = latest_row.get("画像URL", "")
                    current_gen = latest_row.get("ジャンル", "")
                    current_type = latest_row.get("アイテムタイプ", "")
                    current_ingredients = latest_row.get("全成分", "")


       # --- 入力エリアのレイアウト修正 ---
        st.markdown("---")
        st.markdown("### 📝 カルテ入力")
        
        col_info1, col_info2, col_info3 = st.columns([2, 2, 1])
        with col_info1:
            gen_idx = list(COLUMN_CONFIG.keys()).index(current_gen) if current_gen in COLUMN_CONFIG else 0
            main_cat = st.selectbox("✨ ジャンル", list(COLUMN_CONFIG.keys()), index=gen_idx)
        with col_info2:
            types = COLUMN_CONFIG[main_cat]["types"]
            type_idx = types.index(current_type) if current_type in types else 0
            sub_cat = st.selectbox("🏷️ アイテムタイプ", types, index=type_idx)
        with col_info3:
            edit_author = st.text_input("✍️ 作成者", value=author_val)

        edit_item_name = st.text_input("🎁 商品名", value=target_item_name)

        # 【追加】全成分の入力欄
        current_ingredients = latest_row.get("全成分", "") if mode == "既存データから選んで編集" else ""
        edit_ingredients = st.text_area("🧪 全成分", value=current_ingredients, placeholder="・ビタミンC・レチノール...（配合量順に・で区切る）", height=100)

        col_text1, col_text2 = st.columns(2)
        with col_text1:
            edit_official_info = st.text_area("📖 公式情報（特徴など）", value=official_info_val, height=150)
        with col_text2:
            edit_memo = st.text_area("💡 スタッフメモ・備考", value=memo_val, height=150)

       # --- 画像セクション ---
        st.subheader("📸 商品画像")
        
        # 保存ボタンの外側で変数を初期化
        delete_image = False
        uploaded_file = None

        if current_img_url:
            st.image(current_img_url, caption="現在登録されている画像", width=200)
            # 変数の定義
            delete_image = st.checkbox("🗑️ この画像を削除する")
        
        # 変数の定義
        uploaded_file = st.file_uploader("新しい画像を選択（上書き）", type=["jpg", "jpeg", "png"])

        st.markdown("---")

        # 保存ボタン
        if st.button("💾 カルテ内容を保存・更新", key="save_karte_edit"):
            # ここから下の保存処理で delete_image や uploaded_file を安全に使えるようになります

            if not edit_item_name:
                st.error("商品名を入力してください。")
            else:
                with st.spinner("データを保存中..."):
                    now_jst = datetime.datetime.now() + datetime.timedelta(hours=9)
                    now_str = now_jst.strftime("%Y-%m-%d %H:%M:%S")
                    final_base_date = base_date if mode == "既存データから選んで編集" and base_date else now_str

                    # 画像URLの確定
                    if delete_image: new_image_url = ""
                    elif uploaded_file:
                        res_url = upload_to_imgbb(uploaded_file)
                        new_image_url = res_url if res_url else current_img_url
                    else: new_image_url = current_img_url

                    # 【重要】新しい列順 A～K に完全対応
                    # スプレッドシート：新規(A), 更新(B), 作成者(C), ジャンル(D), タイプ(E), 商品名(F), 全成分(G), 公式情報(H), AIコピー/ポップ案(I), メモ(J), 画像URL(K)
                    new_row = [
                        final_base_date,    # A: 新規
                        now_str,            # B: 更新
                        edit_author,        # C: 作成者
                        main_cat,           # D: ジャンル
                        sub_cat,            # E: アイテムタイプ
                        edit_item_name,     # F: 商品名
                        edit_ingredients,   # G: 全成分 ★ここが追加
                        edit_official_info, # H: 公式情報
                        "",                 # I: AIコピー/ポップ案 (空で保存)
                        edit_memo,          # J: メモ
                        new_image_url       # K: 画像URL
                    ]

                    # --- 保存処理 ---
                    all_records = sheet_karte.get_all_records()
                    df_all = pd.DataFrame(all_records)

                    if not df_all.empty and edit_item_name in df_all["商品名"].values:
                        matching_rows = df_all[df_all["商品名"] == edit_item_name]
                        row_index = matching_rows.index[0] + 2 
                        if "新規" in df_all.columns:
                            new_row[0] = str(matching_rows["新規"].values[0])
                        
                        sheet_karte.update(range_name=f"A{row_index}:K{row_index}", values=[new_row])
                        st.success(f"「{edit_item_name}」の情報を更新しました！")
                    else:
                        sheet_karte.append_row(new_row)
                        st.success(f"「{edit_item_name}」を新規登録しました！")

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

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

elif menu == "🧪 成分マスタ編集":
    st.header("🧪 成分・悩みマスタ編集")
    st.caption("ここで設定した成分とフレーズが、アンケート分析時のおすすめ理由になります。")

    try:
        client = get_gspread_client()
        sh = client.open("Cosme Data")
        
        # マスタ用シートの取得（なければ作成）
        try:
            sheet_master = sh.worksheet("ingredient_master")
        except:
            sheet_master = sh.add_worksheet(title="ingredient_master", rows="100", cols="10")
            sheet_master.append_row(["分類", "キーワード", "推奨成分", "フレーズ", "更新日"])

        records = sheet_master.get_all_records()
        df_master = pd.DataFrame(records)

        # 設定項目の定義
        trouble_list = ["ハリ・弾力", "毛穴", "くすみ・透明感", "乾燥", "テカリ・べたつき", "肌荒れ"]
        env_list = ["乾燥", "日差し・紫外線", "湿気によるべたつき・蒸れ", "摩擦"]
        l_key = "ストレス・睡眠・食生活"

        # --- ここからフォーム開始 ---
        with st.form(key="master_management_form"):
            master_data = [] # データを一時保存するリスト
            
            st.subheader("🎯 肌悩み別の設定")
            for t in trouble_list:
                col1, col2 = st.columns([1, 2])
                row = df_master[df_master["キーワード"] == t].iloc[0] if not df_master.empty and t in df_master["キーワード"].values else {}
                with col1:
                    ing = st.text_input(f"【{t}】の成分", value=row.get("推奨成分", ""), key=f"ing_{t}")
                with col2:
                    phrase = st.text_input(f"【{t}】のフレーズ", value=row.get("フレーズ", ""), key=f"ph_{t}")
                master_data.append(["悩み", t, ing, phrase])

            st.divider()
            st.subheader("🌍 環境・ライフスタイルの設定")
            for e in env_list:
                col1, col2 = st.columns([1, 2])
                row = df_master[df_master["キーワード"] == e].iloc[0] if not df_master.empty and e in df_master["キーワード"].values else {}
                with col1:
                    ing = st.text_input(f"【{e}】の成分", value=row.get("推奨成分", ""), key=f"ing_{e}")
                with col2:
                    phrase = st.text_input(f"【{e}】のフレーズ", value=row.get("フレーズ", ""), key=f"ph_{e}")
                master_data.append(["環境", e, ing, phrase])

            st.info(f"💡 {l_key} の設定（一括り項目）")
            col1, col2 = st.columns([1, 2])
            row_l = df_master[df_master["キーワード"] == l_key].iloc[0] if not df_master.empty and l_key in df_master["キーワード"].values else {}
            with col1:
                ing_l = st.text_input("推奨成分", value=row_l.get("推奨成分", "CICA, ナイアシンアミド"), key="mst_lifestyle_all")
            with col2:
                phrase_l = st.text_input("推奨フレーズ", value=row_l.get("フレーズ", "生活の乱れから肌を守る"), key="ph_lifestyle_all")
            master_data.append(["ライフスタイル", l_key, ing_l, phrase_l])

            # ★【最重要】ここが「with st.form」のインデント（右空白）の終わりの位置です
            submitted = st.form_submit_button("✅ この内容でマスタを保存する")

        # --- ここからフォームの外（保存処理） ---
        if submitted:
            with st.spinner("スプレッドシートを更新中..."):
                now_str = (datetime.datetime.now() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
                header = ["分類", "キーワード", "推奨成分", "フレーズ", "更新日"]
                final_rows = [header]
                for data_row in master_data:
                    final_rows.append(data_row + [now_str])
                
                sheet_master.clear()
                sheet_master.update("A1", final_rows)
                st.success("成分マスタを更新しました！スプレッドシートを確認してください。")

    except Exception as e:
        st.error(f"システムエラーが発生しました: {e}")

elif menu == "📈 アンケート分析":
    st.header("📊 アンケートデータ詳細分析")

    if sub_df.empty:
        st.warning("⚠️ 現在の絞り込み条件に一致するデータがありません。")
    else:
        # --- 1. 変数の定義（まず最初にすべて準備する） ---
        age_col = "年代" if "年代" in sub_df.columns else None
        gen_col = "性別" if "性別" in sub_df.columns else None
        skin_col = "肌悩み" if "肌悩み" in sub_df.columns else None
        
        valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
        item_col_name = conf["item_col"]

        # --- 2. タブの定義 ---
        tabs = st.tabs(["🎯 推奨商品", "📈 スコア分析", "📉 相関分析", "📊 ボックスプロット", "🗣️ 生の声分析", "🔍 その他内訳"])
        tab1, tab2, tab3, tab4, tab5, tab6 = tabs

        # --- Tab 1: 🎯 推奨商品（逆引き） ---
        with tab1:
            st.subheader("🎯 ターゲット別・推奨商品")
            st.caption("特定の層で最も満足度が高い商品を抽出します。")

            # ターゲット絞り込みUI
            c1, c2, c3 = st.columns(3)
            with c1:
                f_age = st.multiselect("年代で絞り込む", sorted(sub_df[age_col].dropna().unique()), key="tab1_age_f") if age_col else []
            with c2:
                f_gender = st.multiselect("性別で絞り込む", sorted(sub_df[gen_col].dropna().unique()), key="tab1_gen_f") if gen_col else []
            with c3:
                f_skin = st.multiselect("肌悩みで絞り込む", sorted(sub_df[skin_col].dropna().unique()), key="tab1_skin_f") if skin_col else []

            # フィルタリング実行
            rev_df = sub_df.copy()
            if f_age and age_col: rev_df = rev_df[rev_df[age_col].isin(f_age)]
            if f_gender and gen_col: rev_df = rev_df[rev_df[gen_col].isin(f_gender)]
            if f_skin and skin_col: 
                rev_df = rev_df[rev_df[skin_col].apply(lambda x: any(s in str(x) for s in f_skin))]

            # ランキング表示
            if not rev_df.empty and valid_scores:
                # 商品名とスコアの抽出
                rev_melted = rev_df.melt(id_vars=valid_scores, value_vars=item_col_name, value_name="対象商品").dropna(subset=["対象商品"])
                if not rev_melted.empty:
                    product_ranking = rev_melted.groupby("対象商品")[valid_scores].mean()
                    product_ranking["総合スコア"] = product_ranking.mean(axis=1)
                    product_ranking = product_ranking.sort_values("総合スコア", ascending=False)

                    st.write(f"📊 **条件に合致する回答: {len(rev_df)}件**")
                    for i, (p_name, row) in enumerate(product_ranking.head(3).iterrows()):
                        with st.container(border=True):
                            cl_r, cl_t = st.columns([1, 4])
                            cl_r.title(f"#{i+1}")
                            with cl_t:
                                st.markdown(f"### {p_name}")
                                best_feat = row[valid_scores].idxmax()
                                st.write(f"🌟 強み: **{best_feat}** ({row[best_feat]:.2f}点)")
                                st.progress(row["総合スコア"]/5.0, text=f"総合満足度: {row['総合スコア']:.2f}")
                                
                                # AIポップ連携ボタン
                                if st.button(f"✨ {p_name} のポップ案を作る", key=f"link_{p_name}"):
                                    st.session_state["ai_pop_selected_item"] = p_name
                                    if "menu_selection" in st.session_state:
                                        st.session_state["menu_selection"] = "✨ AIポップ作成"
                                    st.rerun()
            else:
                st.info("条件に一致するデータがありません。")

        # --- Tab 2: 📈 スコア分析（レーダーチャート） ---
        with tab2:
            st.write("### 📈 商品間スコア比較")
            # 商品リスト取得
            all_items = sorted(sub_df[item_col_name].stack().dropna().unique()) if isinstance(sub_df[item_col_name], pd.DataFrame) else sorted(sub_df[item_col_name].dropna().unique())
            sel_items = st.multiselect("比較する商品を選択", all_items, key="sel_t2")
            
            if sel_items and valid_scores:
                import plotly.graph_objects as go
                fig = go.Figure()
                for i, item in enumerate(sel_items):
                    # 各商品の平均を計算（複数列対応）
                    if isinstance(sub_df[item_col_name], pd.DataFrame):
                        mask = (sub_df[item_col_name] == item).any(axis=1)
                    else:
                        mask = (sub_df[item_col_name] == item)
                    
                    item_avg = sub_df[mask][valid_scores].mean()
                    r_val = item_avg.values.tolist() + [item_avg.values[0]]
                    theta_val = valid_scores + [valid_scores[0]]
                    fig.add_trace(go.Scatterpolar(r=r_val, theta=theta_val, fill='toself', name=item))
                
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), height=450)
                st.plotly_chart(fig, use_container_width=True)

        # --- Tab 3: 📉 相関分析 ---
        with tab3:
            st.subheader("📉 スコアの相関分析")
            if len(valid_scores) >= 2:
                c1, c2 = st.columns(2)
                x_ax = c1.selectbox("横軸", valid_scores, index=0)
                y_ax = c2.selectbox("縦軸", valid_scores, index=1)
                import plotly.express as px
                fig_scatter = px.scatter(sub_df, x=x_ax, y=y_ax, color="年代" if "年代" in sub_df.columns else None, range_x=[0,5.5], range_y=[0,5.5], template="plotly_white")
                st.plotly_chart(fig_scatter, use_container_width=True)

        # --- Tab 4: 📊 ボックスプロット（比較分析） ---
        with tab4:
            st.subheader("📊 項目別スコア分布比較")
            all_items = sorted(sub_df[item_col_name].stack().dropna().unique()) if isinstance(sub_df[item_col_name], pd.DataFrame) else sorted(sub_df[item_col_name].dropna().unique())
            
            col_a, col_b = st.columns(2)
            item_a = col_a.selectbox("商品A", all_items, index=0)
            item_b = col_b.selectbox("商品B", all_items, index=min(1, len(all_items)-1))

            if item_a and item_b:
                # データの抽出
                def get_item_df(name):
                    mask = (sub_df[item_col_name] == name).any(axis=1) if isinstance(sub_df[item_col_name], pd.DataFrame) else (sub_df[item_col_name] == name)
                    res = sub_df[mask][valid_scores].copy()
                    res["商品名"] = name
                    return res

                df_compare = pd.concat([get_item_df(item_a), get_item_df(item_b)])
                melted_compare = df_compare.melt(id_vars=["商品名"], var_name="項目", value_name="スコア")
                melted_compare["スコア"] = pd.to_numeric(melted_compare["スコア"], errors='coerce')

                import plotly.express as px
                fig_box = px.box(melted_compare, x="項目", y="スコア", color="商品名", points="all", title=f"{item_a} vs {item_b} の分布")
                fig_box.update_layout(yaxis=dict(range=[0, 5.5]))
                st.plotly_chart(fig_box, use_container_width=True)

        # --- Tab 5: 🗣️ 生の声分析 ---
        with tab5:
            st.subheader("🗣️ 届いた感想（生の声）")
            fb_col = "感想"
            if fb_col in sub_df.columns:
                f_df = sub_df[sub_df[fb_col].notna() & (sub_df[fb_col] != "")]
                for _, row in f_df.iterrows():
                    with st.container(border=True):
                        # 商品名（複数列対応）
                        p_display = row[item_col_name].dropna().values[0] if isinstance(row[item_col_name], pd.Series) else row[item_col_name]
                        st.markdown(f"**📍 {p_display}** ({row.get('年代', '不明')})")
                        st.write(row[fb_col])

        # --- Tab 6: 🔍 その他内訳 ---
        with tab6:
            st.subheader("🔍 その他自由回答")
            other_col = "商品のアイテムタイプにて『その他』を選んだ方は入力してください。"
            if other_col in sub_df.columns:
                others = sub_df[sub_df[other_col].notna() & (sub_df[other_col] != "")]
                st.dataframe(others[[other_col]], use_container_width=True)