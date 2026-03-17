"""Tests for QueryGPT data models."""

from querygpt.models import (
    AggregationType,
    Column,
    ColumnType,
    Filter,
    FilterOperator,
    ForeignKeyRelation,
    GroupByClause,
    OrderByClause,
    Schema,
    SelectField,
    SortOrder,
    Table,
)


class TestColumn:
    def test_qualified_name(self):
        col = Column(name="price", data_type=ColumnType.DECIMAL)
        assert col.qualified_name == "price"

    def test_defaults(self):
        col = Column(name="test")
        assert col.nullable is True
        assert col.primary_key is False


class TestTable:
    def test_get_column(self):
        t = Table(name="t", columns=[Column(name="id"), Column(name="name")])
        assert t.get_column("id") is not None
        assert t.get_column("missing") is None

    def test_get_primary_key(self):
        t = Table(name="t", columns=[
            Column(name="id", primary_key=True),
            Column(name="name"),
        ])
        pk = t.get_primary_key()
        assert pk is not None
        assert pk.name == "id"

    def test_column_names(self):
        t = Table(name="t", columns=[Column(name="a"), Column(name="b")])
        assert t.column_names == ["a", "b"]


class TestSchema:
    def test_get_table(self):
        s = Schema(tables=[Table(name="users")])
        assert s.get_table("users") is not None
        assert s.get_table("missing") is None

    def test_find_relation(self):
        rel = ForeignKeyRelation(from_table="orders", from_column="user_id",
                                 to_table="users", to_column="id")
        s = Schema(tables=[], relations=[rel])
        assert s.find_relation("orders", "users") is not None
        assert s.find_relation("users", "orders") is not None
        assert s.find_relation("orders", "products") is None


class TestSelectField:
    def test_to_sql_simple(self):
        f = SelectField(column="name")
        assert f.to_sql() == "name"

    def test_to_sql_with_table(self):
        f = SelectField(column="name", table="users")
        assert f.to_sql() == "users.name"

    def test_to_sql_with_aggregation(self):
        f = SelectField(column="price", aggregation=AggregationType.AVG, alias="avg_price")
        assert f.to_sql() == "AVG(price) AS avg_price"


class TestFilter:
    def test_to_sql_eq(self):
        f = Filter(column="status", operator=FilterOperator.EQ, value="active")
        assert f.to_sql() == "status = 'active'"

    def test_to_sql_gt_numeric(self):
        f = Filter(column="price", operator=FilterOperator.GT, value=100)
        assert f.to_sql() == "price > 100"

    def test_to_sql_is_null(self):
        f = Filter(column="email", operator=FilterOperator.IS_NULL)
        assert f.to_sql() == "email IS NULL"

    def test_to_sql_between(self):
        f = Filter(column="price", operator=FilterOperator.BETWEEN, value=10, value2=50)
        assert f.to_sql() == "price BETWEEN 10 AND 50"

    def test_to_sql_in(self):
        f = Filter(column="status", operator=FilterOperator.IN, value=["a", "b"])
        assert f.to_sql() == "status IN ('a', 'b')"


class TestOrderByClause:
    def test_to_sql(self):
        o = OrderByClause(column="price", direction=SortOrder.DESC)
        assert o.to_sql() == "price DESC"


class TestGroupByClause:
    def test_to_sql(self):
        g = GroupByClause(columns=["category"])
        assert g.to_sql() == "GROUP BY category"

    def test_to_sql_with_having(self):
        g = GroupByClause(columns=["category"], having="COUNT(*) > 5")
        assert "HAVING COUNT(*) > 5" in g.to_sql()


class TestForeignKeyRelation:
    def test_join_clause(self):
        rel = ForeignKeyRelation(from_table="orders", from_column="user_id",
                                 to_table="users", to_column="id")
        assert rel.join_clause == "orders.user_id = users.id"
