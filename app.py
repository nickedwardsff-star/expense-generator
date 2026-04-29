import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime

# --- 1. SESSION STATE SETUP ---
# This acts as a temporary "shopping cart" to hold multiple receipts
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# --- 2. AI EXTRACTION FUNCTION (Simulated) ---
def extract_receipt_data(uploaded_file):
    """
    This is a placeholder. When you are ready, you will replace this with 
    a call to Google Document AI or OpenAI to extract the real data.
    """
    return {
        "Date": datetime.now().strftime("%d/%m/%Y"), 
        "Merchant": "Example Merchant",
        "File Name": uploaded_file.name,
        "Total Amount": 14.50
    }

# --- 3. USER INTERFACE ---
st.set_page_config(page_title="My Expense Form", layout="centered")

st.title("🧾 Personal Expense Generator")
st.write("Process your receipts below. When you're done, download your Excel form to send to Finance.")

# Employee Identification
employee_name = st.text_input("Enter your full name:", placeholder="e.g., Jane Doe")

# File Uploader
uploaded_file = st.file_uploader("Upload a Receipt", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file is not None and employee_name:
    if st.button("Process This Receipt"):
        with st.spinner("AI is analyzing the document..."):
            
            # Extract data and add it to our temporary "shopping cart"
            extracted_data = extract_receipt_data(uploaded_file)
            st.session_state.expenses.append(extracted_data)
            
            st.success(f"Added {uploaded_file.name} to your report!")

# --- 4. DISPLAY AND TEMPLATE DOWNLOAD ---
# Only show this section if there is at least one processed expense
if len(st.session_state.expenses) > 0:
    st.divider()
    st.subheader(f"Current Report for {employee_name}")
    
    # Show the table on the screen for the user to review
    df = pd.DataFrame(st.session_state.expenses)
    st.dataframe(df, use_container_width=True)
    
    # --- The Template Mapping for Farmfoods ---
    try:
        # 1. Load your specific template
        wb = openpyxl.load_workbook("Template_Expenses.xlsx") 
        ws = wb.active 
        
        # 2. Fill in the Header Information (Row 3)
        ws['B3'] = employee_name 
        ws['H3'] = datetime.now().strftime("%d/%m/%Y")
        
        # 3. Loop through the receipts and fill in the rows (Starts Row 6)
        start_row = 6 
        
        for index, expense in enumerate(st.session_state.expenses):
            current_row = start_row + index
            
            # Mapping to your specific Farmfoods columns:
            ws.cell(row=current_row, column=1, value=expense["Date"])         # Col A: Date
            ws.cell(row=current_row, column=2, value=expense["Merchant"])     # Col B: Expenditure
            ws.cell(row=current_row, column=3, value=expense["File Name"])    # Col C: Reason for claim
            ws.cell(row=current_row, column=9, value=expense["Total Amount"]) # Col I: Total
        
        # 4. Save to temporary memory (In-Memory File)
        buffer = io.BytesIO()
        wb.save(buffer)
        
        # Format the file name dynamically
        safe_name = employee_name.replace(" ", "_")
        excel_file_name = f"Expense_Report_{safe_name}.xlsx"
        
        # 5. The Download Button
        st.download_button(
            label="📥 Download Formatted Expense Form",
            data=buffer.getvalue(),
            file_name=excel_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
    except FileNotFoundError:
        st.error("⚠️ Could not find 'Template_Expenses.xlsx'. Please make sure it is saved in the same folder as this script.")
    
    # Clear data button
    if st.button("Clear Data and Start Over"):
        st.session_state.expenses = []
        st.rerun()