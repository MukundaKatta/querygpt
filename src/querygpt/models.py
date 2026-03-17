"""Data models for QueryGPT."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Schema models ---


class ColumnType(str, Enum):
    """Common SQL column types."""

    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    VARCHAR = "VARCHAR"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    DECIMAL = "DECIMAL"
    BLOB = "BLOB"


class Column(BaseModel):
    """A database column."""

    name: str
    data_type: ColumnType = ColumnType.TEXT
    nullable: bool = True
    primary_key: bool = False
    foreign_key: str | None = None  # "table.column" format
    unique: bool = False
    default: Any = None
    description: str = ""
    aliases: list[str] = Field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return self.name


class Index(BaseModel):
    """A database index."""

    name: str
    columns: list[str]
    unique: bool = False


class Table(BaseModel):
    """A database table."""

    name: str
    columns: list[Column] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)

    def get_column(self, name: str) -> Column | None:
        """Find column by name (case-insensitive)."""
        name_lower = name.lower()
        for col in self.columns:
            if col.name.lower() == name_lower:
                return col
        return None

    def get_primary_key(self) -> Column | None:
        """Return the primary key column, if any."""
        for col in self.columns:
            if col.primary_key:
                return col
        return None

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


class ForeignKeyRelation(BaseModel):
    """A foreign key relationship between two tables."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str

    @property
    def join_clause(self) -> str:
        return f"{self.from_table}.{self.from_column} = {self.to_table}.{self.to_column}"


class Schema(BaseModel):
    """A complete database schema."""

    name: str = "default"
    tables: list[Table] = Field(default_factory=list)
    relations: list[ForeignKeyRelation] = Field(default_factory=list)

    def get_table(self, name: str) -> Table | None:
        name_lower = name.lower()
        for t in self.tables:
            if t.name.lower() == name_lower:
                return t
        return None

    @property
    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]

    def find_relation(self, table1: str, table2: str) -> ForeignKeyRelation | None:
        """Find a FK relation between two tables (either direction)."""
        for rel in self.relations:
            if (rel.from_table == table1 and rel.to_table == table2) or \
               (rel.from_table == table2 and rel.to_table == table1):
                return rel
        return None


# --- Query models ---


class AggregationType(str, Enum):
    """SQL aggregation functions."""

    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"


class SortOrder(str, Enum):
    """Sort direction."""

    ASC = "ASC"
    DESC = "DESC"


class FilterOperator(str, Enum):
    """Comparison operators for WHERE clauses."""

    EQ = "="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    LIKE = "LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"


class SelectField(BaseModel):
    """A field in the SELECT clause."""

    column: str
    table: str | None = None
    alias: str | None = None
    aggregation: AggregationType | None = None

    def to_sql(self) -> str:
        parts = []
        col = f"{self.table}.{self.column}" if self.table else self.column
        if self.aggregation:
            parts.append(f"{self.aggregation.value}({col})")
        else:
            parts.append(col)
        if self.alias:
            parts.append(f"AS {self.alias}")
        return " ".join(parts)


class Filter(BaseModel):
    """A WHERE condition."""

    column: str
    table: str | None = None
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None
    value2: Any = None  # For BETWEEN

    def to_sql(self) -> str:
        col = f"{self.table}.{self.column}" if self.table else self.column
        if self.operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
            return f"{col} {self.operator.value}"
        if self.operator == FilterOperator.BETWEEN:
            return f"{col} BETWEEN {self._quote(self.value)} AND {self._quote(self.value2)}"
        if self.operator in (FilterOperator.IN, FilterOperator.NOT_IN):
            vals = ", ".join(self._quote(v) for v in (self.value if isinstance(self.value, list) else [self.value]))
            return f"{col} {self.operator.value} ({vals})"
        return f"{col} {self.operator.value} {self._quote(self.value)}"

    @staticmethod
    def _quote(val: Any) -> str:
        if isinstance(val, str):
            return f"'{val}'"
        if val is None:
            return "NULL"
        return str(val)


class JoinClause(BaseModel):
    """A JOIN clause."""

    join_type: str = "JOIN"  # JOIN, LEFT JOIN, RIGHT JOIN, etc.
    table: str = ""
    on_condition: str = ""

    def to_sql(self) -> str:
        return f"{self.join_type} {self.table} ON {self.on_condition}"


class OrderByClause(BaseModel):
    """An ORDER BY clause."""

    column: str
    table: str | None = None
    direction: SortOrder = SortOrder.ASC

    def to_sql(self) -> str:
        col = f"{self.table}.{self.column}" if self.table else self.column
        return f"{col} {self.direction.value}"


class GroupByClause(BaseModel):
    """A GROUP BY clause."""

    columns: list[str]
    having: str | None = None

    def to_sql(self) -> str:
        result = f"GROUP BY {', '.join(self.columns)}"
        if self.having:
            result += f" HAVING {self.having}"
        return result


class ParsedIntent(BaseModel):
    """The structured intent extracted from natural language."""

    raw_text: str
    select_fields: list[SelectField] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    joins: list[JoinClause] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    group_by: GroupByClause | None = None
    order_by: list[OrderByClause] = Field(default_factory=list)
    limit: int | None = None
    distinct: bool = False
    confidence: float = 0.0


class Query(BaseModel):
    """A generated SQL query with metadata."""

    sql: str
    intent: ParsedIntent
    tables_used: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class SQLResult(BaseModel):
    """Result of SQL execution (for display/testing)."""

    query: Query
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None
