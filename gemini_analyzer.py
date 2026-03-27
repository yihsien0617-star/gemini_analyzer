import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai

# ==========================================
# 內部輔助函數：清洗 Gemini 回傳的 JSON
# ==========================================
def clean_json_response(text):
    """清除 LLM 可能自帶的 Markdown 標記，以確保 JSON 格式正確"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

# ==========================================
# 核心功能：呼叫 Gemini API 進行語意分析
# ==========================================
def analyze_topic_with_gemini(topic, text_content, api_key):
    """將該主題的考題送給 Gemini，要求萃取最核心的醫學關鍵字"""
    
    # 初始化 Gemini API
    genai.configure(api_key=api_key)
    
    # 使用 Gemini 1.5 Flash 模型 (速度最快、最適合做大量文字萃取)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 限制字數，避免單次請求過大 (取前 15000 字元，通常足以代表該單元特徵)
    truncated_text = text_content[:15000]
    
    # 精心設計的 AI 提示詞 (Prompt)
    prompt = f"""
    你現在是一位台灣的「專業醫事檢驗師」與「國考出題委員」。
    以下是屬於【{topic}】這個分類的國考題庫內容：
    
    {truncated_text}
    
    請分析這些題目與解析的語意，並萃取出最能代表【{topic}】這個分類的 10 到 15 個「核心專業關鍵字」。
    
    萃取規則：
    1. 必須包含最重要的英文專有名詞 (如 IgE, CD4, GVHD, ELISA 等)。
    2. 必須包含代表性的中文醫學名詞 (如 巨噬細胞, 紅斑性狼瘡, 遲發性過敏反應 等)。
    3. 絕對不要包含沒有意義的考試用語 (如 下列何者, 正確, 敘述, 選項, 檢驗結果)。
    
    請「只」回傳一個純 JSON 陣列 (Array of strings)，不要有任何其他的開頭或結尾問候語。
    範例格式：["關鍵字1", "關鍵字2", "KEYWORD_A"]
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = clean_json_response(response.text)
        keywords = json.loads(clean_text)
        return keywords
    except Exception as e:
        return [f"API_ERROR: {str(e)}"]

# ==========================================
# 網頁介面開始
# ==========================================
st.set_page_config(page_title="Gemini 聯網題庫分析引擎", page_icon="🧠", layout="wide")

st.title("🧠 Gemini 聯網題庫智慧探勘引擎")
st.write("直接連線至 Gemini AI 大腦！系統會完整理解考題語意，精準提煉出最專業的醫學關鍵字，徹底解放老師的手動校正時間。")

st.divider()

# 讓使用者輸入 API Key
api_key = st.text_input("AIzaSyBHXWWa6wPbHZSQ0tlxoP-XDxNI2hOifN0：", type="password", help="請至 Google AI Studio 免費申請 API Key")

if not api_key:
    st.warning("⚠️ 請先在上方輸入 API Key 以啟動 Gemini 聯網功能。")
    st.stop()

# 左側：輸入舊字典 / 右側：上傳 Excel
col_dict, col_upload = st.columns([1, 1])

with col_dict:
    st.subheader("1️⃣ 貼上您目前的字典")
    default_dict = {
        "過敏反應": ["IgE", "過敏", "氣喘"],
        "腫瘤免疫": ["腫瘤", "癌症", "tumor"],
        "自體免疫": ["自體免疫", "紅斑性狼瘡", "風濕", "SLE"],
        "移植免疫": ["移植", "排斥", "GVHD", "MHC"],
        "先天免疫": ["先天免疫", "巨噬細胞", "補體"],
        "細胞免疫": ["T細胞", "CD4", "CD8", "T cell"],
        "體液免疫": ["B細胞", "B cell", "抗體", "IgG"]
    }
    old_dict_str = st.text_area("現有 JSON 字典：", value=json.dumps(default_dict, ensure_ascii=False, indent=4), height=200)
    try:
        current_dict = json.loads(old_dict_str)
    except:
        st.error("字典格式錯誤，請確認是正確的 JSON 格式。")
        current_dict = {}

with col_upload:
    st.subheader("2️⃣ 上傳已分類的題庫 (Excel)")
    uploaded_excel = st.file_uploader("選擇 Excel 檔案 (.xlsx)", type=["xlsx"])

if uploaded_excel and st.button("🚀 啟動 Gemini 聯網分析", type="primary", use_container_width=True):
    
    df = pd.read_excel(uploaded_excel).fillna("")
    topic_col = "主題 (下拉選單)" if "主題 (下拉選單)" in df.columns else "主題"
    
    if topic_col not in df.columns:
        st.error("分析失敗。請確認 Excel 中有「主題」欄位。")
        st.stop()
        
    grouped = df.groupby(topic_col)
    
    # 建立進度條
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    analysis_result = {}
    topics = [str(t) for t in grouped.groups.keys() if str(t) != "未分類" and str(t).strip()]
    
    # 逐一將每個單元的題目送給 Gemini 處理
    for i, topic in enumerate(topics):
        status_text.markdown(f"**🔄 正在呼叫 Gemini 分析單元：【{topic}】... ({i+1}/{len(topics)})**")
        
        group = grouped.get_group(topic)
        # 將該單元的所有題目與解析合併成一大段文字
        text_to_analyze = ""
        for _, row in group.iterrows():
            text_to_analyze += f"題目：{row.get('題目', '')}\n解析：{row.get('解析', '')}\n---\n"
            
        # 呼叫 Gemini
        ai_suggested_keywords = analyze_topic_with_gemini(topic, text_to_analyze, api_key)
        analysis_result[topic] = ai_suggested_keywords
        
        # 更新進度條
        progress_bar.progress((i + 1) / len(topics))
        
    status_text.success("✅ Gemini 分析完畢！")
    
    st.divider()
    st.subheader("🤖 Gemini 智慧分析結果")
    
    updated_dict = current_dict.copy()
    tabs = st.tabs(list(analysis_result.keys()))
    
    for idx, (topic, ai_words) in enumerate(analysis_result.items()):
        with tabs[idx]:
            st.markdown(f"#### 🏷️ 關於【{topic}】")
            
            # 檢查是否有 API 錯誤
            if ai_words and str(ai_words[0]).startswith("API_ERROR"):
                st.error(f"連線失敗：{ai_words[0]}")
                continue
                
            existing_words = [w.upper() for w in current_dict.get(topic, [])]
            
            # 過濾出「字典裡還沒有」的 AI 推薦新詞彙
            suggested_new_words = [w for w in ai_words if w.upper() not in existing_words]
            
            if suggested_new_words:
                st.info(f"✨ Gemini 閱讀考題後，強烈建議您加入以下專業關鍵字：")
                
                selected_new = st.multiselect(
                    f"挑選要加入【{topic}】的關鍵字：",
                    options=suggested_new_words,
                    default=suggested_new_words # AI 抓的通常很準，預設全選！
                )
                
                if topic not in updated_dict:
                    updated_dict[topic] = []
                
                # 合併儲存
                updated_dict[topic] = list(set(current_dict.get(topic, []) + selected_new))
            else:
                st.success("👍 您的字典已經無懈可擊！Gemini 認為不需要再補充了。")
                
    st.divider()
    st.subheader("3️⃣ 獲取終極 AI 升級版字典")
    st.write("這是融合了 Gemini 智慧判斷後的終極字典，將它放入您的轉檔系統中，未來的自動分類將會擁有 AI 級的精準度！")
    
    new_dict_json = json.dumps(updated_dict, ensure_ascii=False, indent=4)
    st.code(new_dict_json, language="json")
    
    st.download_button(
        label="💾 下載 AI 升級版字典 (ai_dict.json)",
        data=new_dict_json,
        file_name="gemini_upgraded_dict.json",
        mime="application/json",
        type="primary",
        use_container_width=True
    )
