"""
Email Service — orchestrates email sending via pluggable provider (SMTP or SendGrid).

Templates live in app/services/email/templates/ as Jinja2 files.
Subjects are localized via app/i18n/messages.py.
"""

import os

from app.config.settings import get_settings
from app.i18n.messages import get_message
from app.services.email.provider_factory import get_email_provider
from app.services.email.template_renderer import render_email
from app.utils.log import log_email_tracking


class EmailService:
    def __init__(self):
        self._provider = get_email_provider()
        settings = get_settings()
        self.from_email = settings.EMAIL_FROM_ADDRESS or os.getenv("FROM_EMAIL", os.getenv("SMTP_USERNAME", ""))
        self.from_name = settings.EMAIL_FROM_NAME or os.getenv("FROM_NAME", "Vianda")
        self.reply_to = settings.EMAIL_REPLY_TO or None

        if not self._provider.is_configured():
            log_email_tracking("Email service not configured. Check EMAIL_PROVIDER settings in .env", level="warning")
        else:
            log_email_tracking(f"Email service configured: provider={settings.EMAIL_PROVIDER}, from={self.from_email}")

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        category: str | None = None,
    ) -> bool:
        """Send email via the configured provider."""
        return self._provider.send(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            cc=cc,
            bcc=bcc,
            reply_to=self.reply_to,
            category=category,
        )

    # =========================================================================
    # Transactional emails
    # =========================================================================

    def send_password_reset_email(
        self,
        to_email: str,
        reset_code: str,
        user_first_name: str,
        expiry_hours: int = 24,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_password_reset", locale)
        body_text, body_html = render_email(
            "transactional/password_reset",
            user_first_name=user_first_name,
            reset_code=reset_code,
            expiry_hours=expiry_hours,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_b2b_invite_email(
        self,
        to_email: str,
        reset_code: str,
        user_first_name: str | None,
        expiry_hours: int = 24,
        *,
        set_password_url_template: str | None = None,
        locale: str = "en",
    ) -> bool:
        template = set_password_url_template or get_settings().B2B_INVITE_SET_PASSWORD_URL or ""
        if template:
            set_password_url = template.replace("{code}", reset_code)
        else:
            b2b_url = (get_settings().B2B_FRONTEND_URL or "").rstrip("/")
            set_password_url = (
                f"{b2b_url}/set-password?code={reset_code}"
                if b2b_url
                else f"https://vianda-platform-dev.web.app/set-password?code={reset_code}"
            )
        first_name = user_first_name or "there"
        subject = get_message("email.subject_b2b_invite", locale)
        body_text, body_html = render_email(
            "transactional/b2b_invite",
            first_name=first_name,
            set_password_url=set_password_url,
            expiry_hours=expiry_hours,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_benefit_employee_invite_email(
        self,
        to_email: str,
        reset_code: str,
        user_first_name: str | None,
        employer_name: str = "your employer",
        expiry_hours: int = 24,
        locale: str = "en",
    ) -> bool:
        settings = get_settings()
        template = settings.BENEFIT_INVITE_SET_PASSWORD_URL or settings.B2B_INVITE_SET_PASSWORD_URL or ""
        if template:
            set_password_url = template.replace("{code}", reset_code)
        else:
            b2b_url = (settings.B2B_FRONTEND_URL or "").rstrip("/")
            set_password_url = (
                f"{b2b_url}/set-password?code={reset_code}"
                if b2b_url
                else f"https://vianda-platform-dev.web.app/set-password?code={reset_code}"
            )
        first_name = user_first_name or "there"
        subject = get_message("email.subject_benefit_invite", locale, employer_name=employer_name)
        body_text, body_html = render_email(
            "transactional/benefit_employee_invite",
            first_name=first_name,
            employer_name=employer_name,
            set_password_url=set_password_url,
            app_store_url=settings.APP_STORE_URL,
            play_store_url=settings.PLAY_STORE_URL,
            expiry_hours=expiry_hours,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_email_change_verification_email(
        self,
        to_email: str,
        verification_code: str,
        user_first_name: str | None,
        expiry_hours: int = 24,
        locale: str = "en",
    ) -> bool:
        first_name = user_first_name or "there"
        subject = get_message("email.subject_email_change_verify", locale)
        body_text, body_html = render_email(
            "transactional/email_change_verify",
            first_name=first_name,
            verification_code=verification_code,
            expiry_hours=expiry_hours,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_email_change_confirmation_email(
        self,
        to_email: str,
        user_first_name: str | None,
        new_email: str,
        locale: str = "en",
    ) -> bool:
        first_name = user_first_name or "there"
        subject = get_message("email.subject_email_change_confirm", locale)
        body_text, body_html = render_email(
            "transactional/email_change_confirm",
            first_name=first_name,
            new_email=new_email,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_username_recovery_email(
        self,
        to_email: str,
        username: str,
        user_first_name: str | None = None,
        locale: str = "en",
    ) -> bool:
        first_name = user_first_name or "there"
        subject = get_message("email.subject_username_recovery", locale)
        body_text, body_html = render_email(
            "transactional/username_recovery",
            first_name=first_name,
            username=username,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_signup_verification_email(
        self,
        to_email: str,
        verification_code: str,
        user_first_name: str | None = None,
        expiry_hours: int = 24,
        locale: str = "en",
    ) -> bool:
        first_name = user_first_name or "there"
        log_email_tracking(f"Signup verification: to={to_email}, expiry_hours={expiry_hours}")
        subject = get_message("email.subject_signup_verify", locale)
        body_text, body_html = render_email(
            "transactional/signup_verify",
            first_name=first_name,
            verification_code=verification_code,
            expiry_hours=expiry_hours,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    def send_welcome_email(self, to_email: str, user_first_name: str, locale: str = "en") -> bool:
        subject = get_message("email.subject_welcome", locale)
        body_text, body_html = render_email("transactional/welcome", user_first_name=user_first_name)
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="transactional"
        )

    # =========================================================================
    # Supplier/employer onboarding outreach
    # =========================================================================

    def send_onboarding_getting_started_email(
        self,
        to_email: str,
        institution_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_onboarding_getting_started", locale)
        b2b_url = get_settings().B2B_FRONTEND_URL or "https://b2b.vianda.market"
        body_text, body_html = render_email(
            "onboarding/getting_started",
            institution_name=institution_name,
            b2b_url=b2b_url,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="onboarding"
        )

    def send_onboarding_need_help_email(
        self,
        to_email: str,
        institution_name: str,
        completion_percentage: int,
        missing_steps: list[str],
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_onboarding_need_help", locale)
        b2b_url = get_settings().B2B_FRONTEND_URL or "https://b2b.vianda.market"
        steps_html = "".join(f"<li>{s.replace('_', ' ').title()}</li>" for s in missing_steps)
        body_text, body_html = render_email(
            "onboarding/need_help",
            institution_name=institution_name,
            completion_percentage=completion_percentage,
            steps_html=steps_html,
            b2b_url=b2b_url,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="onboarding"
        )

    def send_onboarding_incomplete_email(
        self,
        to_email: str,
        institution_name: str,
        completion_percentage: int,
        missing_steps: list[str],
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_onboarding_incomplete", locale)
        b2b_url = get_settings().B2B_FRONTEND_URL or "https://b2b.vianda.market"
        steps_html = "".join(f"<li>{s.replace('_', ' ').title()}</li>" for s in missing_steps)
        body_text, body_html = render_email(
            "onboarding/incomplete",
            institution_name=institution_name,
            completion_percentage=completion_percentage,
            steps_html=steps_html,
            b2b_url=b2b_url,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="onboarding"
        )

    def send_onboarding_complete_email(
        self,
        to_email: str,
        institution_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_onboarding_complete", locale)
        body_text, body_html = render_email("onboarding/complete", institution_name=institution_name)
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="onboarding"
        )

    # =========================================================================
    # Customer engagement emails
    # =========================================================================

    def _customer_email_context(self) -> dict:
        """Common context for customer engagement email templates."""
        settings = get_settings()
        return {
            "app_store_url": settings.APP_STORE_URL,
            "play_store_url": settings.PLAY_STORE_URL,
            "app_deep_link": f"{settings.APP_DEEP_LINK_BASE}plans" if settings.APP_DEEP_LINK_BASE else "",
        }

    def send_customer_subscribe_email(
        self,
        to_email: str,
        user_first_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_customer_subscribe", locale)
        body_text, body_html = render_email(
            "customer/subscribe_prompt",
            locale=locale,
            user_first_name=user_first_name,
            **self._customer_email_context(),
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="customer-engagement"
        )

    def send_customer_missing_out_email(
        self,
        to_email: str,
        user_first_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_customer_missing_out", locale)
        body_text, body_html = render_email(
            "customer/missing_out",
            locale=locale,
            user_first_name=user_first_name,
            **self._customer_email_context(),
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="customer-engagement"
        )

    def send_benefit_waiting_email(
        self,
        to_email: str,
        user_first_name: str,
        employer_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_benefit_waiting", locale, employer_name=employer_name)
        body_text, body_html = render_email(
            "customer/benefit_waiting",
            locale=locale,
            user_first_name=user_first_name,
            employer_name=employer_name,
            **self._customer_email_context(),
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="customer-engagement"
        )

    def send_benefit_reminder_email(
        self,
        to_email: str,
        user_first_name: str,
        employer_name: str,
        locale: str = "en",
    ) -> bool:
        subject = get_message("email.subject_benefit_reminder", locale, employer_name=employer_name)
        body_text, body_html = render_email(
            "customer/benefit_reminder",
            locale=locale,
            user_first_name=user_first_name,
            employer_name=employer_name,
            **self._customer_email_context(),
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="customer-engagement"
        )

    # =========================================================================
    # Promotional emails
    # =========================================================================

    def send_subscription_promo_email(
        self,
        to_email: str,
        user_first_name: str,
        promo_details: str,
        locale: str = "en",
    ) -> bool:
        settings = get_settings()
        subject = get_message("email.subject_subscription_promo", locale, promo_details=promo_details)
        body_text, body_html = render_email(
            "promotional/subscription_promo",
            user_first_name=user_first_name,
            promo_details=promo_details,
            app_store_url=settings.APP_STORE_URL,
            play_store_url=settings.PLAY_STORE_URL,
        )
        return self.send_email(
            to_email=to_email, subject=subject, body_text=body_text, body_html=body_html, category="promotional"
        )

    def is_configured(self) -> bool:
        return self._provider.is_configured()


# Singleton instance
email_service = EmailService()
