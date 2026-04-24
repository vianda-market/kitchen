"""
Message catalog for localized API responses.
Phase 1: scaffold. Phase 5: full entity CRUD, DB constraint, and email subject translations.
"""

from typing import Any

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Auth / user errors
        "error.user_not_found": "User not found.",
        "error.duplicate_email": "An account with this email already exists.",
        "error.invalid_credentials": "Invalid username or password.",
        "error.email_change_code_expired": "Verification code has expired. Please request a new one.",
        "error.email_change_code_invalid": "Invalid verification code.",
        # Auth / user alerts
        "alert.email_verified": "Email verified successfully.",
        "alert.email_change_requested": "A verification code has been sent to {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} not found",
        "error.entity_not_found_by_id": "{entity} with ID {id} not found",
        "error.entity_creation_failed": "Failed to create {entity}",
        "error.entity_update_failed": "Failed to update {entity}",
        "error.entity_deletion_failed": "Failed to delete {entity}",
        "error.entity_operation_failed": "{entity} not found or {operation} failed",
        # Database constraint errors
        "error.db_duplicate_key": "Record with this value already exists",
        "error.db_duplicate_email": "User with this email already exists",
        "error.db_duplicate_username": "User with this username already exists",
        "error.db_duplicate_market": "Market already exists for this country",
        "error.db_duplicate_currency": "Credit currency with this code already exists",
        "error.db_duplicate_institution": "Institution with this name already exists",
        "error.db_duplicate_restaurant": "Restaurant with this name already exists",
        "error.db_fk_user": "Referenced user does not exist",
        "error.db_fk_institution": "Referenced institution does not exist",
        "error.db_fk_currency": "Referenced credit currency does not exist",
        "error.db_fk_subscription": "Referenced subscription does not exist",
        "error.db_fk_plan": "Referenced plan does not exist",
        "error.db_fk_payment": "Referenced payment attempt does not exist",
        "error.db_fk_generic": "Referenced record does not exist",
        "error.db_notnull_modified_by": "Modified by field is required",
        "error.db_notnull_currency_code": "Currency code is required",
        "error.db_notnull_currency_name": "Currency name is required",
        "error.db_notnull_username": "Username is required",
        "error.db_notnull_email": "Email is required",
        "error.db_notnull_generic": "Required field is missing",
        "error.db_check_violation": "Invalid data provided violates business rules",
        "error.db_invalid_uuid": "Invalid UUID format",
        "error.db_invalid_format": "Invalid data format",
        "error.db_generic": "Database error during {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Reset Your Vianda Password",
        "email.subject_b2b_invite": "You've been invited to Vianda – Set your password",
        "email.subject_benefit_invite": "{employer_name} has set up a Vianda meal benefit for you",
        "email.subject_email_change_verify": "Confirm your new email for Vianda",
        "email.subject_email_change_confirm": "Your Vianda account email was changed",
        "email.subject_username_recovery": "Your Vianda username",
        "email.subject_signup_verify": "Verify your email to complete signup",
        "email.subject_welcome": "Welcome to Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Welcome to Vianda — let's set up your restaurant",
        "email.subject_onboarding_need_help": "Need help finishing your Vianda setup?",
        "email.subject_onboarding_incomplete": "Your Vianda setup is almost there",
        "email.subject_onboarding_complete": "Your restaurant is live on Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Start your Vianda subscription",
        "email.subject_customer_missing_out": "You're missing out on Vianda",
        "email.subject_benefit_waiting": "{employer_name} is covering your meals — activate now",
        "email.subject_benefit_reminder": "Your meal benefit from {employer_name} is still waiting",
        # Promotional
        "email.subject_subscription_promo": "Special offer: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Too many requests. Please try again later.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.* — pre-route errors (set by catch-all handler, K3)
        "request.not_found": "The requested resource was not found.",
        "request.method_not_allowed": "This HTTP method is not allowed for this endpoint.",
        "request.malformed_body": "The request body could not be parsed.",
        "request.too_large": "The request payload is too large.",
        "request.rate_limited": "Too many requests. Please try again in {retry_after_seconds} seconds.",
        # legacy.* — transitional; wrapping handler maps unmigrated bare-string raises
        "legacy.uncoded": "{message}",
        # validation.* — emitted by RequestValidationError handler (K3/K5)
        "validation.field_required": "This field is required.",
        "validation.invalid_format": "The value has an invalid format.",
        "validation.value_too_short": "The value is too short.",
        "validation.value_too_long": "The value is too long.",
        "validation.custom": "{msg}",
        # auth.*
        "auth.invalid_token": "Authentication token is invalid or expired.",
        "auth.captcha_required": "CAPTCHA verification is required.",
        # subscription.*
        "subscription.already_active": "This subscription is already active.",
    },
    "es": {
        # Auth / user errors
        "error.user_not_found": "Usuario no encontrado.",
        "error.duplicate_email": "Ya existe una cuenta con este correo electrónico.",
        "error.invalid_credentials": "Usuario o contraseña inválidos.",
        "error.email_change_code_expired": "El código de verificación ha expirado. Solicita uno nuevo.",
        "error.email_change_code_invalid": "Código de verificación inválido.",
        # Auth / user alerts
        "alert.email_verified": "Correo electrónico verificado exitosamente.",
        "alert.email_change_requested": "Se ha enviado un código de verificación a {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} no encontrado/a",
        "error.entity_not_found_by_id": "{entity} con ID {id} no encontrado/a",
        "error.entity_creation_failed": "Error al crear {entity}",
        "error.entity_update_failed": "Error al actualizar {entity}",
        "error.entity_deletion_failed": "Error al eliminar {entity}",
        "error.entity_operation_failed": "{entity} no encontrado/a o la operación {operation} falló",
        # Database constraint errors
        "error.db_duplicate_key": "Ya existe un registro con este valor",
        "error.db_duplicate_email": "Ya existe un usuario con este correo electrónico",
        "error.db_duplicate_username": "Ya existe un usuario con este nombre de usuario",
        "error.db_duplicate_market": "Ya existe un mercado para este país",
        "error.db_duplicate_currency": "Ya existe una moneda con este código",
        "error.db_duplicate_institution": "Ya existe una institución con este nombre",
        "error.db_duplicate_restaurant": "Ya existe un restaurante con este nombre",
        "error.db_fk_user": "El usuario referenciado no existe",
        "error.db_fk_institution": "La institución referenciada no existe",
        "error.db_fk_currency": "La moneda referenciada no existe",
        "error.db_fk_subscription": "La suscripción referenciada no existe",
        "error.db_fk_plan": "El plan referenciado no existe",
        "error.db_fk_payment": "El intento de pago referenciado no existe",
        "error.db_fk_generic": "El registro referenciado no existe",
        "error.db_notnull_modified_by": "El campo modificado por es obligatorio",
        "error.db_notnull_currency_code": "El código de moneda es obligatorio",
        "error.db_notnull_currency_name": "El nombre de moneda es obligatorio",
        "error.db_notnull_username": "El nombre de usuario es obligatorio",
        "error.db_notnull_email": "El correo electrónico es obligatorio",
        "error.db_notnull_generic": "Falta un campo obligatorio",
        "error.db_check_violation": "Los datos proporcionados violan las reglas de negocio",
        "error.db_invalid_uuid": "Formato de UUID inválido",
        "error.db_invalid_format": "Formato de datos inválido",
        "error.db_generic": "Error de base de datos durante {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Restablece tu contraseña de Vianda",
        "email.subject_b2b_invite": "Has sido invitado a Vianda – Configura tu contraseña",
        "email.subject_benefit_invite": "{employer_name} ha configurado un beneficio de comidas Vianda para ti",
        "email.subject_email_change_verify": "Confirma tu nuevo correo para Vianda",
        "email.subject_email_change_confirm": "Tu correo de Vianda fue actualizado",
        "email.subject_username_recovery": "Tu nombre de usuario de Vianda",
        "email.subject_signup_verify": "Verifica tu correo para completar el registro",
        "email.subject_welcome": "¡Bienvenido a Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Bienvenido a Vianda — configuremos tu restaurante",
        "email.subject_onboarding_need_help": "¿Necesitas ayuda para completar tu configuración de Vianda?",
        "email.subject_onboarding_incomplete": "Tu configuración de Vianda está casi lista",
        "email.subject_onboarding_complete": "¡Tu restaurante ya está activo en Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Activa tu suscripción en Vianda",
        "email.subject_customer_missing_out": "Te estás perdiendo Vianda",
        "email.subject_benefit_waiting": "{employer_name} cubre tus comidas — actívalo ahora",
        "email.subject_benefit_reminder": "Tu beneficio de comidas de {employer_name} te está esperando",
        # Promotional
        "email.subject_subscription_promo": "Oferta especial: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Demasiadas solicitudes. Intenta de nuevo más tarde.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.*
        "request.not_found": "El recurso solicitado no fue encontrado.",
        "request.method_not_allowed": "Este método HTTP no está permitido para este endpoint.",
        "request.malformed_body": "No se pudo interpretar el cuerpo de la solicitud.",
        "request.too_large": "El cuerpo de la solicitud es demasiado grande.",
        "request.rate_limited": "Demasiadas solicitudes. Intenta de nuevo en {retry_after_seconds} segundos.",
        # legacy.*
        "legacy.uncoded": "{message}",
        # validation.*
        "validation.field_required": "Este campo es obligatorio.",
        "validation.invalid_format": "El valor tiene un formato inválido.",
        "validation.value_too_short": "El valor es demasiado corto.",
        "validation.value_too_long": "El valor es demasiado largo.",
        "validation.custom": "{msg}",
        # auth.*
        "auth.invalid_token": "El token de autenticación es inválido o expiró.",
        "auth.captcha_required": "Se requiere verificación CAPTCHA.",
        # subscription.*
        "subscription.already_active": "Esta suscripción ya está activa.",
    },
    "pt": {
        # Auth / user errors
        "error.user_not_found": "Usuário não encontrado.",
        "error.duplicate_email": "Já existe uma conta com este e-mail.",
        "error.invalid_credentials": "Usuário ou senha inválidos.",
        "error.email_change_code_expired": "O código de verificação expirou. Solicite um novo.",
        "error.email_change_code_invalid": "Código de verificação inválido.",
        # Auth / user alerts
        "alert.email_verified": "E-mail verificado com sucesso.",
        "alert.email_change_requested": "Um código de verificação foi enviado para {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} não encontrado/a",
        "error.entity_not_found_by_id": "{entity} com ID {id} não encontrado/a",
        "error.entity_creation_failed": "Falha ao criar {entity}",
        "error.entity_update_failed": "Falha ao atualizar {entity}",
        "error.entity_deletion_failed": "Falha ao excluir {entity}",
        "error.entity_operation_failed": "{entity} não encontrado/a ou a operação {operation} falhou",
        # Database constraint errors
        "error.db_duplicate_key": "Já existe um registro com este valor",
        "error.db_duplicate_email": "Já existe um usuário com este e-mail",
        "error.db_duplicate_username": "Já existe um usuário com este nome de usuário",
        "error.db_duplicate_market": "Já existe um mercado para este país",
        "error.db_duplicate_currency": "Já existe uma moeda com este código",
        "error.db_duplicate_institution": "Já existe uma instituição com este nome",
        "error.db_duplicate_restaurant": "Já existe um restaurante com este nome",
        "error.db_fk_user": "O usuário referenciado não existe",
        "error.db_fk_institution": "A instituição referenciada não existe",
        "error.db_fk_currency": "A moeda referenciada não existe",
        "error.db_fk_subscription": "A assinatura referenciada não existe",
        "error.db_fk_plan": "O plano referenciado não existe",
        "error.db_fk_payment": "A tentativa de pagamento referenciada não existe",
        "error.db_fk_generic": "O registro referenciado não existe",
        "error.db_notnull_modified_by": "O campo modificado por é obrigatório",
        "error.db_notnull_currency_code": "O código da moeda é obrigatório",
        "error.db_notnull_currency_name": "O nome da moeda é obrigatório",
        "error.db_notnull_username": "O nome de usuário é obrigatório",
        "error.db_notnull_email": "O e-mail é obrigatório",
        "error.db_notnull_generic": "Campo obrigatório ausente",
        "error.db_check_violation": "Os dados fornecidos violam regras de negócio",
        "error.db_invalid_uuid": "Formato de UUID inválido",
        "error.db_invalid_format": "Formato de dados inválido",
        "error.db_generic": "Erro de banco de dados durante {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Redefina sua senha da Vianda",
        "email.subject_b2b_invite": "Você foi convidado para a Vianda – Configure sua senha",
        "email.subject_benefit_invite": "{employer_name} configurou um benefício de refeições Vianda para você",
        "email.subject_email_change_verify": "Confirme seu novo e-mail para a Vianda",
        "email.subject_email_change_confirm": "Seu e-mail da Vianda foi atualizado",
        "email.subject_username_recovery": "Seu nome de usuário da Vianda",
        "email.subject_signup_verify": "Verifique seu e-mail para completar o cadastro",
        "email.subject_welcome": "Bem-vindo à Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Bem-vindo à Vianda — vamos configurar seu restaurante",
        "email.subject_onboarding_need_help": "Precisa de ajuda para concluir sua configuração na Vianda?",
        "email.subject_onboarding_incomplete": "Sua configuração na Vianda está quase pronta",
        "email.subject_onboarding_complete": "Seu restaurante está ativo na Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Ative sua assinatura na Vianda",
        "email.subject_customer_missing_out": "Você está perdendo a Vianda",
        "email.subject_benefit_waiting": "{employer_name} está cobrindo suas refeições — ative agora",
        "email.subject_benefit_reminder": "Seu benefício de refeições de {employer_name} ainda está esperando",
        # Promotional
        "email.subject_subscription_promo": "Oferta especial: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Muitas solicitações. Tente novamente mais tarde.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.*
        "request.not_found": "O recurso solicitado não foi encontrado.",
        "request.method_not_allowed": "Este método HTTP não é permitido para este endpoint.",
        "request.malformed_body": "Não foi possível interpretar o corpo da solicitação.",
        "request.too_large": "O corpo da solicitação é muito grande.",
        "request.rate_limited": "Muitas solicitações. Tente novamente em {retry_after_seconds} segundos.",
        # legacy.*
        "legacy.uncoded": "{message}",
        # validation.*
        "validation.field_required": "Este campo é obrigatório.",
        "validation.invalid_format": "O valor tem um formato inválido.",
        "validation.value_too_short": "O valor é muito curto.",
        "validation.value_too_long": "O valor é muito longo.",
        "validation.custom": "{msg}",
        # auth.*
        "auth.invalid_token": "O token de autenticação é inválido ou expirou.",
        "auth.captcha_required": "Verificação CAPTCHA é necessária.",
        # subscription.*
        "subscription.already_active": "Esta assinatura já está ativa.",
    },
}


def get_message(key: str, locale: str = "en", **params: Any) -> str:
    """
    Localized message for key; falls back to English then to key string.
    Supports str.format for params when the template exists.
    """
    msg = MESSAGES.get(locale, {}).get(key) or MESSAGES["en"].get(key, key)
    if params:
        try:
            msg = msg.format(**params)
        except KeyError:
            pass
    return msg
