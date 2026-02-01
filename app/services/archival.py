"""
Archival Service - Centralized data lifecycle management

This service handles the archival of records across all entities based on
configurable retention periods. It uses direct database operations for
data archival since models have been migrated to DTO pattern.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from app.config.archival_config import get_table_archival_config, get_archival_priority_order
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read, db_update, db_batch_delete


class ArchivalService:
    """Service for managing automatic data archival based on configured retention periods"""
    
    # Note: Archival service now uses direct database operations
    # since models have been migrated to DTO pattern

    @classmethod
    def get_eligible_records(cls, table_name: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Find records eligible for archival based on configuration"""
        try:
            config = get_table_archival_config(table_name)
            
            # Skip if retention period is too high (never archived)
            if config.retention_days > 50000:  # Effectively never
                return []
            
            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=config.retention_days + config.grace_period_days
            )
            
            # Query for eligible records
            query = f"""
            SELECT * FROM {table_name}
            WHERE is_archived = false 
              AND created_date < %s
            ORDER BY created_date ASC
            LIMIT %s
            """
            
            results = db_read(query, (cutoff_date, limit), fetch_one=False)
            
            if not results:
                return []
            
            # Get model class to parse results properly
            model_class = cls._get_model_class(table_name)
            if not model_class:
                # Return raw results if no model class found
                return [dict(zip([desc[0] for desc in results], row)) for row in results]
            
            # Parse results using model class
            try:
                parsed_records = []
                for result in results:
                    parsed_record = model_class._parse_result(result)
                    parsed_records.append(parsed_record.dict() if hasattr(parsed_record, 'dict') else parsed_record)
                return parsed_records
            except Exception as e:
                log_warning(f"Error parsing results for {table_name}: {e}, returning raw results")
                # Fallback to raw results
                return [dict(zip([desc[0] for desc in results], row)) for row in results]
                
        except Exception as e:
            log_error(f"Error finding eligible records for {table_name}: {e}")
            return []

    @classmethod
    def archive_records(cls, table_name: str, record_ids: List[UUID], modified_by: UUID) -> Dict[str, Any]:
        """Archive specific records by setting is_archived = True"""
        try:
            if not record_ids:
                return {"archived_count": 0, "error": "No record IDs provided"}
            
            config = get_table_archival_config(table_name)
            model_class = cls._get_model_class(table_name)
            
            if not model_class:
                log_warning(f"No model class found for {table_name}, using direct SQL update")
                # Direct SQL update as fallback
                id_column = cls._get_primary_key_column(table_name)
                placeholders = ','.join(['%s'] * len(record_ids))
                query = f"""
                UPDATE {table_name} 
                SET is_archived = true, modified_date = CURRENT_TIMESTAMP, modified_by = %s
                WHERE {id_column} IN ({placeholders}) AND is_archived = false
                """
                
                try:
                    from app.utils.db import get_db_connection, close_db_connection
                    import time
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    start_time = time.time()
                    cursor.execute(query, [modified_by] + [str(rid) for rid in record_ids])
                    execution_time = time.time() - start_time
                    archived_count = cursor.rowcount
                    conn.commit()
                    close_db_connection(conn)
                    
                    log_info(f"Archived {archived_count} records in {table_name}")
                    log_info(f"📊 Archival executed in {execution_time:.3f}s")
                    
                    if execution_time > 1.0:  # Log slow operations
                        log_warning(f"🐌 Slow archival detected: {execution_time:.3f}s - {table_name}")
                    
                    return {"archived_count": archived_count, "table_name": table_name}
                except Exception as e:
                    log_error(f"Direct SQL archival failed for {table_name}: {e}")
                    return {"archived_count": 0, "error": str(e)}
            
            # Use batch delete with soft delete for atomic archival
            # This is more efficient than looping through individual updates
            try:
                id_column = cls._get_primary_key_column(table_name)
                where_list = [{id_column: str(record_id)} for record_id in record_ids]
                
                soft_update_fields = {
                    "modified_by": str(modified_by),
                    "modified_date": datetime.now(timezone.utc)
                }
                
                from app.utils.db import get_db_connection, close_db_connection
                import time
                conn = get_db_connection()
                start_time = time.time()
                
                archived_count = db_batch_delete(
                    table_name,
                    where_list,
                    connection=conn,
                    soft=True,
                    soft_update_fields=soft_update_fields
                )
                
                execution_time = time.time() - start_time
                close_db_connection(conn)
                
                log_info(f"Archived {archived_count} records in {table_name} using batch delete")
                log_info(f"📊 Batch archival executed in {execution_time:.3f}s")
                
                if execution_time > 1.0:
                    log_warning(f"🐌 Slow batch archival detected: {execution_time:.3f}s - {table_name}")
                
                return {"archived_count": archived_count, "table_name": table_name}
            except Exception as e:
                log_error(f"Batch archival failed for {table_name}: {e}")
                # Fallback to individual updates if batch fails
                archived_count = 0
                errors = []
                
                for record_id in record_ids:
                    try:
                        update_data = {
                            "is_archived": True,
                            "modified_by": modified_by,
                            "modified_date": datetime.now(timezone.utc)
                        }
                        
                        success = model_class.update(record_id, update_data)
                        if success:
                            archived_count += 1
                        else:
                            errors.append(f"Failed to archive record {record_id}")
                    except Exception as e:
                        errors.append(f"Error archiving record {record_id}: {e}")
                    
            log_info(f"Archived {archived_count}/{len(record_ids)} records in {table_name}")
            
            result = {
                "archived_count": archived_count,
                "total_requested": len(record_ids),
                "table_name": table_name
            }
            
            if errors:
                result["errors"] = errors[:10]  # Limit error list
                
            return result
            
        except Exception as e:
            log_error(f"Error archiving records in {table_name}: {e}")
            return {"archived_count": 0, "error": str(e)}

    @classmethod
    def _get_primary_key_column(cls, table_name: str) -> str:
        """Get primary key column name for a table"""
        from app.utils.db import PRIMARY_KEY_MAPPING
        return PRIMARY_KEY_MAPPING.get(table_name, "id")

    @classmethod
    def run_scheduled_archival(cls, modified_by: UUID, batch_size: int = 100, max_tables: int = 10) -> Dict[str, Any]:
        """Run scheduled archival process for all eligible tables"""
        start_time = datetime.now(timezone.utc)
        log_info("Starting scheduled archival process")
        
        try:
            # Get tables in priority order
            priority_tables = get_archival_priority_order()
            
            # Limit to max_tables for this run
            tables_to_process = priority_tables[:max_tables]
            
            results = {
                "start_time": start_time.isoformat(),
                "tables_processed": [],
                "total_archived": 0,
                "errors": []
            }
            
            for table_name in tables_to_process:
                try:
                    log_info(f"Processing archival for table: {table_name}")
                    
                    # Get eligible records
                    eligible_records = cls.get_eligible_records(table_name, limit=batch_size)
                    
                    if not eligible_records:
                        log_info(f"No eligible records found for {table_name}")
                        results["tables_processed"].append({
                            "table_name": table_name,
                            "eligible_count": 0,
                            "archived_count": 0
                        })
                        continue
                    
                    # Extract record IDs
                    id_column = cls._get_primary_key_column(table_name)
                    record_ids = []
                    
                    for record in eligible_records:
                        if isinstance(record, dict) and id_column in record:
                            record_ids.append(record[id_column])
                        elif hasattr(record, id_column):
                            record_ids.append(getattr(record, id_column))
                    
                    if not record_ids:
                        log_warning(f"Could not extract record IDs for {table_name}")
                        continue
                    
                    # Archive records
                    archival_result = cls.archive_records(table_name, record_ids, modified_by)
                    
                    table_result = {
                        "table_name": table_name,
                        "eligible_count": len(eligible_records),
                        "archived_count": archival_result.get("archived_count", 0)
                    }
                    
                    if "error" in archival_result:
                        table_result["error"] = archival_result["error"]
                        results["errors"].append(f"{table_name}: {archival_result['error']}")
                    
                    results["tables_processed"].append(table_result)
                    results["total_archived"] += archival_result.get("archived_count", 0)
                    
                except Exception as e:
                    error_msg = f"Error processing {table_name}: {e}"
                    log_error(error_msg)
                    results["errors"].append(error_msg)
                    results["tables_processed"].append({
                        "table_name": table_name,
                        "eligible_count": 0,
                        "archived_count": 0,
                        "error": str(e)
                    })
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            results.update({
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "success": len(results["errors"]) == 0
            })
            
            log_info(f"Scheduled archival completed. Total archived: {results['total_archived']}, Duration: {duration:.2f}s")
            return results
            
        except Exception as e:
            error_msg = f"Fatal error in scheduled archival: {e}"
            log_error(error_msg)
            return {
                "start_time": start_time.isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "total_archived": 0,
                "success": False,
                "fatal_error": error_msg
            }

    @classmethod
    def get_archival_stats(cls) -> Dict[str, Any]:
        """Get comprehensive archival statistics"""
        try:
            stats = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "table_stats": [],
                "summary": {
                    "total_tables": 0,
                    "total_active_records": 0,
                    "total_archived_records": 0,
                    "tables_with_eligible_records": 0
                }
            }
            
            priority_tables = get_archival_priority_order()
            
            for table_name in priority_tables:
                try:
                    config = get_table_archival_config(table_name)
                    
                    # Get record counts
                    count_query = f"""
                    SELECT 
                        COUNT(*) FILTER (WHERE is_archived = false) as active_count,
                        COUNT(*) FILTER (WHERE is_archived = true) as archived_count,
                        COUNT(*) as total_count
                    FROM {table_name}
                    """
                    
                    result = db_read(count_query, fetch_one=True)
                    if result:
                        active_count, archived_count, total_count = result
                    else:
                        active_count = archived_count = total_count = 0
                    
                    # Get eligible count
                    cutoff_date = datetime.now(timezone.utc) - timedelta(
                        days=config.retention_days + config.grace_period_days
                    )
                    
                    eligible_query = f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE is_archived = false AND created_date < %s
                    """
                    
                    eligible_result = db_read(eligible_query, (cutoff_date,), fetch_one=True)
                    try:
                        eligible_count = int(eligible_result[0]) if eligible_result and isinstance(eligible_result, (tuple, list)) and len(eligible_result) > 0 else 0
                    except (TypeError, ValueError, IndexError):
                        eligible_count = 0
                    
                    table_stat = {
                        "table_name": table_name,
                        "category": config.category.value,
                        "retention_days": config.retention_days,
                        "active_records": active_count,
                        "archived_records": archived_count,
                        "total_records": total_count,
                        "eligible_for_archival": eligible_count,
                        "archival_cutoff_date": cutoff_date.isoformat()
                    }
                    
                    stats["table_stats"].append(table_stat)
                    
                    # Update summary
                    stats["summary"]["total_active_records"] += active_count
                    stats["summary"]["total_archived_records"] += archived_count
                    if eligible_count > 0:
                        stats["summary"]["tables_with_eligible_records"] += 1
                        
                except Exception as e:
                    log_warning(f"Error getting stats for {table_name}: {e}")
                    stats["table_stats"].append({
                        "table_name": table_name,
                        "error": str(e)
                    })
            
            stats["summary"]["total_tables"] = len(priority_tables)
            return stats
            
        except Exception as e:
            log_error(f"Error getting archival stats: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }

    @classmethod
    def validate_archival_integrity(cls) -> Dict[str, Any]:
        """Validate archival system integrity"""
        try:
            validation_results = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_status": "healthy",
                "issues": [],
                "tables_checked": 0,
                "configuration_issues": []
            }
            
            priority_tables = get_archival_priority_order()
            
            for table_name in priority_tables:
                try:
                    validation_results["tables_checked"] += 1
                    
                    # Check if table exists
                    check_table_query = f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                    """
                    
                    table_exists = db_read(check_table_query, (table_name,), fetch_one=True)
                    if not table_exists or not table_exists[0]:
                        issue = f"Table {table_name} does not exist but is configured for archival"
                        validation_results["issues"].append(issue)
                        validation_results["overall_status"] = "warning"
                        continue
                    
                    # Check required columns
                    column_query = f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = %s AND column_name IN ('is_archived', 'created_date')
                    """
                    
                    columns = db_read(column_query, (table_name,), fetch_one=False)
                    column_names = [col[0] for col in columns] if columns else []
                    
                    if 'is_archived' not in column_names:
                        issue = f"Table {table_name} missing required column: is_archived"
                        validation_results["issues"].append(issue)
                        validation_results["overall_status"] = "error"
                    
                    if 'created_date' not in column_names:
                        issue = f"Table {table_name} missing required column: created_date"
                        validation_results["issues"].append(issue)
                        validation_results["overall_status"] = "error"
                    
                    # Check configuration
                    config = get_table_archival_config(table_name)
                    if config.retention_days < 0:
                        issue = f"Table {table_name} has negative retention days: {config.retention_days}"
                        validation_results["configuration_issues"].append(issue)
                        validation_results["overall_status"] = "warning"
                        
                except Exception as e:
                    issue = f"Error validating table {table_name}: {e}"
                    validation_results["issues"].append(issue)
                    validation_results["overall_status"] = "error"
            
            # Summary
            if validation_results["overall_status"] == "healthy":
                log_info("Archival system validation passed")
            else:
                log_warning(f"Archival system validation found issues: {validation_results['overall_status']}")
            
            return validation_results
            
        except Exception as e:
            log_error(f"Error during archival validation: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_status": "error",
                "fatal_error": str(e)
            } 