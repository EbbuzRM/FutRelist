import logging
import os
from pathlib import Path
import logging.handlers

def setup_logging() -> None:
    """
    Configura il sistema di logging dell'applicazione.
    Rimuove la definizione della classe CustomDailyRotatingHandler dal main per isolarla qui.
    """
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    class CustomDailyRotatingHandler(logging.handlers.TimedRotatingFileHandler):
        def doRollover(self):
            super().doRollover()
            log_dir_str = os.path.dirname(self.baseFilename)
            old_log_file = os.path.join(log_dir_str, "old-log.txt")
            for f in os.listdir(log_dir_str):
                if f.startswith("app.log."):
                    file_path = os.path.join(log_dir_str, f)
                    try:
                        with open(file_path, "r", encoding="utf-8") as src, \
                             open(old_log_file, "a", encoding="utf-8") as dst:
                            dst.write(src.read())
                        os.remove(file_path)
                    except Exception:
                        pass

    file_handler = CustomDailyRotatingHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stdout) if 'sys' in globals() else logging.StreamHandler()
    # Note: sys.stdout is usually available in the main process
    import sys
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

    # Logger azioni strutturato (JSON) → logs/actions.jsonl
    from models.action_log import JsonFormatter
    actions_file_handler = logging.FileHandler(
        log_dir / "actions.jsonl", mode="a", encoding="utf-8"
    )
    actions_file_handler.setLevel(logging.INFO)
    actions_file_handler.setFormatter(JsonFormatter())
    
    action_logger = logging.getLogger("actions")
    action_logger.setLevel(logging.INFO)
    action_logger.addHandler(actions_file_handler)
    action_logger.propagate = False
