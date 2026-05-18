import streamlit as st
import pandas as pd
import io
import openpyxl
from openpyxl.styles import Font 
from datetime import datetime
import json
import base64
from openai import OpenAI
import fitz  # PyMuPDF
import re  

# --- 0. FARMFOODS BRANDING & PAGE CONFIG ---
st.set_page_config(page_title="Farmfoods Expenses", page_icon="🛒", layout="wide") 

st.markdown("""
    <style>
        .stApp { background-color: #f9fbf9; }
        h1, h2, h3 { color: #007a33 !important; font-weight: 800 !important; }
        .stButton>button, .stDownloadButton>button {
            background-color: #007a33 !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: bold !important;
            transition: all 0.3s ease !important;
        }
        .stButton>button:hover, .stDownloadButton>button:hover {
            background-color: #da291c !important;
            color: white !important;
            transform: scale(1.02);
        }
        .stFileUploader {
            border: 2px dashed #007a33 !important;
            border-radius: 10px !important;
            padding: 10px !important;
            background-color: #ffffff;
        }
    </style>
""", unsafe_allow_html=True)

# --- 1. SETUP & AUTHENTICATION ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 2. THE REAL AI EXTRACTION ---
def to_float(val):
    try:
        if isinstance(val, str):
            val = val.replace('£', '').replace('$', '').replace(',', '').strip()
        return round(float(val), 2)
    except:
        return 0.00

def safe_extract_json_from_response(response):
    try: return response.choices.message.content
    except: pass
    try: return response['choices']['message']['content']
    except: pass
    try: return response.model_dump()['choices']['message']['content']
    except: pass
    
    raw = str(response)
    match = re.search(r"content='(\{.*?\})', refusal", raw, re.DOTALL)
    if match: return match.group(1).replace('\\n', '\n').replace('\\"', '"')
    match = re.search(r'content="(\{.*?\})", refusal', raw, re.DOTALL)
    if match: return match.group(1).replace('\\n', '\n')
    return "{}"

def extract_receipt_data(uploaded_file):
    extracted_text = ""
    base64_image = None
    
    if uploaded_file.type == 'application/pdf':
        doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
        page = doc.load_page(0) 
        extracted_text = page.get_text().strip()
        
        if len(extracted_text) < 20:
            zoom_matrix = fitz.Matrix(2, 2) 
            pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
            base64_image = base64.b64encode(pix.tobytes("png")).decode('utf-8')
    else:
        base64_image = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

    # NEW: Added "Reason" to the prompt instructions!
    prompt = """
    You are an expert accountant. Analyze this receipt and extract the data. 
    Return a valid JSON object with EXACTLY these keys:
    - "Date": Format as YYYY-MM-DD.
    - "Vendor": The name of the shop or company.
    - "Reason": A short, 2-4 word reason/category for the expense based on what was purchased (e.g. 'Staff Lunch', 'Parking', 'Office Supplies').
    - "Amount Excl VAT": The subtotal before tax (number only).
    - "VAT": The tax amount (number only).
    - "Total Amount": The final total paid (number only).
    
    Return ONLY the JSON object. Do not use nulls. If a number is missing, use 0.
    """
    
    if len(extracted_text) >= 20:
        messages_payload = [
            {"type": "text", "text": prompt},
            {"type": "text", "text": f"Receipt Text:\n{extracted_text}"}
        ]
    else:
        messages_payload = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}", "detail": "high"}}
        ]
        
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[{"role": "user", "content": messages_payload}]
    )
    
    content = safe_extract_json_from_response(response)
        
    if "
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

Save your changes on GitHub, reboot the app on Streamlit, and upload a few test files. When you open the generated PDF, you'll see a pristine, Farmfoods-red reference stamp sitting squarely in the top-left corner of every single receipt!
