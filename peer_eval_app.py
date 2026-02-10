import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import smtplib
import ssl
from email.message import EmailMessage
import random

# --- CONFIGURATION ---
# This must match your Google Sheet Name exactly
GOOGLE_SHEET_NAME = "MECE 2860U Results"
STUDENT_FILE = "students.csv"

# --- TEXT CONTENT (From your Fluid Mechanics Doc) ---
TITLE = "MECE 2860U Fluid Mechanics - Lab Report Peer Review"

CONFIDENTIALITY_TEXT = """
**This is a Self and Peer Review Form for MECE2860U related to Lab Reports 1 to 5.**

**CONFIDENTIALITY:** This evaluation is a secret vote. Please do not base your evaluations on friendship or personality conflicts.
**THESE EVALUATIONS WILL NOT BE PUBLISHED.**

**SUBMISSION DEADLINE:** One week after you attend Lab 5. If you submit late or not at all, it will be interpreted as giving 0% to yourself and 100% to others.
"""

CRITERIA = [
    "Attendance at Meetings",
    "Meeting Deadlines",
    "Quality of Work",
    "Amount of Work",
    "Attitudes & Commitment"
]

# --- GOOGLE SHEETS CONNECTION ---
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
        try:
            all_data = sheet.get_all_records()
            df = pd.DataFrame(all_data)
        except:
            df = pd.DataFrame()

        # Overwrite logic: Remove old submission from this student
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
        st.error(f"Error saving data: {e}")
        return False

# --- EMAIL OTP ---
def send_otp_email(to_email, otp_code):
    try:
        secrets = st.secrets["email"]
        msg = EmailMessage()
        msg.set_content(f"Your Code is: {otp_code}")
        msg["Subject"] = "Peer Eval Login Code"
        msg["From"] = secrets["sender_email"]
        msg["To"] = to_email
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(secrets["smtp_server"], 465, context=context) as server:
            server.login(secrets["sender_email"], secrets["sender_password"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False

# --- MAIN APP ---
st.set_page_config(page_title="MECE 2860U Eval", layout="wide")

# Custom CSS for that "Green/Red" score box you liked
st.markdown("""
<style>
    .score-box {
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 20px;
        margin-top: 25px;
        color: white;
    }
    .score-green { background-color: #28a745; }
    .score-red { background-color: #dc3545; } 
</style>
""", unsafe_allow_html=True)

if 'user' not in st.session_state: st.session_state['user'] = None
if 'otp_code' not in st.session_state: st.session_state['otp_code'] = None

# LOAD STUDENTS
try:
    df_students = pd.read_csv(STUDENT_FILE)
    df_students.columns = df_students.columns.str.strip()
    df_students['Student ID'] = df_students['Student ID'].astype(str)
except:
    st.error(f"Could not load {STUDENT_FILE}")
    st.stop()

# --- LOGIN SCREEN ---
if st.session_state['user'] is None:
    st.title(TITLE)
    names = sorted(df_students['Student Name'].unique().tolist())
    selected_name = st.selectbox("Select your name:", [""] + names)
    
    if st.button("Send Verification Code"):
        if selected_name:
            user_row = df_students[df_students['Student Name'] == selected_name]
            if not user_row.empty:
                email = user_row.iloc[0]['Email']
                code = str(random.randint(100000, 999999))
                st.session_state['otp_code'] = code
                st.session_state['temp_user'] = user_row.iloc[0].to_dict()
                if send_otp_email(email, code):
                    st.success(f"Code sent to {email}")
    
    code_input = st.text_input("Enter 6-digit Code:")
    if st.button("Login"):
        if code_input == st.session_state['otp_code']:
            st.session_state['user'] = st.session_state['temp_user']
            st.rerun()
        else:
            st.error("Invalid Code")

# --- EVALUATION FORM ---
else:
    user = st.session_state['user']
    st.title(TITLE)
    st.markdown(CONFIDENTIALITY_TEXT)
    
    # Logout Button
    col1, col2 = st.columns([8,1])
    with col1: st.info(f"Logged in as: **{user['Student Name']}** (Group {user['Group #']})")
    with col2: 
        if st.button("Logout"):
            st.session_state['user'] = None
            st.rerun()
            
    group_members = df_students[df_students['Group #'] == user['Group #']]
    submission_data = []
    
    st.write("---")
    
    # Loop through group members
    for idx, member in group_members.iterrows():
        st.subheader(f"Evaluating: {member['Student Name']}")
        if member['Student Name'] == user['Student Name']:
            st.caption("(Self-Evaluation)")

        # Create columns for criteria
        cols = st.columns(len(CRITERIA) + 1)
        member_scores = []
        
        for i, criterion in enumerate(CRITERIA):
            with cols[i]:
                # Unique key for every input
                score = st.number_input(
                    criterion, 
                    min_value=0, max_value=100, value=100, step=5, 
                    key=f"{member['Student ID']}_{i}"
                )
                if score < 80:
                    st.markdown(":red[⚠️ **< 80%**]")
                member_scores.append(score)
        
        # Calculate Average
        avg = sum(member_scores) / len(member_scores) if member_scores else 0
        
        # The Colorful Score Box
        with cols[-1]:
            color_class = "score-green" if avg >= 80 else "score-red"
            st.markdown(f"""
                <div class="score-box {color_class}">
                    OVERALL<br>{avg:.1f}%
                </div>
            """, unsafe_allow_html=True)
        
        # Prepare data for saving
        row = {
            "Evaluator": user['Student Name'],
            "Evaluator ID": str(user['Student ID']),
            "Group": user['Group #'],
            "Peer Name": member['Student Name'],
            "Peer ID": str(member['Student ID']),
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Overall Score": avg,
            "Comments": st.text_input(f"Comments for {member['Student Name']}:", key=f"comm_{member['Student ID']}")
        }
        # Add individual scores to the row
        for i, cr in enumerate(CRITERIA): row[cr] = member_scores[i]
        submission_data.append(row)
        st.markdown("---")

    # Submit Button
    if st.button("Submit Evaluation", type="primary"):
        with st.spinner("Saving..."):
            if save_to_google_sheets(user['Student ID'], submission_data):
                st.success("Saved successfully!")
                st.balloons()