"""
emailer.py
----------
Sends email notifications using Flask-Mail.
Triggered on:
  - Loan application submitted
  - Application approved / rejected by lender

Setup: add to .env file:
  MAIL_USERNAME=your@gmail.com
  MAIL_PASSWORD=your_app_password   (Gmail App Password, not account password)
  MAIL_DEFAULT_SENDER=your@gmail.com
"""

import os

def _get_mail():
    """Lazy import to avoid circular imports."""
    from extensions import mail
    from flask_mail import Message
    return mail, Message


def send_application_received(applicant_email: str, applicant_name: str,
                               business_name: str, app_id: int,
                               loan_amount: float) -> bool:
    try:
        mail, Message = _get_mail()
        msg = Message(
            subject = f'Application #{app_id} Received — SMECreditAI',
            recipients = [applicant_email],
        )
        msg.html = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:560px;margin:0 auto;background:#f8fafc;padding:0;">
          <div style="background:linear-gradient(135deg,#0f172a,#1a56db);padding:32px 36px;border-radius:12px 12px 0 0;">
            <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">SMECreditAI</h1>
            <p style="color:rgba(255,255,255,0.6);margin:6px 0 0;font-size:13px;">AI-Powered SME Credit Scoring</p>
          </div>
          <div style="background:white;padding:32px 36px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;border-top:none;">
            <h2 style="color:#0f172a;font-size:18px;margin:0 0 16px;">Application Received ✅</h2>
            <p style="color:#334155;font-size:14px;line-height:1.6;">Hi <b>{applicant_name}</b>,</p>
            <p style="color:#334155;font-size:14px;line-height:1.6;">
              Your loan application for <b>{business_name}</b> has been received and is being processed.
              Our AI model will generate your credit score shortly.
            </p>
            <div style="background:#f1f5f9;border-radius:10px;padding:16px 20px;margin:20px 0;">
              <p style="margin:0;font-size:13px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Application Details</p>
              <p style="margin:8px 0 0;font-size:14px;color:#0f172a;">ID: <b>#{app_id}</b></p>
              <p style="margin:4px 0 0;font-size:14px;color:#0f172a;">Amount Requested: <b>Rs.{loan_amount}L</b></p>
            </div>
            <a href="http://localhost:5000/loan/my-applications"
               style="display:inline-block;background:#1a56db;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
              View My Applications →
            </a>
            <p style="color:#94a3b8;font-size:12px;margin-top:24px;border-top:1px solid #e2e8f0;padding-top:16px;">
              SMECreditAI — AI-Powered SME Credit Scoring | This is an automated message.
            </p>
          </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f'[emailer] Failed to send application_received: {e}')
        return False


def send_decision_notification(applicant_email: str, applicant_name: str,
                                business_name: str, app_id: int,
                                decision: str, credit_score: int) -> bool:
    try:
        mail, Message = _get_mail()
        is_approved = decision == 'approved'
        color       = '#10b981' if is_approved else '#ef4444'
        icon        = '✅' if is_approved else '❌'
        headline    = 'Congratulations! Your Loan is Approved' if is_approved else 'Application Update'
        body_line   = (
            f'Great news! Your loan application for <b>{business_name}</b> has been <b>approved</b> by our lending team.'
            if is_approved else
            f'After careful review, your application for <b>{business_name}</b> has not been approved at this time.'
        )
        cta_url  = f'http://localhost:5000/score/result/{app_id}'
        cta_text = 'View Score Report →' if is_approved else 'View Details →'

        msg = Message(
            subject = f'{icon} Loan {decision.title()} — SMECreditAI',
            recipients = [applicant_email],
        )
        msg.html = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:560px;margin:0 auto;">
          <div style="background:linear-gradient(135deg,#0f172a,#1a56db);padding:32px 36px;border-radius:12px 12px 0 0;">
            <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">SMECreditAI</h1>
          </div>
          <div style="background:white;padding:32px 36px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;border-top:none;">
            <div style="background:{color}1a;border-left:4px solid {color};padding:14px 18px;border-radius:8px;margin-bottom:20px;">
              <h2 style="color:{color};margin:0;font-size:17px;">{icon} {headline}</h2>
            </div>
            <p style="color:#334155;font-size:14px;line-height:1.6;">Hi <b>{applicant_name}</b>,</p>
            <p style="color:#334155;font-size:14px;line-height:1.6;">{body_line}</p>
            <div style="background:#f1f5f9;border-radius:10px;padding:16px 20px;margin:20px 0;">
              <p style="margin:0;font-size:13px;color:#64748b;font-weight:600;text-transform:uppercase;">Application Summary</p>
              <p style="margin:8px 0 0;font-size:14px;color:#0f172a;">Application: <b>#{app_id}</b></p>
              <p style="margin:4px 0 0;font-size:14px;color:#0f172a;">AI Credit Score: <b style="color:{color};">{credit_score}</b></p>
              <p style="margin:4px 0 0;font-size:14px;color:#0f172a;">Decision: <b style="color:{color};">{decision.title()}</b></p>
            </div>
            <a href="{cta_url}"
               style="display:inline-block;background:#1a56db;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
              {cta_text}
            </a>
            <p style="color:#94a3b8;font-size:12px;margin-top:24px;border-top:1px solid #e2e8f0;padding-top:16px;">
              SMECreditAI — AI-Powered SME Credit Scoring
            </p>
          </div>
        </div>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f'[emailer] Failed to send decision_notification: {e}')
        return False