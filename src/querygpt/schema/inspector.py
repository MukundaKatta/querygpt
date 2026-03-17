"""SchemaInspector - reads table/column metadata from databases or definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from querygpt.models import Column, ColumnType, ForeignKeyRelation, Index, Schema, Table


# Sample schemas for demonstration and testing

ECOMMERCE_SCHEMA = Schema(
    name="ecommerce",
    tables=[
        Table(
            name="customers",
            description="Customer accounts",
            aliases=["users", "clients", "buyers"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="name", data_type=ColumnType.VARCHAR, aliases=["customer_name", "full_name"]),
                Column(name="email", data_type=ColumnType.VARCHAR, unique=True, aliases=["email_address"]),
                Column(name="city", data_type=ColumnType.VARCHAR, aliases=["location"]),
                Column(name="country", data_type=ColumnType.VARCHAR),
                Column(name="created_at", data_type=ColumnType.DATETIME, aliases=["signup_date", "joined"]),
            ],
            indexes=[Index(name="idx_customers_email", columns=["email"], unique=True)],
        ),
        Table(
            name="products",
            description="Product catalog",
            aliases=["items", "goods"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="name", data_type=ColumnType.VARCHAR, aliases=["product_name", "title"]),
                Column(name="category", data_type=ColumnType.VARCHAR, aliases=["type", "department"]),
                Column(name="price", data_type=ColumnType.DECIMAL, aliases=["cost", "amount"]),
                Column(name="stock", data_type=ColumnType.INTEGER, aliases=["quantity", "inventory"]),
                Column(name="rating", data_type=ColumnType.FLOAT, aliases=["score", "stars"]),
            ],
            indexes=[
                Index(name="idx_products_category", columns=["category"]),
                Index(name="idx_products_price", columns=["price"]),
            ],
        ),
        Table(
            name="orders",
            description="Customer orders",
            aliases=["purchases", "transactions"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="customer_id", data_type=ColumnType.INTEGER, foreign_key="customers.id"),
                Column(name="product_id", data_type=ColumnType.INTEGER, foreign_key="products.id"),
                Column(name="quantity", data_type=ColumnType.INTEGER, aliases=["qty", "amount"]),
                Column(name="total_price", data_type=ColumnType.DECIMAL, aliases=["total", "order_total"]),
                Column(name="status", data_type=ColumnType.VARCHAR, aliases=["order_status"]),
                Column(name="order_date", data_type=ColumnType.DATETIME, aliases=["date", "ordered_at"]),
            ],
            indexes=[
                Index(name="idx_orders_customer", columns=["customer_id"]),
                Index(name="idx_orders_product", columns=["product_id"]),
                Index(name="idx_orders_date", columns=["order_date"]),
            ],
        ),
        Table(
            name="reviews",
            description="Product reviews",
            aliases=["feedback", "ratings"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="customer_id", data_type=ColumnType.INTEGER, foreign_key="customers.id"),
                Column(name="product_id", data_type=ColumnType.INTEGER, foreign_key="products.id"),
                Column(name="rating", data_type=ColumnType.INTEGER, aliases=["score", "stars"]),
                Column(name="comment", data_type=ColumnType.TEXT, aliases=["review_text", "feedback"]),
                Column(name="created_at", data_type=ColumnType.DATETIME),
            ],
        ),
    ],
    relations=[
        ForeignKeyRelation(from_table="orders", from_column="customer_id", to_table="customers", to_column="id"),
        ForeignKeyRelation(from_table="orders", from_column="product_id", to_table="products", to_column="id"),
        ForeignKeyRelation(from_table="reviews", from_column="customer_id", to_table="customers", to_column="id"),
        ForeignKeyRelation(from_table="reviews", from_column="product_id", to_table="products", to_column="id"),
    ],
)

HR_SCHEMA = Schema(
    name="hr",
    tables=[
        Table(
            name="employees",
            description="Employee records",
            aliases=["staff", "workers", "people"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="name", data_type=ColumnType.VARCHAR, aliases=["employee_name", "full_name"]),
                Column(name="department_id", data_type=ColumnType.INTEGER, foreign_key="departments.id"),
                Column(name="salary", data_type=ColumnType.DECIMAL, aliases=["pay", "wage", "compensation"]),
                Column(name="hire_date", data_type=ColumnType.DATE, aliases=["start_date", "joined"]),
                Column(name="title", data_type=ColumnType.VARCHAR, aliases=["position", "role", "job_title"]),
                Column(name="manager_id", data_type=ColumnType.INTEGER, foreign_key="employees.id"),
            ],
        ),
        Table(
            name="departments",
            description="Company departments",
            aliases=["depts", "teams", "divisions"],
            columns=[
                Column(name="id", data_type=ColumnType.INTEGER, primary_key=True, nullable=False),
                Column(name="name", data_type=ColumnType.VARCHAR, aliases=["department_name", "dept_name"]),
                Column(name="budget", data_type=ColumnType.DECIMAL),
                Column(name="location", data_type=ColumnType.VARCHAR, aliases=["office"]),
            ],
        ),
    ],
    relations=[
        ForeignKeyRelation(from_table="employees", from_column="department_id", to_table="departments", to_column="id"),
    ],
)


class SchemaInspector:
    """Reads and provides database schema metadata.

    Can load schemas from built-in samples, JSON files, or live database connections.
    """

    BUILTIN_SCHEMAS: dict[str, Schema] = {
        "ecommerce": ECOMMERCE_SCHEMA,
        "hr": HR_SCHEMA,
    }

    def __init__(self, schema: Schema | None = None) -> None:
        self._schema = schema

    @classmethod
    def from_builtin(cls, name: str) -> SchemaInspector:
        """Load a built-in sample schema."""
        schema = cls.BUILTIN_SCHEMAS.get(name)
        if not schema:
            available = ", ".join(cls.BUILTIN_SCHEMAS.keys())
            raise ValueError(f"Unknown built-in schema '{name}'. Available: {available}")
        return cls(schema)

    @classmethod
    def from_json(cls, path: str | Path) -> SchemaInspector:
        """Load schema from a JSON file."""
        data = json.loads(Path(path).read_text())
        schema = Schema(**data)
        return cls(schema)

    @property
    def schema(self) -> Schema:
        if not self._schema:
            raise RuntimeError("No schema loaded")
        return self._schema

    def get_table(self, name: str) -> Table | None:
        return self.schema.get_table(name)

    def get_tables(self) -> list[Table]:
        return self.schema.tables

    def get_table_names(self) -> list[str]:
        return self.schema.table_names

    def get_columns(self, table_name: str) -> list[Column]:
        table = self.schema.get_table(table_name)
        return table.columns if table else []

    def get_relations(self) -> list[ForeignKeyRelation]:
        return self.schema.relations

    def get_relations_for(self, table_name: str) -> list[ForeignKeyRelation]:
        return [
            r for r in self.schema.relations
            if r.from_table == table_name or r.to_table == table_name
        ]

    def describe(self) -> dict[str, Any]:
        """Return a summary dict of the schema."""
        return {
            "name": self.schema.name,
            "tables": [
                {
                    "name": t.name,
                    "columns": [c.name for c in t.columns],
                    "description": t.description,
                }
                for t in self.schema.tables
            ],
            "relations": [
                f"{r.from_table}.{r.from_column} -> {r.to_table}.{r.to_column}"
                for r in self.schema.relations
            ],
        }
