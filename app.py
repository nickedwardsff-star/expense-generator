import streamlit as st
import pandas as pd
import io
import openpyxl
from openpyxl.styles import Font 
from datetime import datetime
import json
import base64
from openai import OpenAI
import fitz  # PyMuPDF (Our digital stapler!)
import re  

# --- 1. SETUP & AUTHENTICATION ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 2. THE REAL AI EXTRACTION ---
def to_float(val):
    try:
        if isinstance(val, str):
            val = val.replace('£', '').replace('$', '').replace(',', '').strip()
        return float(val)
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

    prompt = """
    You are an expert accountant. Analyze this receipt and extract the data. 
    Return a valid JSON object with EXACTLY these keys:
    - "Date": Format as YYYY-MM-DD.
    - "Vendor": The name of the shop or company.
    - "Amount Excl VAT": The subtotal before tax (number only).
    - "VAT": The tax amount (number only).
    - "Total Amount": The final total paid (number only).
    
    Return ONLY the JSON object, nothing else. Do not use nulls. If a number is missing, use 0.
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
