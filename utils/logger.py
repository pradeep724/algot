import logging
import sys
import os

def setup_logger(log_file="pro_trader_bot.log"):
    logger = logging.getLogger("ProTraderBot")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler for INFO level and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # File handler for DEBUG level and above (rotating file you can configure if needed)
    if not os.path.exists("logs"):
        os.makedirs("logs")
    file_handler = logging.FileHandler(os.path.join("logs", log_file), mode='a')
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


# Global logger instance that other modules can import
log = setup_logger()
