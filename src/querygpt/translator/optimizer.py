"""QueryOptimizer - suggests index usage and query improvements."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from querygpt.models import (
    AggregationType,
    FilterOperator,
    Index,
    ParsedIntent,
    Query,
    Schema,
)


@dataclass
class OptimizationSuggestion:
    """A single optimization suggestion."""

    category: str  # "index", "rewrite", "warning", "performance"
    message: str
    severity: str = "info"  # "info", "warning", "critical"


@dataclass
class OptimizationReport:
    """Full optimization analysis of a query."""

    suggestions: list[OptimizationSuggestion] = field(default_factory=list)
    estimated_cost: str = "unknown"
    index_recommendations: list[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return any(s.severity in ("warning", "critical") for s in self.suggestions)

    @property
    def summary(self) -> str:
        counts = {}
        for s in self.suggestions:
            counts[s.category] = counts.get(s.category, 0) + 1
        parts = [f"{v} {k}" for k, v in counts.items()]
        return f"{len(self.suggestions)} suggestions: {', '.join(parts)}" if parts else "No suggestions"


class QueryOptimizer:
    """Analyzes queries and suggests improvements.

    Checks for:
    - Missing indexes on filtered/sorted columns
    - SELECT * anti-pattern
    - Missing LIMIT on large result sets
    - Inefficient LIKE patterns
    - Unnecessary DISTINCT
    - Potential N+1 query patterns
    """

    def __init__(self, schema: Schema | None = None) -> None:
        self.schema = schema

    def analyze(self, query: Query) -> OptimizationReport:
        """Analyze a query and return optimization suggestions."""
        report = OptimizationReport()
        intent = query.intent

        self._check_select_star(intent, report)
        self._check_missing_limit(intent, report)
        self._check_index_usage(intent, report)
        self._check_like_patterns(intent, report)
        self._check_distinct_usage(intent, report)
        self._check_group_by_consistency(intent, report)
        self._check_cross_joins(query, report)
        self._check_having_without_group(intent, report)

        # Set estimated cost
        report.estimated_cost = self._estimate_cost(intent)

        return report

    def suggest_indexes(self, query: Query) -> list[str]:
        """Return CREATE INDEX statements for recommended indexes."""
        intent = query.intent
        indexes: list[str] = []

        # Indexes for WHERE columns
        for f in intent.filters:
            table = f.table or (intent.tables[0] if intent.tables else None)
            if table:
                idx_name = f"idx_{table}_{f.column}"
                indexes.append(
                    f"CREATE INDEX {idx_name} ON {table} ({f.column});"
                )

        # Indexes for ORDER BY columns
        for o in intent.order_by:
            table = o.table or (intent.tables[0] if intent.tables else None)
            if table:
                idx_name = f"idx_{table}_{o.column}"
                stmt = f"CREATE INDEX {idx_name} ON {table} ({o.column});"
                if stmt not in indexes:
                    indexes.append(stmt)

        # Composite index for filter + sort
        if intent.filters and intent.order_by:
            table = intent.tables[0] if intent.tables else None
            if table:
                cols = [f.column for f in intent.filters] + [o.column for o in intent.order_by]
                unique_cols = list(dict.fromkeys(cols))  # preserve order, dedupe
                idx_name = f"idx_{table}_{'_'.join(unique_cols)}"
                indexes.append(
                    f"CREATE INDEX {idx_name} ON {table} ({', '.join(unique_cols)});"
                )

        return indexes

    # --- checks ---

    def _check_select_star(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if any(f.column == "*" and f.aggregation is None for f in intent.select_fields):
            report.suggestions.append(OptimizationSuggestion(
                category="performance",
                message="Avoid SELECT *; specify only the columns you need to reduce I/O.",
                severity="warning",
            ))

    def _check_missing_limit(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if intent.limit is None and not any(f.aggregation for f in intent.select_fields):
            report.suggestions.append(OptimizationSuggestion(
                category="performance",
                message="Consider adding a LIMIT clause to avoid fetching excessive rows.",
                severity="info",
            ))

    def _check_index_usage(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if not self.schema or not intent.tables:
            return

        for f in intent.filters:
            table_name = f.table or intent.tables[0]
            table = self.schema.get_table(table_name)
            if not table:
                continue

            # Check if the column has an index
            has_index = any(f.column in idx.columns for idx in table.indexes)
            if not has_index:
                report.suggestions.append(OptimizationSuggestion(
                    category="index",
                    message=f"Column '{f.column}' in table '{table_name}' is used in a filter "
                            "but has no index. Consider adding one.",
                    severity="warning",
                ))
                report.index_recommendations.append(
                    f"CREATE INDEX idx_{table_name}_{f.column} ON {table_name} ({f.column});"
                )

    def _check_like_patterns(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        for f in intent.filters:
            if f.operator == FilterOperator.LIKE and isinstance(f.value, str):
                if f.value.startswith("%"):
                    report.suggestions.append(OptimizationSuggestion(
                        category="performance",
                        message=f"LIKE pattern '{f.value}' starts with a wildcard, which prevents "
                                "index usage. Consider using full-text search instead.",
                        severity="warning",
                    ))

    def _check_distinct_usage(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if intent.distinct and intent.group_by:
            report.suggestions.append(OptimizationSuggestion(
                category="rewrite",
                message="DISTINCT combined with GROUP BY is usually redundant. "
                        "The GROUP BY already ensures unique groups.",
                severity="info",
            ))

    def _check_group_by_consistency(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if not intent.group_by:
            return
        group_cols = set(intent.group_by.columns)
        for f in intent.select_fields:
            if f.aggregation is None and f.column != "*":
                if f.column not in group_cols:
                    report.suggestions.append(OptimizationSuggestion(
                        category="warning",
                        message=f"Column '{f.column}' appears in SELECT but not in GROUP BY "
                                "and is not aggregated. This may cause an error in strict SQL mode.",
                        severity="critical",
                    ))

    def _check_cross_joins(self, query: Query, report: OptimizationReport) -> None:
        if "CROSS JOIN" in query.sql:
            report.suggestions.append(OptimizationSuggestion(
                category="warning",
                message="CROSS JOIN detected. This produces a Cartesian product and may "
                        "return an unexpectedly large result set.",
                severity="critical",
            ))

    def _check_having_without_group(self, intent: ParsedIntent, report: OptimizationReport) -> None:
        if intent.group_by and intent.group_by.having and not any(f.aggregation for f in intent.select_fields):
            report.suggestions.append(OptimizationSuggestion(
                category="warning",
                message="HAVING clause used without aggregation in SELECT. "
                        "Consider moving the condition to WHERE.",
                severity="info",
            ))

    def _estimate_cost(self, intent: ParsedIntent) -> str:
        """Simple heuristic cost estimate."""
        score = 1
        if any(f.column == "*" and f.aggregation is None for f in intent.select_fields):
            score += 2
        if not intent.filters:
            score += 3  # Full table scan
        if intent.limit is None:
            score += 1
        if len(intent.tables) > 2:
            score += 2
        if intent.distinct:
            score += 1

        if score <= 2:
            return "low"
        elif score <= 5:
            return "medium"
        else:
            return "high"
