"""Tests for Cypher identifier validation utility."""

import pytest
from infrastructure.cypher_utils import validate_cypher_identifier


class TestValidateCypherIdentifier:
    """Tests for validate_cypher_identifier()."""

    def test_valid_simple_type(self):
        assert validate_cypher_identifier("ASSOCIATED_WITH") == "ASSOCIATED_WITH"

    def test_valid_underscore_prefix(self):
        assert validate_cypher_identifier("_internal") == "_internal"

    def test_valid_single_letter(self):
        assert validate_cypher_identifier("r") == "r"

    def test_valid_mixed_case(self):
        assert validate_cypher_identifier("RelatesTo") == "RelatesTo"

    def test_valid_with_numbers(self):
        assert validate_cypher_identifier("HAS_V2") == "HAS_V2"

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_cypher_identifier("")

    def test_none_coerced_to_empty_rejected(self):
        with pytest.raises(ValueError):
            validate_cypher_identifier("")

    def test_backtick_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("type`]->(t) DELETE t//")

    def test_brackets_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("type]->(t)")

    def test_braces_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("type{id:1}")

    def test_spaces_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("HAS SPACE")

    def test_dash_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("HAS-DASH")

    def test_starts_with_number_rejected(self):
        with pytest.raises(ValueError, match="Must match pattern"):
            validate_cypher_identifier("2FAST")

    def test_reserved_word_match(self):
        with pytest.raises(ValueError, match="reserved keyword"):
            validate_cypher_identifier("MATCH")

    def test_reserved_word_delete(self):
        with pytest.raises(ValueError, match="reserved keyword"):
            validate_cypher_identifier("DELETE")

    def test_reserved_word_drop(self):
        with pytest.raises(ValueError, match="reserved keyword"):
            validate_cypher_identifier("DROP")

    def test_reserved_word_case_insensitive(self):
        with pytest.raises(ValueError, match="reserved keyword"):
            validate_cypher_identifier("match")

    def test_custom_label_in_error(self):
        with pytest.raises(ValueError, match="relationship_type"):
            validate_cypher_identifier("", "relationship_type")

    def test_injection_payload_rejected(self):
        with pytest.raises(ValueError):
            validate_cypher_identifier(
                "ASSOCIATED_WITH`]->(t) DETACH DELETE t WITH 1 as x//"
            )


class TestDeleteRelationshipValidation:
    """Tests that delete_relationship rejects malicious input.

    These are unit tests for the validation gate — they don't need
    a real Neo4j connection since ValueError is raised before any query.
    """

    @pytest.mark.asyncio
    async def test_malicious_type_raises_before_query(self):
        from infrastructure.neo4j_backend import Neo4jBackend

        backend = Neo4jBackend.__new__(Neo4jBackend)
        with pytest.raises(ValueError):
            await backend.delete_relationship(
                source_id="src1",
                relationship_type="TYPE`]->(t) DELETE t//",
                target_id="tgt1",
            )

    @pytest.mark.asyncio
    async def test_empty_type_raises_before_query(self):
        from infrastructure.neo4j_backend import Neo4jBackend

        backend = Neo4jBackend.__new__(Neo4jBackend)
        with pytest.raises(ValueError, match="must not be empty"):
            await backend.delete_relationship(
                source_id="src1",
                relationship_type="",
                target_id="tgt1",
            )

    @pytest.mark.asyncio
    async def test_reserved_word_type_raises(self):
        from infrastructure.neo4j_backend import Neo4jBackend

        backend = Neo4jBackend.__new__(Neo4jBackend)
        with pytest.raises(ValueError, match="reserved keyword"):
            await backend.delete_relationship(
                source_id="src1",
                relationship_type="DELETE",
                target_id="tgt1",
            )
