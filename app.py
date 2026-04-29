import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime

# --- 1. SESSION STATE SETUP ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# --- 2. AI EXTRACTION FUNCTION (Simulated) ---
def extract_receipt_data(uploaded_file):
    """
    Simulated AI: In the future, this is where you ask the real AI to 
    specifically extract the Vendor, Subtotal, Tax, and Total.
    """
    # We use YYYY-MM-DD here temporarily so the computer can sort it alphabetically
    return {
        "Date": "2026-04-15", # Example date for sorting
        "Vendor": "Example Vendor Ltd",
        "File Name": uploaded_file.name,
        "Amount Excl VAT": 12.08,
        "VAT": 2.42,
        "Total Amount": 14.50
    }

# --- 3. USER INTERFACE ---
st.set_page_config(page_title="My Expense Form", layout="centered")

st.title("🧾 Bulk Expense Generator")
st.write("Upload all your receipts for the month. The system will sort them by date and fill out your form.")

# Employee Identification
employee_name = st.text_input("Enter your full name:", placeholder="e.g., Jane Doe")

# File Uploader - UPGRADED TO MULTIPLE FILES
uploaded_files = st.file_uploader("Upload Receipts", type=['png', 'jpg', 'jpeg', 'pdf'], accept_multiple_files=True)

if uploaded_files and employee_name:
    # Changed button text to reflect multiple files
    if st.button(f"Process {len(uploaded_files)} Receipt(s)"):
        with st.spinner("AI is analyzing the documents..."):
            
            # Loop through every file you uploaded
            for file in uploaded_files:
                extracted_data = extract_receipt_data(file)
                st.session_state.expenses.append(extracted_data)
            
            st.success(f"Successfully processed {len(uploaded_files)} receipts!")

# --- 4. DISPLAY AND TEMPLATE DOWNLOAD ---
if len(st.session_state.expenses) > 0:
    st.divider()
    st.subheader(f"Current Report for {employee_name}")
    
    # --- SORTING MAGIC ---
    # Convert shopping cart to a DataFrame
    df = pd.DataFrame(st.session_state.expenses)
    # Sort chronologically by the Date column
    df = df.sort_values(by="Date")
    # Change the date format back to UK standard (DD/MM/YYYY) for the display and Excel
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%d/%m/%Y")
    
    # Show the sorted table on the screen
    st.dataframe(df, use_container_width=True)
    
    # --- The Template Mapping for Farmfoods ---
    try:
        wb = openpyxl.load_workbook("Template_Expenses.xlsx") 
        ws = wb.active 
        
        # Header Information
        ws['B3'] = employee_name 
        ws['H3'] = datetime.now().strftime("%d/%m/%Y")
        
        start_row = 6 
        
        # We loop through our newly sorted DataFrame instead of the raw session state
        for index, expense in enumerate(df.to_dict('records')):
            current_row = start_row + index
            
            # UPGRADED MAPPING: Includes Vendor, Excl VAT, and VAT
            ws.cell(row=current_row, column=1, value=expense["Date"])            # Col A: Date
            ws.cell(row=current_row, column=2, value=expense["Vendor"])          # Col B: Expenditure (Vendor)
            ws.cell(row=current_row, column=3, value=expense["File Name"])       # Col C: Reason for claim
            ws.cell(row=current_row, column=5, value=expense["Amount Excl VAT"]) # Col E: Amount Excl VAT
            ws.cell(row=current_row, column=7, value=expense["VAT"])             # Col G: VAT
            ws.cell(row=current_row, column=9, value=expense["Total Amount"])    # Col I: Total
        
        buffer = io.BytesIO()
        wb.save(buffer)
        
        safe_name = employee_name.replace(" ", "_")
        excel_file_name = f"Expense_Report_{safe_name}.xlsx"
        
        # Download Button
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
