from email.message import EmailMessage
import smtplib

from ..config import get_settings

settings = get_settings()


def _build_reset_code_html(code: str) -> str:
        app_label = settings.app_name.replace(" API", "").strip()
        expiry_minutes = settings.password_reset_code_expiry_minutes

        return f"""
<!doctype html>
<html>
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{app_label} Password Reset Code</title>
    </head>
    <body style=\"margin:0;padding:0;background:#f3f6fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;\">
        <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"background:#f3f6fb;padding:24px 12px;\">
            <tr>
                <td align=\"center\">
                    <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:560px;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;\">
                        <tr>
                            <td style=\"background:linear-gradient(135deg,#6f79ea,#7dd3fc);padding:18px 24px;color:#ffffff;\">
                                <div style=\"font-size:18px;font-weight:700;\">{app_label}</div>
                                <div style=\"font-size:13px;opacity:0.95;margin-top:4px;\">Password Reset Verification</div>
                            </td>
                        </tr>
                        <tr>
                            <td style=\"padding:24px;\">
                                <p style=\"margin:0 0 12px;font-size:15px;line-height:1.6;\">You requested a password reset for your account.</p>
                                <p style=\"margin:0 0 16px;font-size:15px;line-height:1.6;\">Use this 6-digit verification code:</p>

                                <div style=\"margin:0 auto 18px;max-width:260px;background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:14px 16px;text-align:center;\">
                                    <span style=\"font-size:30px;letter-spacing:8px;font-weight:800;color:#3730a3;\">{code}</span>
                                </div>

                                <p style=\"margin:0 0 10px;font-size:13px;color:#475569;line-height:1.6;\">This code will expire in <strong>{expiry_minutes} minutes</strong>.</p>
                                <p style=\"margin:0;font-size:13px;color:#64748b;line-height:1.6;\">If you did not request this, you can safely ignore this email.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style=\"padding:14px 24px;background:#f8fafc;border-top:1px solid #e5e7eb;font-size:12px;color:#64748b;\">
                                Sent by {app_label}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
"""


def send_reset_code_email(to_email: str, code: str) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise ValueError("SMTP credentials are not configured")

    from_email = settings.smtp_from_email or settings.smtp_user

    msg = EmailMessage()
    msg["Subject"] = "Scholarly Aether Password Reset Code"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(
        "You requested a password reset for Scholarly Aether.\n\n"
        f"Your 6-digit verification code is: {code}\n\n"
        f"This code expires in {settings.password_reset_code_expiry_minutes} minutes.\n"
        "If you did not request this, you can ignore this email."
    )
    msg.add_alternative(_build_reset_code_html(code), subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return
    except OSError:
        # Some hosting networks block STARTTLS route on port 587; try implicit SSL on 465.
        with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=20) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
