import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import smtplib
import ssl
from email.message import EmailMessage
import random

# --- CONFIGURATION FOR NEW COURSE ---
STUDENT_FILE = "students.csv"
GOOGLE_SHEET_NAME = "MECE2860U Results"  # <--- Make sure you name your Google Sheet exactly this
TITLE = "MECE2860U Fluid Mechanics - Lab Report Peer Review"

# --- UPDATED TEXT FROM YOUR DOCX ---
CONFIDENTIALITY_TEXT = """
**This is a Self and Peer Review Form for MECE2860U related to Lab Reports 1 to 5.**

**CONFIDENTIALITY:** This evaluation is a secret vote. Don’t show your vote to others, nor try to see or discuss others’ and your votes. Please do not base your evaluations on friendship or personality conflicts. Your input is a valuable indicator to help assess contributions in a fair manner.

**THESE EVALUATIONS WILL NOT BE PUBLISHED; YOUR IDENTITY WILL BE KEPT STRICTLY CONFIDENTIAL.**

**SUBMISSION DEADLINE:** The peer evaluation should be submitted within one week after you attend Lab 5. No late submission of this form will be acceptable. If you submit this form late or do not submit it at all, that will be interpreted like you want to give 0% to yourself and 100% to all other team members.

**INSTRUCTIONS:** Please evaluate the contributions of your team members, including yourself, based on each member’s performance over the semester. Give 0% (Did not contribute anything) to 100% (Very good job).
"""

# I kept the standard criteria to help calculate the grade, 
# but you can delete items from this list if you want simpler grading.
CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- GOOGLE SHEETS & EMAIL SETUP ---
# (This section is identical to your previous working app)
def get_google_sheet_connection():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets not found! Check your .streamlit/secrets.toml file.")
            return None
        s_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(s_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

def save_to_google_sheets(current_user_id, new_rows):
    gc = get_google_sheet_connection()
    if not gc: return False
    try:
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame()

        # Remove previous submission from this student if it exists
        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([df, new_df], ignore_index=True)
        
        sheet.clear()
        if not final_df.empty:
            sheet.append_row(final_df.columns.tolist())
            sheet.append_rows(final_df.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")
        st.error(f"Make sure you created a Sheet named '{GOOGLE_SHEET_NAME}' and shared it with the bot email.")
        return False

# --- EMAIL OTP FUNCTION ---
def send_otp_email(to_email, otp_code):
    try:
        secrets = st.secrets["email"]
        msg = EmailMessage()
        msg.set_content(f"Your Code is: {otp_code}")
        msg["Subject"] = "Peer Eval Code"
        msg["From"] = secrets["sender_email"]
        msg["To"] = to_email
        
        context = ssl.create_default_context()
        if secrets["smtp_port"] == 465:
            with smtplib.SMTP_SSL(secrets["smtp_server"], secrets["smtp_port"], context=context) as server:
                server.login(secrets["sender_email"], secrets["sender_password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(secrets["smtp_server"], secrets["smtp_port"]) as server:
                server.starttls(context=context)
                server.login(secrets["sender_email"], secrets["sender_password"])
                server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False

# --- MAIN APP UI ---
st.set_page_config(page_title="MECE2860U Peer Eval", layout="wide")
if 'user' not in st.session_state: st.session_state['user'] = None
if 'otp_code' not in st.session_state: st.session_state['otp_code'] = None

# LOAD STUDENTS
try:
    df_students = pd.read_csv(STUDENT_FILE)
    df_students.columns = df_students.columns.str.strip()
    df_students['Student ID'] = df_students['Student ID'].astype(str)
except:
    st.error(f"Could not load {STUDENT_FILE}. Make sure it exists!")
    st.stop()

# LOGIN SCREEN
if st.session_state['user'] is None:
    st.title(TITLE)
    names = sorted(df_students['Student Name'].unique().tolist())
    selected_name = st.selectbox("Select your name:", [""] + names)
    
    if st.button("Send Login Code"):
        user_row = df_students[df_students['Student Name'] == selected_name]
        if not user_row.empty:
            email = user_row.iloc[0]['Email']
            code = str(random.randint(1000,9999))
            st.session_state['otp_code'] = code
            st.session_state['temp_user'] = user_row.iloc[0].to_dict()
            if send_otp_email(email, code):
                st.success(f"Code sent to {email}")
    
    code_input = st.text_input("Enter Code:")
    if st.button("Login"):
        if code_input == st.session_state['otp_code']:
            st.session_state['user'] = st.session_state['temp_user']
            st.rerun()
        else:
            st.error("Wrong Code")

# EVALUATION SCREEN
else:
    user = st.session_state['user']
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    st.info(f"Welcome, {user['Student Name']} (Group {user['Group #']})")
    
    group_members = df_students[df_students['Group #'] == user['Group #']]
    submission_data = []

    with st.form("eval_form"):
        for _, member in group_members.iterrows():
            st.write(f"### Evaluating: {member['Student Name']}")
            cols = st.columns(len(CRITERIA))
            scores = []
            for i, crit in enumerate(CRITERIA):
                val = cols[i].number_input(crit, 0, 100, 100, key=f"{member['Student ID']}_{i}")
                scores.append(val)
            
            avg_score = sum(scores)/len(scores)
            st.caption(f"Average: {avg_score}%")
            
            submission_data.append({
                "Evaluator": user['Student Name'],
                "Evaluator ID": str(user['Student ID']),
                "Peer Name": member['Student Name'],
                "Peer ID": str(member['Student ID']),
                "Group": user['Group #'],
                "Overall Score": avg_score,
                "Comments": st.text_input(f"Comments for {member['Student Name']}:")
            })
            st.markdown("---")
        
        if st.form_submit_button("Submit Evaluation"):
            if save_to_google_sheets(user['Student ID'], submission_data):
                st.success("Submitted successfully!")
                st.balloons()