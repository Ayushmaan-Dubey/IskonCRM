import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_smtp_config():
    return {
        'server': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        'port': int(os.environ.get('MAIL_PORT', 587)),
        'username': os.environ.get('MAIL_USERNAME', ''),
        'password': os.environ.get('MAIL_PASSWORD', ''),
        'from': os.environ.get('MAIL_FROM', os.environ.get('MAIL_USERNAME', '')),
        'use_tls': os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes'),
    }


def send_email(to_email, subject, body_html, body_text=None):
    """Send an email. Returns (success: bool, error: str)."""
    cfg = _get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        return False, 'MAIL_USERNAME or MAIL_PASSWORD not configured'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = cfg['from']
        msg['To'] = to_email

        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP(cfg['server'], cfg['port']) as server:
            if cfg['use_tls']:
                server.starttls()
            server.login(cfg['username'], cfg['password'])
            server.sendmail(cfg['from'], [to_email], msg.as_string())

        return True, None
    except Exception as e:
        return False, str(e)


def send_new_user_email(to_email, temp_password):
    """Send welcome email with temporary password to a newly created user."""
    subject = 'Welcome to Temple CRM — Your Account Details'
    body_html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#143642;">Welcome to Temple CRM</h2>
      <p>An account has been created for you. Please log in using the credentials below and change your password on first login.</p>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:8px;color:#6b7280;">Email</td><td style="padding:8px;font-weight:600;">{to_email}</td></tr>
        <tr><td style="padding:8px;color:#6b7280;">Temporary Password</td><td style="padding:8px;font-weight:600;font-family:monospace;">{temp_password}</td></tr>
      </table>
      <p style="margin-top:24px;color:#6b7280;font-size:0.9em;">Please keep this email confidential.</p>
    </div>
    """
    return send_email(to_email, subject, body_html)


def send_not_yet_paid_email(to_email, name, payment_settings, form_url):
    """Send payment instruction email when a donation is marked Not Yet Paid."""
    details_html = ''
    if payment_settings:
        if payment_settings.zelle_details:
            details_html += f'<li><strong>Zelle:</strong> {payment_settings.zelle_details}</li>'
        if payment_settings.gpay_details:
            details_html += f'<li><strong>Google Pay:</strong> {payment_settings.gpay_details}</li>'
        if payment_settings.paypal_details:
            details_html += f'<li><strong>PayPal:</strong> {payment_settings.paypal_details}</li>'
        if payment_settings.other_details:
            details_html += f'<li><strong>Other:</strong> {payment_settings.other_details}</li>'

    subject = 'Temple Donation — Payment Instructions'
    body_html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#143642;">Hare Krishna, {name}</h2>
      <p>Thank you for your kind offering to the temple. A donation record has been created for you. To complete your donation, please send payment using one of the following methods:</p>
      <ul style="line-height:2;">{details_html or '<li>Please contact the temple for payment details.</li>'}</ul>
      <p>Once you have sent the payment, you can also confirm it here:</p>
      <p><a href="{form_url}" style="background:#143642;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;">Confirm Donation</a></p>
      <p style="margin-top:24px;color:#6b7280;font-size:0.9em;">Hare Krishna. Thank you for your seva.</p>
    </div>
    """
    return send_email(to_email, subject, body_html)


def send_donation_confirmation_email(to_email, name, sponsorship_categories, amount):
    """Send confirmation email after a donation is submitted via the public form."""
    subject = 'Temple Donation — Thank You'
    body_html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#143642;">Thank You, {name}!</h2>
      <p>We have received your donation record. May Krishna bless you for your generosity.</p>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:8px;color:#6b7280;">Sponsorship For</td><td style="padding:8px;">{sponsorship_categories or 'General Donation'}</td></tr>
        <tr><td style="padding:8px;color:#6b7280;">Amount</td><td style="padding:8px;font-weight:600;">{amount or 'Not specified'}</td></tr>
      </table>
      <p style="margin-top:24px;color:#6b7280;font-size:0.9em;">Hare Krishna. Thank you for your seva.</p>
    </div>
    """
    return send_email(to_email, subject, body_html)


def render_template_body(template_body, context):
    """Replace {token} placeholders with context values."""
    text = template_body
    for key, value in context.items():
        text = text.replace('{' + key + '}', str(value) if value is not None else '')
    return text
