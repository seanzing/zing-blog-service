#!/usr/bin/env python3
"""
Customer Onboarding Script for Blog Generation

Usage:
    python onboard_customers.py --validate          # Generate validation report only
    python onboard_customers.py --dry-run           # Dry run (no actual API calls)
    python onboard_customers.py --process           # Process all customers
    python onboard_customers.py --process --limit 5 # Process first 5 customers only

Options:
    --csv PATH      Path to CSV file (default: auto-detect in current directory)
    --validate      Generate validation report without processing
    --dry-run       Simulate processing without sending to Duda
    --process       Actually process customers and send blogs to Duda
    --limit N       Limit to first N customers (useful for testing)
"""
import argparse
import asyncio
import sys
from pathlib import Path
from glob import glob


def find_csv_file():
    """Find the onboarding CSV file in current directory."""
    csv_files = glob("hubspot-crm-exports-*.csv")
    if csv_files:
        return csv_files[0]

    csv_files = glob("*.csv")
    if csv_files:
        return csv_files[0]

    return None


async def main():
    parser = argparse.ArgumentParser(description="Customer Onboarding for Blog Generation")
    parser.add_argument("--csv", type=str, help="Path to CSV file")
    parser.add_argument("--validate", action="store_true", help="Generate validation report only")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without sending to Duda")
    parser.add_argument("--process", action="store_true", help="Process customers and send blogs")
    parser.add_argument("--limit", type=int, help="Limit number of customers to process")

    args = parser.parse_args()

    # Find CSV file
    csv_path = args.csv or find_csv_file()
    if not csv_path:
        print("Error: No CSV file found. Please specify with --csv PATH")
        sys.exit(1)

    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    print(f"Using CSV file: {csv_path}")

    # Import services (after ensuring we're in the right directory)
    from app.services.onboarding_service import OnboardingService, run_validation_report
    from app.services.onboarding_parser import parse_onboarding_csv, generate_validation_report

    if args.validate:
        # Validation report only
        print("\n" + "="*60)
        print("GENERATING VALIDATION REPORT")
        print("="*60 + "\n")

        report = await run_validation_report(csv_path)
        print(report)

        # Also save to file
        report_path = "onboarding_validation_report.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")

    elif args.dry_run:
        # Dry run
        print("\n" + "="*60)
        print("DRY RUN MODE")
        print("="*60 + "\n")

        service = OnboardingService()
        result = await service.process_batch(csv_path, dry_run=True, limit=args.limit)

        print(f"\nDry run complete. {result.successful} customers would be processed successfully.")

    elif args.process:
        # Actual processing
        print("\n" + "="*60)
        print("PROCESSING CUSTOMERS")
        print("="*60 + "\n")

        # Confirm before processing
        valid, flagged = parse_onboarding_csv(csv_path)
        to_process = len(valid) if not args.limit else min(args.limit, len(valid))

        print(f"Ready to process {to_process} customers.")
        print(f"This will generate and send blogs to Duda.")

        confirm = input("\nProceed? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

        service = OnboardingService()
        result = await service.process_batch(csv_path, dry_run=False, limit=args.limit)

        # Save results
        results_path = "onboarding_results.txt"
        with open(results_path, 'w') as f:
            f.write(f"Onboarding Results\n")
            f.write(f"="*60 + "\n")
            f.write(f"Processed: {result.processed}\n")
            f.write(f"Successful: {result.successful}\n")
            f.write(f"Failed: {result.failed}\n")
            f.write(f"Flagged: {result.flagged_for_review}\n\n")

            for r in result.results:
                status = "SUCCESS" if r.success else "FAILED"
                f.write(f"\n{r.customer.business_name} [{status}]\n")
                f.write(f"  Site: {r.customer.duda_site_code}\n")
                f.write(f"  Blogs Generated: {r.blogs_generated}\n")
                f.write(f"  Blogs Sent: {r.blogs_sent}\n")
                f.write(f"  First Blog Published: {r.first_blog_published}\n")
                if r.errors:
                    f.write(f"  Errors: {', '.join(r.errors)}\n")

        print(f"\nResults saved to: {results_path}")

    else:
        # Default: show help
        parser.print_help()
        print("\n\nQuick start:")
        print("  1. python onboard_customers.py --validate    # Review parsed data first")
        print("  2. python onboard_customers.py --dry-run     # Test without sending")
        print("  3. python onboard_customers.py --process     # Actually send blogs")


if __name__ == "__main__":
    asyncio.run(main())
