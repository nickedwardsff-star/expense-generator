import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime
import random # Added for the temporary random data generator

# --- 1. SESSION STATE SETUP ---
# This acts as a temporary "shopping cart" to hold multiple receipts
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# --- 2. AI EXTRACTION FUNCTION (Simulated) ---
def extract_receipt_data(uploaded_file):
    """
    Simulated AI: Generating fake random data to prove the loop and sorting work.
    In the future, replace this with a call to OpenAI or Google Document AI.
    """
    random_day = random.randint(1, 28)
    random_amount = round(random.uniform(5.00, 100.00), 2)
    vat = round(random_amount * 0.20, 2)
    total = round(random_amount + vat, 2)
    vendors = ["Costa Coffee", "Tesco", "Shell Petrol", "WHSmith", "National Express"]
    
    # We use YYYY-MM-DD here temporarily so the computer can sort it chronologically
    return {
        "Date": f"2026-04-{random_day:02d}", 
        "Vendor": random.choice(vendors),
        "File Name": uploaded_file.name,
        "Amount Excl VAT": random_amount,
        "VAT": vat,
        "Total Amount": total
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
            
            ## 3. Loop through the receipts and fill in the rows
        start_row = 6 
        
        # --- NEW HELPER TOOL ---
        def split_pounds_pence(amount):
            # Forces the amount to have exactly 2 decimal places (e.g., "14.50")
            formatted_amount = f"{float(amount):.2f}"
            # Splits the text at the full stop
            parts = formatted_amount.split('.')
            # Returns the two parts as whole numbers: (Pounds, Pence)
            return int(parts), int(parts)

        # We loop through our newly sorted DataFrame
        for index, expense in enumerate(df.to_dict('records')):
            current_row = start_row + index
            
            ws.cell(row=current_row, column=1, value=expense["Date"])         
            ws.cell(row=current_row, column=2, value=expense["Vendor"])       
            ws.cell(row=current_row, column=3, value=expense["File Name"])    
            
            # --- THE POUNDS & PENCE SPLIT ---
            # 1. Split the Total Amount
            total_pounds, total_pence = split_pounds_pence(expense["Total Amount"])
            
            # 2. Write them to separate columns 
            # (Change column=9 and column=10 to match wherever they actually live in your template!)
            ws.cell(row=current_row, column=9, value=total_pounds) # E.g., Col I: Total Pounds
            ws.cell(row=current_row, column=10, value=total_pence) # E.g., Col J: Total Pence
            
            # You can also do the exact same thing for the VAT and Excl VAT!
            vat_pounds, vat_pence = split_pounds_pence(expense["VAT"])
            ws.cell(row=current_row, column=7, value=vat_pounds)  # E.g., Col G: VAT Pounds
            ws.cell(row=current_row, column=8, value=vat_pence)   # E.g., Col H: VAT Pence
            
            excl_pounds, excl_pence = split_pounds_pence(expense["Amount Excl VAT"])
            ws.cell(row=current_row, column=5, value=excl_pounds) # E.g., Col E: Excl Pounds
            ws.cell(row=current_row, column=6, value=excl_pence)  # E.g., Col F: Excl Pence

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
