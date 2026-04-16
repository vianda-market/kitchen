#!/usr/bin/env python3
"""
Performance Analysis Script

Analyzes application logs to identify performance bottlenecks:
- Slow database queries
- Slow API endpoints
- Error patterns
- Resource usage patterns
"""

import argparse
import re
import sys
from collections import Counter, defaultdict


def parse_log_file(log_file_path):
    """Parse log file and extract performance metrics"""

    # Performance patterns to look for
    slow_query_pattern = r"🐌 Slow query detected: ([\d.]+)s - (.+)"
    slow_operation_pattern = r"🐌 Slow (INSERT|UPDATE|DELETE|archival) detected: ([\d.]+)s - (.+)"
    query_timing_pattern = r"📊 Query executed in ([\d.]+)s: (.+)"
    operation_timing_pattern = r"📊 (INSERT|UPDATE|DELETE) executed in ([\d.]+)s"

    # Endpoint patterns
    endpoint_pattern = r"INFO: ([^:]+): ([A-Z]+) ([^ ]+) completed in ([\d.]+)s"
    error_pattern = r"ERROR: (.+)"

    slow_queries = []
    slow_operations = []
    query_timings = []
    operation_timings = []
    endpoints = []
    errors = []

    try:
        with open(log_file_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Extract slow queries
                slow_query_match = re.search(slow_query_pattern, line)
                if slow_query_match:
                    execution_time = float(slow_query_match.group(1))
                    query = slow_query_match.group(2)
                    slow_queries.append((execution_time, query, line_num))

                # Extract slow operations
                slow_op_match = re.search(slow_operation_pattern, line)
                if slow_op_match:
                    op_type = slow_op_match.group(1)
                    execution_time = float(slow_op_match.group(2))
                    table = slow_op_match.group(3)
                    slow_operations.append((op_type, execution_time, table, line_num))

                # Extract query timings
                query_timing_match = re.search(query_timing_pattern, line)
                if query_timing_match:
                    execution_time = float(query_timing_match.group(1))
                    query = query_timing_match.group(2)
                    query_timings.append((execution_time, query))

                # Extract operation timings
                op_timing_match = re.search(operation_timing_pattern, line)
                if op_timing_match:
                    op_type = op_timing_match.group(1)
                    execution_time = float(op_timing_match.group(2))
                    operation_timings.append((op_type, execution_time))

                # Extract endpoint performance
                endpoint_match = re.search(endpoint_pattern, line)
                if endpoint_match:
                    method = endpoint_match.group(2)
                    path = endpoint_match.group(3)
                    execution_time = float(endpoint_match.group(4))
                    endpoints.append((method, path, execution_time))

                # Extract errors
                error_match = re.search(error_pattern, line)
                if error_match:
                    error_msg = error_match.group(1)
                    errors.append((error_msg, line_num))

    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file_path}")
        return None
    except Exception as e:
        print(f"❌ Error parsing log file: {e}")
        return None

    return {
        "slow_queries": slow_queries,
        "slow_operations": slow_operations,
        "query_timings": query_timings,
        "operation_timings": operation_timings,
        "endpoints": endpoints,
        "errors": errors,
    }


def analyze_performance(metrics):
    """Analyze performance metrics and generate insights"""

    if not metrics:
        return

    print("🚀 Performance Analysis Report")
    print("=" * 50)

    # Slow queries analysis
    if metrics["slow_queries"]:
        print(f"\n🐌 Slow Queries Found: {len(metrics['slow_queries'])}")
        print("-" * 30)
        for execution_time, query, line_num in sorted(metrics["slow_queries"], reverse=True):
            print(f"  {execution_time:.3f}s (line {line_num}): {query[:80]}...")

    # Slow operations analysis
    if metrics["slow_operations"]:
        print(f"\n🐌 Slow Operations Found: {len(metrics['slow_operations'])}")
        print("-" * 30)
        for op_type, execution_time, table, line_num in sorted(
            metrics["slow_operations"], key=lambda x: x[1], reverse=True
        ):
            print(f"  {op_type}: {execution_time:.3f}s on {table} (line {line_num})")

    # Query performance summary
    if metrics["query_timings"]:
        print("\n📊 Query Performance Summary")
        print("-" * 30)
        times = [t[0] for t in metrics["query_timings"]]
        print(f"  Total queries: {len(times)}")
        print(f"  Average time: {sum(times) / len(times):.3f}s")
        print(f"  Max time: {max(times):.3f}s")
        print(f"  Min time: {min(times):.3f}s")

        # Performance distribution
        fast_queries = len([t for t in times if t < 0.1])
        medium_queries = len([t for t in times if 0.1 <= t < 1.0])
        slow_queries = len([t for t in times if t >= 1.0])

        print(f"  Fast (<0.1s): {fast_queries}")
        print(f"  Medium (0.1-1s): {medium_queries}")
        print(f"  Slow (≥1s): {slow_queries}")

    # Endpoint performance
    if metrics["endpoints"]:
        print("\n🌐 Endpoint Performance")
        print("-" * 30)

        # Group by endpoint
        endpoint_stats = defaultdict(list)
        for method, path, execution_time in metrics["endpoints"]:
            endpoint_stats[f"{method} {path}"].append(execution_time)

        for endpoint, times in endpoint_stats.items():
            avg_time = sum(times) / len(times)
            max_time = max(times)
            print(f"  {endpoint}: {len(times)} calls, avg {avg_time:.3f}s, max {max_time:.3f}s")

    # Error analysis
    if metrics["errors"]:
        print(f"\n❌ Errors Found: {len(metrics['errors'])}")
        print("-" * 30)
        error_counts = Counter([e[0] for e in metrics["errors"]])
        for error_msg, count in error_counts.most_common(5):
            print(f"  {error_msg}: {count} occurrences")


def main():
    parser = argparse.ArgumentParser(description="Analyze application performance from logs")
    parser.add_argument("log_file", help="Path to the log file to analyze")
    parser.add_argument(
        "--slow-threshold",
        type=float,
        default=1.0,
        help="Threshold in seconds for considering operations slow (default: 1.0)",
    )

    args = parser.parse_args()

    print(f"📖 Analyzing log file: {args.log_file}")
    print(f"⏱️  Slow operation threshold: {args.slow_threshold}s")
    print()

    # Parse and analyze logs
    metrics = parse_log_file(args.log_file)
    if metrics:
        analyze_performance(metrics)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
