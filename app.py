import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime
import random 

# --- 1. SESSION STATE SETUP ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# --- 2. AI EXTRACTION FUNCTION (Simulated) ---
def extract_receipt_data(uploaded_file):
    """
    Simulated AI: Generating fake random data to prove the loop and sorting work.
    """
    random_day = random.randint(1, 28)
    random_amount = round(random.uniform(5.00, 100.00), 2)
    vat = round(random_amount * 0.20, 2)
    total = round(random_amount + vat, 2)
    vendors = ["Costa Coffee", "Tesco", "Shell Petrol", "WHSmith", "National Express"]
    
    return {
        "Date": f"2026-04-{random_day:02d}", 
        "Vendor": random.choice(vendors),
        "File Name": uploaded_file.name,
        "Amount Excl VAT": random_amount,
        "VAT": vat,
        "Total Amount": total
    }

# --- 3. HELPER TOOL FOR POUNDS & PENCE ---
def split_pounds_pence(amount):
    """Forces the amount to have 2 decimal places and splits it into two numbers."""
    formatted_amount = f"{float(amount):.2f}"
    parts = formatted_amount.split('.')
    # The grabs the pounds, the grabs the pence
    return int(parts), int(parts)

# --- 4. USER INTERFACE ---
st.set_page_config(page_title="My Expense Form", layout="centered")

st.title("🧾 Bulk Expense Generator")
st.write("Upload all your receipts for the month. The system will sort them by date and fill out your form.")

employee_name = st.text_input("Enter your full name:", placeholder="e.g., Jane Doe")

uploaded_files = st.file_uploader("Upload Receipts", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)

if uploaded_files and employee_name:
    if st.button(f"Process {len(uploaded_files)} Receipt(s)"):
        with st.spinner("AI is analyzing the documents..."):
            
            for file in uploaded_files:
                extracted_data = extract_receipt_data(file)
                st.session_state.expenses.append(extracted_data)
            
            st.success(f"Successfully processed {len(uploaded_files)} receipts!")

# --- 5. DISPLAY AND TEMPLATE DOWNLOAD ---
if len(st.session_state.expenses) > 0:
    st.divider()
    st.subheader(f"Current Report for {employee_name}")
    
    # --- SORTING MAGIC ---
    df = pd.DataFrame(st.session_state.expenses)
    df = df.sort_values(by="Date")
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%d/%m/%Y")
    
    st.dataframe(df, use_container_width=True)
    
    # --- The Template Mapping for Farmfoods ---
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
