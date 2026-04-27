import logging
import os

# Log level is env-controlled. Set LOG_LEVEL=ERROR (or WARNING/DEBUG/etc.) to change.
# Default is INFO for dev visibility.
_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

# Apply LOG_LEVEL to the root logger too so module-scoped loggers
# (e.g. app.gateways.base_gateway uses logging.getLogger(__name__)) are also quieted.
logging.getLogger().setLevel(_LOG_LEVEL)

# Create a custom logger
logger = logging.getLogger("my_app")
logger.setLevel(_LOG_LEVEL)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(_LOG_LEVEL)

# Create a formatter and set it for the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)


def log_info(message: str) -> None:
    """
    Log an informational message.
    """
    # This wrapper is the log sink; CodeQL flags it because sensitive data can flow through
    # call-site messages. The wrapper itself does no scrubbing — call sites are responsible.
    logger.info(message)  # codeql[py/clear-text-logging-sensitive-data]


def log_warning(message: str) -> None:
    """
    Log a warning message.
    """
    # Same rationale as log_info: wrapper sink, call-site responsibility.
    logger.warning(message)  # codeql[py/clear-text-logging-sensitive-data]


def log_error(message: str) -> None:
    """
    Log an error message.
    """
    # Same rationale as log_info: wrapper sink, call-site responsibility.
    logger.error(message)  # codeql[py/clear-text-logging-sensitive-data]


def log_debug(message: str) -> None:
    """
    Log a debug message.
    """
    logger.debug(message)


def log_critical(message: str) -> None:
    """
    Log a critical message.
    """
    logger.critical(message)


def _is_password_recovery_debug_enabled() -> bool:
    """True if DEBUG_PASSWORD_RECOVERY env is set to 1, true, or yes (case-insensitive)."""
    val = os.environ.get("DEBUG_PASSWORD_RECOVERY", "").strip().lower()
    return val in ("1", "true", "yes")


def log_password_recovery_debug(message: str) -> None:
    """
    Log a message only when DEBUG_PASSWORD_RECOVERY is enabled (env var 1/true/yes).
    Use for password/username recovery workflow debugging; leave off in production.

    IMPORTANT: Call-site messages MUST NOT include raw passwords or secret tokens.
    Email addresses are acceptable because this function is dev-debug-only and is
    disabled by default in all environments. Never enable DEBUG_PASSWORD_RECOVERY in
    a shared or production environment.
    """
    if _is_password_recovery_debug_enabled():
        # Dev-debug-only (DEBUG_PASSWORD_RECOVERY=1 required). Messages may include email
        # for debugging, but must never include raw passwords or secret tokens.
        logger.info(f"[PasswordRecovery] {message}")  # codeql[py/clear-text-logging-sensitive-data]


def _is_email_tracking_enabled() -> bool:
    """True if LOG_EMAIL_TRACKING env is set to 1, true, or yes (case-insensitive)."""
    val = os.environ.get("LOG_EMAIL_TRACKING", "").strip().lower()
    return val in ("1", "true", "yes")


def log_email_tracking(message: str, level: str = "info") -> None:
    """
    Log an email-related message only when LOG_EMAIL_TRACKING is enabled.
    Enable: set LOG_EMAIL_TRACKING=1 (or true/yes) in .env. Disable: leave unset or set to 0/false.
    Use for email send/tracking (SMTP connect, success, failures). Off by default to avoid noisy logs.
    """
    if not _is_email_tracking_enabled():
        return
    if level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)


def _is_employer_assign_debug_enabled() -> bool:
    """True if LOG_EMPLOYER_ASSIGN is set to 1, true, or yes (case-insensitive). Checks os.environ first (load_dotenv), then Settings."""
    val = os.environ.get("LOG_EMPLOYER_ASSIGN", "").strip().lower()
    if val:
        return val in ("1", "true", "yes")
    try:
        from app.config.settings import get_settings

        val = (get_settings().LOG_EMPLOYER_ASSIGN or "").strip().lower()
        return val in ("1", "true", "yes")
    except Exception:
        return False


def log_deprecated_endpoint_usage(endpoint: str, user_id: str, role_type: str, role_name: str = "") -> None:
    """
    Log usage of deprecated endpoint for monitoring (Phase 4 of API deprecation plan).
    Use when a user hits a deprecated path for self-operations (e.g. PUT /users/{id} for self-update).
    Enables grepping logs for "DEPRECATED ENDPOINT USAGE" to track migration progress.
    """
    role_info = f"{role_type}/{role_name}" if role_name else role_type
    logger.warning(
        f"DEPRECATED ENDPOINT USAGE: {endpoint} by {role_info} user {user_id}. "
        f"Timestamp: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}"
    )


def log_employer_assign_debug(message: str) -> None:
    """
    Log a message only when LOG_EMPLOYER_ASSIGN is enabled (env var 1/true/yes).
    Use for PUT /users/me/employer (employer assignment) debugging; leave off in production.
    Enable: set LOG_EMPLOYER_ASSIGN=1 in .env. Disable: leave unset or set to 0/false.

    IMPORTANT: Call-site messages must not include raw passwords, tokens, or secrets.
    UUIDs (user_id, entity_id, address_id) are acceptable operational identifiers.
    """
    if _is_employer_assign_debug_enabled():
        # Dev-debug-only (LOG_EMPLOYER_ASSIGN=1 required). Call sites log only UUIDs
        # and operational identifiers, not passwords or secrets.
        logger.info(f"[EmployerAssign] {message}")  # codeql[py/clear-text-logging-sensitive-data]
