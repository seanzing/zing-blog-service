"""CSV parser for customer onboarding data."""
import csv
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from pathlib import Path

from app.services.manual_overrides import get_business_name_override


@dataclass
class CustomerData:
    """Parsed customer data for blog onboarding."""
    record_id: str
    business_name: str
    duda_site_code: str
    industry: str
    location: str
    blog_count: int
    deal_type: str
    parse_confidence: str  # "high", "medium", "low"
    parse_notes: str


def parse_business_name(deal_name: str) -> Tuple[str, str, str]:
    """
    Intelligently parse business name from Deal Name field.

    Returns:
        Tuple of (business_name, confidence, notes)
    """
    if not deal_name or not deal_name.strip():
        return "", "low", "Empty deal name"

    deal_name = deal_name.strip()

    # Fix common encoding issues (e.g., "Bradd‚Äôs" -> "Bradd's")
    deal_name = deal_name.replace("‚Äô", "'")

    # Deal type keywords that should NOT be treated as business names
    deal_type_keywords = [
        "discover", "boost", "annual", "monthly", "subscription",
        "blogs", "pages", "landing", "free", "upgrade"
    ]

    def is_deal_type_keyword(name: str) -> bool:
        """Check if the name is actually a deal type keyword."""
        return name.lower().strip() in deal_type_keywords

    # Normalize dash patterns for consistent parsing
    # Handle " -Name" -> " - Name" (space before dash, no space after)
    deal_name = re.sub(r'\s+-([A-Z])', r' - \1', deal_name)
    # Handle "-Name" at start of potential business name after package text
    deal_name = re.sub(r'(\S)-([A-Z])', r'\1 - \2', deal_name)

    # Pattern 1: "Package Type - Business Name" (most common)
    # Look for the last occurrence of " - " to handle cases like
    # "$529 Annual + 50 Local Landing Pages + 3 Months of Free Blogs - Business Name"
    if " - " in deal_name:
        parts = deal_name.rsplit(" - ", 1)
        if len(parts) == 2:
            potential_name = parts[1].strip()
            # Check if it looks like a business name (not a price/package descriptor)
            price_patterns = [r'\$\d+', r'Blogs?', r'Pages?', r'Annual', r'Monthly']
            is_likely_package = any(re.search(p, potential_name, re.IGNORECASE) for p in price_patterns)

            # Also check if it's a deal type keyword like "Discover" or "Boost"
            if is_deal_type_keyword(potential_name):
                # Try to get the business name from before the keyword
                # e.g., "Bradd's Tax and Bookkeeping - Discover" -> "Bradd's Tax and Bookkeeping"
                before_keyword = parts[0].strip()

                # First, check if the before_keyword part IS the business name
                # (no package prefixes, just the name)
                package_prefixes = ['$', 'local landing', 'blogs', 'annual', 'monthly', 'subscription']
                has_package_prefix = any(before_keyword.lower().startswith(p) or p in before_keyword.lower() for p in package_prefixes)

                if not has_package_prefix and len(before_keyword) > 2:
                    # The part before " - Discover/Boost" is the business name
                    return before_keyword, "high", f"Extracted business name before '{potential_name}' suffix"

                # Check if there's another " - " to split on
                if " - " in before_keyword:
                    inner_parts = before_keyword.rsplit(" - ", 1)
                    potential_name = inner_parts[1].strip()
                    if potential_name and len(potential_name) > 2 and not is_deal_type_keyword(potential_name):
                        return potential_name, "high", "Extracted from 'Package - Name - DealType' pattern"

                # If no inner split, this is a package-only name with deal type suffix
                return "", "low", f"Deal type keyword '{parts[1].strip()}' found instead of business name"

            if not is_likely_package and len(potential_name) > 2:
                return potential_name, "high", "Extracted from 'Package - Name' pattern"

    # Pattern 2: Simple business name (no package prefix)
    # These are usually short deal names that are just the business name
    package_indicators = [
        "Local Landing", "Blogs", "Annual", "Monthly", "$",
        "Subscription", "One-Time", "Free", "Upgrade", "Discover", "Boost"
    ]

    has_package_indicator = any(ind.lower() in deal_name.lower() for ind in package_indicators)

    if not has_package_indicator:
        # Likely just the business name
        return deal_name, "high", "Deal name appears to be business name only"

    # Pattern 3: Try to extract from various formats
    # "$429 Annual + 50 Local Landing Pages + 3 Months of Free Blogs"
    # These have no business name
    if deal_name.startswith("$") and " - " not in deal_name:
        return "", "low", "Package-only deal name, no business name found"

    # Pattern 4: Check for business name at the end after common separators
    for separator in [" - ", "- ", " -"]:
        if separator in deal_name:
            potential_name = deal_name.split(separator)[-1].strip()
            if potential_name and len(potential_name) > 2:
                # Verify it's not a package descriptor or deal type keyword
                if not any(re.search(p, potential_name, re.IGNORECASE) for p in [r'\$\d+', r'Annual', r'Monthly']):
                    if not is_deal_type_keyword(potential_name):
                        return potential_name, "medium", f"Extracted using '{separator}' separator"

    return "", "low", "Could not parse business name from deal name"


def determine_blog_count(deal_type: str) -> int:
    """Determine number of blogs based on deal type."""
    if not deal_type:
        return 12  # Default

    deal_type_lower = deal_type.lower()

    # Dominate deals get 24 blogs (2x)
    if "dominate" in deal_type_lower:
        return 24

    # Check for explicit blog count
    if "8 blog" in deal_type_lower:
        return 8

    # All other packages get 12 blogs
    return 12


def parse_location(city: str, state: str) -> str:
    """Combine city and state into location string."""
    city = (city or "").strip()
    state = (state or "").strip()

    if city and state:
        return f"{city}, {state}"
    elif city:
        return city
    elif state:
        return state
    return ""


def clean_industry(industry: str) -> str:
    """Clean up industry field (remove newlines, extra spaces)."""
    if not industry:
        return ""
    # Replace newlines with spaces and collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', industry.strip())
    return cleaned


def parse_onboarding_csv(csv_path: str) -> Tuple[List[CustomerData], List[CustomerData]]:
    """
    Parse the onboarding CSV file and extract customer data.

    Returns:
        Tuple of (valid_customers, flagged_customers)
        - valid_customers: Ready for processing
        - flagged_customers: Need manual review
    """
    valid_customers = []
    flagged_customers = []

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            record_id = row.get('Record ID', '').strip()
            deal_name = row.get('Deal Name', '').strip()
            deal_type = row.get('Deal Type', '').strip()
            duda_site_code = row.get('Duda Site Code', '').strip()
            industry = clean_industry(row.get('Industry Details', ''))
            city = row.get('City', '').strip()
            state = row.get('State', '').strip()

            # Skip empty rows
            if not record_id and not deal_name:
                continue

            # Parse business name
            business_name, confidence, notes = parse_business_name(deal_name)

            # Check for manual override if parsing failed or low confidence
            if not business_name or confidence == "low":
                override_name = get_business_name_override(duda_site_code)
                if override_name:
                    business_name = override_name
                    confidence = "high"
                    notes = "Business name from manual override (Duda domain lookup)"

            # Determine blog count
            blog_count = determine_blog_count(deal_type)

            # Build location
            location = parse_location(city, state)

            customer = CustomerData(
                record_id=record_id,
                business_name=business_name,
                duda_site_code=duda_site_code,
                industry=industry,
                location=location,
                blog_count=blog_count,
                deal_type=deal_type,
                parse_confidence=confidence,
                parse_notes=notes
            )

            # Determine if valid or needs review
            if confidence == "low" or not business_name or not duda_site_code:
                flagged_customers.append(customer)
            else:
                valid_customers.append(customer)

    return valid_customers, flagged_customers


def generate_validation_report(valid: List[CustomerData], flagged: List[CustomerData]) -> str:
    """Generate a human-readable validation report."""
    lines = []
    lines.append("=" * 80)
    lines.append("ONBOARDING VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Total Customers: {len(valid) + len(flagged)}")
    lines.append(f"Ready for Processing: {len(valid)}")
    lines.append(f"Needs Manual Review: {len(flagged)}")
    lines.append("")

    if flagged:
        lines.append("-" * 80)
        lines.append("FLAGGED FOR MANUAL REVIEW")
        lines.append("-" * 80)
        for i, c in enumerate(flagged, 1):
            lines.append(f"\n{i}. Record ID: {c.record_id}")
            lines.append(f"   Deal Type: {c.deal_type}")
            lines.append(f"   Site Code: {c.duda_site_code or 'MISSING'}")
            lines.append(f"   Industry: {c.industry}")
            lines.append(f"   Location: {c.location}")
            lines.append(f"   Issue: {c.parse_notes}")
        lines.append("")

    lines.append("-" * 80)
    lines.append("READY FOR PROCESSING")
    lines.append("-" * 80)

    # Group by blog count
    by_count = {}
    for c in valid:
        if c.blog_count not in by_count:
            by_count[c.blog_count] = []
        by_count[c.blog_count].append(c)

    for count, customers in sorted(by_count.items()):
        lines.append(f"\n{count} Blogs ({len(customers)} customers):")
        for c in customers:
            conf_marker = "" if c.parse_confidence == "high" else " [medium confidence]"
            lines.append(f"  - {c.business_name}{conf_marker}")
            lines.append(f"    Site: {c.duda_site_code} | {c.industry} | {c.location}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)
