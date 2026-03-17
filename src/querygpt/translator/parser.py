"""NLParser - extracts entities, filters, and aggregations from natural language."""

from __future__ import annotations

import re
from typing import Any

from querygpt.models import (
    AggregationType,
    Filter,
    FilterOperator,
    GroupByClause,
    OrderByClause,
    ParsedIntent,
    SelectField,
    SortOrder,
)


# Mapping from natural language terms to aggregation types
AGGREGATION_KEYWORDS: dict[str, AggregationType] = {
    "count": AggregationType.COUNT,
    "number of": AggregationType.COUNT,
    "how many": AggregationType.COUNT,
    "total": AggregationType.SUM,
    "sum": AggregationType.SUM,
    "sum of": AggregationType.SUM,
    "average": AggregationType.AVG,
    "avg": AggregationType.AVG,
    "mean": AggregationType.AVG,
    "minimum": AggregationType.MIN,
    "min": AggregationType.MIN,
    "lowest": AggregationType.MIN,
    "smallest": AggregationType.MIN,
    "maximum": AggregationType.MAX,
    "max": AggregationType.MAX,
    "highest": AggregationType.MAX,
    "largest": AggregationType.MAX,
    "most": AggregationType.MAX,
    "biggest": AggregationType.MAX,
    "top": AggregationType.MAX,
}

# Mapping from natural language operators to SQL operators
OPERATOR_KEYWORDS: dict[str, FilterOperator] = {
    "equal to": FilterOperator.EQ,
    "equals": FilterOperator.EQ,
    "is": FilterOperator.EQ,
    "are": FilterOperator.EQ,
    "was": FilterOperator.EQ,
    "not equal to": FilterOperator.NEQ,
    "isn't": FilterOperator.NEQ,
    "is not": FilterOperator.NEQ,
    "greater than": FilterOperator.GT,
    "more than": FilterOperator.GT,
    "above": FilterOperator.GT,
    "over": FilterOperator.GT,
    "exceeds": FilterOperator.GT,
    "at least": FilterOperator.GTE,
    "greater than or equal": FilterOperator.GTE,
    "no less than": FilterOperator.GTE,
    "less than": FilterOperator.LT,
    "below": FilterOperator.LT,
    "under": FilterOperator.LT,
    "fewer than": FilterOperator.LT,
    "at most": FilterOperator.LTE,
    "less than or equal": FilterOperator.LTE,
    "no more than": FilterOperator.LTE,
    "like": FilterOperator.LIKE,
    "contains": FilterOperator.LIKE,
    "containing": FilterOperator.LIKE,
    "starts with": FilterOperator.LIKE,
    "starting with": FilterOperator.LIKE,
    "ends with": FilterOperator.LIKE,
    "ending with": FilterOperator.LIKE,
    "between": FilterOperator.BETWEEN,
    "in": FilterOperator.IN,
}

# Sort keywords
SORT_KEYWORDS: dict[str, SortOrder] = {
    "ascending": SortOrder.ASC,
    "asc": SortOrder.ASC,
    "alphabetical": SortOrder.ASC,
    "lowest first": SortOrder.ASC,
    "oldest first": SortOrder.ASC,
    "descending": SortOrder.DESC,
    "desc": SortOrder.DESC,
    "highest first": SortOrder.DESC,
    "newest first": SortOrder.DESC,
    "reverse": SortOrder.DESC,
}


class NLParser:
    """Parses natural language questions into structured ParsedIntent objects.

    The parser uses keyword matching and regex patterns to extract:
    - Entities (tables, columns)
    - Filters (WHERE conditions)
    - Aggregations (COUNT, SUM, AVG, etc.)
    - Sorting (ORDER BY)
    - Grouping (GROUP BY)
    - Limits (LIMIT)
    """

    def __init__(self, known_tables: list[str] | None = None,
                 known_columns: dict[str, list[str]] | None = None) -> None:
        self.known_tables = [t.lower() for t in (known_tables or [])]
        self.known_columns = {
            t.lower(): [c.lower() for c in cols]
            for t, cols in (known_columns or {}).items()
        }

    def parse(self, text: str) -> ParsedIntent:
        """Parse natural language text into a structured intent."""
        text = text.strip()
        if not text:
            return ParsedIntent(raw_text=text, confidence=0.0)

        text_lower = text.lower()
        intent = ParsedIntent(raw_text=text)

        # Extract tables
        intent.tables = self._extract_tables(text_lower)

        # Extract aggregations and select fields
        intent.select_fields = self._extract_select_fields(text_lower, intent.tables)

        # Extract filters
        intent.filters = self._extract_filters(text_lower)

        # Extract ordering
        intent.order_by = self._extract_order_by(text_lower)

        # Extract grouping
        intent.group_by = self._extract_group_by(text_lower, intent.select_fields)

        # Extract limit
        intent.limit = self._extract_limit(text_lower)

        # Extract distinct
        intent.distinct = self._detect_distinct(text_lower)

        # Calculate confidence based on how many components were extracted
        parts = sum([
            bool(intent.tables),
            bool(intent.select_fields),
            bool(intent.filters),
            bool(intent.order_by),
            bool(intent.group_by),
        ])
        intent.confidence = min(1.0, parts * 0.25)

        return intent

    def _extract_tables(self, text: str) -> list[str]:
        """Find table names mentioned in the text."""
        found: list[str] = []

        # Check for "from <table>" pattern
        from_match = re.findall(r"\bfrom\s+(\w+)", text)
        for t in from_match:
            if t.lower() in self.known_tables or not self.known_tables:
                found.append(t)

        # Check for "in <table>" pattern
        in_match = re.findall(r"\bin\s+(?:the\s+)?(\w+)\s+table", text)
        for t in in_match:
            if t not in found:
                found.append(t)

        # Check for known table names anywhere in text
        for table in self.known_tables:
            if table in text and table not in [f.lower() for f in found]:
                found.append(table)

        return found

    def _extract_select_fields(self, text: str, tables: list[str]) -> list[SelectField]:
        """Extract columns and aggregations for the SELECT clause."""
        fields: list[SelectField] = []

        # Check for aggregation keywords
        for keyword, agg_type in AGGREGATION_KEYWORDS.items():
            pattern = rf"\b{re.escape(keyword)}\s+(?:of\s+)?(?:the\s+)?(\w+)"
            match = re.search(pattern, text)
            if match:
                col = match.group(1)
                # Skip if the matched word is a table name or common word
                if col in ("the", "all", "each", "every", "from", "in", "by"):
                    col = "*"
                table = tables[0] if tables else None
                alias = f"{agg_type.value.lower()}_{col}" if col != "*" else f"{agg_type.value.lower()}_all"
                fields.append(SelectField(
                    column=col,
                    table=table,
                    aggregation=agg_type,
                    alias=alias,
                ))

        # Check for "show <columns>" or "get <columns>" or "list <columns>"
        show_match = re.search(
            r"\b(?:show|get|list|display|find|give me|select|what (?:is|are))\s+(?:me\s+)?(?:the\s+)?(?:all\s+)?(.+?)(?:\s+from\s+|\s+in\s+|\s+where\s+|\s+order|\s+sort|\s+group|\s+limit|$)",
            text,
        )
        if show_match and not fields:
            col_text = show_match.group(1).strip()
            # Split on "and" or ","
            col_names = re.split(r"\s*(?:,|and)\s*", col_text)
            for col_name in col_names:
                col_name = col_name.strip()
                if col_name and col_name not in ("the", "all", "every"):
                    table = tables[0] if tables else None
                    fields.append(SelectField(column=col_name.replace(" ", "_"), table=table))

        # Default: select all
        if not fields:
            fields.append(SelectField(column="*"))

        return fields

    def _extract_filters(self, text: str) -> list[Filter]:
        """Extract WHERE conditions from text."""
        filters: list[Filter] = []

        # Pattern: "where <column> <operator> <value>"
        where_match = re.search(r"\bwhere\s+(.+?)(?:\s+order|\s+sort|\s+group|\s+limit|$)", text)
        if where_match:
            filter_text = where_match.group(1)
            parsed = self._parse_filter_expression(filter_text)
            if parsed:
                filters.extend(parsed)
            return filters

        # Pattern: "with <column> <operator> <value>"
        with_match = re.search(r"\bwith\s+(\w+)\s+(.+?)(?:\s+order|\s+sort|\s+group|\s+limit|$)", text)
        if with_match:
            col = with_match.group(1)
            rest = with_match.group(2)
            f = self._parse_condition(col, rest)
            if f:
                filters.append(f)

        # Pattern: "<column> greater/less than <value>"
        for op_keyword, op in OPERATOR_KEYWORDS.items():
            pattern = rf"(\w+)\s+{re.escape(op_keyword)}\s+(\S+)"
            match = re.search(pattern, text)
            if match and not filters:
                col = match.group(1)
                val = self._parse_value(match.group(2))
                if col not in ("is", "are", "the", "a", "an"):
                    filters.append(Filter(column=col, operator=op, value=val))

        return filters

    def _parse_filter_expression(self, text: str) -> list[Filter]:
        """Parse a filter expression like 'age > 25 and name = John'."""
        filters: list[Filter] = []
        # Split on 'and'
        parts = re.split(r"\s+and\s+", text)
        for part in parts:
            part = part.strip()
            # Try operator patterns
            for op_str, op_enum in [
                (">=", FilterOperator.GTE), ("<=", FilterOperator.LTE),
                ("!=", FilterOperator.NEQ), ("=", FilterOperator.EQ),
                (">", FilterOperator.GT), ("<", FilterOperator.LT),
            ]:
                match = re.match(rf"(\w+)\s*{re.escape(op_str)}\s*(.+)", part)
                if match:
                    col = match.group(1).strip()
                    val = self._parse_value(match.group(2).strip().strip("'\""))
                    filters.append(Filter(column=col, operator=op_enum, value=val))
                    break
            else:
                # Try NL operators
                for kw, op in OPERATOR_KEYWORDS.items():
                    pattern = rf"(\w+)\s+{re.escape(kw)}\s+(.+)"
                    match = re.match(pattern, part)
                    if match:
                        col = match.group(1)
                        val = self._parse_value(match.group(2).strip().strip("'\""))
                        if op == FilterOperator.LIKE:
                            if "starts with" in kw or "starting with" in kw:
                                val = f"{val}%"
                            elif "ends with" in kw or "ending with" in kw:
                                val = f"%{val}"
                            else:
                                val = f"%{val}%"
                        filters.append(Filter(column=col, operator=op, value=val))
                        break
        return filters

    def _parse_condition(self, column: str, rest: str) -> Filter | None:
        """Parse a condition expression for a known column."""
        for kw, op in OPERATOR_KEYWORDS.items():
            if rest.startswith(kw):
                val_text = rest[len(kw):].strip().strip("'\"")
                return Filter(column=column, operator=op, value=self._parse_value(val_text))
        # Default to equals
        val = rest.strip().strip("'\"")
        return Filter(column=column, operator=FilterOperator.EQ, value=self._parse_value(val))

    def _extract_order_by(self, text: str) -> list[OrderByClause]:
        """Extract ORDER BY from text."""
        orders: list[OrderByClause] = []

        # "order by <column> [asc/desc]" or "sort by <column>"
        match = re.search(r"\b(?:order|sort|sorted)\s+by\s+(\w+)(?:\s+(asc|desc|ascending|descending))?", text)
        if match:
            col = match.group(1)
            direction = SortOrder.ASC
            if match.group(2):
                dir_text = match.group(2).lower()
                direction = SORT_KEYWORDS.get(dir_text, SortOrder.ASC)
            orders.append(OrderByClause(column=col, direction=direction))
            return orders

        # "highest/lowest <column>" implies ordering
        high_match = re.search(r"\b(?:highest|largest|most|top)\s+(\w+)", text)
        if high_match:
            orders.append(OrderByClause(column=high_match.group(1), direction=SortOrder.DESC))

        low_match = re.search(r"\b(?:lowest|smallest|least)\s+(\w+)", text)
        if low_match:
            orders.append(OrderByClause(column=low_match.group(1), direction=SortOrder.ASC))

        return orders

    def _extract_group_by(self, text: str, fields: list[SelectField]) -> GroupByClause | None:
        """Extract GROUP BY from text."""
        # Explicit "group by"
        match = re.search(r"\bgroup(?:ed)?\s+by\s+(\w+(?:\s*,\s*\w+)*)", text)
        if match:
            cols = [c.strip() for c in match.group(1).split(",")]
            having = None
            having_match = re.search(r"\bhaving\s+(.+?)(?:\s+order|\s+sort|\s+limit|$)", text)
            if having_match:
                having = having_match.group(1).strip()
            return GroupByClause(columns=cols, having=having)

        # "per <column>" or "by <column>" or "for each <column>"
        per_match = re.search(r"\b(?:per|by|for each|for every)\s+(\w+)", text)
        if per_match:
            col = per_match.group(1)
            # Only if there's an aggregation in the fields
            has_agg = any(f.aggregation for f in fields)
            if has_agg and col not in ("the", "a", "an"):
                return GroupByClause(columns=[col])

        return None

    def _extract_limit(self, text: str) -> int | None:
        """Extract LIMIT from text."""
        match = re.search(r"\blimit\s+(\d+)", text)
        if match:
            return int(match.group(1))

        match = re.search(r"\btop\s+(\d+)", text)
        if match:
            return int(match.group(1))

        match = re.search(r"\bfirst\s+(\d+)", text)
        if match:
            return int(match.group(1))

        return None

    def _detect_distinct(self, text: str) -> bool:
        """Detect if the query should use DISTINCT."""
        return bool(re.search(r"\b(?:distinct|unique|different)\b", text))

    @staticmethod
    def _parse_value(val: str) -> Any:
        """Try to convert a string value to the appropriate Python type."""
        val = val.strip().rstrip(".")
        if not val:
            return val
        # Try integer
        try:
            return int(val)
        except ValueError:
            pass
        # Try float
        try:
            return float(val)
        except ValueError:
            pass
        # Boolean
        if val.lower() in ("true", "yes"):
            return True
        if val.lower() in ("false", "no"):
            return False
        return val
