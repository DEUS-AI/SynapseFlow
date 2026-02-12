"""
Medication Validation Service

Validates medication names against a curated drug database using fuzzy matching.
This prevents typos and non-existent medications from being stored in the patient graph.

Integration with SNOMED-CT/RxNorm can be added in the future for clinical deployments.
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


@dataclass
class MedicationValidationResult:
    """Result of medication validation."""
    is_valid: bool
    original_name: str
    validated_name: Optional[str]  # The corrected/validated name if found
    confidence: float  # 0.0 to 1.0
    suggestions: List[str]  # Alternative suggestions if not exact match
    message: str  # Human-readable explanation


# Common medication database (expandable, can be replaced with RxNorm lookup)
# This is a subset focused on commonly mentioned medications in patient conversations
COMMON_MEDICATIONS = {
    # Immunosuppressants
    "azathioprine": ["imurel", "imuran", "azasan"],
    "mercaptopurine": ["purinethol", "6-mp"],
    "methotrexate": ["trexall", "rheumatrex", "mtx"],
    "cyclosporine": ["neoral", "sandimmune", "gengraf"],
    "tacrolimus": ["prograf", "envarsus"],
    "mycophenolate": ["cellcept", "myfortic"],
    "infliximab": ["remicade", "inflectra", "renflexis"],
    "adalimumab": ["humira", "hadlima", "hyrimoz"],
    "vedolizumab": ["entyvio"],
    "ustekinumab": ["stelara"],

    # NSAIDs & Pain
    "ibuprofen": ["advil", "motrin", "nurofen"],
    "naproxen": ["aleve", "naprosyn"],
    "acetaminophen": ["tylenol", "paracetamol", "panadol"],
    "aspirin": ["bayer", "bufferin", "ecotrin"],
    "celecoxib": ["celebrex"],
    "diclofenac": ["voltaren", "cataflam"],
    "tramadol": ["ultram", "conzip"],
    "morphine": ["ms contin", "kadian"],
    "oxycodone": ["oxycontin", "percocet", "roxicodone"],

    # Gastrointestinal
    "omeprazole": ["prilosec", "losec"],
    "esomeprazole": ["nexium"],
    "pantoprazole": ["protonix"],
    "lansoprazole": ["prevacid"],
    "famotidine": ["pepcid"],
    "ranitidine": ["zantac"],
    "mesalamine": ["asacol", "pentasa", "lialda", "apriso", "delzicol"],
    "sulfasalazine": ["azulfidine"],
    "budesonide": ["entocort", "uceris"],
    "prednisone": ["deltasone", "rayos"],
    "loperamide": ["imodium"],
    "ondansetron": ["zofran"],

    # Cardiovascular
    "lisinopril": ["prinivil", "zestril"],
    "losartan": ["cozaar"],
    "amlodipine": ["norvasc"],
    "metoprolol": ["lopressor", "toprol"],
    "atenolol": ["tenormin"],
    "carvedilol": ["coreg"],
    "furosemide": ["lasix"],
    "hydrochlorothiazide": ["microzide", "hctz"],
    "atorvastatin": ["lipitor"],
    "simvastatin": ["zocor"],
    "rosuvastatin": ["crestor"],
    "warfarin": ["coumadin", "jantoven"],
    "rivaroxaban": ["xarelto"],
    "apixaban": ["eliquis"],
    "clopidogrel": ["plavix"],

    # Diabetes
    "metformin": ["glucophage", "fortamet"],
    "glipizide": ["glucotrol"],
    "glyburide": ["diabeta", "micronase"],
    "sitagliptin": ["januvia"],
    "empagliflozin": ["jardiance"],
    "dapagliflozin": ["farxiga"],
    "liraglutide": ["victoza", "saxenda"],
    "semaglutide": ["ozempic", "wegovy", "rybelsus"],
    "insulin": ["humalog", "novolog", "lantus", "levemir", "basaglar"],

    # Mental Health
    "sertraline": ["zoloft"],
    "fluoxetine": ["prozac"],
    "escitalopram": ["lexapro"],
    "citalopram": ["celexa"],
    "paroxetine": ["paxil"],
    "venlafaxine": ["effexor"],
    "duloxetine": ["cymbalta"],
    "bupropion": ["wellbutrin", "zyban"],
    "trazodone": ["desyrel"],
    "mirtazapine": ["remeron"],
    "quetiapine": ["seroquel"],
    "aripiprazole": ["abilify"],
    "risperidone": ["risperdal"],
    "olanzapine": ["zyprexa"],
    "lorazepam": ["ativan"],
    "alprazolam": ["xanax"],
    "clonazepam": ["klonopin"],
    "diazepam": ["valium"],
    "zolpidem": ["ambien"],

    # Antibiotics
    "amoxicillin": ["amoxil"],
    "azithromycin": ["zithromax", "z-pack"],
    "ciprofloxacin": ["cipro"],
    "levofloxacin": ["levaquin"],
    "doxycycline": ["vibramycin"],
    "metronidazole": ["flagyl"],
    "clindamycin": ["cleocin"],
    "trimethoprim": ["bactrim", "septra"],
    "nitrofurantoin": ["macrobid"],

    # Respiratory
    "albuterol": ["proventil", "ventolin", "proair"],
    "fluticasone": ["flovent", "flonase"],
    "montelukast": ["singulair"],
    "budesonide": ["pulmicort", "rhinocort"],
    "tiotropium": ["spiriva"],
    "benzonatate": ["tessalon"],
    "guaifenesin": ["mucinex"],
    "dextromethorphan": ["delsym", "robitussin"],

    # Thyroid
    "levothyroxine": ["synthroid", "levoxyl", "tirosint"],
    "liothyronine": ["cytomel"],
    "methimazole": ["tapazole"],

    # Other Common
    "gabapentin": ["neurontin"],
    "pregabalin": ["lyrica"],
    "cyclobenzaprine": ["flexeril"],
    "tizanidine": ["zanaflex"],
    "hydroxychloroquine": ["plaquenil"],
    "colchicine": ["colcrys"],
    "allopurinol": ["zyloprim"],
    "febuxostat": ["uloric"],
    "vitamin d": ["ergocalciferol", "cholecalciferol", "d3"],
    "vitamin b12": ["cyanocobalamin", "methylcobalamin"],
    "folic acid": ["folate"],
    "iron": ["ferrous sulfate", "ferrous gluconate"],
}


class MedicationValidator:
    """
    Validates medication names using fuzzy matching against a known drug database.

    Features:
    - Fuzzy matching for typo tolerance
    - Brand name to generic name resolution
    - Confidence scoring
    - Suggestions for unrecognized medications
    """

    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize the validator.

        Args:
            min_confidence: Minimum confidence threshold to consider a match valid
        """
        self.min_confidence = min_confidence
        self._build_search_index()

    def _build_search_index(self) -> None:
        """Build a searchable index of all medication names."""
        self.name_to_generic: dict[str, str] = {}
        self.all_names: set[str] = set()

        for generic, brand_names in COMMON_MEDICATIONS.items():
            # Add generic name
            self.name_to_generic[generic.lower()] = generic
            self.all_names.add(generic.lower())

            # Add all brand names
            for brand in brand_names:
                self.name_to_generic[brand.lower()] = generic
                self.all_names.add(brand.lower())

    def _normalize_name(self, name: str) -> str:
        """Normalize a medication name for comparison."""
        # Lowercase, remove extra spaces, strip common suffixes
        name = name.lower().strip()
        name = re.sub(r'\s+', ' ', name)  # Collapse multiple spaces
        name = re.sub(r'\s*(tablets?|capsules?|pills?|mg|ml|solution|suspension)\s*$', '', name)
        return name

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate string similarity using SequenceMatcher."""
        return SequenceMatcher(None, name1, name2).ratio()

    def _find_best_matches(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Find the best matching medication names for a query."""
        normalized_query = self._normalize_name(query)
        matches = []

        for name in self.all_names:
            similarity = self._calculate_similarity(normalized_query, name)
            if similarity > 0.4:  # Minimum threshold for considering a match
                matches.append((name, similarity))

        # Sort by similarity (descending) and return top_k
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]

    def validate(self, medication_name: str) -> MedicationValidationResult:
        """
        Validate a medication name.

        Args:
            medication_name: The medication name to validate

        Returns:
            MedicationValidationResult with validation status and suggestions
        """
        if not medication_name or not medication_name.strip():
            return MedicationValidationResult(
                is_valid=False,
                original_name=medication_name,
                validated_name=None,
                confidence=0.0,
                suggestions=[],
                message="Empty medication name provided"
            )

        normalized = self._normalize_name(medication_name)

        # Check for exact match first
        if normalized in self.name_to_generic:
            generic_name = self.name_to_generic[normalized]
            return MedicationValidationResult(
                is_valid=True,
                original_name=medication_name,
                validated_name=generic_name.title(),
                confidence=1.0,
                suggestions=[],
                message=f"Exact match found: {generic_name.title()}"
            )

        # Fuzzy match
        matches = self._find_best_matches(normalized)

        if not matches:
            return MedicationValidationResult(
                is_valid=False,
                original_name=medication_name,
                validated_name=None,
                confidence=0.0,
                suggestions=[],
                message=f"'{medication_name}' is not recognized as a medication. Please verify the spelling."
            )

        best_match, best_score = matches[0]
        generic_name = self.name_to_generic[best_match]

        # Get suggestions (convert to generic names, deduplicate)
        suggestions = []
        seen_generics = set()
        for match_name, score in matches:
            generic = self.name_to_generic[match_name]
            if generic not in seen_generics and score >= 0.5:
                suggestions.append(generic.title())
                seen_generics.add(generic)

        if best_score >= self.min_confidence:
            # High confidence match - consider valid but note it was fuzzy matched
            return MedicationValidationResult(
                is_valid=True,
                original_name=medication_name,
                validated_name=generic_name.title(),
                confidence=best_score,
                suggestions=suggestions,
                message=f"Matched to '{generic_name.title()}' with {best_score:.0%} confidence"
            )
        else:
            # Low confidence - needs user confirmation
            suggestions_str = ", ".join(suggestions[:3])
            return MedicationValidationResult(
                is_valid=False,
                original_name=medication_name,
                validated_name=None,
                confidence=best_score,
                suggestions=suggestions,
                message=f"'{medication_name}' is not recognized. Did you mean: {suggestions_str}?"
            )

    def validate_batch(self, medication_names: List[str]) -> List[MedicationValidationResult]:
        """
        Validate multiple medication names.

        Args:
            medication_names: List of medication names to validate

        Returns:
            List of MedicationValidationResult objects
        """
        return [self.validate(name) for name in medication_names]

    def is_likely_medication(self, text: str) -> bool:
        """
        Quick check if a string looks like it could be a medication name.
        Useful for filtering before detailed validation.

        Args:
            text: Text to check

        Returns:
            True if text looks like it could be a medication
        """
        if not text or len(text) < 2:
            return False

        # Check if it has a high similarity to any known medication
        matches = self._find_best_matches(text, top_k=1)
        return len(matches) > 0 and matches[0][1] >= 0.6


# Global instance for easy access
_validator_instance: Optional[MedicationValidator] = None


def get_medication_validator() -> MedicationValidator:
    """Get the global medication validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = MedicationValidator()
    return _validator_instance
