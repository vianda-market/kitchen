import logging

# Create a custom logger
logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

def log_info(message: str):
    """
    Log an informational message.
    """
    logger.info(message)

def log_warning(message: str):
    """
    Log a warning message.
    """
    logger.warning(message)

def log_error(message: str):
    """
    Log an error message.
    """
    logger.error(message)

def log_debug(message: str):
    """
    Log a debug message.
    """
    logger.debug(message)

def log_critical(message: str):
    """
    Log a critical message.
    """
    logger.critical(message)