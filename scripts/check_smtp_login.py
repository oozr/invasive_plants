import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.utils.email_sender import send_email


def main():
    parser = argparse.ArgumentParser(description="Check configured login email delivery.")
    parser.add_argument("--to", help="Optional recipient for a real test email.")
    args = parser.parse_args()

    app = create_app()
    config = app.config

    recipient = args.to or config.get("CONTACT_EMAIL") or config.get("EMAIL_USERNAME")
    if not recipient:
        print("No recipient configured. Pass --to or set CONTACT_EMAIL/EMAIL_USERNAME.", file=sys.stderr)
        return 2

    try:
        send_email(
            config,
            "Regulated Plants email delivery test",
            recipient,
            "This is a test email from the Regulated Plants email configuration.",
        )
        print(f"Email delivery succeeded using provider {config.get('EMAIL_PROVIDER') or 'smtp'} to {recipient}.")
    except Exception as exc:
        print(f"Email delivery check failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
