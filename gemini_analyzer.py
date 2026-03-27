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
    """清除 LLM 可能自帶的 Markdown 標記，以確保 JSON 格式正確"""
    text = text.strip()
    if text.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1
http://googleusercontent.com/immersive_entry_chip/2

### 💡 這次的更新亮點：
1. **完全捨棄 Excel**：系統現在可以直接吃您上傳的 `臨床血清免疫學解析.docx` 原始檔！它會借用您轉檔系統中的「穿透表格」技術，直接把題目抓出來餵給 AI。
2. **API Key 內建化**：您只要在程式碼的第 9 行填入那串鑰匙（記得保留前後的雙引號 `""`），以後打開網頁就可以直接按「啟動分析」，再也不用複製貼上密碼了。
3. **無痛相容 Streamlit Cloud**：因為已經不再需要 `openpyxl`，那個惱人的 `ImportError` 徹底消失了！

快去填上 API Key 並上傳一份您的 Word 檔，看看 Gemini 能為您提煉出多麼精準的國考關鍵字吧！
