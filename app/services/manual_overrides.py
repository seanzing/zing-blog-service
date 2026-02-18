"""Manual overrides for customers missing business names in HubSpot data."""

# Map of Duda site codes to business names
# These customers had no business name in their HubSpot Deal Name field
# Business names were derived from their Duda site domains

BUSINESS_NAME_OVERRIDES = {
    "56fac060": "Taking Care of Books",           # takingcareofbooks.com - Bookkeeping, ADA OK
    "ea51dfd7": "Phoenix Emergency Movers",       # phoenixemergencymoverss.com - Moving, Phoenix AZ
    "1e779a00": "QP Drywall Specialist",          # qpdrywallspecialist.com - Drywall, Exton PA
    "89108263": "MO Plumbing SA",                 # moplumbingsa.com - Plumbing, San Antonio TX
    "0063a578": "Quiet Waters Esthetics",         # quietwatersesthetics.com - Skincare, Millersville MD
    "c886ca3c": "Atlas Counseling & Trauma",      # atlascounselingtrauma.com - Counseling, San Angelo TX
    "49fd049e": "At Home Health Chicago",         # athomehealthchicago.com - Healthcare, Chicago IL
    "50fb882a": "Clobes Books",                   # clobesbooks.com - Bookkeeping, Minnetrista MN
    "17e1aba5": "All For One Property",           # allforoneproperty.com - Property Maintenance, Greeley CO
    "6cb25523": "The Maldon Academy",             # themaldonacademy.com - Sign Language, Clinton MD
    "bfd0fcf5": "Drain Masters PA",               # drainmasters-pa.com - Drain/Pipe, Redding PA
    "939b06a7": "Home Electrical Solution",       # homeelectricalsolution.com - Electrical, Dacula GA
    "2dbe78c8": "Mortgages by Cory",              # mortgagesbycory.com - Mortgage, Highlands Ranch CO
    "e29bcfb0": "A and G Grooming",               # aandggrooming.com - Pet Grooming, Corona De Tucson AZ
    "67c85484": "The Beloved Pet Nanny",          # thebelovedpetnanny.com - Pet Sitting, Wichita KS (8 blogs)
}


def get_business_name_override(site_code: str) -> str:
    """
    Get manual business name override for a site code.

    Args:
        site_code: Duda site code

    Returns:
        Business name if override exists, empty string otherwise
    """
    return BUSINESS_NAME_OVERRIDES.get(site_code, "")
