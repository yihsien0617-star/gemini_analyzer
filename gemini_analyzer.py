import streamlit as st
import json
import re
import docx
import google.generativeai as genai

# ==========================================
# 🔑 1. 請在此處填入您的 Gemini API Key (保留雙引號)
# ==========================================
GEMINI_API_KEY = "AIzaSyBHXWWa6wPbHZSQ0tlxoP-XDxNI2hOifN0"

# ==========================================
# 2. 內部輔助函數：清洗 Gemini 回傳的 JSON 
# ==========================================
def clean_json_response(text):
    """清除 LLM 可能自帶的 Markdown 標記，避開引號換行錯誤"""
    text = str(text).strip()
    text = text.replace('```json', '')
    text = text.replace('```', '')
    return text.strip()

# ==========================================
# 3. 核心功能：呼叫 Gemini API 進行「深度多維度」語意分析
# ==========================================
def analyze_topic_with_gemini(topic, text_content, api_key):
    """將該主題的考題送給 Gemini，要求萃取最豐富的醫學關鍵字"""
    genai.configure(api_key=api_key)
    
    truncated_text = text_content[:30000] 
    
    prompt = f"""
    你現在是一位台灣的「專業醫事檢驗師」與「國考出題委員」。
    以下是屬於【{topic}】這個分類的國考題庫內容：
    
    {truncated_text}
    
    請深度分析這些題目與解析的語意，並為【{topic}】這個分類萃取出「30 到 50 個」最核心且具代表性的專業關鍵字。
    為了確保關鍵字夠豐富且涵蓋全面，請務必從以下 4 個維度進行萃取：
    1. 疾病與症狀名稱 (如：紅斑性狼瘡、氣喘、重肌無力症、GVHD等)
    2. 檢驗標記與細胞分子 (如：IgE, CD4, ANA, HLA-B27, 補體, Cytokine等)
    3. 醫學專有名詞與病理機制 (如：遲發性過敏反應、巨噬細胞、ADCC、免疫耐受性等)
    4. 檢驗技術與試劑 (如：ELISA, Flow-Cytometry, 免疫螢光染色, 西方墨點法等)
    
    萃取規則：
    - 中英文名詞皆須包含，盡量挖出所有該單元常考的專有名詞。
    - 絕對不要包含沒有意義的考試用語 (如：下列何者, 正確, 敘述, 選項, 檢驗結果, 解析, 試題, 何者錯誤)。
    
    請「只」回傳一個純 JSON 陣列 (Array of strings)，不要有任何其他的開頭或結尾問候語，也不要包含維度分類，全部放在同一個陣列中。
    範例格式：["關鍵字1", "關鍵字2", "KEYWORD_A", "KEYWORD_B"]
    """
    
    try:
        # 🌟 終極防呆：動態尋找這把鑰匙能用的模型名單
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not available_models:
            return ["API_ERROR: 您的 API Key 無法存取任何生成模型，請確認帳號權限。"]
            
        # 優先挑選 1.5-flash，沒有的話找 1.5-pro，再沒有就抓名單裡第一個能用的！
        target_model_name = available_models[0]
        for m_name in available_models:
            if 'gemini-1.5-flash' in m_name:
                target_model_name = m_name
                break
            elif 'gemini-1.5-pro' in m_name:
                target_model_name = m_name
                
        model = genai.GenerativeModel(target_model_name)
        response = model.generate_content(prompt)
        clean_text = clean_json_response(response.text)
        keywords = json.loads(clean_text)
        return keywords
        
    except Exception as e:
        return [f"API_ERROR: 系統連線或解析失敗 ({str(e)})"]

# ==========================================
# 4. Word 題庫解析與分類引擎 (極速無圖版)
# ==========================================
def parse_docx_for_analysis(uploaded_file, mapping):
    """直接穿透讀取 Word 檔，並依照現有字典自動將文字歸類到各主題"""
    doc = docx.Document(uploaded_file)
    all_lines = []
    
    for block in doc.element.body.iterchildren():
        if block.tag.endswith('p'):
            para = docx.text.paragraph.Paragraph(block, doc)
            for line in re.split(r'[\n\v]', para.text):
                if line.strip(): all_lines.append(line.strip())
        elif block.tag.endswith('tbl'):
            table = docx.table.Table(block, doc)
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        for line in re.split(r'[\n\v]', para.text):
                            if line.strip(): all_lines.append(line.strip())

    topic_pattern = re.compile(r'^(?:【([^】]+)】|(?:\w{2}[:：]\s*)(.+))$')
    q_start_pattern = re.compile(r'^.*?[\(]\s*[A-Ea-e,皆全對送分]+\s*[\)]\s*\d+\s*[.、\s]')
    
    topic_contents = {}
    current_topic = "未分類"
    current_block = ""
    
    for text in all_lines:
        t_match = topic_pattern.match(text)
        if t_match and not q_start_pattern.search(text):
            if current_block.strip():
                if current_topic not in topic_contents: topic_contents[current_topic] = ""
                topic_contents[current_topic] += current_block + "\n"
            current_topic = t_match.group(1) or t_match.group(2)
            current_block = ""
            continue
            
        current_block += text + "\n"
        
        if current_topic == "未分類":
            for top, kws in mapping.items():
                for kw in kws:
                    if kw.lower() in text.lower():
                        current_topic = top
                        break

    if current_block.strip():
        if current_topic not in topic_contents: topic_contents[current_topic] = ""
        topic_contents[current_topic] += current_block + "\n"
        
    return topic_contents

# ==========================================
# 網頁介面開始
# ==========================================
st.set_page_config(page_title="Gemini 聯網題庫分析引擎", page_icon="🧠", layout="wide")

st.title("🧠 Gemini 聯網題庫智慧探勘引擎 (動態防呆版)")
st.write("已內建 API Key！系統將動態偵測可用的 AI 模型，深入閱讀高達 3 萬字的考題，並為您提煉出 30~50 個最豐富的醫學專業關鍵字。")

if GEMINI_API_KEY == "請在這裡貼上您的_API_KEY" or not GEMINI_API_KEY:
    st.error("⚠️ 系統尚未設定 API Key！請先在程式碼第 10 行填入您的 Gemini API Key。")
    st.stop()

st.divider()

col_dict, col_upload = st.columns([1, 1])

with col_dict:
    st.subheader("1️⃣ 確認您目前的字典")
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
    st.subheader("2️⃣ 餵食原始 Word 題庫檔 (.docx)")
    st.caption("直接上傳尚未轉檔的原始 Word 解析檔，系統會自動歸類並分析！")
    uploaded_word = st.file_uploader("選擇 Word 檔案 (.docx)", type=["docx"])

if uploaded_word and st.button("🚀 啟動 Gemini 深度聯網分析", type="primary", use_container_width=True):
    
    with st.spinner("📄 正在穿透讀取 Word 檔案內容..."):
        topic_contents = parse_docx_for_analysis(uploaded_word, current_dict)
    
    if not topic_contents or (len(topic_contents) == 1 and "未分類" in topic_contents):
        st.error("無法將考題歸類到主題中。請確認 Word 檔內有【主題標籤】或您的字典內有足夠的關鍵字。")
        st.stop()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    analysis_result = {}
    topics = [str(t) for t in topic_contents.keys() if str(t) != "未分類" and str(t).strip()]
    
    for i, topic in enumerate(topics):
        status_text.markdown(f"**🔄 正在自動切換並呼叫模型分析：【{topic}】... ({i+1}/{len(topics)})**")
        
        text_to_analyze = topic_contents[topic]
        ai_suggested_keywords = analyze_topic_with_gemini(topic, text_to_analyze, GEMINI_API_KEY)
        analysis_result[topic] = ai_suggested_keywords
        
        progress_bar.progress((i + 1) / len(topics))
        
    status_text.success("✅ Gemini 深度分析完畢！")
    
    st.divider()
    st.subheader("🤖 Gemini 智慧分析結果")
    
    updated_dict = current_dict.copy()
    tabs = st.tabs(list(analysis_result.keys()))
    
    for idx, (topic, ai_words) in enumerate(analysis_result.items()):
        with tabs[idx]:
            st.markdown(f"#### 🏷️ 關於【{topic}】")
            
            if ai_words and str(ai_words[0]).startswith("API_ERROR"):
                st.error(f"連線失敗：{ai_words[0]}")
                continue
                
            existing_words = [w.upper() for w in current_dict.get(topic, [])]
            suggested_new_words = [w for w in ai_words if w.upper() not in existing_words]
            
            if suggested_new_words:
                st.info(f"✨ Gemini 深度閱讀後，為您挖掘出以下 {len(suggested_new_words)} 個豐富的專業關鍵字：")
                
                selected_new = st.multiselect(
                    f"挑選要加入【{topic}】的關鍵字：",
                    options=suggested_new_words,
                    default=suggested_new_words 
                )
                
                if topic not in updated_dict:
                    updated_dict[topic] = []
                
                updated_dict[topic] = list(set(current_dict.get(topic, []) + selected_new))
            else:
                st.success("👍 您的字典已經無懈可擊！Gemini 認為不需要再補充了。")
                
    st.divider()
    st.subheader("3️⃣ 獲取終極 AI 升級版字典")
    st.write("這是融合了 Gemini 智慧判斷後的終極字典，您可以複製貼回轉檔系統的輸入框中，未來的自動分類將會擁有 AI 級的精準度！")
    
    new_dict_json = json.dumps(updated_dict, ensure_ascii=False, indent=4)
    st.code(new_dict_json, language="json")
    
    st.download_button(
        label="💾 下載 AI 升級版字典 (gemini_dict.json)",
        data=new_dict_json,
        file_name="gemini_upgraded_dict.json",
        mime="application/json",
        type="primary",
        use_container_width=True
    )
