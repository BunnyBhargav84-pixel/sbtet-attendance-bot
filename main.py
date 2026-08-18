import os
import json
import time
# UPDATED: IMPORTED RANDOM MODULE TO GENERATE HUMAN-LIKE NETWORK JITTER
import random
import base64
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# --- STEP 1: INITIALIZE SECURE GMAIL API ENGINE ---
print("Initializing Gmail API Client...")
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
token_raw = os.environ.get('GMAIL_TOKEN_JSON')

if not token_raw:
    print("Critical Error: GMAIL_TOKEN_JSON secret is missing from environment variables!")
    students = []
    service = None
else:
    try:
        creds_dict = json.loads(token_raw)
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            print("Access token expired. Refreshing securely via credentials keys...")
            creds.refresh(Request())

        service = build('gmail', 'v1', credentials=creds)
        print("Gmail API Service successfully built.")
    except Exception as e:
        print(f"Failed to boot Gmail API: {e}")
        service = None

# --- STEP 2: FETCH DATA SECURELY FROM GOOGLE SHEETS ---
if service:
    print("Connecting to Google Sheets...")
    SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")

    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open_by_key(SHEET_KEY)
        worksheet = sh.get_worksheet(0) 

        df = pd.DataFrame(worksheet.get_all_records())
        filtered_df = df[["Student_Pin", "Email", "Full_name"]].copy()

        students = filtered_df.to_dict(orient="records")
        print(f"Successfully loaded {len(students)} student records from Google Sheets.\n")

    except Exception as e:
        print(f"Critical Error connecting to Google Sheets: {e}")
        students = [] 
else:
    students = []

# --- STEP 3: LOOP AND PROCESS ATTENDANCE CONFIGURATION ---
email_count = 0
# UPDATED: CREATED MASTER LOGGING BUCKET TO CAPTURE ALL SKIPPED/FAILED PINS
failed_dispatches = []

for student in students:
    SBTET_PIN = student['Student_Pin']       
    RECEIVER_EMAIL = student['Email']   

    url = "https://www.sbtet.telangana.gov.in/api/api/PreExamination/getAttendanceReport"
    payload = {"Pin": SBTET_PIN}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
    }

    try:
        print(f"\nProcessing student: {student['Full_name']} (PIN: {SBTET_PIN})")
        print("Fetching attendance data from SBTET...")
        response = requests.get(url, params=payload, headers=headers)

        if response.status_code == 200:
            raw_string = response.text

            try:
            
                data = json.loads(raw_string)
                
                
                if isinstance(data, str):
                    data = json.loads(data)

                # UPDATED: ADDED DEFENSIVE SHIELD AGAINST EMPTY TABLES (PREVENTS INDEXERROR ON TYPOS)
                if not data.get("Table") or len(data["Table"]) == 0:
                    print(f"Warning: SBTET returned blank data for {SBTET_PIN}. Skipping safely.")
                    failed_dispatches.append({"pin": SBTET_PIN, "name": student['Full_name'], "reason": "Invalid PIN / Empty Table"})
                    continue

                # --- YOUR CUSTOM CALCULATIONS ---
                percentage = data["Table"][0]["Percentage"]
                exam_percentage = data["Table"][0]["ExamsPer"]
                TOTAL_SEMESTER_WORKING_DAYS = data["Table"][0]["TotalWorkingDays"]
                present_days = data["Table"][0]["NumberOfDaysPresent"]
                sbtet_working_days = data["Table"][0]["WorkingDays"]
                True_working_days = int(sbtet_working_days)
            
                remaining_working_days = 90 - int(True_working_days)
                required_present_days = 68 - int(present_days)
                chance_for_leave = remaining_working_days - required_present_days
                if chance_for_leave < 0:
                    chance_for_leave = 0

                # --- FETCH PAST WEEK'S ATTENDANCE ---
                today = datetime.now()
                today_str = datetime.today().strftime('%d-%b-%Y')
                past_week_info = [
                    ((today - timedelta(days=i)).strftime("%Y-%m-%d"), (today - timedelta(days=i)).strftime("%A")) 
                    for i in range(6, 0, -1)
                ]

                past_week_lookup = {date_str: day_name for date_str, day_name in past_week_info}
                week_attendance_list = []

                for day_record in data.get("Table1", []):
                    record_date = day_record.get("Date", "")[:10] 

                    if record_date in past_week_lookup:
                        status = day_record.get("Status", "-")
                        day_name = past_week_lookup[record_date]
                        week_attendance_list.append(f"{record_date} {day_name} : {status}")

                week_attendance_str = "\n".join(week_attendance_list)
                if not week_attendance_str:
                    week_attendance_str = "No attendance records found for the past week."
                



                # --- PREPARE THE EMAIL BODY ---
                # Copy and paste this directly into your email body text configuration
                footer_note = """
<div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px; line-height: 1.6; color: #64748b;">
    <span style="color: #1e293b; font-weight: 700; display: block; margin-bottom: 4px;">📌 Important Note for Students:</span>
    To help you stay on track, this attendance summary will be sent to you every Sunday.
    <br><br>
    Please make sure to open this email weekly. If this message accidentally landed in your 
    <span style="background-color: #ffe4e6; color: #e11d48; padding: 2px 6px; border-radius: 4px; font-weight: 600;">Spam</span> or 
    <strong>Promotions</strong> folder, please open it and click 
    <span style="color: #2563eb; font-weight: 700; text-decoration: underline;">'Report as not spam'</span> or drag it to your Primary Inbox.
    <br><br>
    Thank you!
</div>
"""
                disclaimer_note = """
<div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px; line-height: 1.6; color: #64748b;">
    
    <!-- ⚠️ OFFICIAL DISCLAIMER BOX -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #64748b; padding: 12px 14px; border-radius: 8px; margin-bottom: 20px; font-size: 12px; color: #475569; line-height: 1.5;">
        <strong style="color: #0f172a; display: block; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">⚠️ Important Disclaimer:</strong>
        This email dashboard is an <strong>independent, unofficial notification service</strong> created solely for the convenience of students to help monitor daily attendance habits. This service is <strong>not affiliated with, authorized by, sponsored by, or in any way officially connected</strong> to the State Board of Technical Education and Training (SBTET). All official attendance records, updates, and exam eligibility criteria must be cross-verified directly through your official college administration portal or the formal SBTET website.
    </div>

    <!-- 📌 STUDENT NOTE -->
    
"""

                email_subject = f"SBTET ATTENDANCE UPDATE: {percentage}% ({today_str})"
                email_body =  f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="format-detection" content="telephone=no">
    <title>SBTET Attendance</title>
    <style>
        /* Mobile Specific Overrides */
        @media screen and (max-width: 480px) {{
            .email-container {{ padding: 16px !important; }}
            .header-title {{ font-size: 20px !important; }}
            .metric-val {{ font-size: 15px !important; }}
            .log-box {{ font-size: 13px !important; padding: 12px !important; }}
        }}
    </style>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; width: 100% !important;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; padding: 12px 4px;">
        <tr>
            <td align="center">
                <!-- Main Container Card (Fluid max-width for modern phone screens) -->
                <div class="email-container" style="max-width: 500px; width: 100%; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04); border: 1px solid #e2e8f0; text-align: left; box-sizing: border-box; padding: 24px; margin: 0 auto;">
                    
                    <!-- Header Icon & Label -->
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 class="header-title" style="color: #0f172a; margin: 10px 0 0 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">SBTET Attendance</h2>
                    </div>

                    <!-- Greeting Section -->
                    <div style="margin-bottom: 20px;">
                        <p style="font-size: 15px; color: #334155; margin: 0; line-height: 1.5;">Hello <strong style="color: #0f172a;">{student['Full_name']}</strong>,</p>
                        <p style="font-size: 14px; color: #64748b; margin: 4px 0 0 0;">Here is your current attendance information:</p>
                    </div>

                    <!-- Highlight Info Badge Group -->
                    <div style="background-color: #f1f5f9; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td style="padding-bottom: 10px; font-size: 14px; color: #475569; font-weight: 600;">Student PIN:</td>
                                <td align="right" style="padding-bottom: 10px; font-size: 14px; font-weight: 700; color: #0f172a; font-family: monospace;">{SBTET_PIN}</td>
                            </tr>
                            <tr style="border-top: 1px solid #e2e8f0;">
                                <td style="padding-top: 10px; padding-bottom: 10px; font-size: 14px; color: #475569; font-weight: 600;">Current Percentage:</td>
                                <td align="right" style="padding-top: 10px; padding-bottom: 10px; font-size: 18px; font-weight: 800; color: #ea580c;">{percentage}%</td>
                            </tr>
                            <tr>
                                <td style="padding-top: 10px; font-size: 14px; color: #475569; font-weight: 600;">Exam Consideration %:</td>
                                <td align="right" style="padding-top: 10px; font-size: 15px; font-weight: 700; color: #16a34a;">{exam_percentage}%</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Core Metrics Rows -->
                    <div style="margin-bottom: 24px;">
                        <div style="border-bottom: 1px solid #f1f5f9; padding: 12px 0; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 14px; color: #475569;">Present Days: </span>
                            <strong class="metric-val" style="font-size: 16px; color: #0f172a;">{present_days} / {True_working_days} Days</strong>
                        </div>
                        <div style="border-bottom: 1px solid #f1f5f9; padding: 12px 0; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 14px; color: #475569;">Remaining Working Days: </span>
                            <strong class="metric-val" style="font-size: 16px; color: #475569;">{remaining_working_days} Days</strong>
                        </div>
                        <div style="border-bottom: 1px solid #f1f5f9; padding: 12px 0; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 14px; color: #475569;">Required Present Days (For 75%): </span>
                            <strong class="metric-val" style="font-size: 16px; color: #dc2626;">{required_present_days} Days</strong>
                        </div>
                        <div style="padding: 12px 0; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 14px; color: #475569;">Available Leaves: </span>
                            <strong class="metric-val" style="font-size: 16px; color: #16a34a;">{chance_for_leave} Days</strong>
                        </div>
                    </div>

                    <!-- Visual Log Box -->
                    <div style="margin-bottom: 20px;">
                        <span style="font-size: 13px; font-weight: 700; color: #475569; display: block; margin-bottom: 8px; letter-spacing: 0.3px;">📅 PAST  WEEK  ATTENDANCE</span>
                        <div class="log-box" style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background-color: #0f172a; color: #f8fafc; padding: 16px; border-radius: 10px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; letter-spacing: -0.2px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);">{week_attendance_str}</div>
                    </div>

                    <!-- Injected Mobile Footer -->
                    {disclaimer_note}
                    

                </div>
            </td>
        </tr>
    </table>
</body>
</html>
"""
                # 1. Your unique Mixpanel project configuration token string
                WEB_APP_URL = "https://script.google.com/macros/s/AKfycbw99joxoNqiFu2iT_45mrVapo95N1zbUgLkWPkAnTZxCxJ1WboVhC9sq8vsF_3Tguby/exec"

                # We are adding &sent_date={today_str} to the end of the URL
                tracking_pixel = f'<img src="{WEB_APP_URL}?pin={SBTET_PIN}&sent_date={today_str}" width="1" height="1" style="display:none !important;" alt="" />'

                # Inject into the email body right before the closing body tag
                email_body = email_body.replace("</body>", f"{tracking_pixel}</body>")


                print("Email Preview generated.")

                # --- SEND VIA GMAIL API ---
                print(f"Sending API email to {RECEIVER_EMAIL}...")

                msg = MIMEMultipart('alternative')
                msg['to'] = RECEIVER_EMAIL
                msg['from'] = 'me'  
                msg['subject'] = email_subject

                html_part = MIMEText(email_body, 'html')
                msg.attach(html_part)

                raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
                payload_data = {'raw': raw_message}

                service.users().messages().send(userId='me', body=payload_data).execute()

                email_count += 1
                print(f"[{email_count}] Email successfully fired via Gmail API!")

            # UPDATED: BROADENED INNER EXCEPTIONS TO CATCH KEY ERRORS OR INDEX ERRORS WITHOUT CRASHING
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as parse_err:
                print(f"Failed to extract data for {SBTET_PIN}: {parse_err}")
                failed_dispatches.append({"pin": SBTET_PIN, "name": student['Full_name'], "reason": f"Data Parse Error ({type(parse_err).__name__})"})

            except HttpError as api_err:
                print(f"Google Gmail API reject error occurred: {api_err}")
                # UPDATED: LOGGED GMAIL REJECTION TO THE MASTER FAIL LIST
                failed_dispatches.append({"pin": SBTET_PIN, "name": student['Full_name'], "reason": "Gmail API Send Rejected"})
                time.sleep(3)
        else:
            print(f"Failed to fetch data. Status Code: {response.status_code}")
            # UPDATED: LOGGED SERVER REJECTION TO THE MASTER FAIL LIST
            failed_dispatches.append({"pin": SBTET_PIN, "name": student['Full_name'], "reason": f"HTTP {response.status_code}"})

    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
        # UPDATED: LOGGED NETWORK CONNECTION TIMEOUTS TO THE MASTER FAIL LIST
        failed_dispatches.append({"pin": SBTET_PIN, "name": student['Full_name'], "reason": "Network Request Exception"})

    # UPDATED: REPLACED STATIC 2.0s WITH RANDOMIZED JITTER (1.5s TO 3.2s) TO EVADE ANTI-BOT DETECTORS
    time.sleep(random.uniform(1.5, 3.2))  

print(f"\nTask Complete. Total execution run pushed: {email_count} emails.")

# UPDATED: AUTOMATED DEBUGGING PRINTOUT AND EMAIL NOTIFICATION
if len(failed_dispatches) > 0:
    print(f"\nSending Admin Alert for {len(failed_dispatches)} failed dispatches...")
    
    # 1. Build a clean, readable text body including the Name, PIN, and Reason
    admin_body = "The SBTET Automation Bot skipped the following students during this run:\n\n"
    for f in failed_dispatches:
        admin_body += f"• PIN: {f.get('pin', 'N/A')} | Name: {f.get('name', 'N/A')} | Error: {f.get('reason', 'Unknown')}\n"
    
    # 2. Add the proper headers (including 'from' and plain text formatting)
    admin_msg = MIMEText(admin_body, 'plain')
    admin_msg['to'] = "bunnybhargav112233@gmail.com"
    admin_msg['from'] = "me"
    admin_msg['subject'] = f"⚠️ [SBTET BOT] {len(failed_dispatches)} Dispatches Failed"
    
    # 3. Dispatch the email
    raw_message = base64.urlsafe_b64encode(admin_msg.as_bytes()).decode('utf-8')
    payload_data = {'raw': raw_message}

    try:
        service.users().messages().send(userId='me', body=payload_data).execute()
        print("Admin alert email successfully delivered to you.")
    except Exception as e:
        print(f"Failed to send Admin alert email: {e}")

print(f"Failed dispatches list: {failed_dispatches}")    