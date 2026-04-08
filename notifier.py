import urllib.request
import json
import logging

logger = logging.getLogger(__name__)

def send_telegram_alert(config, message: str) -> None:
    """Invia un messaggio Telegram usando la configurazione NotificationsConfig."""
    if not config or not config.telegram_token or not config.telegram_chat_id:
        return
    
    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={"Content-Type": "application/json"}, 
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.info("Notifica Telegram inviata con successo!")
    except Exception as e:
        logger.error(f"Errore durante l'invio notifica Telegram: {e}")


def send_telegram_photo(config, photo_path: str, caption: str) -> None:
    """Invia una foto a Telegram con didascalia (multipart/form-data)."""
    if not config or not config.telegram_token or not config.telegram_chat_id:
        return

    import os
    import mimetypes
    from uuid import uuid4

    boundary = f"----TelegramBoundary{uuid4().hex}"
    url = f"https://api.telegram.org/bot{config.telegram_token}/sendPhoto"

    try:
        with open(photo_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(photo_path)
        mimetype = mimetypes.guess_type(photo_path)[0] or "application/octet-stream"

        # Costruzione manuale multipart
        body = []
        # Campo chat_id
        body.extend([
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="chat_id"',
            b'',
            str(config.telegram_chat_id).encode(),
        ])
        # Campo caption
        body.extend([
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="caption"',
            b'',
            caption.encode(),
        ])
        # Campo photo
        body.extend([
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="photo"; filename="{filename}"'.encode(),
            f'Content-Type: {mimetype}'.encode(),
            b'',
            file_data,
        ])
        body.append(f"--{boundary}--".encode())
        
        full_body = b"\r\n".join(body)

        req = urllib.request.Request(
            url,
            data=full_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(full_body))
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status == 200:
                logger.info("Screenshot Telegram inviato con successo!")
    except Exception as e:
        logger.error(f"Errore invio screenshot Telegram: {e}")
