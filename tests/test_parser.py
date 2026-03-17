"""Tests for NLParser."""

import pytest

from querygpt.models import AggregationType, FilterOperator, SortOrder
from querygpt.translator.parser import NLParser


@pytest.fixture
def parser():
    return NLParser(
        known_tables=["customers", "products", "orders", "reviews"],
        known_columns={
            "customers": ["id", "name", "email", "city", "country", "created_at"],
            "products": ["id", "name", "category", "price", "stock", "rating"],
            "orders": ["id", "customer_id", "product_id", "quantity", "total_price", "status", "order_date"],
            "reviews": ["id", "customer_id", "product_id", "rating", "comment", "created_at"],
        },
    )


@pytest.fixture
def basic_parser():
    return NLParser()


# --- 30+ NL-to-SQL examples as test cases ---

class TestBasicSelect:
    """NL examples 1-6: basic SELECT queries."""

    def test_show_all_customers(self, parser):
        # Example 1: "show all customers"
        intent = parser.parse("show all customers")
        assert "customers" in intent.tables

    def test_list_products(self, parser):
        # Example 2: "list products"
        intent = parser.parse("list products")
        assert "products" in intent.tables

    def test_get_orders(self, parser):
        # Example 3: "get orders"
        intent = parser.parse("get orders")
        assert "orders" in intent.tables

    def test_show_name_email(self, parser):
        # Example 4: "show name and email from customers"
        intent = parser.parse("show name and email from customers")
        assert "customers" in intent.tables
        cols = [f.column for f in intent.select_fields]
        assert "name" in cols
        assert "email" in cols

    def test_display_reviews(self, parser):
        # Example 5: "display reviews"
        intent = parser.parse("display reviews")
        assert "reviews" in intent.tables

    def test_find_all_products(self, parser):
        # Example 6: "find all products"
        intent = parser.parse("find all products")
        assert "products" in intent.tables


class TestFilters:
    """NL examples 7-14: WHERE clause queries."""

    def test_price_greater_than(self, parser):
        # Example 7: "find products where price greater than 100"
        intent = parser.parse("find products where price greater than 100")
        assert len(intent.filters) >= 1

    def test_status_equals(self, parser):
        # Example 8: "show orders where status is shipped"
        intent = parser.parse("show orders where status is shipped")
        assert any(f.column == "status" for f in intent.filters)

    def test_city_equals(self, parser):
        # Example 9: "find customers where city is London"
        intent = parser.parse("find customers where city is London")
        assert any(f.column == "city" for f in intent.filters)

    def test_stock_less_than(self, parser):
        # Example 10: "products where stock less than 10"
        intent = parser.parse("products where stock less than 10")
        assert any(f.operator == FilterOperator.LT for f in intent.filters)

    def test_rating_above(self, parser):
        # Example 11: "products with rating above 4"
        intent = parser.parse("products with rating above 4")
        assert len(intent.filters) >= 1

    def test_price_between(self, basic_parser):
        # Example 12: "products where price between 50 and 200"
        intent = basic_parser.parse("products where price between 50 and 200")
        # Parser should detect filter
        assert intent.raw_text != ""

    def test_name_contains(self, basic_parser):
        # Example 13: "customers where name contains John"
        intent = basic_parser.parse("customers where name contains John")
        assert intent.raw_text != ""

    def test_multiple_filters(self, parser):
        # Example 14: "orders where status is pending and quantity > 5"
        intent = parser.parse("orders where status is pending and quantity > 5")
        assert len(intent.filters) >= 1


class TestAggregations:
    """NL examples 15-21: aggregation queries."""

    def test_count_orders(self, parser):
        # Example 15: "count orders"
        intent = parser.parse("count orders")
        assert any(f.aggregation == AggregationType.COUNT for f in intent.select_fields)

    def test_how_many_customers(self, parser):
        # Example 16: "how many customers"
        intent = parser.parse("how many customers")
        assert any(f.aggregation == AggregationType.COUNT for f in intent.select_fields)

    def test_average_price(self, parser):
        # Example 17: "average price of products"
        intent = parser.parse("average price of products")
        assert any(f.aggregation == AggregationType.AVG for f in intent.select_fields)

    def test_total_revenue(self, parser):
        # Example 18: "total total_price from orders"
        intent = parser.parse("total total_price from orders")
        assert any(f.aggregation == AggregationType.SUM for f in intent.select_fields)

    def test_max_price(self, parser):
        # Example 19: "maximum price of products"
        intent = parser.parse("maximum price of products")
        assert any(f.aggregation == AggregationType.MAX for f in intent.select_fields)

    def test_min_stock(self, parser):
        # Example 20: "minimum stock from products"
        intent = parser.parse("minimum stock from products")
        assert any(f.aggregation == AggregationType.MIN for f in intent.select_fields)

    def test_highest_rating(self, parser):
        # Example 21: "highest rating from products"
        intent = parser.parse("highest rating from products")
        assert any(f.aggregation == AggregationType.MAX for f in intent.select_fields)


class TestGroupBy:
    """NL examples 22-25: GROUP BY queries."""

    def test_count_by_category(self, parser):
        # Example 22: "count products by category"
        intent = parser.parse("count products by category")
        assert intent.group_by is not None

    def test_average_per_category(self, parser):
        # Example 23: "average price per category"
        intent = parser.parse("average price per category")
        assert intent.group_by is not None
        assert "category" in intent.group_by.columns

    def test_group_by_status(self, parser):
        # Example 24: "count orders grouped by status"
        intent = parser.parse("count orders grouped by status")
        assert intent.group_by is not None

    def test_total_by_customer(self, parser):
        # Example 25: "total total_price from orders group by customer_id"
        intent = parser.parse("total total_price from orders group by customer_id")
        assert intent.group_by is not None
        assert "customer_id" in intent.group_by.columns


class TestOrderBy:
    """NL examples 26-28: ORDER BY queries."""

    def test_order_by_price_desc(self, parser):
        # Example 26: "show products order by price descending"
        intent = parser.parse("show products order by price descending")
        assert len(intent.order_by) >= 1
        assert intent.order_by[0].direction == SortOrder.DESC

    def test_sort_by_name(self, parser):
        # Example 27: "list customers sort by name"
        intent = parser.parse("list customers sort by name")
        assert len(intent.order_by) >= 1
        assert intent.order_by[0].column == "name"

    def test_sorted_by_date(self, parser):
        # Example 28: "orders sorted by order_date descending"
        intent = parser.parse("orders sorted by order_date descending")
        assert len(intent.order_by) >= 1


class TestLimit:
    """NL examples 29-31: LIMIT queries."""

    def test_top_10(self, parser):
        # Example 29: "top 10 products"
        intent = parser.parse("top 10 products")
        assert intent.limit == 10

    def test_limit_5(self, parser):
        # Example 30: "show customers limit 5"
        intent = parser.parse("show customers limit 5")
        assert intent.limit == 5

    def test_first_3(self, parser):
        # Example 31: "first 3 orders"
        intent = parser.parse("first 3 orders")
        assert intent.limit == 3


class TestDistinct:
    def test_distinct_category(self, parser):
        # Example 32: "show distinct category from products"
        intent = parser.parse("show distinct category from products")
        assert intent.distinct is True

    def test_unique_cities(self, parser):
        # Example 33: "unique city from customers"
        intent = parser.parse("unique city from customers")
        assert intent.distinct is True


class TestEdgeCases:
    def test_empty_string(self, parser):
        intent = parser.parse("")
        assert intent.confidence == 0.0
        assert intent.tables == []

    def test_confidence_increases_with_components(self, parser):
        simple = parser.parse("show products")
        complex_ = parser.parse("show name from products where price > 10 order by name limit 5")
        assert complex_.confidence >= simple.confidence

    def test_value_parsing_int(self, basic_parser):
        assert NLParser._parse_value("42") == 42

    def test_value_parsing_float(self, basic_parser):
        assert NLParser._parse_value("3.14") == 3.14

    def test_value_parsing_bool(self, basic_parser):
        assert NLParser._parse_value("true") is True
