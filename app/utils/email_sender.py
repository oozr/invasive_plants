import smtplib
from email.message import EmailMessage

import requests


class EmailDeliveryError(RuntimeError):
    pass


def _config_timeout(config) -> int:
    return max(1, int(config.get("EMAIL_SEND_TIMEOUT_SECONDS", 8) or 8))


def _sender(config) -> str:
    return config.get("MAIL_DEFAULT_SENDER") or config.get("EMAIL_USERNAME") or ""


def _send_smtp(config, subject: str, recipients: list, body: str, reply_to: str = None):
    server = config.get("MAIL_SERVER")
    port = int(config.get("MAIL_PORT") or 25)
    username = config.get("MAIL_USERNAME")
    password = config.get("MAIL_PASSWORD")
    sender = _sender(config)
    timeout = _config_timeout(config)

    if not server or not sender or not username or not password:
        raise EmailDeliveryError("SMTP email is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    try:
        if config.get("MAIL_USE_SSL"):
            with smtplib.SMTP_SSL(server, port, timeout=timeout) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(server, port, timeout=timeout) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        raise EmailDeliveryError(str(exc)) from exc


def _send_postmark(config, subject: str, recipients: list, body: str, reply_to: str = None):
    token = config.get("POSTMARK_SERVER_TOKEN")
    sender = _sender(config)
    timeout = _config_timeout(config)
    api_url = config.get("POSTMARK_API_URL") or "https://api.postmarkapp.com/email"
    message_stream = config.get("POSTMARK_MESSAGE_STREAM") or "outbound"

    if not token or not sender:
        raise EmailDeliveryError("Postmark email is not configured")

    payload = {
        "From": sender,
        "To": ", ".join(recipients),
        "Subject": subject,
        "TextBody": body,
        "MessageStream": message_stream,
    }
    if reply_to:
        payload["ReplyTo"] = reply_to

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": token,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise EmailDeliveryError(str(exc)) from exc

    if response.status_code >= 400:
        raise EmailDeliveryError(f"Postmark returned {response.status_code}: {response.text[:300]}")


def send_email(config, subject: str, recipients, body: str, reply_to: str = None):
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [item for item in recipients if item]
    if not recipients:
        raise EmailDeliveryError("No email recipients configured")

    provider = str(config.get("EMAIL_PROVIDER") or "smtp").strip().lower()
    if provider == "postmark":
        return _send_postmark(config, subject, recipients, body, reply_to=reply_to)
    if provider == "smtp":
        return _send_smtp(config, subject, recipients, body, reply_to=reply_to)
    raise EmailDeliveryError(f"Unsupported email provider: {provider}")
