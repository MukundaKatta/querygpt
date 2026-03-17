"""Tests for QueryOptimizer."""

import pytest

from querygpt.models import (
    AggregationType,
    Filter,
    FilterOperator,
    GroupByClause,
    OrderByClause,
    ParsedIntent,
    Query,
    SelectField,
    SortOrder,
)
from querygpt.schema.inspector import ECOMMERCE_SCHEMA
from querygpt.translator.optimizer import QueryOptimizer


@pytest.fixture
def optimizer():
    return QueryOptimizer(schema=ECOMMERCE_SCHEMA)


def _make_query(sql: str, intent: ParsedIntent) -> Query:
    return Query(sql=sql, intent=intent, tables_used=intent.tables)


class TestSelectStar:
    def test_warns_on_select_star(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["products"],
        )
        query = _make_query("SELECT * FROM products;", intent)
        report = optimizer.analyze(query)
        assert any("SELECT *" in s.message for s in report.suggestions)

    def test_no_warning_on_specific_columns(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="name")],
            tables=["products"],
        )
        query = _make_query("SELECT name FROM products;", intent)
        report = optimizer.analyze(query)
        assert not any("SELECT *" in s.message for s in report.suggestions)


class TestMissingLimit:
    def test_suggests_limit(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="name")],
            tables=["products"],
        )
        query = _make_query("SELECT name FROM products;", intent)
        report = optimizer.analyze(query)
        assert any("LIMIT" in s.message for s in report.suggestions)


class TestIndexSuggestions:
    def test_suggests_index_for_unindexed_filter(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["customers"],
            filters=[Filter(column="city", operator=FilterOperator.EQ, value="London")],
        )
        query = _make_query("SELECT * FROM customers WHERE city = 'London';", intent)
        report = optimizer.analyze(query)
        assert any("index" in s.message.lower() for s in report.suggestions)

    def test_no_index_warning_for_indexed_column(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["products"],
            filters=[Filter(column="category", operator=FilterOperator.EQ, value="Electronics")],
        )
        query = _make_query("SELECT * FROM products WHERE category = 'Electronics';", intent)
        report = optimizer.analyze(query)
        # category has an index in the schema, so no index warning for this specific column
        index_warnings = [s for s in report.suggestions if s.category == "index" and "category" in s.message]
        assert len(index_warnings) == 0


class TestLikePatterns:
    def test_warns_leading_wildcard(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["customers"],
            filters=[Filter(column="name", operator=FilterOperator.LIKE, value="%john%")],
        )
        query = _make_query("SELECT * FROM customers WHERE name LIKE '%john%';", intent)
        report = optimizer.analyze(query)
        assert any("wildcard" in s.message.lower() for s in report.suggestions)


class TestCrossJoin:
    def test_warns_cross_join(self, optimizer):
        intent = ParsedIntent(raw_text="test", select_fields=[SelectField(column="*")], tables=["a", "b"])
        query = _make_query("SELECT * FROM a CROSS JOIN b;", intent)
        report = optimizer.analyze(query)
        assert any("CROSS JOIN" in s.message for s in report.suggestions)


class TestSuggestIndexes:
    def test_generates_create_index(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["customers"],
            filters=[Filter(column="city", operator=FilterOperator.EQ, value="NYC")],
        )
        query = _make_query("SELECT * FROM customers WHERE city = 'NYC';", intent)
        indexes = optimizer.suggest_indexes(query)
        assert any("CREATE INDEX" in idx for idx in indexes)
        assert any("city" in idx for idx in indexes)


class TestCostEstimate:
    def test_high_cost_for_unfiltered_select_star(self, optimizer):
        intent = ParsedIntent(
            raw_text="test",
            select_fields=[SelectField(column="*")],
            tables=["products"],
        )
        query = _make_query("SELECT * FROM products;", intent)
        report = optimizer.analyze(query)
        assert report.estimated_cost in ("medium", "high")
