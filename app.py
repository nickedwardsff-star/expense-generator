import streamlit as st
import pandas as pd
import io
import openpyxl
from openpyxl.styles import Font 
from datetime import datetime
import json
import base64
from openai import OpenAI
import fitz  
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
    try: 
        return response.choices.message.content
    except: 
        pass
        
    try: 
        return response['choices']['message']['content']
    except: 
        pass
        
    try: 
        return response.model_dump()['choices']['message']['content']
    except: 
        pass
    
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

    prompt = (
        "You are an expert accountant. Analyze this receipt and extract the data. "
        "Return a valid JSON object with EXACTLY these keys: "
        "'Date': Format as YYYY-MM-DD. "
        "'Vendor': The name of the shop or company. "
        "'Reason': A short, 2-4 word reason/category for the expense based on what was purchased (e.g. 'Staff Lunch', 'Parking', 'Office Supplies'). "
        "'Amount Excl VAT': The subtotal before tax (number only). "
        "'VAT': The tax amount (number only). "
        "'Total Amount': The final total paid (number only). "
        "Return ONLY the JSON object. Do not use nulls. If a number is missing, use 0."
    )
    
    if len(extracted_text) >= 20:
        messages_payload = [
            {"type": "text", "text": prompt},
            {"type": "text", "text": "Receipt Text:\n" + extracted_text}
        ]
    else:
        messages_payload = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64_image, "detail": "high"}}
        ]
        
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[{"role": "user", "content": messages_payload}]
    )
    
    content = safe_extract_json_from_response(response)
        
    bticks = chr(96) * 3
    json_marker = bticks + "json"
    
    if json_marker in content: 
        content = content.split(json_marker).split(bticks).strip()
    elif bticks in content: 
        content = content.split(bticks).split(bticks).strip()
        
    try: 
        data = json.loads(content)
    except Exception: 
        data = {}
        
    while isinstance(data, list): 
        if len(data) > 0:
            data = data
        else:
            data = {}
        
    if isinstance(data, dict) and "Date" not in data:
        for key, value in data.items():
            if isinstance(value, dict) and "Date" in value:
                data = value
                break

    clean_data = {
        "Date": str(data.get("Date") or datetime.now().strftime("%Y-%m-%d")),
        "Vendor": str(data.get("Vendor") or "Unknown Vendor"),
        "Reason": str(data.get("Reason") or "General Expense"),
        "File Name": uploaded_file.name,
        "Amount Excl VAT": to_float(data.get("Amount Excl VAT")),
        "VAT": to_float(data.get("VAT")),
        "Total Amount": to_float(data.get("Total Amount"))
    }
    
    return clean_data

# --- 3. USER INTERFACE ---
st.title("🛒 Farmfoods Expense Generator")
st.write("Upload your receipts. The AI will read them, sort them, assign audit references, and build your submission pack.")

employee_name = st.text_input("Enter your full name:", placeholder="e.g., Jane Doe")
uploaded_files = st.file_uploader("Upload Receipts", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)

if uploaded_files and employee_name:
    if st.button("Process " + str(len(uploaded_files)) + " Receipt(s)"):
        with st.spinner("AI is analyzing the documents..."):
            for file in uploaded_files:
                try:
                    extracted_data = extract_receipt_data(file)
                    st.session_state.expenses.append(extracted_data)
                except Exception as e:
                    st.error("Could not process " + file.name + ". Error: " + str(e))
                    
            st.success("Finished processing!")

# --- 4. DISPLAY AND TEMPLATE DOWNLOAD ---
if len(st.session_state.expenses) > 0:
    st.divider()
    st.subheader("Current Report for " + employee_name)
    
    # 1. Sort the data chronologically and assign Reference IDs
    df = pd.DataFrame(st.session_state.expenses)
    df = df.sort_values(by="Date").reset_index(drop=True)
    df["Reference"] = [str(i) for i in range(1, len(df) + 1)] 
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%d/%m/%Y")
    
    # Show the table on screen (Keeping reference separate visually for the user)
    display_cols = ["Reference", "Date", "Vendor", "Reason", "Amount Excl VAT", "VAT", "Total Amount"]
    st.dataframe(df[display_cols], use_container_width=True)
    
    try:
        # 2. Build the Excel File
        wb = openpyxl.load_workbook("Template_Expenses.xlsx") 
        ws = wb.active 
        
        ws['B3'] = employee_name 
        ws['H3'] = datetime.now().strftime("%d/%m/%Y")
        
        start_row = 6 
        
        for index, row in df.iterrows():
            current_row = start_row + index
            
            # --- THE FIX: Stitching the Reference into the Vendor name ---
            audited_vendor = "REF " + str(row["Reference"]) + " - " + str(row["Vendor"])
            
            ws.cell(row=current_row, column=1, value=row["Date"])       
            ws.cell(row=current_row, column=2, value=audited_vendor)    
            ws.cell(row=current_row, column=3, value=row["Reason"])    
            ws.cell(row=current_row, column=4, value=row["Amount Excl VAT"]) 
            ws.cell(row=current_row, column=5, value=row["VAT"])  
            ws.cell(row=current_row, column=6, value=row["Total Amount"]) 
            
        # Grand Totals Row (Shifted columns to match the new 6-column layout)
        totals_row = start_row + len(df) + 1 
        bold_font = Font(bold=True)
        
        ws.cell(row=totals_row, column=3, value="GRAND TOTAL").font = bold_font
        ws.cell(row=totals_row, column=4, value=df["Amount Excl VAT"].sum()).font = bold_font
        ws.cell(row=totals_row, column=5, value=df["VAT"].sum()).font = bold_font
        ws.cell(row=totals_row, column=6, value=df["Total Amount"].sum()).font = bold_font
        
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        
        # 3. Build the Master PDF pack with Audit Stamps!
        master_pdf = fitz.open() 
        
        for index, row in df.iterrows():
            filename = row["File Name"]
            ref_id = row["Reference"]
            
            file_obj = next((f for f in uploaded_files if f.name == filename), None)
            if file_obj:
                ext = file_obj.name.split('.')[-1].lower()
                try:
                    if ext == 'pdf':
                        temp_doc = fitz.open(stream=file_obj.getvalue(), filetype="pdf")
                    elif ext in ['jpg', 'jpeg', 'png']:
                        img_doc = fitz.open(stream=file_obj.getvalue(), filetype=ext)
                        pdf_bytes = img_doc.convert_to_pdf()
                        temp_doc = fitz.open("pdf", pdf_bytes)
                    else:
                        continue
                        
                    for page in temp_doc:
                        rect = fitz.Rect(20, 20, 100, 50) 
                        page.draw_rect(rect, color=(0.85, 0.16, 0.11), fill=(0.85, 0.16, 0.11))
                        page.insert_textbox(rect, "REF: " + str(ref_id), fontsize=14, color=(1, 1, 1), fontname="helv", align=1)
                        
                    master_pdf.insert_pdf(temp_doc)
                except Exception as e:
                    st.warning("Could not stitch " + filename + " into the pack. Error: " + str(e))
                    
        pdf_bytes = master_pdf.tobytes()
        
        # 4. Create the dual download buttons
        safe_name = employee_name.replace(" ", "_")
        
        st.write("### Download Your Audited Files")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📊 Download Excel Spreadsheet",
                data=excel_buffer.getvalue(),
                file_name="Farmfoods_Expense_Report_" + safe_name + ".xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
            
        with col2:
            st.download_button(
                label="📑 Download Audited Receipt Pack",
                data=pdf_bytes,
                file_name="Farmfoods_Audited_Receipts_" + safe_name + ".pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        
    except FileNotFoundError:
        st.error("⚠️ Could not find 'Template_Expenses.xlsx'. Please make sure it is saved in the same folder as this script.")
    
    st.divider()
    if st.button("Clear Data and Start Over"):
        st.session_state.expenses = []
        st.rerun()
