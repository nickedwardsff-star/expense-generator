import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime
import json
import base64
from openai import OpenAI
import fitz  # PyMuPDF
import re  # New library to slice the text open!

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
    """The Ultimate Swiss Army Knife to open the AI's envelope, no matter the server version."""
    # Method 1: The standard modern way
    try:
        return response.choices.message.content
    except: pass
    
    # Method 2: The older dictionary way
    try:
        return response['choices']['message']['content']
    except: pass
    
    # Method 3: The Pydantic dump way
    try:
        return response.model_dump()['choices']['message']['content']
    except: pass
    
    # Method 4: The Nuclear Option (Physically slices the JSON out of the raw text)
    raw = str(response)
    match = re.search(r"content='(\{.*?\})', refusal", raw, re.DOTALL)
    if match:
        return match.group(1).replace('\\n', '\n').replace('\\"', '"')
    
    match = re.search(r'content="(\{.*?\})", refusal', raw, re.DOTALL)
    if match:
        return match.group(1).replace('\\n', '\n')
        
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
    
    # We now use our indestructible Swiss Army knife here!
    content = safe_extract_json_from_response(response)
        
    if "```json" in content:
        content = content.split("```json").split("```").strip()
    elif "```" in content:
        content = content.split("```").split("```").strip()
        
    try:
        data = json.loads(content)
    except Exception:
        data = {}
        
    while isinstance(data, list):
        data = data if len(data) > 0 else {}
        
    if isinstance(data, dict) and "Date" not in data:
        for key, value in data.items():
            if isinstance(value, dict) and "Date" in value:
                data = value
                break

    clean_data = {
        "Date": str(data.get("Date") or datetime.now().strftime("%Y-%m-%d")),
        "Vendor": str(data.get("Vendor") or "Unknown Vendor"),
        "File Name": uploaded_file.name,
        "Amount Excl VAT": to_float(data.get("Amount Excl VAT")),
        "VAT": to_float(data.get("VAT")),
        "Total Amount": to_float(data.get("Total Amount")),
        "_raw": content 
    }
    
    return clean_data

# --- 3. HELPER TOOL FOR POUNDS & PENCE ---
def split_pounds_pence(amount):
    formatted_amount = f"{float(amount):.2f}"
    pounds, pence = formatted_amount.split('.')
    return int(pounds), int(pence)

# --- 4. USER INTERFACE ---
st.set_page_config(page_title="My Expense Form", layout="centered")

st.title("🧾 Bulk Expense Generator")
st.write("Upload all your receipts for the month. The AI will read them, sort them by date, and fill out your form.")

employee_name = st.text_input("Enter your full name:", placeholder="e.g., Jane Doe")
uploaded_files = st.file_uploader("Upload Receipts", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)

if uploaded_files and employee_name:
    if st.button(f"Process {len(uploaded_files)} Receipt(s)"):
        with st.spinner("AI is analyzing the documents..."):
            for file in uploaded_files:
                try:
                    extracted_data = extract_receipt_data(file)
                    # We can remove the raw text now since we know it works, but keeping it invisible for safety!
                    extracted_data.pop("_raw", None)
                    st.session_state.expenses.append(extracted_data)
                        
                except Exception as e:
                    st.error(f"Could not process {file.name}. Error: {e}")
                    
            st.success(f"Finished processing!")

# --- 5. DISPLAY AND TEMPLATE DOWNLOAD ---
if len(st.session_state.expenses) > 0:
    st.divider()
    st.subheader(f"Current Report for {employee_name}")
    
    df = pd.DataFrame(st.session_state.expenses)
    df = df.sort_values(by="Date")
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%d/%m/%Y")
    
    st.dataframe(df, use_container_width=True)
    
    try:
        wb = openpyxl.load_workbook("Template_Expenses.xlsx") 
        ws = wb.active 
        
        ws['B3'] = employee_name 
        ws['H3'] = datetime.now().strftime("%d/%m/%Y")
        
        start_row = 6 
        
        for index, expense in enumerate(df.to_dict('records')):
            current_row = start_row + index
            
            ws.cell(row=current_row, column=1, value=expense["Date"])         
            ws.cell(row=current_row, column=2, value=expense["Vendor"])       
            ws.cell(row=current_row, column=3, value=expense["File Name"])    
            
            excl_pounds, excl_pence = split_pounds_pence(expense["Amount Excl VAT"])
            ws.cell(row=current_row, column=5, value=excl_pounds) 
            ws.cell(row=current_row, column=6, value=excl_pence)  
            
            vat_pounds, vat_pence = split_pounds_pence(expense["VAT"])
            ws.cell(row=current_row, column=7, value=vat_pounds)  
            ws.cell(row=current_row, column=8, value=vat_pence)   
            
            total_pounds, total_pence = split_pounds_pence(expense["Total Amount"])
            ws.cell(row=current_row, column=9, value=total_pounds) 
            ws.cell(row=current_row, column=10, value=total_pence) 
        
        buffer = io.BytesIO()
        wb.save(buffer)
        
        safe_name = employee_name.replace(" ", "_")
        excel_file_name = f"Expense_Report_{safe_name}.xlsx"
        
        st.download_button(
            label="📥 Download Formatted Expense Form",
            data=buffer.getvalue(),
            file_name=excel_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
    except FileNotFoundError:
        st.error("⚠️ Could not find 'Template_Expenses.xlsx'. Please make sure it is saved in the same folder as this script.")
    
    if st.button("Clear Data and Start Over"):
        st.session_state.expenses = []
        st.rerun()
