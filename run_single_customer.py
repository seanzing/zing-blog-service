#!/usr/bin/env python3
"""
One-off script for generating blogs for a single customer.
Usage:
    python run_single_customer.py                  # Process customer
    python run_single_customer.py --dry-run        # Simulate without sending to Duda
"""

import asyncio
import argparse
from app.services.onboarding_parser import CustomerData
from app.services.onboarding_service import OnboardingService


# ============================================================
# CUSTOMER CONFIGURATION - Edit these values as needed
# ============================================================
CUSTOMER = CustomerData(
    record_id="one-off",
    business_name="Hair Matters",
    duda_site_code="e5fe7339",
    industry="Hair Salon and Barber",
    location="Costa Mesa, California",
    blog_count=12,
    deal_type="One-off Generation",
    parse_confidence="high",
    parse_notes="Manual one-off generation"
)
# ============================================================


async def main(dry_run: bool = False):
    """Process the single customer."""
    print(f"\n{'='*60}")
    print("SINGLE CUSTOMER BLOG GENERATION")
    print(f"{'='*60}")
    print(f"Business: {CUSTOMER.business_name}")
    print(f"Site Code: {CUSTOMER.duda_site_code}")
    print(f"Industry: {CUSTOMER.industry}")
    print(f"Location: {CUSTOMER.location}")
    print(f"Blogs: {CUSTOMER.blog_count}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    service = OnboardingService()
    result = await service.process_single_customer(CUSTOMER, dry_run=dry_run)

    print(f"\n{'='*60}")
    print("RESULT SUMMARY")
    print(f"{'='*60}")
    print(f"Success: {result.success}")
    print(f"Blogs Generated: {result.blogs_generated}")
    print(f"Blogs Sent to Duda: {result.blogs_sent}")
    print(f"Site Published: {result.site_is_published}")
    print(f"First Blog Published: {result.first_blog_published}")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate blogs for a single customer")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending to Duda")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))