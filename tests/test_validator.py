"""Tests for QueryValidator."""

import pytest

from querygpt.models import (
    Filter,
    FilterOperator,
    JoinClause,
    ParsedIntent,
    Query,
    SelectField,
)
from querygpt.schema.inspector import ECOMMERCE_SCHEMA
from querygpt.schema.validator import QueryValidator


@pytest.fixture
def validator():
    return QueryValidator(ECOMMERCE_SCHEMA)


def _make_query(sql: str, intent: ParsedIntent, tables_used: list[str] | None = None) -> Query:
    return Query(sql=sql, intent=intent, tables_used=tables_used or intent.tables)


class TestTableValidation:
    def test_valid_table(self, validator):
        intent = ParsedIntent(raw_text="test", tables=["customers"])
        query = _make_query("SELECT * FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert result.valid

    def test_invalid_table(self, validator):
        intent = ParsedIntent(raw_text="test", tables=["nonexistent"])
        query = _make_query("SELECT * FROM nonexistent;", intent, ["nonexistent"])
        result = validator.validate(query)
        assert not result.valid
        assert result.error_count > 0


class TestColumnValidation:
    def test_valid_columns(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="name", table="customers")],
            tables=["customers"],
        )
        query = _make_query("SELECT name FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert result.valid

    def test_invalid_column(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="nonexistent_col", table="customers")],
            tables=["customers"],
        )
        query = _make_query("SELECT nonexistent_col FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert not result.valid

    def test_star_column_valid(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["customers"],
        )
        query = _make_query("SELECT * FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert result.valid


class TestFilterValidation:
    def test_type_mismatch_warning(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            filters=[Filter(column="price", operator=FilterOperator.EQ, value="abc")],
        )
        query = _make_query("SELECT * FROM products WHERE price = 'abc';", intent, ["products"])
        result = validator.validate(query)
        assert result.warning_count > 0


class TestJoinValidation:
    def test_valid_join(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["orders"],
            joins=[JoinClause(
                join_type="JOIN",
                table="customers",
                on_condition="orders.customer_id = customers.id",
            )],
        )
        query = _make_query(
            "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id;",
            intent,
            ["orders", "customers"],
        )
        result = validator.validate(query)
        assert result.valid

    def test_join_invalid_column(self, validator):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["orders"],
            joins=[JoinClause(
                join_type="JOIN",
                table="customers",
                on_condition="orders.fake_col = customers.id",
            )],
        )
        query = _make_query(
            "SELECT * FROM orders JOIN customers ON orders.fake_col = customers.id;",
            intent,
            ["orders", "customers"],
        )
        result = validator.validate(query)
        assert not result.valid


class TestSyntaxChecks:
    def test_unbalanced_parens(self, validator):
        intent = ParsedIntent(raw_text="test", tables=["customers"])
        query = _make_query("SELECT COUNT(* FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert not result.valid

    def test_dangerous_statement(self, validator):
        intent = ParsedIntent(raw_text="test", tables=["customers"])
        query = _make_query("SELECT * FROM customers; DROP TABLE customers;", intent, ["customers"])
        result = validator.validate(query)
        assert not result.valid

    def test_summary(self, validator):
        intent = ParsedIntent(raw_text="test", tables=["customers"])
        query = _make_query("SELECT * FROM customers;", intent, ["customers"])
        result = validator.validate(query)
        assert "valid" in result.summary.lower() or "Valid" in result.summary
