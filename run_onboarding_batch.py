#!/usr/bin/env python3
"""
Run onboarding batch with concurrent processing (5 customers at a time).

Usage:
    python run_onboarding_batch.py --csv BlogOnboardingV2_enriched.csv
    python run_onboarding_batch.py --csv BlogOnboardingV2_enriched.csv --skip 3  # skip first 3 (already done)
    python run_onboarding_batch.py --csv BlogOnboardingV2_enriched.csv --batch-size 5
    python run_onboarding_batch.py --csv BlogOnboardingV2_enriched.csv --dry-run
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

from app.services.onboarding_parser import parse_onboarding_csv
from app.services.onboarding_service import OnboardingService, OnboardingResult


async def process_customer(service, customer, index, total, dry_run):
    """Process a single customer and return result."""
    print(f"\n[{index}/{total}] Starting: {customer.business_name} ({customer.duda_site_code})")
    try:
        result = await service.process_single_customer(customer, dry_run=dry_run)
        status = "SUCCESS" if result.success else "FAILED"
        print(f"[{index}/{total}] {status}: {customer.business_name} — {result.blogs_sent}/{result.blogs_generated} sent")
        return result
    except Exception as e:
        print(f"[{index}/{total}] ERROR: {customer.business_name} — {str(e)}")
        return OnboardingResult(
            customer=customer, success=False,
            blogs_generated=0, blogs_sent=0,
            first_blog_published=False, site_is_published=False,
            errors=[str(e)]
        )


async def main():
    parser = argparse.ArgumentParser(description="Run onboarding batch (concurrent)")
    parser.add_argument("--csv", type=str, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip", type=int, default=0, help="Skip first N customers (already processed)")
    parser.add_argument("--batch-size", type=int, default=5, help="Concurrent customers per batch")
    args = parser.parse_args()

    if not Path(args.csv).exists():
        print(f"Error: CSV not found: {args.csv}")
        sys.exit(1)

    valid_customers, flagged = parse_onboarding_csv(args.csv)

    # Apply skip and limit
    customers = valid_customers[args.skip:]
    if args.limit:
        customers = customers[:args.limit]

    total = len(customers)
    print(f"CSV: {args.csv}")
    print(f"Total valid: {len(valid_customers)}, Skipping: {args.skip}, Processing: {total}")
    print(f"Batch size: {args.batch_size} concurrent customers")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")

    service = OnboardingService()
    all_results = []

    # Process in batches
    for batch_start in range(0, total, args.batch_size):
        batch = customers[batch_start:batch_start + args.batch_size]
        batch_num = batch_start // args.batch_size + 1
        total_batches = (total + args.batch_size - 1) // args.batch_size

        print(f"\n{'#'*60}")
        print(f"BATCH {batch_num}/{total_batches} ({len(batch)} customers)")
        print(f"{'#'*60}")

        tasks = [
            process_customer(service, customer, args.skip + batch_start + i + 1, args.skip + total, args.dry_run)
            for i, customer in enumerate(batch)
        ]
        results = await asyncio.gather(*tasks)
        all_results.extend(results)

        print(f"\nBatch {batch_num} complete. Time: {datetime.now().strftime('%H:%M:%S')}")

    # Summary
    successful = sum(1 for r in all_results if r.success)
    failed = sum(1 for r in all_results if not r.success)

    print(f"\n{'#'*60}")
    print(f"ALL DONE — {successful} succeeded, {failed} failed out of {total}")
    print(f"Finished: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'#'*60}")

    # Save results
    with open("onboarding_results.txt", "w") as f:
        f.write(f"Onboarding Results\n{'='*60}\n")
        f.write(f"Processed: {total}\n")
        f.write(f"Successful: {successful}\n")
        f.write(f"Failed: {failed}\n\n")
        for r in all_results:
            status = "SUCCESS" if r.success else "FAILED"
            f.write(f"\n{r.customer.business_name} [{status}]\n")
            f.write(f"  Site: {r.customer.duda_site_code}\n")
            f.write(f"  Blogs Generated: {r.blogs_generated}\n")
            f.write(f"  Blogs Sent: {r.blogs_sent}\n")
            f.write(f"  First Blog Published: {r.first_blog_published}\n")
            if r.errors:
                f.write(f"  Errors: {', '.join(r.errors)}\n")
    print(f"\nResults saved to: onboarding_results.txt")


if __name__ == "__main__":
    asyncio.run(main())
