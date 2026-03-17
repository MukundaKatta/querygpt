"""Tests for SQLGenerator."""

import pytest

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
from querygpt.schema.inspector import ECOMMERCE_SCHEMA
from querygpt.translator.generator import SQLGenerator


@pytest.fixture
def generator():
    return SQLGenerator(schema=ECOMMERCE_SCHEMA)


@pytest.fixture
def basic_generator():
    return SQLGenerator()


class TestSelectGeneration:
    def test_simple_select_all(self, generator):
        intent = ParsedIntent(
            raw_text="show all customers",
            select_fields=[SelectField(column="*")],
            tables=["customers"],
        )
        query = generator.generate(intent)
        assert "SELECT *" in query.sql
        assert "FROM customers" in query.sql

    def test_select_specific_columns(self, generator):
        intent = ParsedIntent(
            raw_text="show name and email",
            select_fields=[
                SelectField(column="name", table="customers"),
                SelectField(column="email", table="customers"),
            ],
            tables=["customers"],
        )
        query = generator.generate(intent)
        assert "customers.name" in query.sql
        assert "customers.email" in query.sql

    def test_select_distinct(self, generator):
        intent = ParsedIntent(
            raw_text="distinct categories",
            select_fields=[SelectField(column="category")],
            tables=["products"],
            distinct=True,
        )
        query = generator.generate(intent)
        assert "SELECT DISTINCT" in query.sql


class TestWhereGeneration:
    def test_simple_filter(self, generator):
        intent = ParsedIntent(
            raw_text="products over 100",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            filters=[Filter(column="price", operator=FilterOperator.GT, value=100)],
        )
        query = generator.generate(intent)
        assert "WHERE" in query.sql
        assert "price > 100" in query.sql

    def test_string_filter(self, generator):
        intent = ParsedIntent(
            raw_text="shipped orders",
            select_fields=[SelectField(column="*")],
            tables=["orders"],
            filters=[Filter(column="status", operator=FilterOperator.EQ, value="shipped")],
        )
        query = generator.generate(intent)
        assert "'shipped'" in query.sql

    def test_multiple_filters(self, generator):
        intent = ParsedIntent(
            raw_text="complex filter",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            filters=[
                Filter(column="price", operator=FilterOperator.GT, value=50),
                Filter(column="stock", operator=FilterOperator.GT, value=0),
            ],
        )
        query = generator.generate(intent)
        assert "AND" in query.sql


class TestJoinGeneration:
    def test_auto_join(self, generator):
        intent = ParsedIntent(
            raw_text="orders with customers",
            select_fields=[SelectField(column="*")],
            tables=["orders", "customers"],
        )
        query = generator.generate(intent)
        assert "JOIN" in query.sql
        assert "customers" in query.sql

    def test_no_schema_cross_join(self, basic_generator):
        intent = ParsedIntent(
            raw_text="a and b",
            select_fields=[SelectField(column="*")],
            tables=["a", "b"],
        )
        query = basic_generator.generate(intent)
        assert "CROSS JOIN" in query.sql


class TestGroupByGeneration:
    def test_group_by(self, generator):
        intent = ParsedIntent(
            raw_text="count by category",
            select_fields=[SelectField(column="*", aggregation=AggregationType.COUNT)],
            tables=["products"],
            group_by=GroupByClause(columns=["category"]),
        )
        query = generator.generate(intent)
        assert "GROUP BY category" in query.sql

    def test_group_by_having(self, generator):
        intent = ParsedIntent(
            raw_text="having clause",
            select_fields=[SelectField(column="*", aggregation=AggregationType.COUNT, alias="cnt")],
            tables=["orders"],
            group_by=GroupByClause(columns=["customer_id"], having="COUNT(*) > 5"),
        )
        query = generator.generate(intent)
        assert "HAVING" in query.sql


class TestOrderByGeneration:
    def test_order_desc(self, generator):
        intent = ParsedIntent(
            raw_text="order by price desc",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            order_by=[OrderByClause(column="price", direction=SortOrder.DESC)],
        )
        query = generator.generate(intent)
        assert "ORDER BY" in query.sql
        assert "DESC" in query.sql


class TestLimitGeneration:
    def test_limit(self, generator):
        intent = ParsedIntent(
            raw_text="top 10",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            limit=10,
        )
        query = generator.generate(intent)
        assert "LIMIT 10" in query.sql


class TestQueryMetadata:
    def test_tables_used(self, generator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["products"],
        )
        query = generator.generate(intent)
        assert "products" in query.tables_used

    def test_warnings_on_no_table(self, basic_generator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=[],
        )
        query = basic_generator.generate(intent)
        assert any("table" in w.lower() for w in query.warnings)
