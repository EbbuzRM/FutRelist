import urllib.request
import json
import logging
import os

logger = logging.getLogger(__name__)

def send_telegram_emergency_alert(config, message: str) -> None:
    """Invia un messaggio di allerta ad alta priorità (Ban Risk)."""
    emoji_alert = "🚨 [BAN RISK ALERT] 🚨\n"
    full_message = f"{emoji_alert}{message}"
    send_telegram_alert(config, full_message)


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


def send_telegram_error_with_screenshot(config, message: str, page=None) -> None:
    """Invia un messaggio di errore Telegram con screenshot allegato.
    
    Se page è disponibile, cattura uno screenshot e lo invia come foto con
    il messaggio di errore come didascalia. Se lo screenshot fallisce, 
    fallback a messaggio testuale semplice.
    
    Args:
        config: NotificationsConfig con telegram_token e telegram_chat_id.
        message: Messaggio di errore da inviare.
        page: Oggetto Page di Playwright (opzionale). Se None, invia solo testo.
    """
    if not config or not config.telegram_token or not config.telegram_chat_id:
        return

    screenshot_path = None
    try:
        if page is not None:
            import tempfile
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            screenshot_path = os.path.join(temp_dir, f"fifa_error_screenshot_{timestamp}.png")
            page.screenshot(path=screenshot_path)
            logger.info(f"Screenshot errore catturato: {screenshot_path}")
            send_telegram_photo(config, screenshot_path, message)
            return
    except Exception as e:
        logger.warning(f"Screenshot per errore fallito, fallback a testo: {e}")
    finally:
        # Cleanup: rimuovi il file screenshot temporaneo
        if screenshot_path:
            try:
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
            except Exception:
                pass

    # Fallback: invia solo testo
    send_telegram_alert(config, message)


def send_telegram_photo(config, photo_path: str, caption: str) -> None:
    """Invia una foto a Telegram con didascalia (multipart/form-data)."""
    if not config or not config.telegram_token or not config.telegram_chat_id:
        return

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
