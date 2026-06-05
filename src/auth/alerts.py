"""
src/auth/alerts.py — Deadline alert email sender
Run manually or via scheduler: python -m src.auth.alerts
"""
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Add to your .env:
# ALERT_EMAIL=your_gmail@gmail.com
# ALERT_PASSWORD=your_app_password   (Gmail App Password, not your main password)

SENDER_EMAIL    = os.getenv("ALERT_EMAIL", "")
SENDER_PASSWORD = os.getenv("ALERT_PASSWORD", "")


def send_alert_email(to_email: str, name: str, scheme_title: str, deadline: str, link: str = ""):
    """Send a deadline reminder email."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print(f"[ALERT] Email not configured — would have sent to {to_email}")
        return False

    subject = f"⏰ Deadline Reminder: {scheme_title}"

    html_body = f"""
    <div style="font-family:Inter,sans-serif;max-width:560px;margin:0 auto;color:#333;">
        <div style="background:#0d0d0d;padding:24px;border-radius:12px;margin-bottom:16px;">
            <h2 style="color:#fff;margin:0;font-size:20px;">🔍 Scheme Scout</h2>
            <p style="color:#888;margin:4px 0 0;font-size:13px;">Deadline Alert</p>
        </div>

        <p style="font-size:15px;">Hi <b>{name}</b>,</p>

        <p style="font-size:15px;line-height:1.6;">
            This is a reminder that the deadline for <b>{scheme_title}</b> is approaching.
        </p>

        <div style="background:#f9f9f9;border:1px solid #eee;border-radius:10px;
                    padding:16px;margin:20px 0;">
            <p style="margin:0 0 8px;font-size:14px;">
                <b>Scheme:</b> {scheme_title}
            </p>
            <p style="margin:0;font-size:14px;color:#e53e3e;">
                <b>Deadline:</b> {deadline}
            </p>
            {f'<p style="margin:8px 0 0;font-size:14px;"><a href="{link}" style="color:#4a9eff;">Apply Here →</a></p>' if link else ''}
        </div>

        <p style="font-size:13px;color:#999;">
            Don't miss this opportunity! Apply before the deadline.
        </p>

        <p style="font-size:12px;color:#bbb;margin-top:32px;border-top:1px solid #eee;padding-top:12px;">
            You're receiving this because you set a deadline alert on Scheme Scout.
        </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"[ALERT] Sent to {to_email} for '{scheme_title}'")
        return True
    except Exception as e:
        print(f"[ALERT ERROR] {e}")
        return False


def run_alerts():
    """
    Check for due alerts and send emails.
    Call this daily — via cron, APScheduler, or manually.
    """
    from src.database.database import get_pending_alerts, mark_alert_sent

    today = datetime.now().strftime("%Y-%m-%d")
    alerts = get_pending_alerts(today)

    if not alerts:
        print(f"[ALERTS] No pending alerts for {today}")
        return

    print(f"[ALERTS] Processing {len(alerts)} alert(s)...")

    for alert in alerts:
        sent = send_alert_email(
            to_email     = alert["email"],
            name         = alert["name"],
            scheme_title = alert["title"],
            deadline     = alert["deadline"],
            link         = alert.get("link", ""),
        )
        if sent:
            mark_alert_sent(alert["id"])

    print(f"[ALERTS] Done.")


if __name__ == "__main__":
    run_alerts()