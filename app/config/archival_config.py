# Archival Configuration - Category-Based SLA Management
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import os
from app.utils.log import log_info, log_warning

class ArchivalCategory(Enum):
    """Archival categories with different business requirements"""
    FINANCIAL_CRITICAL = "financial_critical"      # 2+ years (legal compliance)
    FINANCIAL_OPERATIONAL = "financial_operational" # 3-6 months (dispute resolution)
    CUSTOMER_SERVICE = "customer_service"          # 1-3 months (support window)
    OPERATIONAL_DATA = "operational_data"          # 2-6 months (business operations)
    REFERENCE_DATA = "reference_data"              # Long-term (rarely archived)
    SECURITY_COMPLIANCE = "security_compliance"    # 7+ years (legal requirements)
    SYSTEM_CONFIGURATION = "system_configuration"  # Never archived

@dataclass
class ArchivalConfig:
    """Configuration for a specific archival category"""
    category: ArchivalCategory
    retention_days: int
    grace_period_days: int
    priority: int  # 1 = highest priority for archival
    description: str

# Category SLA Definitions (FALLBACK FOR DEV)
CATEGORY_SLA_CONFIG: Dict[ArchivalCategory, ArchivalConfig] = {
    ArchivalCategory.FINANCIAL_CRITICAL: ArchivalConfig(
        category=ArchivalCategory.FINANCIAL_CRITICAL,
        retention_days=2555,  # 7 years - legal compliance
        grace_period_days=30,
        priority=1,
        description="Critical financial records requiring long-term retention for legal compliance"
    ),
    
    ArchivalCategory.FINANCIAL_OPERATIONAL: ArchivalConfig(
        category=ArchivalCategory.FINANCIAL_OPERATIONAL,
        retention_days=365,  # 1 year - financial operations
        grace_period_days=14,
        priority=2,
        description="Operational financial data for dispute resolution and auditing"
    ),
    
    ArchivalCategory.CUSTOMER_SERVICE: ArchivalConfig(
        category=ArchivalCategory.CUSTOMER_SERVICE,
        retention_days=90,  # 3 months - customer support window
        grace_period_days=7,
        priority=3,
        description="Customer interaction data for support and service quality"
    ),
    
    ArchivalCategory.OPERATIONAL_DATA: ArchivalConfig(
        category=ArchivalCategory.OPERATIONAL_DATA,
        retention_days=180,  # 6 months - operational analytics
        grace_period_days=14,
        priority=4,
        description="Business operational data for analytics and process improvement"
    ),
    
    ArchivalCategory.REFERENCE_DATA: ArchivalConfig(
        category=ArchivalCategory.REFERENCE_DATA,
        retention_days=730,  # 2 years - reference data
        grace_period_days=30,
        priority=5,
        description="Reference data like products, plans, and QR codes"
    ),
    
    ArchivalCategory.SECURITY_COMPLIANCE: ArchivalConfig(
        category=ArchivalCategory.SECURITY_COMPLIANCE,
        retention_days=2555,  # 7 years - security compliance
        grace_period_days=30,
        priority=1,
        description="Security-related data with compliance requirements"
    ),
    
    ArchivalCategory.SYSTEM_CONFIGURATION: ArchivalConfig(
        category=ArchivalCategory.SYSTEM_CONFIGURATION,
        retention_days=99999,  # Never archived
        grace_period_days=0,
        priority=99,
        description="System configuration data that should never be archived"
    )
}

# Table to Category Mapping (FALLBACK FOR DEV)
TABLE_CATEGORY_MAPPING: Dict[str, ArchivalCategory] = {
    # FINANCIAL CRITICAL (7 years - legal compliance)
    "user_info": ArchivalCategory.FINANCIAL_CRITICAL,
    "client_bill_info": ArchivalCategory.FINANCIAL_CRITICAL,
    "institution_payment_attempt": ArchivalCategory.FINANCIAL_CRITICAL,
    
    # FINANCIAL OPERATIONAL (1 year - financial operations)  
    "client_transaction": ArchivalCategory.FINANCIAL_OPERATIONAL,
    "restaurant_transaction": ArchivalCategory.FINANCIAL_OPERATIONAL,
    "fintech_link_assignment": ArchivalCategory.FINANCIAL_OPERATIONAL,
    "subscription_info": ArchivalCategory.FINANCIAL_OPERATIONAL,
    "payment_method": ArchivalCategory.FINANCIAL_OPERATIONAL,
    
    # CUSTOMER SERVICE (3 months - support window)
    "plate_pickup_live": ArchivalCategory.CUSTOMER_SERVICE,
    "client_payment_attempt": ArchivalCategory.CUSTOMER_SERVICE,
    "plate_selection": ArchivalCategory.CUSTOMER_SERVICE,
    "restaurant_holidays": ArchivalCategory.CUSTOMER_SERVICE,
    "credential_recovery": ArchivalCategory.CUSTOMER_SERVICE,
    
    # OPERATIONAL DATA (6 months - business operations)
    "restaurant_info": ArchivalCategory.OPERATIONAL_DATA,
    "institution_entity_info": ArchivalCategory.OPERATIONAL_DATA, 
    "institution_info": ArchivalCategory.OPERATIONAL_DATA,
    "address_info": ArchivalCategory.OPERATIONAL_DATA,
    "geolocation_info": ArchivalCategory.OPERATIONAL_DATA,
    "restaurant_balance_info": ArchivalCategory.OPERATIONAL_DATA,
    "institution_bank_account": ArchivalCategory.OPERATIONAL_DATA,
    "discretionary_info": ArchivalCategory.OPERATIONAL_DATA,
    "discretionary_history": ArchivalCategory.OPERATIONAL_DATA,
    "discretionary_resolution_info": ArchivalCategory.OPERATIONAL_DATA,
    "discretionary_resolution_history": ArchivalCategory.OPERATIONAL_DATA,
    
    # REFERENCE DATA (2 years - product/catalog data)
    "product_info": ArchivalCategory.REFERENCE_DATA,
    "plate_info": ArchivalCategory.REFERENCE_DATA,
    "plan_info": ArchivalCategory.REFERENCE_DATA,
    "qr_code": ArchivalCategory.REFERENCE_DATA,
    "credit_currency_info": ArchivalCategory.REFERENCE_DATA,
    "plate_kitchen_days": ArchivalCategory.REFERENCE_DATA,
    "fintech_link_info": ArchivalCategory.REFERENCE_DATA,
    "fintech_wallet": ArchivalCategory.REFERENCE_DATA,
    "fintech_wallet_auth": ArchivalCategory.REFERENCE_DATA,
    "credit_card": ArchivalCategory.REFERENCE_DATA,
    "bank_account": ArchivalCategory.REFERENCE_DATA,
    "appstore_account": ArchivalCategory.REFERENCE_DATA,
    
    # SYSTEM CONFIGURATION (never archived)
    # role_info, status_info, transaction_type_info removed - enums stored directly on entities
    
    # History tables (never archived - they are already historical)
    # role_history, status_history, transaction_type_history removed - tables deprecated
    "client_bill_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "credit_currency_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "fintech_link_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "geolocation_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "institution_entity_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "institution_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "plan_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "plate_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "plate_kitchen_days_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "product_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    # Removed qr_code_history since we removed the history table
    "restaurant_balance_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "restaurant_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "restaurant_holidays_history": ArchivalCategory.SYSTEM_CONFIGURATION,
    "subscription_history": ArchivalCategory.SYSTEM_CONFIGURATION,
}

# Configuration Cache
_config_cache: Optional[Dict[str, ArchivalConfig]] = None
_use_database_config = os.getenv("USE_DATABASE_ARCHIVAL_CONFIG", "false").lower() == "true"

def _load_database_config() -> Optional[Dict[str, ArchivalConfig]]:
    """Load archival configuration from database"""
    if not _use_database_config:
        return None
        
    try:
        from app.utils.db import db_read
        
        query = """
        SELECT table_name, category, retention_days, grace_period_days, priority, description
        FROM archival_config 
        WHERE is_active = true
        ORDER BY table_name
        """
        
        results = db_read(query, fetch_one=False)
        if not results:
            log_warning("No database archival configuration found, using code fallback")
            return None
            
        config_dict = {}
        for result in results:
            table_name, category_str, retention_days, grace_period_days, priority, description = result
            
            try:
                category = ArchivalCategory(category_str)
            except ValueError:
                log_warning(f"Unknown archival category '{category_str}' for table '{table_name}', skipping")
                continue
                
            config_dict[table_name] = ArchivalConfig(
                category=category,
                retention_days=retention_days,
                grace_period_days=grace_period_days,
                priority=priority,
                description=description or ""
            )
            
        log_info(f"Loaded archival configuration for {len(config_dict)} tables from database")
        return config_dict
        
    except Exception as e:
        log_warning(f"Failed to load database archival configuration: {e}, using code fallback")
        return None

def _get_config_cache() -> Dict[str, ArchivalConfig]:
    """Get cached configuration, loading from database if needed"""
    global _config_cache
    
    if _config_cache is None:
        # Try to load from database first
        db_config = _load_database_config()
        
        if db_config:
            _config_cache = db_config
        else:
            # Fallback to code-based configuration
            _config_cache = {}
            for table_name, category in TABLE_CATEGORY_MAPPING.items():
                _config_cache[table_name] = CATEGORY_SLA_CONFIG[category]
            log_info(f"Using code-based archival configuration for {len(_config_cache)} tables")
    
    return _config_cache

def get_table_archival_config(table_name: str) -> ArchivalConfig:
    """Get archival configuration for a specific table"""
    config_cache = _get_config_cache()
    
    if table_name in config_cache:
        return config_cache[table_name]
    
    # Fallback to OPERATIONAL_DATA category for unknown tables
    log_warning(f"No archival configuration found for table '{table_name}', using OPERATIONAL_DATA defaults")
    return CATEGORY_SLA_CONFIG[ArchivalCategory.OPERATIONAL_DATA]

def get_retention_days(table_name: str) -> int:
    """Get retention days for a specific table"""
    return get_table_archival_config(table_name).retention_days

def get_tables_by_category(category: ArchivalCategory) -> List[str]:
    """Get all tables in a specific archival category"""
    config_cache = _get_config_cache()
    return [table for table, config in config_cache.items() if config.category == category]

def get_archival_priority_order() -> List[str]:
    """Get tables ordered by archival priority (highest priority first)"""
    config_cache = _get_config_cache()
    table_priorities = []
    
    for table_name, config in config_cache.items():
        table_priorities.append((table_name, config.priority, config.retention_days))
    
    # Sort by priority (lower number = higher priority), then by retention days
    table_priorities.sort(key=lambda x: (x[1], x[2]))
    return [table for table, _, _ in table_priorities]

def refresh_config_cache():
    """Force refresh of configuration cache from database"""
    global _config_cache
    _config_cache = None
    log_info("Archival configuration cache refreshed")

def get_config_source() -> str:
    """Get the current configuration source (database or code)"""
    return "database" if _use_database_config and _config_cache else "code"

# Export for use in other modules
__all__ = [
    'ArchivalCategory',
    'ArchivalConfig', 
    'CATEGORY_SLA_CONFIG',
    'TABLE_CATEGORY_MAPPING',
    'get_table_archival_config',
    'get_retention_days',
    'get_tables_by_category',
    'get_archival_priority_order',
    'refresh_config_cache',
    'get_config_source'
] 