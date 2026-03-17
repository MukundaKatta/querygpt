"""CLI entry point for QueryGPT."""

from __future__ import annotations

import click
from rich.console import Console

from querygpt import __version__
from querygpt.report import (
    print_optimization,
    print_query,
    print_schema,
    print_validation,
)
from querygpt.schema.inspector import SchemaInspector
from querygpt.schema.mapper import SchemaMapper
from querygpt.schema.validator import QueryValidator
from querygpt.translator.generator import SQLGenerator
from querygpt.translator.optimizer import QueryOptimizer
from querygpt.translator.parser import NLParser

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """QueryGPT - Natural Language to SQL."""


@main.command()
@click.argument("question")
@click.option("--schema", "schema_name", default="ecommerce",
              help="Built-in schema to use (ecommerce, hr)")
@click.option("--validate/--no-validate", default=True, help="Validate the generated query")
@click.option("--optimize/--no-optimize", default=True, help="Show optimization suggestions")
def translate(question: str, schema_name: str, validate: bool, optimize: bool) -> None:
    """Translate a natural language question to SQL."""
    # Load schema
    inspector = SchemaInspector.from_builtin(schema_name)
    schema = inspector.schema

    # Build parser with schema awareness
    known_tables = inspector.get_table_names()
    known_columns = {
        t.name: [c.name for c in t.columns]
        for t in inspector.get_tables()
    }
    parser = NLParser(known_tables=known_tables, known_columns=known_columns)

    # Parse
    intent = parser.parse(question)

    # Generate SQL
    generator = SQLGenerator(schema=schema)
    query = generator.generate(intent)
    print_query(query)

    # Validate
    if validate:
        validator = QueryValidator(schema)
        result = validator.validate(query)
        print_validation(result)

    # Optimize
    if optimize:
        optimizer = QueryOptimizer(schema=schema)
        report = optimizer.analyze(query)
        print_optimization(report)

        indexes = optimizer.suggest_indexes(query)
        if indexes:
            console.print("\n[bold]Suggested CREATE INDEX statements:[/bold]")
            from rich.syntax import Syntax
            for idx in indexes:
                console.print(Syntax(idx, "sql", theme="monokai", line_numbers=False))


@main.command()
@click.option("--schema", "schema_name", default="ecommerce",
              help="Built-in schema to display")
def schema(schema_name: str) -> None:
    """Display schema information."""
    inspector = SchemaInspector.from_builtin(schema_name)
    print_schema(inspector.schema)


@main.command()
def examples() -> None:
    """Show example natural language queries and their SQL translations."""
    from querygpt.schema.inspector import ECOMMERCE_SCHEMA
    schema = ECOMMERCE_SCHEMA

    known_tables = [t.name for t in schema.tables]
    known_columns = {t.name: [c.name for c in t.columns] for t in schema.tables}
    parser = NLParser(known_tables=known_tables, known_columns=known_columns)
    generator = SQLGenerator(schema=schema)

    example_queries = [
        "show all customers",
        "count orders",
        "show name and email from customers",
        "find products where price greater than 100",
        "average price of products by category",
        "show customers from orders where status is shipped",
        "top 10 products order by price descending",
        "count orders by customer_id having count greater than 5",
        "show distinct category from products",
        "total total_price from orders where status is completed",
    ]

    from rich.table import Table
    table = Table(title="Example NL-to-SQL Translations", show_header=True)
    table.add_column("Natural Language", style="cyan", max_width=50)
    table.add_column("Generated SQL", style="green", max_width=60)

    for q in example_queries:
        intent = parser.parse(q)
        query = generator.generate(intent)
        table.add_row(q, query.sql.replace("\n", " "))

    console.print(table)


if __name__ == "__main__":
    main()
