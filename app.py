import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime
import json
import base64
from openai import OpenAI
import fitz  # This is PyMuPDF (Reads your PDFs)

# --- 1. SETUP & AUTHENTICATION ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# Securely grab the API key from Streamlit Secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 2. THE REAL AI EXTRACTION ---
def file_to_base64_image(uploaded_file):
    """Converts images or PDFs into the format OpenAI needs to 'see' them."""
    if uploaded_file.type == 'application/pdf':
        # Open the PDF and take a picture of the first page
        doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
        page = doc.load_page(0) 
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        return base64.b64encode(img_bytes).decode('utf-8')
    else:
        # If it's already an image (jpg/png), just encode it
        return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def extract_receipt_data(uploaded_file):
    """Sends the document to GPT-4o and asks for specific financial data."""
    base64_image = file_to_base64_image(uploaded_file)
    
    prompt = """
    You are an expert accountant. Analyze this receipt and extract the data. 
    Return a valid JSON object with EXACTLY these keys:
    - "Date": Format as YYYY-MM-DD.
    - "Vendor": The name of the shop or company.
    - "Amount Excl VAT": The subtotal before tax (number only, e.g. 12.50).
    - "VAT": The tax amount (number only, e.g. 2.50).
    - "Total Amount": The final total paid (number only, e.g. 15.00).
    
    If VAT is not shown, calculate it (assume UK standard 20% if applicable, or put 0 if it's 0). 
    Return ONLY the JSON object, nothing else.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={ "type": "json_object" },
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    }
                ]
            }
        ]
    )
    
    # Read the AI's response and turn it into a Python dictionary
    extracted_data = json.loads(response.choices.message.content)
    
    # Add the file name manually so we have the reference
    extracted_data["File Name"] = uploaded_file.name
    
    return extracted_data

# --- 3. HELPER TOOL FOR POUNDS & PENCE ---
def split_pounds_pence(amount):
    """Forces the amount to have 2 decimal places and splits it without brackets."""
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
        with st.spinner("AI is analyzing the documents (this takes a few seconds per receipt)..."):
            for file in uploaded_files:
                try:
                    extracted_data = extract_receipt_data(file)
                    st.session_state.expenses.append(extracted_data)
                except Exception as e:
                    st.error(f"Could not process {file.name}. Error: {e}")
                    
            st.success(f"Successfully processed {len(uploaded_files)} receipts!")

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
