import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import random
import time

# --- 1. CONFIGURATION ---
GOOGLE_SHEET_NAME = "MECE2860U Results" # Make sure this matches your Sheet Name
STUDENT_FILE = "students.csv"

# --- 2. TEXT CONTENT (RESTORED) ---
TITLE = "MECE 2860U Fluid Mechanics - Lab Report Peer Review"

CONFIDENTIALITY_TEXT = """
**This is a Self and Peer Review Form for MECE2860U related to Lab Reports 1 to 5.**

**CONFIDENTIALITY:** This evaluation is a secret vote. Don’t show your vote to others, nor try to see or discuss others’ and your votes. Please do not base your evaluations on friendship or personality conflicts. Your input is a valuable indicator to help assess contributions in a fair manner.

**THESE EVALUATIONS WILL NOT BE PUBLISHED; YOUR IDENTITY WILL BE KEPT STRICTLY CONFIDENTIAL AND WILL NOT BE REVEALED IN ANY CIRCUMSTANCES.**

**SUBMISSION DEADLINE:** The peer evaluation should be submitted within one week after you attend Lab 5. No late submission of this form will be acceptable. If you submit this form late or do not submit it at all, that will be interpreted like you want to give 0% to yourself and 100% to all other team members.

**INSTRUCTIONS:** Please evaluate the contributions of your team members, including yourself, based on each member’s performance over the semester. Give 0% (Did not contribute anything) to 100% (Very good job).
"""

CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- 3. GOOGLE SHEETS CONNECTION ---
def get_google_sheet_connection():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets not found!")
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
        
        # 1. Get existing data safely
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame()

        # 2. Filter out old submissions from this user (Overwrite logic)
        if not df.empty and 'Evaluator ID' in df.columns:
            df['Evaluator ID'] = df['Evaluator ID'].astype(str)
            df = df[df['Evaluator ID'] != str(current_user_id)]
        
        # 3. Combine with new data
        new_df = pd.DataFrame(new_rows)
        final_df = pd.concat([df, new_df], ignore_index=True)
        
        # 4. Clear and Write
        sheet.clear()
        
        # We use a robust way to write data that catches the "200" error
        data = [final_df.columns.tolist()] + final_df.values.tolist()
        sheet.update(range_name='A1', values=data)
        
        return True

    except Exception as e:
        # ⚠️ CRITICAL FIX: If the error message contains "200", it is actually a success.
        if "200" in str(e):
            return True
        st.error(f"Error saving data: {e}")
        return False

# --- 4. EMAIL FUNCTION ---
def send_otp_email(to_email, otp_code):
    try:
        secrets = st.secrets["email"]
        msg = EmailMessage()
        msg.set_content(f"Your Code is: {otp_code}")
        msg["Subject"] = "Peer Eval Code"
        msg["From"] = secrets["sender_email"]
        msg["To"] = to_email
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(secrets["smtp_server"], 465, context=context) as server:
            server.login(secrets["sender_email"], secrets["sender_password"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email Failed: {e}")
        return False

# --- 5. MAIN APP UI ---
st.set_page_config(page_title="MECE 2860U Eval", layout="wide")

st.markdown("""
<style>
    .score-box { padding: 10px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 20px; color: white; margin-top: 25px; }
    .score-green { background-color: #28a745; }
    .score-red { background-color: #dc3545; } 
</style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state['user'] = None
if 'otp_code' not in st.session_state: st.session_state['otp_code'] = None

# LOAD DATA
try:
    df_students = pd.read_csv(STUDENT_FILE)
    df_students.columns = df_students.columns.str.strip()
    df_students['Student ID'] = df_students['Student ID'].astype(str)
except:
    st.error(f"Could not load {STUDENT_FILE}")
    st.stop()

# --- LOGIN ---
if st.session_state['user'] is None:
    st.title(TITLE)
    names = sorted(df_students['Student Name'].unique().tolist())
    selected_name = st.selectbox("Select your name:", [""] + names)
    
    if st.button("Send Code"):
        if selected_name:
            user_row = df_students[df_students['Student Name'] == selected_name]
            email = user_row.iloc[0]['Email']
            code = str(random.randint(100000, 999999))
            st.session_state['otp_code'] = code
            st.session_state['temp_user'] = user_row.iloc[0].to_dict()
            
            with st.spinner("Sending email..."):
                if send_otp_email(email, code):
                    st.success(f"Code sent to {email}")
                else:
                    st.error("Email failed. Check your Streamlit Secrets.")

    code_input = st.text_input("Enter Code:")
    if st.button("Login"):
        if code_input == st.session_state['otp_code']:
            st.session_state['user'] = st.session_state['temp_user']
            st.rerun()
        else:
            st.error("Invalid Code")

# --- EVALUATION ---
else:
    user = st.session_state['user']
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    
    col1, col2 = st.columns([8,1])
    with col1: st.info(f"Logged in as: **{user['Student Name']}** (Group {user['Group #']})")
    with col2: 
        if st.button("Logout"):
            st.session_state['user'] = None
            st.rerun()
            
    group_members = df_students[df_students['Group #'] == user['Group #']]
    submission_data = []
    
    st.divider()
    
    for idx, member in group_members.iterrows():
        st.subheader(f"Evaluating: {member['Student Name']}")
        if member['Student Name'] == user['Student Name']:
            st.caption("(Self-Evaluation)")

        cols = st.columns(len(CRITERIA) + 1)
        scores = []
        
        for i, criterion in enumerate(CRITERIA):
            with cols[i]:
                s = st.number_input(criterion, 0, 100, 100, step=5, key=f"{member['Student ID']}_{i}")
                if s < 80: st.caption(":red[Low Score]")
                scores.append(s)
        
        avg = sum(scores) / len(scores) if scores else 0
        
        with cols[-1]:
            color = "score-green" if avg >= 80 else "score-red"
            st.markdown(f'<div class="score-box {color}">OVERALL<br>{avg:.1f}%</div>', unsafe_allow_html=True)
            
        submission_data.append({
            "Evaluator": user['Student Name'],
            "Evaluator ID": str(user['Student ID']),
            "Group": user['Group #'],
            "Peer Name": member['Student Name'],
            "Peer ID": str(member['Student ID']),
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Overall Score": avg,
            "Details": str(scores),
            "Comments": st.text_input(f"Comments for {member['Student Name']}:", key=f"c_{member['Student ID']}")
        })
        st.divider()

    if st.button("Submit Evaluation", type="primary"):
        with st.spinner("Saving to Google Sheets..."):
            if save_to_google_sheets(user['Student ID'], submission_data):
                st.success("✅ Saved Successfully!")
                time.sleep(2)
                st.balloons()