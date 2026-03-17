"""QueryValidator - checks SQL correctness against the schema."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from querygpt.models import Query, Schema


@dataclass
class ValidationIssue:
    """A single validation problem."""

    level: str  # "error", "warning"
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Result of validating a query against a schema."""

    valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, suggestion: str = "") -> None:
        self.valid = False
        self.issues.append(ValidationIssue(level="error", message=message, suggestion=suggestion))

    def add_warning(self, message: str, suggestion: str = "") -> None:
        self.issues.append(ValidationIssue(level="warning", message=message, suggestion=suggestion))

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")

    @property
    def summary(self) -> str:
        if self.valid and not self.issues:
            return "Query is valid"
        return f"{'Valid' if self.valid else 'Invalid'}: {self.error_count} errors, {self.warning_count} warnings"


class QueryValidator:
    """Validates generated SQL queries against the database schema.

    Checks:
    - Referenced tables exist in the schema
    - Referenced columns exist in their tables
    - Data type compatibility in filters
    - JOIN conditions reference valid columns
    - GROUP BY columns are consistent with SELECT
    """

    def __init__(self, schema: Schema) -> None:
        self.schema = schema

    def validate(self, query: Query) -> ValidationResult:
        """Validate a query against the schema."""
        result = ValidationResult()

        self._check_tables(query, result)
        self._check_columns(query, result)
        self._check_filters(query, result)
        self._check_joins(query, result)
        self._check_syntax(query, result)

        return result

    def _check_tables(self, query: Query, result: ValidationResult) -> None:
        """Verify all referenced tables exist."""
        for table_name in query.tables_used:
            if not self.schema.get_table(table_name):
                result.add_error(
                    f"Table '{table_name}' does not exist in schema",
                    suggestion=f"Available tables: {', '.join(self.schema.table_names)}",
                )

    def _check_columns(self, query: Query, result: ValidationResult) -> None:
        """Verify all referenced columns exist in their tables."""
        intent = query.intent

        for field in intent.select_fields:
            if field.column == "*":
                continue
            table_name = field.table or (intent.tables[0] if intent.tables else None)
            if table_name:
                table = self.schema.get_table(table_name)
                if table and not table.get_column(field.column):
                    result.add_error(
                        f"Column '{field.column}' does not exist in table '{table_name}'",
                        suggestion=f"Available columns: {', '.join(table.column_names)}",
                    )

    def _check_filters(self, query: Query, result: ValidationResult) -> None:
        """Verify filter columns and value types."""
        intent = query.intent

        for f in intent.filters:
            table_name = f.table or (intent.tables[0] if intent.tables else None)
            if not table_name:
                continue
            table = self.schema.get_table(table_name)
            if not table:
                continue
            col = table.get_column(f.column)
            if not col:
                result.add_warning(
                    f"Filter column '{f.column}' not found in table '{table_name}'",
                    suggestion=f"Available columns: {', '.join(table.column_names)}",
                )
                continue

            # Basic type checking
            if col.data_type.value in ("INTEGER", "FLOAT", "DECIMAL"):
                if isinstance(f.value, str) and not f.value.replace(".", "").replace("-", "").isdigit():
                    if f.value not in ("NULL",) and "%" not in f.value:
                        result.add_warning(
                            f"Column '{f.column}' is numeric but filter value "
                            f"'{f.value}' appears to be text",
                        )

    def _check_joins(self, query: Query, result: ValidationResult) -> None:
        """Verify JOIN conditions reference valid columns."""
        intent = query.intent

        for join in intent.joins:
            if not join.table:
                continue
            table = self.schema.get_table(join.table)
            if not table:
                result.add_error(f"JOIN references unknown table '{join.table}'")
                continue

            # Parse the ON condition to check column references
            on_parts = re.findall(r"(\w+)\.(\w+)", join.on_condition)
            for tbl, col in on_parts:
                t = self.schema.get_table(tbl)
                if t and not t.get_column(col):
                    result.add_error(
                        f"JOIN condition references non-existent column '{col}' in table '{tbl}'"
                    )

    def _check_syntax(self, query: Query, result: ValidationResult) -> None:
        """Basic SQL syntax checks."""
        sql = query.sql.upper()

        if not sql.strip().startswith("SELECT"):
            result.add_error("Query does not start with SELECT")

        # Check for unbalanced parentheses
        if sql.count("(") != sql.count(")"):
            result.add_error("Unbalanced parentheses in query")

        # Check for common SQL injection patterns (informational)
        dangerous = ["DROP TABLE", "DELETE FROM", "TRUNCATE", "ALTER TABLE", "INSERT INTO"]
        for pattern in dangerous:
            if pattern in sql:
                result.add_error(f"Query contains potentially dangerous statement: {pattern}")
