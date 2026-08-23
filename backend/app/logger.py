import json
import logging
import sys
from datetime import datetime

logger = logging.getLogger("healthcare_app")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}'
)
handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(handler)

def log_event(event_type: str, details: dict):
    payload = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        **details
    }
    logger.info(json.dumps(payload))
