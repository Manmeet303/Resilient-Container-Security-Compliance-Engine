import logging, json, sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {"timestamp": datetime.utcnow().isoformat(), "level": record.levelname,
                 "module": record.name, "message": record.getMessage()}
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JSONFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
