import resend
from dotenv import load_dotenv
import os

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_verification_email(name: str, email: str, token: str):
    verification_link = f"{FRONTEND_URL}/verify?token={token}"

    resend.Emails.send({
        "from": "ResumeIQ <onboarding@resend.dev>",
        "to": email,
        "subject": "Verify your ResumeIQ account",
        "html": f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px;">
            <h1 style="color: #10b981;">Welcome to ResumeIQ! 🎉</h1>
            <p>Hi {name},</p>
            <p>Thanks for signing up. Please verify your email to get started.</p>
            <a href="{verification_link}"
               style="background-color: #10b981; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 8px; display: inline-block; margin: 20px 0;">
                Verify Email
            </a>
            <p style="color: #666;">Or copy this link: {verification_link}</p>
            <p style="color: #666;">This link expires in 24 hours.</p>
        </div>
        """
    })