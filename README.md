# Automated SBTET Academic Tracking Bot 🤖📊

An automated Python pipeline that securely fetches, processes, and distributes real-time academic attendance data via RESTful APIs and Google Cloud services. 

## 🚀 Overview
This project was engineered to eliminate the manual tracking of student attendance. It pulls live data from the SBTET API, calculates academic metrics (such as required days for 75% attendance and available leaves), and automatically dispatches personalized HTML email reports to students every week.

## 🛠️ Tech Stack
* **Language:** Python 3.10
* **APIs & Cloud:** Google Cloud Platform (GCP), Gmail API, Google Sheets API
* **Libraries:** `pandas`, `requests`, `gspread`, `google-auth`
* **Authentication:** OAuth 2.0
* **CI/CD & Automation:** GitHub Actions (Cron scheduling)

## ✨ Key Features
* **Automated Data Extraction:** Reliably fetches payload data using `requests` with randomized network delays (jitter) to prevent API rate-limiting.
* **Data Processing:** Utilizes `pandas` and `json` to parse raw API returns, dynamically calculating attendance deficits and remaining working days.
* **Secure Dispatch System:** Leverages OAuth 2.0 and the Gmail API to securely send thousands of customized, mobile-responsive HTML emails.
* **Resilient Error Handling:** Includes robust `try/except` blocks to handle network timeouts, JSON parse errors, and missing data schemas without crashing.
* **Automated Admin Logging:** Compiles a list of any failed API calls or email rejections and automatically alerts the admin upon workflow completion.

## ⚙️ How It Works
1. A **GitHub Actions** cron job triggers the script automatically every week.
2. The script authenticates securely via hidden GitHub Secrets and pulls the target student list from **Google Sheets**.
3. It iterates through the roster, pinging the SBTET endpoint for each student.
4. Data is parsed, calculations are made, and a customized HTML email is packaged using `MIMEMultipart`.
5. The email is fired off via the **Gmail API**.

*(Note: Sensitive data, `.env` files, and `credentials.json` have been omitted from this repository for security purposes. See `.env.example` for required environment variables).*