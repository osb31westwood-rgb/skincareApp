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

def upload_to_drive(uploaded_file, file_name):
    """Googleドライブに画像をアップロードして直リンクを返す"""
    try:
        # get_gspread_clientの認証情報を流用してドライブサービスを作成
        client = get_gspread_client()
        drive_service = build('drive', 'v3', credentials=client.auth)
        
        # ★★★ 保存用フォルダのIDをここに入れてください ★★★
        folder_id = "10QwrFD5KdfeKiyf5eNLJoN2DPYh6DGWu?usp=sharing" 
        
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # ファイルの内容をメモリ上に読み込む
        media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), 
                                  mimetype=uploaded_file.type, 
                                  resumable=True)
        
        # ドライブにアップロード実行
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        
        # 直リンクURLを生成（この形式ならStreamlitで直接表示できます）
        return f"https://lh3.googleusercontent.com/u/0/d/{file_id}"
    except Exception as e:
        st.error(f"ドライブへの保存に失敗しました: {e}")
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
        
        # --- 設定エリア ---
        col_chart1, col_chart2 = st.columns([2, 1])
        with col_chart2:
            st.write("🔧 チャート設定")
            show_grid = st.toggle("グリッド線を表示", value=True)
            show_axis = st.toggle("軸ラベルを表示", value=True)
            # ★追加：表示モードの切り替え
            display_mode = st.radio("表示形式", ["重ねて比較", "横に並べる"], horizontal=True)

        items = sorted(sub_df[conf["item_col"]].dropna().unique())
        selected_items = st.multiselect("比較する商品を選択", items)
        
        if selected_items:
            valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
            
            if display_mode == "重ねて比較":
                fig = go.Figure()
                for i, item in enumerate(selected_items):
                    item_data = sub_df[sub_df[conf["item_col"]] == item][valid_scores].mean()
                    # 閉じたチャートにするためにデータの終点を始点と繋ぐ
                    r_values = item_data.values.tolist()
                    r_values += r_values[:1]
                    theta_values = valid_scores + [valid_scores[0]]
                    
                    color = theme_colors[i % len(theme_colors)]
                    fig.add_trace(go.Scatterpolar(
                        r=r_values, 
                        theta=theta_values, 
                        fill='toself', 
                        name=item, 
                        line=dict(color=color), 
                        fillcolor=color, 
                        opacity=0.5
                    ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=show_grid, range=[0, 5], showticklabels=show_axis),
                        angularaxis=dict(visible=show_grid, showticklabels=show_axis)
                    ),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)

            else: # 横に並べる
                cols = st.columns(len(selected_items))
                for i, item in enumerate(selected_items):
                    with cols[i]:
                        item_data = sub_df[sub_df[conf["item_col"]] == item][valid_scores].mean()
                        r_values = item_data.values.tolist()
                        r_values += r_values[:1]
                        theta_values = valid_scores + [valid_scores[0]]
                        
                        fig_sub = go.Figure(go.Scatterpolar(
                            r=r_values, theta=theta_values, fill='toself', 
                            name=item, line=dict(color=theme_colors[i % len(theme_colors)])
                        ))
                        fig_sub.update_layout(
                            polar=dict(
                                radialaxis=dict(visible=show_grid, range=[0, 5], showticklabels=False),
                                angularaxis=dict(visible=show_grid, showticklabels=show_axis)
                            ),
                            title=item, showlegend=False, height=300
                        )
                        st.plotly_chart(fig_sub, use_container_width=True)

            # --- 【新機能】分析結果をカルテへ送る ---
            st.markdown("---")
            st.subheader("📝 分析結果をカルテに記録")
            col_save1, col_save2 = st.columns([2, 1])
            
            with col_save1:
                target_save_item = st.selectbox("記録する商品を選択", selected_items, key="save_analysis_item")
                # その商品の最高評価項目を特定
                target_stats = sub_df[sub_df[conf["item_col"]] == target_save_item][valid_scores].mean()
                best_feature = target_stats.idxmax()
            
            with col_save2:
                st.write(" ") # 余白
                if st.button("💾 分析結果をメモに追記"):
                    try:
                        client = get_gspread_client()
                        sh = client.open("Cosme Data")
                        sheet_k = sh.worksheet("カルテ")
                        records = sheet_k.get_all_records()
                        
                        # 行の特定
                        row_idx = None
                        for i, r in enumerate(records):
                            if str(r.get("商品名")) == target_save_item:
                                row_idx = i + 2
                                break
                        
                        if row_idx:
                            headers = sheet_k.row_values(1)
                            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            # メモ欄の更新
                            if "メモ" in headers:
                                col_memo = headers.index("メモ") + 1
                                current_memo = sheet_k.cell(row_idx, col_memo).value or ""
                                analysis_msg = f"【自動追記】分析の結果、{best_feature}が最も高い評価でした。({now_str})"
                                new_memo = f"{current_memo}\n{analysis_msg}".strip()
                                
                                # 更新日時も更新
                                if "更新" in headers:
                                    sheet_k.update_cell(row_idx, headers.index("更新") + 1, now_str)
                                
                                sheet_k.update_cell(row_idx, col_memo, new_memo)
                                st.success(f"「{target_save_item}」のメモに分析結果を追記しました！")
                                st.balloons()
                            else:
                                st.error("「メモ」列が見つかりません。")
                        else:
                            st.warning("この商品はまだカルテに登録されていません。")
                    except Exception as e:
                        st.error(f"保存失敗: {e}")

    elif menu == "分布図分析":
        st.header(f"📈 分析分布 ({selected_theme})")
        valid_scores = [s for s in conf["scores"] if s in sub_df.columns]
        x_ax = st.selectbox("横軸", valid_scores, index=0)
        y_ax = st.selectbox("縦軸", valid_scores, index=len(valid_scores)-1 if len(valid_scores)>1 else 0)
        fig = px.scatter(sub_df, x=x_ax, y=y_ax, color=COL_AGE, hover_name=conf["item_col"], color_discrete_sequence=theme_colors)
        st.plotly_chart(fig, use_container_width=True)

    elif menu == "AIポップ生成":
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
        
        saved_info = ""
        current_row_idx = None
        for i, row in enumerate(saved_records):
            if str(row.get('商品名')) == str(selected_item):
                saved_info = row.get('公式情報', '')
                current_row_idx = i + 2
                break

        # 3. メインレイアウト（2カラム）
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # ★ 商品名と画像を横に並べて表示
            title_col, img_preview_col = st.columns([2, 1])
            with title_col:
                st.subheader("📖 商品情報・指示")
            
            # 選択中の商品の画像URLを取得
            current_item_data = next((row for row in saved_records if str(row.get('商品名')) == str(selected_item)), {})
            img_url = current_item_data.get("画像URL", "")

            with img_preview_col:
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.caption("🖼️ 画像未登録")

            input_info = st.text_area("カルテからの引継ぎ情報", value=saved_info, height=150, key="input_info_area")
            human_hint = st.text_input("AIへの追加指示", placeholder="例：30代向け、上品に", key="input_hint")
            run_generate = st.button("🚀 AIポップコピーを生成", key="btn_generate_ai_pop")
        with col2:
            st.subheader("📊 顧客の声（分析結果）")
            item_stats = sub_df[sub_df[conf["item_col"]] == selected_item][conf["scores"]].mean()
            if not item_stats.dropna().empty:
                st.info(f"評価トップ: {item_stats.idxmax()}")
                import plotly.graph_objects as go
                fig_spy = go.Figure(go.Scatterpolar(r=item_stats.values, theta=conf["scores"], fill='toself', line_color='pink'))
                fig_spy.update_layout(height=250, margin=dict(l=30, r=30, t=20, b=20), polar=dict(radialaxis=dict(visible=True, range=[0, 5])))
                st.plotly_chart(fig_spy, use_container_width=True)
                analysis_hint = f"顧客分析: {item_stats.idxmax()}が特に評価されています。"
            else:
                st.warning("アンケートデータがありません")
                analysis_hint = "新商品として魅力を提案してください。"

        # 4. 生成処理と薬機法チェック
        if run_generate:
            if model:
                with st.spinner("AIが薬機法を考慮して生成中..."):
                    try:
                        prompt = f"""
                        以下の情報をもとに、コスメの店頭POP用キャッチコピーを3案提案してください。
                        【最重要】薬機法（化粧品広告ガイドライン）を遵守し、治療効果や「最高」等の誇大表現は避けてください。
                        商品名: {selected_item}
                        特徴: {input_info}
                        要望: {human_hint}
                        分析: {analysis_hint}
                        """
                        res = model.generate_content(prompt)
                        st.session_state["generated_copy"] = res.text
                    except Exception as e: st.error(f"生成エラー: {e}")
            else:
                st.error("APIキーが設定されていません。")

        # 5. 結果表示と保存
        if "generated_copy" in st.session_state:
            st.markdown("---")
            
            # 💡 ここで薬機法セルフチェックを表示
            st.subheader("⚠️ 薬機法セルフチェック（辞書照合）")
            found_ng = False
            for word, reason in ng_dict.items():
                if word in st.session_state["generated_copy"]:
                    st.error(f"**NGワード検知: 「{word}」** → {reason}")
                    found_ng = True
            if not found_ng:
                st.success("✅ 現在のNG辞書に抵触する表現は見つかりませんでした。")

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
    elif menu == "商品カルテ編集":
        st.header("📋 商品カルテ：編集・管理")
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()
            df_karte = pd.DataFrame(records) if records else pd.DataFrame()

            mode = st.radio("作業を選択してください", ["既存データから選んで編集", "新規カルテ作成"], horizontal=True)

            # 初期値の設定
            target_item_name, official_info_val, memo_val, author_val, current_img_url = "", "", "", "", ""
            base_date = ""

            if mode == "既存データから選んで編集" and not df_karte.empty:
                item_list = [n for n in df_karte["商品名"].unique() if n]
                selected_name = st.selectbox("編集する商品を選択", item_list, key="edit_item_select")
                latest_row = df_karte[df_karte["商品名"] == selected_name].iloc[-1]
                
                target_item_name = selected_name
                official_info_val = latest_row.get("公式情報", "")
                memo_val = latest_row.get("メモ", "")
                author_val = latest_row.get("作成者", "")
                base_date = latest_row.get("日付", "")
                current_img_url = latest_row.get("画像URL", "") # 既存の画像URLを取得

            st.markdown("---")
            
            # --- 入力エリア ---
            col_a, col_b = st.columns(2)
            with col_a:
                edit_item_name = st.text_input("商品名", value=target_item_name)
            with col_b:
                edit_author = st.text_input("作成者・更新者名", value=author_val, placeholder="名前を入力")

            edit_official_info = st.text_area("公式情報（特徴・成分など）", value=official_info_val, height=150)
            edit_memo = st.text_area("スタッフメモ・備考", value=memo_val, height=100)

            # --- 画像アップロードエリア ---
            st.subheader("📸 商品画像")
            if current_img_url:
                st.image(current_img_url, caption="現在登録されている画像", width=200)
            
            uploaded_file = st.file_uploader("スマホで撮影または画像を選択（新しく登録・上書きする場合）", type=["jpg", "jpeg", "png"])

            if st.button("💾 カルテ内容を保存・更新", key="save_karte_edit"):
                if not edit_item_name:
                    st.error("商品名を入力してください。")
                else:
                    with st.spinner("データを保存中..."):
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        final_base_date = base_date if mode == "既存データから選んで編集" and base_date else now_str
                        
                        # 1. 画像の処理
                        new_image_url = current_img_url # 基本は今のURLを維持
                        if uploaded_file:
                            # 新しいファイルがアップロードされたらドライブへ保存
                            file_name = f"{edit_item_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                            res_url = upload_to_drive(uploaded_file, file_name)
                            if res_url:
                                new_image_url = res_url

                        # 2. スプレッドシートへの書き込み
                        # 列順: 日付, 更新, 作成者, 商品名, AIコピー, 公式情報, ポップ案, メモ, 画像URL
                        new_row = [
                            final_base_date, 
                            now_str, 
                            edit_author, 
                            edit_item_name, 
                            "", # AIコピー
                            edit_official_info, 
                            "", # ポップ案
                            edit_memo,
                            new_image_url # ★画像URLを最後に追加
                        ]
                        
                        sheet_karte.append_row(new_row)
                        st.success(f"「{edit_item_name}」の情報を保存しました！")
                        st.balloons()
                        # 保存後にプレビューを更新するため再読み込み
                        st.rerun()

        except Exception as e:
            st.error(f"エラー: {e}")

    elif menu == "商品カルテ一覧":
        st.header("📋 登録済み商品カルテ一覧")
        try:
            client = get_gspread_client()
            sh = client.open("Cosme Data")
            sheet_karte = sh.worksheet("カルテ")
            records = sheet_karte.get_all_records()

            if records:
                df_karte = pd.DataFrame(records)
                st.subheader("📊 全商品アーカイブ")
                
                # 表示する列の整理（画像URLは表には出さず、詳細表示で使う）
                cols = ["日付", "更新", "作成者", "商品名", "AIコピー", "ポップ案", "メモ"]
                display_cols = [c for c in cols if c in df_karte.columns]
                st.dataframe(df_karte[display_cols], use_container_width=True)

                st.markdown("---")
                st.subheader("🔍 商品別・詳細アーカイブ")
                item_list = [n for n in df_karte["商品名"].unique() if n]
                
                if item_list:
                    target_item = st.selectbox("詳しく見たい商品を選択", item_list, key="karte_pro_select")
                    # 最新のデータを取得
                    item_data = df_karte[df_karte["商品名"] == target_item].iloc[-1]
                    
                    # 3カラム構成にして、左側に画像を配置
                    c1, c2, c3 = st.columns([1, 1.2, 1.2])
                    
                    with c1:
                        st.write("📸 **商品画像**")
                        img_url = item_data.get("画像URL", "")
                        if img_url:
                            st.image(img_url, use_container_width=True, caption=target_item)
                        else:
                            st.info("画像は登録されていません")

                    with c2:
                        st.markdown(f"### 🏷️ {target_item}")
                        st.info(f"**📖 公式情報:**\n\n{item_data.get('公式情報', '未登録')}")
                        st.warning(f"**📝 スタッフメモ・備考:**\n\n{item_data.get('メモ', 'なし')}")
                    
                    with c3:
                        st.success(f"**🤖 AI提案コピー:**\n\n{item_data.get('AIコピー', '未登録')}")
                        st.success(f"**✨ 決定ポップ案:**\n\n{item_data.get('ポップ案', '未作成')}")
                        st.caption(f"最終更新: {item_data.get('更新', '---')}")
            else:
                st.info("まだカルテが登録されていません。")

        except Exception as e:
            st.error(f"表示エラー: {e}")