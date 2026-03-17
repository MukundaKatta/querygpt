"""Tests for SchemaInspector."""

import pytest

from querygpt.schema.inspector import SchemaInspector


class TestBuiltinSchemas:
    def test_load_ecommerce(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        assert inspector.schema.name == "ecommerce"
        assert len(inspector.get_tables()) == 4

    def test_load_hr(self):
        inspector = SchemaInspector.from_builtin("hr")
        assert inspector.schema.name == "hr"
        assert len(inspector.get_tables()) == 2

    def test_invalid_schema_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            SchemaInspector.from_builtin("nonexistent")


class TestTableAccess:
    def test_get_table_names(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        names = inspector.get_table_names()
        assert "customers" in names
        assert "products" in names
        assert "orders" in names

    def test_get_table(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        table = inspector.get_table("products")
        assert table is not None
        assert table.name == "products"

    def test_get_nonexistent_table(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        assert inspector.get_table("nonexistent") is None


class TestColumnAccess:
    def test_get_columns(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        cols = inspector.get_columns("customers")
        col_names = [c.name for c in cols]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names


class TestRelations:
    def test_get_relations(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        rels = inspector.get_relations()
        assert len(rels) >= 2

    def test_get_relations_for_table(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        rels = inspector.get_relations_for("orders")
        assert len(rels) >= 2

    def test_describe(self):
        inspector = SchemaInspector.from_builtin("ecommerce")
        desc = inspector.describe()
        assert desc["name"] == "ecommerce"
        assert len(desc["tables"]) == 4
