"""Semantic Normalization Service.

This service normalizes entity names, terms, and concepts to canonical forms.
It handles:
- Abbreviation expansion
- Synonym mapping
- Case normalization
- Domain-specific terminology
- Special character handling

The service maintains a configurable dictionary of normalizations and can be
extended with domain-specific rules.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizationRule:
    """Represents a normalization rule."""
    pattern: str
    replacement: str
    rule_type: str  # "abbreviation", "synonym", "correction"
    domain: Optional[str] = None  # Domain-specific rule
    confidence: float = 1.0


class SemanticNormalizer:
    """
    Normalizes entity names and terms to canonical forms.

    Uses configurable rules for:
    - Common abbreviations (e.g., "Cust" -> "Customer")
    - Synonyms (e.g., "Client" -> "Customer")
    - Domain-specific terms
    - Case and whitespace normalization
    """

    def __init__(self, domain: Optional[str] = None):
        """
        Initialize the SemanticNormalizer.

        Args:
            domain: Optional domain name for domain-specific normalization
        """
        self.domain = domain
        self._rules: List[NormalizationRule] = []
        self._abbreviation_map: Dict[str, str] = {}
        self._synonym_map: Dict[str, str] = {}

        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        """Initialize default normalization rules."""

        # Common database/data modeling abbreviations
        self._abbreviation_map.update({
            # General terms
            "id": "identifier",
            "pk": "primary_key",
            "fk": "foreign_key",
            "uq": "unique",
            "idx": "index",
            "seq": "sequence",
            "tbl": "table",
            "col": "column",
            "attr": "attribute",
            "rel": "relationship",
            "ref": "reference",

            # Data types
            "int": "integer",
            "bool": "boolean",
            "char": "character",
            "varchar": "variable_character",
            "txt": "text",
            "num": "numeric",
            "dec": "decimal",
            "dt": "date",
            "ts": "timestamp",

            # Business terms
            "cust": "customer",
            "acct": "account",
            "addr": "address",
            "dept": "department",
            "emp": "employee",
            "mgr": "manager",
            "org": "organization",
            "prod": "product",
            "svc": "service",
            "qty": "quantity",
            "amt": "amount",
            "desc": "description",
            "cat": "category",
            "subcat": "subcategory",

            # Healthcare/Medical
            "pt": "patient",
            "dx": "diagnosis",
            "rx": "prescription",
            "tx": "treatment",
            "hx": "history",
            "sx": "symptoms",
            "med": "medication",
            "lab": "laboratory",
            "appt": "appointment",
            "hosp": "hospital",
            "prov": "provider",
            "ins": "insurance",

            # Time-related
            "yr": "year",
            "mo": "month",
            "wk": "week",
            "dy": "day",
            "hr": "hour",
            "min": "minute",
            "sec": "second",
        })

        # Common synonyms (map to canonical form)
        self._synonym_map.update({
            # Customer-related
            "client": "customer",
            "buyer": "customer",
            "consumer": "customer",
            "patron": "customer",

            # User-related
            "member": "user",
            "subscriber": "user",
            "participant": "user",

            # Order-related
            "purchase": "order",
            "sale": "order",
            "transaction": "order",

            # Product-related
            "item": "product",
            "article": "product",
            "merchandise": "product",
            "good": "product",

            # Healthcare
            "diagnosis": "medical_diagnosis",
            "condition": "medical_condition",
            "therapy": "treatment",
            "procedure": "medical_procedure",

            # Temporal
            "created": "creation_date",
            "modified": "modification_date",
            "updated": "modification_date",
        })

    def add_rule(self, rule: NormalizationRule):
        """Add a custom normalization rule."""
        self._rules.append(rule)
        logger.info(f"Added normalization rule: {rule.pattern} -> {rule.replacement}")

    def add_abbreviation(self, abbreviation: str, full_form: str, domain: Optional[str] = None):
        """
        Add an abbreviation mapping.

        Args:
            abbreviation: Short form (e.g., "cust")
            full_form: Full form (e.g., "customer")
            domain: Optional domain scope
        """
        self._abbreviation_map[abbreviation.lower()] = full_form.lower()
        logger.info(f"Added abbreviation: {abbreviation} -> {full_form}")

    def add_synonym(self, synonym: str, canonical: str, domain: Optional[str] = None):
        """
        Add a synonym mapping.

        Args:
            synonym: Alternative term
            canonical: Canonical form
            domain: Optional domain scope
        """
        self._synonym_map[synonym.lower()] = canonical.lower()
        logger.info(f"Added synonym: {synonym} -> {canonical}")

    def normalize(self, text: str, apply_synonyms: bool = True) -> str:
        """
        Normalize a text string to canonical form.

        Args:
            text: Text to normalize
            apply_synonyms: Whether to apply synonym mapping

        Returns:
            Normalized text
        """
        if not text:
            return text

        # 1. Basic normalization
        normalized = self._basic_normalization(text)

        # 2. Expand abbreviations
        normalized = self._expand_abbreviations(normalized)

        # 3. Apply synonyms (optional)
        if apply_synonyms:
            normalized = self._apply_synonyms(normalized)

        # 4. Apply custom rules
        normalized = self._apply_custom_rules(normalized)

        logger.debug(f"Normalized '{text}' -> '{normalized}'")
        return normalized

    def normalize_with_trace(self, text: str) -> Tuple[str, List[str]]:
        """
        Normalize text and return transformation trace.

        Args:
            text: Text to normalize

        Returns:
            Tuple of (normalized_text, transformation_steps)
        """
        steps = [f"Original: {text}"]

        # Basic normalization
        normalized = self._basic_normalization(text)
        if normalized != text:
            steps.append(f"Basic normalization: {normalized}")

        # Expand abbreviations
        temp = self._expand_abbreviations(normalized)
        if temp != normalized:
            steps.append(f"Abbreviation expansion: {temp}")
            normalized = temp

        # Apply synonyms
        temp = self._apply_synonyms(normalized)
        if temp != normalized:
            steps.append(f"Synonym mapping: {temp}")
            normalized = temp

        # Custom rules
        temp = self._apply_custom_rules(normalized)
        if temp != normalized:
            steps.append(f"Custom rules: {temp}")
            normalized = temp

        steps.append(f"Final: {normalized}")

        return normalized, steps

    def _basic_normalization(self, text: str) -> str:
        """
        Apply basic text normalization.

        - Lowercase
        - Remove extra whitespace
        - Handle special characters
        - Convert camelCase/PascalCase to snake_case
        """
        # Convert to lowercase
        normalized = text.lower()

        # Handle camelCase and PascalCase
        # Insert underscore before capitals
        normalized = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)
        normalized = normalized.lower()

        # Replace spaces with underscores
        normalized = re.sub(r'\s+', '_', normalized)

        # Remove special characters (keep alphanumeric and underscores)
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)

        # Remove leading/trailing underscores
        normalized = normalized.strip('_')

        # Collapse multiple underscores
        normalized = re.sub(r'_+', '_', normalized)

        return normalized

    def _expand_abbreviations(self, text: str) -> str:
        """Expand known abbreviations."""
        words = text.split('_')
        expanded_words = []

        for word in words:
            # Check if word is an abbreviation
            if word in self._abbreviation_map:
                expanded_words.append(self._abbreviation_map[word])
            else:
                expanded_words.append(word)

        return '_'.join(expanded_words)

    def _apply_synonyms(self, text: str) -> str:
        """Apply synonym mappings."""
        # Check if the entire text is a synonym
        if text in self._synonym_map:
            return self._synonym_map[text]

        # Check word-level synonyms
        words = text.split('_')
        mapped_words = []

        for word in words:
            if word in self._synonym_map:
                mapped_words.append(self._synonym_map[word])
            else:
                mapped_words.append(word)

        return '_'.join(mapped_words)

    def _apply_custom_rules(self, text: str) -> str:
        """Apply custom normalization rules."""
        normalized = text

        for rule in self._rules:
            # Skip if rule is domain-specific and doesn't match
            if rule.domain and rule.domain != self.domain:
                continue

            # Apply regex pattern
            normalized = re.sub(rule.pattern, rule.replacement, normalized)

        return normalized

    def get_canonical_form(self, text: str) -> str:
        """
        Get the canonical form of a term.

        This is the fully normalized, expanded, and synonym-mapped form.
        """
        return self.normalize(text, apply_synonyms=True)

    def are_equivalent(self, text1: str, text2: str) -> bool:
        """
        Check if two terms are semantically equivalent after normalization.

        Args:
            text1: First term
            text2: Second term

        Returns:
            True if terms normalize to the same canonical form
        """
        canonical1 = self.get_canonical_form(text1)
        canonical2 = self.get_canonical_form(text2)

        return canonical1 == canonical2

    def get_similarity(self, text1: str, text2: str) -> float:
        """
        Get semantic similarity between two terms.

        Returns:
            1.0 if equivalent, 0.5 if partially equivalent, 0.0 otherwise
        """
        canonical1 = self.get_canonical_form(text1)
        canonical2 = self.get_canonical_form(text2)

        if canonical1 == canonical2:
            return 1.0

        # Check partial matches (word overlap)
        words1 = set(canonical1.split('_'))
        words2 = set(canonical2.split('_'))

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def load_domain_rules(self, domain: str, rules_dict: Dict[str, str]):
        """
        Load domain-specific normalization rules.

        Args:
            domain: Domain name
            rules_dict: Dictionary of {pattern: replacement}
        """
        for pattern, replacement in rules_dict.items():
            self.add_rule(NormalizationRule(
                pattern=pattern,
                replacement=replacement,
                rule_type="domain_specific",
                domain=domain
            ))

        logger.info(f"Loaded {len(rules_dict)} domain-specific rules for '{domain}'")

    def export_rules(self) -> Dict[str, Dict[str, str]]:
        """
        Export normalization rules for serialization.

        Returns:
            Dictionary with abbreviations, synonyms, and custom rules
        """
        return {
            "abbreviations": self._abbreviation_map.copy(),
            "synonyms": self._synonym_map.copy(),
            "custom_rules": [
                {
                    "pattern": rule.pattern,
                    "replacement": rule.replacement,
                    "type": rule.rule_type,
                    "domain": rule.domain
                }
                for rule in self._rules
            ]
        }

    def import_rules(self, rules_dict: Dict[str, any]):
        """
        Import normalization rules from a dictionary.

        Args:
            rules_dict: Dictionary exported from export_rules()
        """
        if "abbreviations" in rules_dict:
            self._abbreviation_map.update(rules_dict["abbreviations"])

        if "synonyms" in rules_dict:
            self._synonym_map.update(rules_dict["synonyms"])

        if "custom_rules" in rules_dict:
            for rule_data in rules_dict["custom_rules"]:
                self.add_rule(NormalizationRule(
                    pattern=rule_data["pattern"],
                    replacement=rule_data["replacement"],
                    rule_type=rule_data["type"],
                    domain=rule_data.get("domain")
                ))

        logger.info("Imported normalization rules")


# Convenience function for quick normalization
def normalize_term(text: str, domain: Optional[str] = None) -> str:
    """
    Quick normalization function.

    Args:
        text: Text to normalize
        domain: Optional domain

    Returns:
        Normalized text
    """
    normalizer = SemanticNormalizer(domain=domain)
    return normalizer.normalize(text)
