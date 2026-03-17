"""SQLGenerator - builds SQL from parsed intent."""

from __future__ import annotations

from querygpt.models import (
    ForeignKeyRelation,
    JoinClause,
    ParsedIntent,
    Query,
    Schema,
    SelectField,
)


class SQLGenerator:
    """Builds SQL queries from a ParsedIntent.

    Supports SELECT, JOIN, WHERE, GROUP BY, ORDER BY, HAVING, LIMIT, DISTINCT.
    Uses schema information to resolve table/column names and generate JOIN clauses.
    """

    def __init__(self, schema: Schema | None = None) -> None:
        self.schema = schema

    def generate(self, intent: ParsedIntent) -> Query:
        """Generate a SQL query from a parsed intent."""
        parts: list[str] = []
        warnings: list[str] = []
        tables_used: list[str] = list(intent.tables)

        # SELECT clause
        select_clause = self._build_select(intent, warnings)
        parts.append(select_clause)

        # FROM clause
        from_clause = self._build_from(intent, warnings)
        if from_clause:
            parts.append(from_clause)

        # JOIN clauses
        join_clauses = self._build_joins(intent, warnings)
        if join_clauses:
            parts.extend(join_clauses)
            # Track joined tables
            for join in intent.joins:
                if join.table and join.table not in tables_used:
                    tables_used.append(join.table)

        # WHERE clause
        where_clause = self._build_where(intent, warnings)
        if where_clause:
            parts.append(where_clause)

        # GROUP BY clause
        group_clause = self._build_group_by(intent, warnings)
        if group_clause:
            parts.append(group_clause)

        # ORDER BY clause
        order_clause = self._build_order_by(intent, warnings)
        if order_clause:
            parts.append(order_clause)

        # LIMIT clause
        if intent.limit:
            parts.append(f"LIMIT {intent.limit}")

        sql = "\n".join(parts) + ";"

        return Query(
            sql=sql,
            intent=intent,
            tables_used=tables_used,
            confidence=intent.confidence,
            warnings=warnings,
        )

    def _build_select(self, intent: ParsedIntent, warnings: list[str]) -> str:
        """Build the SELECT clause."""
        keyword = "SELECT DISTINCT" if intent.distinct else "SELECT"

        if not intent.select_fields:
            return f"{keyword} *"

        field_strs = [f.to_sql() for f in intent.select_fields]
        return f"{keyword} {', '.join(field_strs)}"

    def _build_from(self, intent: ParsedIntent, warnings: list[str]) -> str:
        """Build the FROM clause."""
        if not intent.tables:
            warnings.append("No table specified; FROM clause omitted")
            return ""
        return f"FROM {intent.tables[0]}"

    def _build_joins(self, intent: ParsedIntent, warnings: list[str]) -> list[str]:
        """Build JOIN clauses using schema relations."""
        join_strs: list[str] = []

        # If multiple tables and no explicit joins, try to auto-join via schema
        if len(intent.tables) > 1 and not intent.joins:
            primary = intent.tables[0]
            for other_table in intent.tables[1:]:
                join = self._find_join(primary, other_table)
                if join:
                    intent.joins.append(join)
                    join_strs.append(join.to_sql())
                else:
                    warnings.append(
                        f"No known relationship between '{primary}' and '{other_table}'; "
                        "using CROSS JOIN"
                    )
                    join_strs.append(f"CROSS JOIN {other_table}")

        # Render explicit joins
        for join in intent.joins:
            sql = join.to_sql()
            if sql not in join_strs:
                join_strs.append(sql)

        return join_strs

    def _build_where(self, intent: ParsedIntent, warnings: list[str]) -> str:
        """Build the WHERE clause."""
        if not intent.filters:
            return ""
        conditions = [f.to_sql() for f in intent.filters]
        return "WHERE " + " AND ".join(conditions)

    def _build_group_by(self, intent: ParsedIntent, warnings: list[str]) -> str:
        """Build the GROUP BY / HAVING clause."""
        if not intent.group_by:
            return ""
        return intent.group_by.to_sql()

    def _build_order_by(self, intent: ParsedIntent, warnings: list[str]) -> str:
        """Build the ORDER BY clause."""
        if not intent.order_by:
            return ""
        clauses = [o.to_sql() for o in intent.order_by]
        return "ORDER BY " + ", ".join(clauses)

    def _find_join(self, table1: str, table2: str) -> JoinClause | None:
        """Try to find a join condition between two tables from the schema."""
        if not self.schema:
            return None

        rel = self.schema.find_relation(table1, table2)
        if rel:
            return JoinClause(
                join_type="JOIN",
                table=table2,
                on_condition=rel.join_clause,
            )
        return None
