import logging
import os
from datetime import datetime

os.makedirs("logs", exist_ok=True)


def setup_logger():
    logger = logging.getLogger("driftless")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"logs/driftless_{today}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
