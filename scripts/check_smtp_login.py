import argparse
import os
import smtplib
import sys
from email.message import EmailMessage

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app


def _smtp_client(config):
    server = config.get("MAIL_SERVER")
    port = int(config.get("MAIL_PORT") or 25)
    timeout = max(1, int(config.get("EMAIL_SEND_TIMEOUT_SECONDS", 8) or 8))

    if config.get("MAIL_USE_SSL"):
        return smtplib.SMTP_SSL(server, port, timeout=timeout)
    return smtplib.SMTP(server, port, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description="Check configured SMTP login email delivery.")
    parser.add_argument("--to", help="Optional recipient for a real test email.")
    args = parser.parse_args()

    app = create_app()
    config = app.config

    server = config.get("MAIL_SERVER")
    username = config.get("MAIL_USERNAME")
    password = config.get("MAIL_PASSWORD")
    sender = config.get("MAIL_DEFAULT_SENDER") or username

    if not server or not username or not password or not sender:
        print("SMTP is not fully configured. Set EMAIL_USERNAME and EMAIL_PASSWORD.", file=sys.stderr)
        return 2

    try:
        with _smtp_client(config) as smtp:
            smtp.set_debuglevel(0)
            if config.get("MAIL_USE_TLS") and not config.get("MAIL_USE_SSL"):
                smtp.starttls()
            smtp.login(username, password)

            if args.to:
                message = EmailMessage()
                message["Subject"] = "Regulated Plants SMTP test"
                message["From"] = sender
                message["To"] = args.to
                message.set_content(
                    "This is a test email from the Regulated Plants login email configuration."
                )
                smtp.send_message(message)
                print(f"SMTP login succeeded and test email was sent to {args.to}.")
            else:
                print("SMTP login succeeded. No email was sent.")
    except Exception as exc:
        print(f"SMTP check failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
