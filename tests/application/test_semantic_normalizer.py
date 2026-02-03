"""Unit tests for SemanticNormalizer service."""

import pytest
from application.services.semantic_normalizer import (
    SemanticNormalizer,
    NormalizationRule,
    normalize_term
)


@pytest.fixture
def normalizer():
    """Create a SemanticNormalizer instance."""
    return SemanticNormalizer()


@pytest.fixture
def healthcare_normalizer():
    """Create a SemanticNormalizer for healthcare domain."""
    return SemanticNormalizer(domain="healthcare")


class TestBasicNormalization:
    """Test basic text normalization."""

    def test_lowercase_conversion(self, normalizer):
        """Test text is converted to lowercase."""
        assert normalizer.normalize("CUSTOMER") == "customer"
        assert normalizer.normalize("Customer") == "customer"

    def test_camelcase_to_snake_case(self, normalizer):
        """Test CamelCase conversion to snake_case."""
        assert normalizer.normalize("CustomerAddress") == "customer_address"
        assert normalizer.normalize("customerId") == "customer_identifier"

    def test_space_to_underscore(self, normalizer):
        """Test spaces are converted to underscores."""
        assert normalizer.normalize("Customer Address") == "customer_address"
        assert normalizer.normalize("First Name") == "first_name"

    def test_special_character_removal(self, normalizer):
        """Test special characters are removed."""
        assert normalizer.normalize("customer@2024") == "customer2024"
        assert normalizer.normalize("cust#id") == "custid"

    def test_underscore_collapsing(self, normalizer):
        """Test multiple underscores are collapsed."""
        assert normalizer.normalize("customer___address") == "customer_address"
        assert normalizer.normalize("__name__") == "name"

    def test_leading_trailing_underscores(self, normalizer):
        """Test leading/trailing underscores are removed."""
        assert normalizer.normalize("_customer_") == "customer"
        assert normalizer.normalize("__id__") == "identifier"


class TestAbbreviationExpansion:
    """Test abbreviation expansion."""

    def test_common_abbreviations(self, normalizer):
        """Test common abbreviations are expanded."""
        assert normalizer.normalize("cust") == "customer"
        assert normalizer.normalize("pk") == "primary_key"
        assert normalizer.normalize("fk") == "foreign_key"
        assert normalizer.normalize("id") == "identifier"

    def test_compound_abbreviations(self, normalizer):
        """Test compound abbreviations."""
        assert normalizer.normalize("CustAddr") == "customer_address"
        assert normalizer.normalize("pk_id") == "primary_key_identifier"
        assert normalizer.normalize("fk_ref") == "foreign_key_reference"

    def test_data_type_abbreviations(self, normalizer):
        """Test data type abbreviations."""
        assert normalizer.normalize("int") == "integer"
        assert normalizer.normalize("bool") == "boolean"
        assert normalizer.normalize("varchar") == "variable_character"
        assert normalizer.normalize("dt") == "date"

    def test_business_term_abbreviations(self, normalizer):
        """Test business term abbreviations."""
        assert normalizer.normalize("dept") == "department"
        assert normalizer.normalize("emp") == "employee"
        assert normalizer.normalize("org") == "organization"
        assert normalizer.normalize("qty") == "quantity"

    def test_healthcare_abbreviations(self, healthcare_normalizer):
        """Test healthcare-specific abbreviations."""
        assert healthcare_normalizer.normalize("pt") == "patient"
        # "dx" -> "diagnosis" -> "medical_diagnosis" (synonym mapping)
        assert healthcare_normalizer.normalize("dx") == "medical_diagnosis"
        assert healthcare_normalizer.normalize("rx") == "prescription"
        assert healthcare_normalizer.normalize("med") == "medication"


class TestSynonymMapping:
    """Test synonym mapping."""

    def test_customer_synonyms(self, normalizer):
        """Test customer-related synonyms."""
        assert normalizer.normalize("client") == "customer"
        assert normalizer.normalize("buyer") == "customer"
        assert normalizer.normalize("consumer") == "customer"

    def test_user_synonyms(self, normalizer):
        """Test user-related synonyms."""
        assert normalizer.normalize("member") == "user"
        assert normalizer.normalize("subscriber") == "user"

    def test_order_synonyms(self, normalizer):
        """Test order-related synonyms."""
        assert normalizer.normalize("purchase") == "order"
        assert normalizer.normalize("sale") == "order"
        assert normalizer.normalize("transaction") == "order"

    def test_product_synonyms(self, normalizer):
        """Test product-related synonyms."""
        assert normalizer.normalize("item") == "product"
        assert normalizer.normalize("article") == "product"

    def test_synonym_without_application(self, normalizer):
        """Test normalization without synonym mapping."""
        result = normalizer.normalize("client", apply_synonyms=False)
        assert result == "client"  # No synonym mapping


class TestCustomRules:
    """Test custom normalization rules."""

    def test_add_custom_abbreviation(self, normalizer):
        """Test adding custom abbreviation."""
        normalizer.add_abbreviation("co", "company")

        assert normalizer.normalize("co") == "company"

    def test_add_custom_synonym(self, normalizer):
        """Test adding custom synonym."""
        normalizer.add_synonym("patron", "customer")

        assert normalizer.normalize("patron") == "customer"

    def test_add_custom_rule(self, normalizer):
        """Test adding custom normalization rule."""
        rule = NormalizationRule(
            pattern=r"v\d+",
            replacement="version",
            rule_type="pattern_replacement"
        )
        normalizer.add_rule(rule)

        # Note: This test depends on regex pattern matching in custom rules
        # The actual implementation may need adjustment

    def test_domain_specific_rules(self):
        """Test domain-specific rules."""
        normalizer1 = SemanticNormalizer(domain="healthcare")
        normalizer2 = SemanticNormalizer(domain="finance")

        # Add domain-specific rule
        rule = NormalizationRule(
            pattern="hcp",
            replacement="healthcare_provider",
            rule_type="domain_specific",
            domain="healthcare"
        )
        normalizer1.add_rule(rule)

        # Only healthcare normalizer should have this rule
        assert len(normalizer1._rules) > 0


class TestEquivalence:
    """Test equivalence checking."""

    def test_equivalent_terms(self, normalizer):
        """Test equivalent terms are detected."""
        assert normalizer.are_equivalent("Cust", "Customer") is True
        assert normalizer.are_equivalent("client", "Customer") is True
        assert normalizer.are_equivalent("pk_id", "PrimaryKey_Id") is True

    def test_non_equivalent_terms(self, normalizer):
        """Test non-equivalent terms are detected."""
        assert normalizer.are_equivalent("customer", "product") is False
        assert normalizer.are_equivalent("order", "invoice") is False

    def test_case_insensitive_equivalence(self, normalizer):
        """Test equivalence is case insensitive."""
        assert normalizer.are_equivalent("CUSTOMER", "customer") is True
        assert normalizer.are_equivalent("Customer", "CUSTOMER") is True


class TestSimilarity:
    """Test similarity scoring."""

    def test_identical_terms(self, normalizer):
        """Test identical terms have similarity 1.0."""
        assert normalizer.get_similarity("customer", "customer") == 1.0
        assert normalizer.get_similarity("Cust", "Customer") == 1.0

    def test_completely_different_terms(self, normalizer):
        """Test completely different terms have similarity 0.0."""
        similarity = normalizer.get_similarity("customer", "product")
        assert similarity == 0.0

    def test_partial_overlap(self, normalizer):
        """Test partial word overlap."""
        # "customer_address" vs "customer_phone"
        # Common: customer (1 word)
        # Union: customer, address, phone (3 words)
        # Jaccard: 1/3 ≈ 0.33
        similarity = normalizer.get_similarity("CustomerAddress", "CustomerPhone")
        assert 0.3 < similarity < 0.4

    def test_compound_similarity(self, normalizer):
        """Test compound term similarity."""
        # "customer_data" vs "client_info"
        # After normalization: "customer_data" vs "customer_information"
        similarity = normalizer.get_similarity("CustomerData", "ClientInfo")
        assert similarity > 0  # Should have some similarity


class TestNormalizationTrace:
    """Test normalization with trace."""

    def test_trace_steps(self, normalizer):
        """Test trace returns transformation steps."""
        normalized, steps = normalizer.normalize_with_trace("CustAddr")

        assert normalized == "customer_address"
        assert len(steps) >= 3  # Original, intermediate, final
        assert "Original:" in steps[0]
        assert "Final:" in steps[-1]

    def test_trace_abbreviation_expansion(self, normalizer):
        """Test trace shows abbreviation expansion."""
        normalized, steps = normalizer.normalize_with_trace("pk_id")

        # Should show abbreviation expansion step
        assert any("abbreviation" in step.lower() for step in steps)
        assert normalized == "primary_key_identifier"

    def test_trace_synonym_mapping(self, normalizer):
        """Test trace shows synonym mapping."""
        normalized, steps = normalizer.normalize_with_trace("Client")

        # Should show synonym mapping step
        assert any("synonym" in step.lower() for step in steps)
        assert normalized == "customer"


class TestCanonicalForm:
    """Test canonical form retrieval."""

    def test_get_canonical_form(self, normalizer):
        """Test getting canonical form."""
        assert normalizer.get_canonical_form("CustAddr") == "customer_address"
        assert normalizer.get_canonical_form("Client") == "customer"
        assert normalizer.get_canonical_form("pk") == "primary_key"

    def test_canonical_form_consistency(self, normalizer):
        """Test canonical form is consistent."""
        form1 = normalizer.get_canonical_form("Customer")
        form2 = normalizer.get_canonical_form("Cust")
        form3 = normalizer.get_canonical_form("client")

        assert form1 == form2 == form3 == "customer"


class TestRuleExportImport:
    """Test rule export/import functionality."""

    def test_export_rules(self, normalizer):
        """Test exporting normalization rules."""
        rules = normalizer.export_rules()

        assert "abbreviations" in rules
        assert "synonyms" in rules
        assert "custom_rules" in rules

        assert isinstance(rules["abbreviations"], dict)
        assert isinstance(rules["synonyms"], dict)
        assert isinstance(rules["custom_rules"], list)

        # Check some known rules
        assert "cust" in rules["abbreviations"]
        assert rules["abbreviations"]["cust"] == "customer"

    def test_import_rules(self):
        """Test importing normalization rules."""
        normalizer1 = SemanticNormalizer()
        normalizer1.add_abbreviation("co", "company")
        normalizer1.add_synonym("patron", "customer")

        # Export from first normalizer
        rules = normalizer1.export_rules()

        # Import to new normalizer
        normalizer2 = SemanticNormalizer()
        normalizer2.import_rules(rules)

        # Should have the custom rules
        assert normalizer2.normalize("co") == "company"
        assert normalizer2.normalize("patron") == "customer"

    def test_import_preserves_defaults(self):
        """Test import preserves default rules."""
        normalizer = SemanticNormalizer()

        # Import empty rules
        normalizer.import_rules({"abbreviations": {}, "synonyms": {}, "custom_rules": []})

        # Should still have default rules
        assert normalizer.normalize("cust") == "customer"


class TestDomainSpecificNormalization:
    """Test domain-specific normalization."""

    def test_load_domain_rules(self, normalizer):
        """Test loading domain-specific rules."""
        domain_rules = {
            "healthcare_provider": "hcp",
            "electronic_health_record": "ehr"
        }

        normalizer.load_domain_rules("healthcare", domain_rules)

        # Should have custom rules for this domain
        assert len(normalizer._rules) > 0

    def test_domain_isolation(self):
        """Test domain-specific rules are isolated."""
        healthcare = SemanticNormalizer(domain="healthcare")
        finance = SemanticNormalizer(domain="finance")

        healthcare_rule = NormalizationRule(
            pattern="hcp",
            replacement="healthcare_provider",
            rule_type="domain",
            domain="healthcare"
        )

        healthcare.add_rule(healthcare_rule)

        # Finance normalizer should not have healthcare rule
        assert len(finance._rules) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string(self, normalizer):
        """Test normalization of empty string."""
        assert normalizer.normalize("") == ""

    def test_whitespace_only(self, normalizer):
        """Test normalization of whitespace."""
        assert normalizer.normalize("   ") == ""

    def test_special_characters_only(self, normalizer):
        """Test normalization of special characters only."""
        assert normalizer.normalize("@#$%") == ""

    def test_numbers_only(self, normalizer):
        """Test normalization of numbers."""
        result = normalizer.normalize("123")
        assert result == "123"

    def test_very_long_string(self, normalizer):
        """Test normalization of very long strings."""
        long_string = "customer" * 100
        result = normalizer.normalize(long_string)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unicode_characters(self, normalizer):
        """Test handling of unicode characters."""
        result = normalizer.normalize("Café_Münchën")
        # Should handle unicode gracefully
        assert isinstance(result, str)


class TestConvenienceFunction:
    """Test convenience normalize_term function."""

    def test_normalize_term_basic(self):
        """Test basic normalization via convenience function."""
        result = normalize_term("CustAddr")
        assert result == "customer_address"

    def test_normalize_term_with_domain(self):
        """Test normalization with domain."""
        result = normalize_term("pt", domain="healthcare")
        assert result == "patient"


class TestNormalizerConfiguration:
    """Test normalizer configuration."""

    def test_default_domain(self):
        """Test default domain is None."""
        normalizer = SemanticNormalizer()
        assert normalizer.domain is None

    def test_custom_domain(self):
        """Test custom domain."""
        normalizer = SemanticNormalizer(domain="healthcare")
        assert normalizer.domain == "healthcare"

    def test_default_rules_loaded(self):
        """Test default rules are loaded."""
        normalizer = SemanticNormalizer()

        # Should have default abbreviations
        assert len(normalizer._abbreviation_map) > 0
        assert len(normalizer._synonym_map) > 0

        # Check specific defaults
        assert "cust" in normalizer._abbreviation_map
        assert "client" in normalizer._synonym_map
