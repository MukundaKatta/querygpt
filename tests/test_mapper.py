"""Tests for SchemaMapper."""

import pytest

from querygpt.schema.inspector import ECOMMERCE_SCHEMA
from querygpt.schema.mapper import SchemaMapper


@pytest.fixture
def mapper():
    return SchemaMapper(ECOMMERCE_SCHEMA)


class TestTableMapping:
    def test_exact_match(self, mapper):
        result = mapper.map_table("customers")
        assert result.table == "customers"
        assert result.confidence == 1.0

    def test_alias_match(self, mapper):
        result = mapper.map_table("users")
        assert result.table == "customers"
        assert result.source == "alias"

    def test_plural_match(self, mapper):
        result = mapper.map_table("customer")
        assert result.table == "customers"
        assert result.confidence >= 0.9

    def test_items_alias(self, mapper):
        result = mapper.map_table("items")
        assert result.table == "products"

    def test_purchases_alias(self, mapper):
        result = mapper.map_table("purchases")
        assert result.table == "orders"

    def test_unknown_table(self, mapper):
        result = mapper.map_table("xyzzy")
        assert result.confidence == 0.0


class TestColumnMapping:
    def test_exact_column(self, mapper):
        result = mapper.map_column("price")
        assert result.column == "price"
        assert result.table == "products"

    def test_alias_column(self, mapper):
        result = mapper.map_column("email_address")
        assert result.column == "email"
        assert result.table == "customers"

    def test_column_with_table_hint(self, mapper):
        result = mapper.map_column("name", table_hint="products")
        assert result.table == "products"
        assert result.column == "name"

    def test_cost_alias(self, mapper):
        result = mapper.map_column("cost")
        assert result.column == "price"

    def test_unknown_column(self, mapper):
        result = mapper.map_column("xyzzy_field")
        # Should have low or zero confidence
        assert result.confidence < 0.5


class TestBulkMapping:
    def test_map_multiple_terms(self, mapper):
        results = mapper.map_terms(["customers", "price", "email"])
        assert len(results) == 3
        assert results[0].table == "customers"


class TestNormalization:
    def test_singularize(self):
        assert SchemaMapper._singularize("customers") == "customer"
        assert SchemaMapper._singularize("categories") == "category"
        assert SchemaMapper._singularize("boxes") == "box"

    def test_pluralize(self):
        assert SchemaMapper._pluralize("customer") == "customers"
        assert SchemaMapper._pluralize("category") == "categories"
        assert SchemaMapper._pluralize("box") == "boxes"
