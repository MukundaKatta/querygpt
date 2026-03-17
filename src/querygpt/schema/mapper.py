"""SchemaMapper - maps natural language terms to database columns and tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from querygpt.models import Column, Schema, Table


@dataclass
class MappingResult:
    """Result of mapping a natural language term to a schema element."""

    term: str
    table: str | None = None
    column: str | None = None
    confidence: float = 0.0
    source: str = ""  # "exact", "alias", "fuzzy", "plural"


class SchemaMapper:
    """Maps natural language terms to database tables and columns.

    Uses multiple strategies:
    1. Exact name match
    2. Alias match (from column/table aliases)
    3. Plural/singular normalization
    4. Fuzzy substring matching
    """

    def __init__(self, schema: Schema) -> None:
        self.schema = schema
        self._build_lookup()

    def _build_lookup(self) -> None:
        """Build reverse-lookup dictionaries for fast mapping."""
        self._table_map: dict[str, str] = {}  # alias -> table_name
        self._column_map: dict[str, tuple[str, str]] = {}  # alias -> (table_name, column_name)

        for table in self.schema.tables:
            name_lower = table.name.lower()
            self._table_map[name_lower] = table.name
            for alias in table.aliases:
                self._table_map[alias.lower()] = table.name
            # Also add singular/plural forms
            self._table_map[self._singularize(name_lower)] = table.name
            self._table_map[self._pluralize(name_lower)] = table.name

            for col in table.columns:
                col_lower = col.name.lower()
                self._column_map[col_lower] = (table.name, col.name)
                for alias in col.aliases:
                    self._column_map[alias.lower()] = (table.name, col.name)

    def map_table(self, term: str) -> MappingResult:
        """Map a natural language term to a table name."""
        term_lower = term.lower().strip()

        # Exact or alias match
        if term_lower in self._table_map:
            source = "exact" if term_lower == self._table_map[term_lower].lower() else "alias"
            return MappingResult(
                term=term,
                table=self._table_map[term_lower],
                confidence=1.0,
                source=source,
            )

        # Singular/plural normalisation
        singular = self._singularize(term_lower)
        if singular in self._table_map:
            return MappingResult(
                term=term,
                table=self._table_map[singular],
                confidence=0.9,
                source="plural",
            )

        plural = self._pluralize(term_lower)
        if plural in self._table_map:
            return MappingResult(
                term=term,
                table=self._table_map[plural],
                confidence=0.9,
                source="plural",
            )

        # Fuzzy substring
        best: MappingResult | None = None
        for key, table_name in self._table_map.items():
            if term_lower in key or key in term_lower:
                conf = len(min(term_lower, key, key=len)) / len(max(term_lower, key, key=len))
                if best is None or conf > best.confidence:
                    best = MappingResult(term=term, table=table_name, confidence=round(conf, 2), source="fuzzy")

        return best or MappingResult(term=term, confidence=0.0)

    def map_column(self, term: str, table_hint: str | None = None) -> MappingResult:
        """Map a natural language term to a column name."""
        term_lower = term.lower().strip().replace(" ", "_")

        # Exact or alias match
        if term_lower in self._column_map:
            table_name, col_name = self._column_map[term_lower]
            if table_hint and table_name.lower() != table_hint.lower():
                # Check if there's a match in the hinted table
                hinted = self._find_column_in_table(term_lower, table_hint)
                if hinted:
                    return hinted
            source = "exact" if term_lower == col_name.lower() else "alias"
            return MappingResult(
                term=term, table=table_name, column=col_name,
                confidence=1.0, source=source,
            )

        # Try with table hint
        if table_hint:
            hinted = self._find_column_in_table(term_lower, table_hint)
            if hinted:
                return hinted

        # Fuzzy search across all columns
        best: MappingResult | None = None
        for key, (table_name, col_name) in self._column_map.items():
            if term_lower in key or key in term_lower:
                conf = len(min(term_lower, key, key=len)) / len(max(term_lower, key, key=len))
                if table_hint and table_name.lower() != table_hint.lower():
                    conf *= 0.5
                if best is None or conf > best.confidence:
                    best = MappingResult(
                        term=term, table=table_name, column=col_name,
                        confidence=round(conf, 2), source="fuzzy",
                    )

        return best or MappingResult(term=term, confidence=0.0)

    def map_terms(self, terms: list[str]) -> list[MappingResult]:
        """Map multiple terms, trying table first then column."""
        results: list[MappingResult] = []
        for term in terms:
            table_result = self.map_table(term)
            if table_result.confidence > 0.7:
                results.append(table_result)
                continue
            col_result = self.map_column(term)
            if col_result.confidence > table_result.confidence:
                results.append(col_result)
            elif table_result.confidence > 0:
                results.append(table_result)
            else:
                results.append(MappingResult(term=term, confidence=0.0))
        return results

    def _find_column_in_table(self, term: str, table_name: str) -> MappingResult | None:
        """Search for a column term within a specific table."""
        table = self.schema.get_table(table_name)
        if not table:
            return None
        for col in table.columns:
            if col.name.lower() == term:
                return MappingResult(
                    term=term, table=table.name, column=col.name,
                    confidence=1.0, source="exact",
                )
            for alias in col.aliases:
                if alias.lower() == term:
                    return MappingResult(
                        term=term, table=table.name, column=col.name,
                        confidence=0.95, source="alias",
                    )
        return None

    @staticmethod
    def _singularize(word: str) -> str:
        """Naive singularization."""
        if word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    @staticmethod
    def _pluralize(word: str) -> str:
        """Naive pluralization."""
        if word.endswith("y") and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        if word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        return word + "s"
