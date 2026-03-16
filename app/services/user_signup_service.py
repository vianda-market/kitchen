"""
User Signup Business Logic Service

This service contains all business logic related to user signup operations,
including password hashing, role assignment, institution assignment, and validation.
Customer signup supports email verification: request stores pending data and sends
verification email; verify step creates the user in user_info.
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
import psycopg2.extensions
import psycopg2.extras

from app.dto.models import UserDTO
from app.services.entity_service import (
    create_user_with_validation,
    get_user_by_email,
    get_user_by_username,
    set_user_market_assignments,
)
from app.services.email_service import email_service
from app.auth.security import create_access_token
from app.utils.log import log_info, log_warning, log_error, log_email_tracking
from app.security.institution_scope import InstitutionScope
from app.config import RoleType, RoleName, Status
from app.config.settings import get_vianda_customers_institution_id, get_vianda_enterprises_institution_id
from app.services.market_service import market_service, GLOBAL_MARKET_ID, is_global_market
from app.services.crud_service import city_service
from app.config.supported_cities import GLOBAL_CITY_ID, is_global_city
from app.utils.country import normalize_country_code


class UserSignupService:
    """Service for handling user signup business logic. Institution IDs come from config (must match seed.sql)."""

    @classmethod
    def get_institutions_not_for_restaurant(cls) -> tuple:
        """Institution IDs that must not be assigned to a restaurant (Vianda Customers + Vianda Enterprises)."""
        return (get_vianda_customers_institution_id(), get_vianda_enterprises_institution_id())
    # Role constants - using enum values instead of UUIDs
    CUSTOMER_ROLE_TYPE = RoleType.CUSTOMER
    CUSTOMER_ROLE_NAME = RoleName.COMENSAL
    # System bot user for automated operations (customer signup modified_by, etc.). Seeded in seed.sql; keeps audit trail separate from super_admin.
    BOT_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    # Default market for new customers (US - must match seed.sql)
    DEFAULT_CUSTOMER_MARKET_ID = UUID("66666666-6666-6666-6666-666666666666")
    # Email verification code (6-digit)
    SIGNUP_VERIFICATION_CODE_EXPIRY_HOURS = 24

    def __init__(self):
        pass

    @staticmethod
    def _is_customer_comensal(user_data: Dict[str, Any]) -> bool:
        """True if role_type is Customer and role_name is Comensal (enum or string)."""
        rt = user_data.get("role_type")
        rn = user_data.get("role_name")
        rt_str = (rt.value if hasattr(rt, "value") else str(rt)) if rt else ""
        rn_str = (rn.value if hasattr(rn, "value") else str(rn)) if rn else ""
        return rt_str == "Customer" and rn_str == "Comensal"

    @staticmethod
    def _is_internal(user_data: Dict[str, Any]) -> bool:
        """True if role_type is Internal (enum or string)."""
        rt = user_data.get("role_type")
        rt_str = (rt.value if hasattr(rt, "value") else str(rt)) if rt else ""
        return rt_str == "Internal"

    def process_customer_signup(
        self, 
        user_data: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> UserDTO:
        """
        Process customer self-registration with business rules.
        
        Args:
            user_data: User data dictionary from signup form
            db: Database connection
            
        Returns:
            Created user DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Validate signup data
        self._validate_signup_data(user_data)
        
        # Resolve country_code to market_id (B2C signup uses country_code)
        self._resolve_country_code_to_market_id(user_data, db)
        
        # Process password security
        self._process_password_security(user_data)
        
        # Apply business rules for customer signup (market_id must be in user_data at this point)
        self._apply_customer_signup_rules(user_data, db)
        
        # Create user with validation
        new_user = create_user_with_validation(user_data, db)
        
        log_info(f"Customer self-signed up: {new_user.user_id}")
        return new_user
    
    def process_admin_user_creation(
        self, 
        user_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection,
        *,
        scope: Optional[InstitutionScope] = None
    ) -> UserDTO:
        """
        Process admin user creation with business rules.
        
        Args:
            user_data: User data dictionary
            current_user: Current admin user information
            db: Database connection
            
        Returns:
            Created user DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Validate user data
        self._validate_user_data(user_data)
        
        # Process password security
        self._process_password_security(user_data)
        # Track invite flow: no password provided -> send invite email after create
        use_invite_flow = "hashed_password" not in user_data
        
        # Apply admin creation rules
        self._apply_admin_creation_rules(user_data, current_user)

        # Customer+Comensal: always assign Vianda Customers; ignore any client-sent institution_id
        if self._is_customer_comensal(user_data):
            user_data["institution_id"] = get_vianda_customers_institution_id()
            log_info("Assigned Vianda Customers institution for Customer + Comensal user")

        # Internal: always assign Vianda Enterprises; ignore any client-sent institution_id
        if self._is_internal(user_data):
            user_data["institution_id"] = get_vianda_enterprises_institution_id()
            log_info("Assigned Vianda Enterprises institution for Internal user")

        # Enforce institution scope for non-global users
        self._apply_scope_constraints(user_data, scope)

        # Resolve and validate market_id (default Global for Admin/Super Admin/Supplier Admin; require for Manager/Operator; Managers cannot assign Global)
        self._resolve_market_id_for_admin_creation(user_data, current_user, db)
        # v2: if market_ids provided, use first as primary and persist assignments after create
        market_ids_list = user_data.pop("market_ids", None)
        if market_ids_list:
            user_data["market_id"] = market_ids_list[0]
        # Supplier and Employer: user's market must be within institution's market(s)
        self._ensure_user_market_within_institution(user_data, db)
        # Internal or Supplier: default city_id to Global when not provided
        rt_str = (user_data.get("role_type").value if hasattr(user_data.get("role_type"), "value") else str(user_data.get("role_type") or "")) if user_data.get("role_type") else ""
        rn_str = (user_data.get("role_name").value if hasattr(user_data.get("role_name"), "value") else str(user_data.get("role_name") or "")) if user_data.get("role_name") else ""
        if (rt_str == "Internal" or rt_str == "Supplier") and not user_data.get("city_id"):
            user_data["city_id"] = GLOBAL_CITY_ID
            log_info(f"Defaulted city_id to Global for {rt_str}/{rn_str}")
        # Customer+Comensal created via B2B: require city_id, reject Global
        if self._is_customer_comensal(user_data):
            if not user_data.get("city_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="city_id is required for Customer (Comensal). Use GET /api/v1/cities/?country_code=... (not the Global city).",
                )
            cid = user_data["city_id"] if isinstance(user_data["city_id"], UUID) else UUID(str(user_data["city_id"]))
            if is_global_city(cid):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Global city cannot be assigned to Customer (Comensal).",
                )
        # Create user with validation
        new_user = create_user_with_validation(user_data, db, scope=scope)
        if market_ids_list:
            from app.services.entity_service import set_user_market_assignments
            set_user_market_assignments(new_user.user_id, market_ids_list, db)
        log_info(f"Admin created user: {new_user.user_id}")
        if use_invite_flow:
            self._send_b2b_invite_email(new_user.user_id, new_user.email, new_user.first_name, db)
        return new_user
    
    def _validate_signup_data(self, user_data: Dict[str, Any]) -> None:
        """
        Validate customer signup data.
        
        Args:
            user_data: User data dictionary
            
        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["email", "password"]
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate email format (basic validation)
        email = user_data.get("email", "").strip().lower()
        if "@" not in email or "." not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password strength (basic validation)
        password = user_data.get("password", "")
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
    
    def _validate_user_data(self, user_data: Dict[str, Any]) -> None:
        """
        Validate general user data for admin creation.
        
        Args:
            user_data: User data dictionary
            
        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["email"]
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate email format
        email = user_data.get("email", "").strip().lower()
        if "@" not in email or "." not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate required fields for admin creation (institution_id optional for Customer+Comensal)
        if not user_data.get("role_type") or not user_data.get("role_name"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role type and role name are required for user creation"
            )

        # Customer+Comensal and Internal get institution_id assigned by the backend
        if not self._is_customer_comensal(user_data) and not self._is_internal(user_data) and not user_data.get("institution_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Institution ID is required for user creation (except Customer+Comensal and Internal)"
            )

    def _process_password_security(self, user_data: Dict[str, Any]) -> None:
        """
        Process password security (hashing and cleanup).
        When password is provided and non-empty, hash it. When omitted or None (B2B invite flow), skip.
        
        Args:
            user_data: User data dictionary (modified in place)
        """
        pwd = user_data.get("password")
        if pwd and isinstance(pwd, str) and pwd.strip():
            from app.auth.security import hash_password
            hashed_pwd = hash_password(pwd)
            user_data["hashed_password"] = hashed_pwd
            del user_data["password"]  # Remove the plain password
            
            log_info(f"🔐 Password hashed successfully:")
            log_info(f"   Hash length: {len(hashed_pwd)}")
            log_info(f"   Hash starts with: {hashed_pwd[:20]}...")
    
    def _resolve_country_code_to_market_id(self, user_data: Dict[str, Any], db: psycopg2.extensions.connection) -> None:
        """
        Resolve country_code to market_id for B2C signup. Requires active, non-archived, non-Global market.
        Raises HTTPException 400 if missing, invalid, archived, or Global.
        """
        country_code_raw = user_data.get("country_code")
        if not country_code_raw or not str(country_code_raw).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="country_code is required. Use GET /api/v1/leads/markets for valid country codes.",
            )
        country_code = normalize_country_code(country_code_raw)
        if not country_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid country_code. Use GET /api/v1/leads/markets for valid country codes.",
            )
        market = market_service.get_by_country_code(country_code)
        if not market:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No market found for country {country_code}. Use GET /api/v1/leads/markets for supported countries.",
            )
        if market.get("is_archived"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Market for {country_code} is archived. Use GET /api/v1/leads/markets for active countries.",
            )
        market_id = market["market_id"] if isinstance(market["market_id"], UUID) else UUID(str(market["market_id"]))
        if is_global_market(market_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Global Marketplace cannot be assigned to B2C customers. Use a country from GET /api/v1/leads/markets.",
            )
        user_data["market_id"] = market_id

    def _validate_and_resolve_city_id(self, user_data: Dict[str, Any], db: psycopg2.extensions.connection) -> None:
        """
        Require and validate city for B2C signup. Accepts city_id or city_name.
        If city_name provided, resolve to city_id by matching name (case-insensitive) in market's country.
        city_id must not be Global; city must exist, not archived, and match market's country.
        """
        city_id_raw = user_data.get("city_id")
        city_name_raw = (user_data.get("city_name") or "").strip()

        if city_id_raw is not None:
            city_id = city_id_raw if isinstance(city_id_raw, UUID) else UUID(str(city_id_raw))
        elif city_name_raw:
            market_id = user_data.get("market_id")
            if not market_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="market_id is required before resolving city_name.",
                )
            market = market_service.get_by_id(market_id if isinstance(market_id, UUID) else UUID(str(market_id)))
            if not market:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid market_id. Use GET /api/v1/leads/markets.",
                )
            market_country = (market.get("country_code") or "").strip().upper()
            cities = city_service.get_all_by_field("country_code", market_country, db, scope=None)
            city_name_lower = city_name_raw.lower()
            matched = None
            for c in cities:
                if c.city_id != GLOBAL_CITY_ID and not c.is_archived and (c.name or "").strip().lower() == city_name_lower:
                    matched = c
                    break
            if not matched:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"City '{city_name_raw}' not found for country {market_country}. Use GET /api/v1/leads/cities?country_code={market_country}.",
                )
            city_id = matched.city_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either city_id or city_name is required. Use GET /api/v1/leads/cities?country_code=... for city names.",
            )

        if is_global_city(city_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Global city cannot be assigned to B2C customers. Use a city from GET /api/v1/cities/?country_code=... for your market.",
            )
        city = city_service.get_by_id(city_id, db, scope=None)
        if not city:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or archived city_id. Use GET /api/v1/cities/?country_code=... to get valid city UUIDs.",
            )
        if city.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or archived city_id. Use GET /api/v1/cities/?country_code=... to get valid city UUIDs.",
            )
        market_id = user_data.get("market_id")
        if market_id:
            market = market_service.get_by_id(market_id if isinstance(market_id, UUID) else UUID(str(market_id)))
            if market:
                market_country = (market.get("country_code") or "").strip().upper()
                city_country = (city.country_code or "").strip().upper()
                if market_country != city_country:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"City must be in the same country as your market. City country: {city_country}, market country: {market_country}.",
                    )
        user_data["city_id"] = city_id

    def _apply_customer_signup_rules(self, user_data: Dict[str, Any], db: Optional[psycopg2.extensions.connection] = None) -> None:
        """
        Apply business rules for customer self-registration.
        market_id must already be set (from pending row at verify, or from client at request). No default.

        Args:
            user_data: User data dictionary (modified in place)
            db: Optional DB connection for re-validation at verify
        """
        # Override to seeded values for customer signup
        user_data["institution_id"] = get_vianda_customers_institution_id()
        user_data["role_type"] = self.CUSTOMER_ROLE_TYPE
        user_data["role_name"] = self.CUSTOMER_ROLE_NAME
        user_data["modified_by"] = self.BOT_USER_ID

        # Ensure email is lowercase
        if "email" in user_data:
            user_data["email"] = user_data["email"].strip().lower()

        # Set default values for customer signup
        user_data.setdefault("is_archived", False)
        user_data.setdefault("status", Status.ACTIVE)

        # market_id is required; must come from client (request) or pending row (verify)
        if user_data.get("market_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="market_id is required for customer signup.",
            )
        market_id = user_data["market_id"] if isinstance(user_data["market_id"], UUID) else UUID(str(user_data["market_id"]))
        if db:
            market = market_service.get_by_id(market_id)
            if not market or market.get("is_archived"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or archived market_id from signup. Please request a new verification code.",
                )
        user_data["market_id"] = market_id

        # city_id is required; must come from client (request) or pending row (verify)
        if user_data.get("city_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="city_id is required for customer signup.",
            )
        city_id_raw = user_data["city_id"]
        city_id = city_id_raw if isinstance(city_id_raw, UUID) else UUID(str(city_id_raw))
        if is_global_city(city_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Global city cannot be assigned to B2C customers.",
            )
        if db:
            city = city_service.get_by_id(city_id, db, scope=None)
            if not city or city.is_archived:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or archived city_id from signup. Please request a new verification code.",
                )
        user_data["city_id"] = city_id

        log_info(f"Applied customer signup rules: institution={get_vianda_customers_institution_id()}, market_id={market_id}, city_id={city_id}, role_type={self.CUSTOMER_ROLE_TYPE.value}, role_name={self.CUSTOMER_ROLE_NAME.value}")
    
    def _apply_admin_creation_rules(self, user_data: Dict[str, Any], current_user: Dict[str, Any]) -> None:
        """
        Apply business rules for admin user creation.
        
        Args:
            user_data: User data dictionary (modified in place)
            current_user: Current admin user information
        """
        # Set modified_by to current admin user
        user_data["modified_by"] = current_user["user_id"]
        
        # Ensure email is lowercase
        if "email" in user_data:
            user_data["email"] = user_data["email"].strip().lower()
        
        # Set default values
        user_data.setdefault("is_archived", False)
        if "hashed_password" not in user_data:
            user_data["status"] = Status.INACTIVE  # Invite flow: Inactive until password set
        else:
            user_data.setdefault("status", Status.ACTIVE)
        
        # If no password/hash provided, generate random hash (B2B invite flow: user sets password via email link)
        if "hashed_password" not in user_data:
            import secrets
            import string
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            user_data["password"] = temp_password
            self._process_password_security(user_data)
            log_info("Generated placeholder hash for B2B invite flow (user will set password via email link)")
        
        log_info(f"Applied admin creation rules: modified_by={current_user['user_id']}")

    def _send_b2b_invite_email(
        self,
        user_id: UUID,
        email: str,
        first_name: Optional[str],
        db: psycopg2.extensions.connection,
    ) -> None:
        """
        Send B2B invite email with link to set password. Generates 6-digit code,
        stores in credential_recovery, sends email. User sets password via POST /auth/reset-password.
        """
        invite_expiry_hours = 24
        reset_code = str(secrets.randbelow(1_000_000)).zfill(6)
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=invite_expiry_hours)
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                UPDATE credential_recovery
                SET is_used = TRUE, is_archived = TRUE
                WHERE user_id = %s AND is_used = FALSE AND is_archived = FALSE
                """,
                (str(user_id),),
            )
            cursor.execute(
                """
                INSERT INTO credential_recovery (
                    user_id, recovery_code, token_expiry, is_used, status, is_archived
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (str(user_id), reset_code, expiry_time, False, Status.ACTIVE.value, False),
            )
            db.commit()
        log_email_tracking(f"B2B invite email: sending to {email} (user_id={user_id})")
        sent = email_service.send_b2b_invite_email(
            to_email=email,
            reset_code=reset_code,
            user_first_name=first_name,
            expiry_hours=invite_expiry_hours,
        )
        if sent:
            log_email_tracking(f"B2B invite email sent to {email}")
        else:
            log_error(f"Failed to send B2B invite email to {email}")

    def resend_b2b_invite_email(
        self,
        user_id: UUID,
        email: str,
        first_name: Optional[str],
        db: psycopg2.extensions.connection,
    ) -> None:
        """
        Resend B2B invite email with set-password link. Generates new 6-digit code,
        invalidates prior unused codes, stores new code in credential_recovery, sends email.
        User sets password via POST /auth/reset-password.
        """
        self._send_b2b_invite_email(user_id, email, first_name, db)

    def _resolve_market_id_for_admin_creation(
        self,
        user_data: Dict[str, Any],
        current_user: Dict[str, Any],
        db: psycopg2.extensions.connection,
    ) -> None:
        """
        Resolve and validate market_id for admin-created users. Default Global for Admin/Super Admin/Supplier Admin.
        Require market_id for Manager/Operator; only Super Admin can assign Global to them.
        """
        from app.services.market_service import is_global_market
        role_type = user_data.get("role_type")
        role_name = user_data.get("role_name")
        rt_str = (role_type.value if hasattr(role_type, "value") else str(role_type)) if role_type else ""
        rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
        creator_rn = (current_user.get("role_name") or "").value if hasattr(current_user.get("role_name"), "value") else str(current_user.get("role_name") or "")
        creator_is_super_admin = creator_rn == "Super Admin"

        # Admin, Super Admin (Internal) -> default to Global if not provided. Supplier Admin and Employer -> default to institution's market
        if rt_str == "Internal" and rn_str in ("Admin", "Super Admin"):
            if not user_data.get("market_id"):
                user_data["market_id"] = GLOBAL_MARKET_ID
                log_info(f"Defaulted market_id to Global for {rt_str}/{rn_str}")
        elif (rt_str == "Supplier" and rn_str == "Admin") or rt_str == "Employer":
            if not user_data.get("market_id"):
                inst_id = user_data.get("institution_id")
                if inst_id:
                    inst_id = inst_id if isinstance(inst_id, UUID) else UUID(str(inst_id))
                    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute(
                            "SELECT market_id FROM institution_info WHERE institution_id = %s",
                            (str(inst_id),),
                        )
                        row = cursor.fetchone()
                    if row and row.get("market_id"):
                        user_data["market_id"] = row["market_id"] if isinstance(row["market_id"], UUID) else UUID(str(row["market_id"]))
                        log_info(f"Defaulted market_id to institution's market for {rt_str}/{rn_str}")
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="institution_id is required for Supplier and Employer; institution must have a market_id",
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="institution_id is required for Supplier and Employer",
                    )

        market_id_raw = user_data.get("market_id")
        if market_id_raw is not None and not isinstance(market_id_raw, UUID):
            market_id_raw = UUID(str(market_id_raw))
        market_id = market_id_raw

        # Manager / Operator (Internal): market_id required; cannot be Global unless creator is Super Admin
        if rt_str == "Internal" and rn_str in ("Manager", "Operator"):
            if not market_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="market_id is required for Manager and Operator",
                )
            if is_global_market(market_id) and not creator_is_super_admin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only Super Admin can assign Global market to Manager or Operator",
                )

        # Customer: default already set in _apply_customer_signup_rules; admin-created Customer gets default US if not provided
        if rt_str == "Customer" and not market_id:
            user_data["market_id"] = self.DEFAULT_CUSTOMER_MARKET_ID
            log_info(f"Defaulted market_id to US for Customer")

        market_id = user_data.get("market_id")
        if market_id is not None and not isinstance(market_id, UUID):
            market_id = UUID(str(market_id))
            user_data["market_id"] = market_id

        if not market_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="market_id is required",
            )

        # Validate market exists and is not archived
        market = market_service.get_by_id(market_id)
        if not market:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Market not found: {market_id}",
            )
        if market.get("is_archived"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Market is archived: {market_id}",
            )

    def _ensure_user_market_within_institution(
        self,
        user_data: Dict[str, Any],
        db: psycopg2.extensions.connection,
    ) -> None:
        """
        For Supplier and Employer, ensure user's market_id is within the institution's assigned market(s).
        Raises 400 if user is Supplier or Employer and market_id does not match institution's market_id (v1: single market).
        """
        rt = user_data.get("role_type")
        rn = user_data.get("role_name")
        rt_str = (rt.value if hasattr(rt, "value") else str(rt)) if rt else ""
        rn_str = (rn.value if hasattr(rn, "value") else str(rn)) if rn else ""
        is_supplier = rt_str == "Supplier"
        is_employer = rt_str == "Employer"
        if not is_supplier and not is_employer:
            return
        institution_id = user_data.get("institution_id")
        if not institution_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="institution_id is required for Supplier and Employer",
            )
        institution_id = institution_id if isinstance(institution_id, UUID) else UUID(str(institution_id))
        market_id = user_data.get("market_id")
        if not market_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="market_id is required for Supplier and Employer and must match the institution's market",
            )
        market_id = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT market_id FROM institution_info WHERE institution_id = %s",
                (str(institution_id),),
            )
            row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Institution not found",
            )
        inst_market_id = row["market_id"]
        if isinstance(inst_market_id, str):
            inst_market_id = UUID(inst_market_id)
        if market_id != inst_market_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier and Employer users must be assigned the same market as their institution. "
                       "User market_id does not match institution's market_id.",
            )

    def _apply_scope_constraints(
        self,
        user_data: Dict[str, Any],
        scope: Optional[InstitutionScope]
    ) -> None:
        """
        Apply institution scoping constraints for admin-created users.

        Args:
            user_data: User data dictionary (modified in place)
            scope: Institution scope for the current admin
        """
        if not scope or scope.is_global:
            return

        if not scope.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: missing institution scope"
            )

        target_institution = user_data.get("institution_id")
        if target_institution:
            scope.enforce(target_institution)
        else:
            user_data["institution_id"] = UUID(scope.institution_id)
    
    def validate_user_permissions(
        self, 
        current_user: Dict[str, Any], 
        target_institution_id: Optional[UUID] = None
    ) -> None:
        """
        Validate user permissions for user creation.
        
        Args:
            current_user: Current user information
            target_institution_id: Target institution ID (if creating for specific institution)
            
        Raises:
            HTTPException: For permission failures
        """
        # Basic permission check - user must be authenticated
        if not current_user or not current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Additional permission checks can be added here based on role/institution
        # For now, we'll allow any authenticated user to create users
        # This can be enhanced with role-based access control
        
        log_info(f"User permissions validated for user creation: {current_user['user_id']}")
    
    def get_signup_constants(self) -> Dict[str, UUID]:
        """
        Get signup constants for external use.
        
        Returns:
            Dictionary of signup constants
        """
        return {
            "customer_institution": get_vianda_customers_institution_id(),
            "customer_role_type": self.CUSTOMER_ROLE_TYPE.value,
            "customer_role_name": self.CUSTOMER_ROLE_NAME.value,
            "bot_user_id": self.BOT_USER_ID
        }

    def request_customer_signup(
        self,
        user_data: Dict[str, Any],
        db: psycopg2.extensions.connection,
    ) -> Dict[str, Any]:
        """
        Handle signup request: validate, store pending signup, send verification email.
        If email is already registered, return same success message (no email sent) to avoid enumeration.
        If username is already taken, raise 400.
        """
        self._validate_signup_data(user_data)
        self._resolve_country_code_to_market_id(user_data, db)
        self._validate_and_resolve_city_id(user_data, db)
        self._process_password_security(user_data)
        email = user_data.get("email", "").strip().lower()
        username = user_data.get("username", "").strip()

        if get_user_by_username(username, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
        if get_user_by_email(email, db):
            return {
                "success": True,
                "message": "This email is already registered. Please log in.",
                "already_registered": True,
            }

        verification_code = str(secrets.randbelow(1_000_000)).zfill(6)
        expiry = datetime.now(timezone.utc) + timedelta(hours=self.SIGNUP_VERIFICATION_CODE_EXPIRY_HOURS)

        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                DELETE FROM pending_customer_signup
                WHERE email = %s AND used = FALSE
                """,
                (email,),
            )
            cursor.execute(
                """
                INSERT INTO pending_customer_signup (
                    email, verification_code, token_expiry,
                    username, hashed_password, first_name, last_name, cellphone, market_id, city_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    email,
                    verification_code,
                    expiry,
                    username,
                    user_data["hashed_password"],
                    user_data.get("first_name"),
                    user_data.get("last_name"),
                    user_data.get("cellphone"),
                    str(user_data["market_id"]),
                    str(user_data["city_id"]),
                ),
            )
            db.commit()

        log_email_tracking(f"Requesting signup verification email to {email} (pending signup stored)")
        sent = email_service.send_signup_verification_email(
            to_email=email,
            verification_code=verification_code,
            user_first_name=user_data.get("first_name"),
            expiry_hours=self.SIGNUP_VERIFICATION_CODE_EXPIRY_HOURS,
        )
        if sent:
            log_email_tracking(f"Signup verification email sent to {email}")
        else:
            log_email_tracking(
                f"Signup verification email FAILED to send to {email}. "
                "Check SMTP_USERNAME/SMTP_PASSWORD in .env and server logs above for SMTP errors.",
                level="error",
            )
        log_email_tracking(f"Pending signup created for email {email}")
        return {
            "success": True,
            "message": "A verification code has been sent to your email.",
            "already_registered": False,
        }

    def verify_and_complete_signup(
        self,
        code: str,
        db: psycopg2.extensions.connection,
    ) -> Tuple[UserDTO, str]:
        """
        Load pending signup by verification code; if valid and not expired, create user and mark code used.
        Accepts 6-digit code (or legacy token for compat). Returns (user_dto, access_token).
        Raises HTTPException if code invalid/expired/used.
        """
        raw = (code or "").strip()
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT pending_id, email, verification_code, token_expiry, used,
                       username, hashed_password, first_name, last_name, cellphone, market_id, city_id
                FROM pending_customer_signup
                WHERE verification_code = %s
                """,
                (raw,),
            )
            row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )
        if row["used"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has already been used",
            )
        now = datetime.now(timezone.utc)
        if row["token_expiry"] and row["token_expiry"].tzinfo is None:
            row["token_expiry"] = row["token_expiry"].replace(tzinfo=timezone.utc)
        if (row["token_expiry"] or now) <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired",
            )

        user_data = {
            "email": row["email"],
            "username": row["username"],
            "hashed_password": row["hashed_password"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "cellphone": row["cellphone"],
            "market_id": row["market_id"],
            "city_id": row["city_id"],
        }
        self._apply_customer_signup_rules(user_data, db)
        new_user = create_user_with_validation(user_data, db)
        # Populate user_market_assignment so GET /restaurants/by-city and other market-scoped APIs see the customer's market
        market_id_uuid = user_data["market_id"] if isinstance(user_data["market_id"], UUID) else UUID(str(user_data["market_id"]))
        set_user_market_assignments(new_user.user_id, [market_id_uuid], db)

        with db.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pending_customer_signup
                SET used = TRUE
                WHERE verification_code = %s
                """,
                (raw,),
            )
            db.commit()

        role_type = getattr(new_user.role_type, "value", str(new_user.role_type))
        role_name = getattr(new_user.role_name, "value", str(new_user.role_name))
        access_token = create_access_token(
            data={
                "sub": str(new_user.user_id),
                "role_type": role_type or "Unknown",
                "role_name": role_name or "Unknown",
                "institution_id": str(new_user.institution_id),
            }
        )
        log_info(f"Customer signup verified and user created: {new_user.user_id}")
        return new_user, access_token


# Create service instance
user_signup_service = UserSignupService()
