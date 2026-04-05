import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_verification_email(name: str, email: str, token: str):
    print(f"[EMAIL] Attempting to send to: {email}")
    print(f"[EMAIL] From: {GMAIL_USER}")
    print(f"[EMAIL] App password set: {bool(GMAIL_APP_PASSWORD)}")
    print(f"[EMAIL] App password length: {len(GMAIL_APP_PASSWORD) if GMAIL_APP_PASSWORD else 0}")
    
    verification_link = f"{FRONTEND_URL}/verify?token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your ResumeIQ account"
    msg["From"] = f"ResumeIQ <{GMAIL_USER}>"
    msg["To"] = email

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; background-color: #f5f0e8;">
        <div style="background-color: white; border-radius: 16px; padding: 48px; border: 1px solid #e2d9c8;">
            <h1 style="font-size: 28px; color: #1a2744; margin-bottom: 8px;">
                Resume<span style="color: #c84b2f;">IQ</span>
            </h1>
            <hr style="border: none; border-top: 1px solid #e2d9c8; margin: 24px 0;" />
            <h2 style="color: #1a1208; font-size: 22px; margin-bottom: 12px;">Verify your email</h2>
            <p style="color: #8a7a60; font-size: 15px; line-height: 1.6; margin-bottom: 8px;">Hi {name},</p>
            <p style="color: #8a7a60; font-size: 15px; line-height: 1.6; margin-bottom: 32px;">
                Thanks for signing up. Click the button below to verify your email and activate your account.
            </p>
            <a href="{verification_link}"
               style="display: inline-block; background-color: #c84b2f; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                Verify Email →
            </a>
            <p style="color: #8a7a60; font-size: 13px; margin-top: 32px;">
                Or copy this link: <a href="{verification_link}" style="color: #c84b2f;">{verification_link}</a>
            </p>
            <p style="color: #8a7a60; font-size: 13px; margin-top: 16px;">
                This link expires in 24 hours. If you didn't sign up, ignore this email.
            </p>
        </div>
    </div>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        print(f"[EMAIL] Connecting to Gmail SMTP...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            print(f"[EMAIL] Connected. Logging in...")
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            print(f"[EMAIL] Logged in. Sending...")
            server.se