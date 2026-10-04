# Cloud Deployment Guide — Job Digest Agent

> **Target:** Render Free-Tier Web Service + GitHub Actions Automated Cron + Supabase PostgreSQL  
> **Cost:** $0 / month  
> **Uptime:** Kept awake 24/7 via free health check keepalive pings.

---

## 1. Overview: The 2-Component Cloud Architecture

1. **Scheduled Autonomous Runner (GitHub Actions):**
   - Runs on GitHub's cloud twice daily at **08:00 AM & 07:00 PM IST** (and on-demand).
   - Ingests from 8 job sources, deduplicates, runs 10-point scoring against your candidate profile (Batch 2027 CSE), delivers to Telegram & Email, and sends instant alerts for jobs closing in ≤ 4 hours.
   - **Never sleeps** — operates independently of whether your web dashboard is open.

2. **Private Web Dashboard (Render Free Web Service):**
   - Runs the FastAPI web application with Argon2 single-user authentication.
   - Accessible from your phone or laptop (`https://your-app.onrender.com`).
   - Allows reviewing jobs, clicking **★ Save** / **✓ Applied** / **✕ Ignore**, editing settings, and clicking **⚡ Check & Notify Now**.

---

## 2. Step-by-Step Deployment Instructions

### Step 1: Push Code to Your GitHub Repository
Ensure all latest code is committed and pushed to your GitHub repository:
```bash
git push origin main
```

---

### Step 2: Deploy Web Dashboard on Render

1. Sign up / Log in to [Render](https://render.com) (free).
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository (`AI AGENT` / `job-digest-agent`).
4. Configure the service:
   - **Name:** `job-digest-dashboard` (or your preferred name)
   - **Region:** `Singapore` (fastest latency for India)
   - **Branch:** `main`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn job_digest.web:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`
5. In **Advanced Settings**:
   - **Health Check Path:** `/health`
   - **Auto-Deploy:** `Yes` (automatically redeploys whenever you `git push`)

---

### Step 3: Configure Environment Secrets on Render

Under the **Environment** tab in your Render Web Service dashboard, add the following variables:

| Environment Variable | Value | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.xxxx:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres` | Your Supabase Transaction Pooler URL |
| `DASHBOARD_PASSWORD` | `your_secret_master_password` | Master password to log into your dashboard |
| `SESSION_SECRET` | *(click 'Generate' or random 32 chars)* | HMAC session signing key |
| `TELEGRAM_BOT_TOKEN` | `123456789:ABCdefGh...` | Telegram BotFather token |
| `TELEGRAM_CHAT_ID` | `123456789` | Your personal Telegram Chat ID |
| `SMTP_HOST` | `smtp.gmail.com` | Mailbox B SMTP host |
| `SMTP_PORT` | `587` | Port 587 STARTTLS |
| `SMTP_USER` | `your_notifications@gmail.com` | Notification email address |
| `SMTP_PASSWORD` | `your_gmail_app_password` | Google 16-character App Password |
| `NOTIFICATION_EMAIL` | `your_notifications@gmail.com` | Recipient address |

Click **Save Changes**. Render will automatically build the container and deploy your live URL:  
`https://job-digest-dashboard.onrender.com`

---

### Step 4: Configure GitHub Actions Secrets (for Autonomous Runs)

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:
- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFICATION_EMAIL`
- `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD` (Mailbox A alerts)
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (if using Adzuna)

This ensures GitHub Actions runs automatically at **08:00 AM & 07:00 PM IST** even if your phone is turned off.

---

### Step 5: Keep Render Awake 24/7 for Free (Zero Sleep)

Render's free tier spins down if no request is received for 15 minutes. To keep it **awake 24/7 with zero lag**:

1. Go to [UptimeRobot](https://uptimerobot.com) (100% free) or [Cron-job.org](https://cron-job.org).
2. Create an account and click **Add New Monitor**.
3. Settings:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `Job Digest Health`
   - **URL:** `https://your-app.onrender.com/health`
   - **Monitoring Interval:** Every `10 minutes`
4. Click **Create Monitor**.

Because UptimeRobot pings `/health` every 10 minutes, **Render never sleeps**, and your dashboard loads instantaneously whenever you open it on your phone!

---

### Step 6: Session 16 Verification Check
1. Turn off Wi-Fi on your phone and enable **Mobile Data**.
2. Open your Render URL in your mobile browser: `https://your-app.onrender.com`.
3. Log in with your master password.
4. Verify that:
   - Today's digest and status cards load cleanly.
   - The navbar displays `🎯 Applied this week: X`.
   - Tap **`⚡ Check & Notify Now`** to trigger an on-demand job scan from your phone!
