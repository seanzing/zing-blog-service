#!/usr/bin/env python3
"""
Publish one more existing draft blog post on each customer's website.
No new blogs are generated - this just publishes drafts already in Duda.

Usage:
    python publish_one_more_blog.py                # Preview all customers
    python publish_one_more_blog.py --dry-run      # Show which draft would be published per site
    python publish_one_more_blog.py --process      # Actually publish one draft per site
    python publish_one_more_blog.py --process --limit 5  # Process first 5 only
"""
import asyncio
import argparse
import sys
from glob import glob
from pathlib import Path

from app.services.onboarding_parser import parse_onboarding_csv
from app.services.duda_client import DudaClient


def find_csv_file():
    csv_files = glob("hubspot-crm-exports-*.csv")
    if csv_files:
        return csv_files[0]
    csv_files = glob("*.csv")
    if csv_files:
        return csv_files[0]
    return None


async def main():
    parser = argparse.ArgumentParser(description="Publish one more draft blog per customer site")
    parser.add_argument("--csv", type=str, nargs="+", help="Path to CSV file(s)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be published without doing it")
    parser.add_argument("--process", action="store_true", help="Actually publish one draft per site")
    parser.add_argument("--limit", type=int, help="Limit number of customers to process")
    args = parser.parse_args()

    csv_paths = args.csv or [find_csv_file()]
    csv_paths = [p for p in csv_paths if p and Path(p).exists()]
    if not csv_paths:
        print("Error: No CSV files found")
        sys.exit(1)

    valid_customers = []
    total_flagged = 0
    seen_sites = set()
    for csv_path in csv_paths:
        print(f"Using CSV file: {csv_path}")
        valid, flagged = parse_onboarding_csv(csv_path)
        for c in valid:
            if c.duda_site_code not in seen_sites:
                seen_sites.add(c.duda_site_code)
                valid_customers.append(c)
        total_flagged += len(flagged)
    flagged_customers = total_flagged

    if args.limit:
        valid_customers = valid_customers[:args.limit]

    print(f"Valid customers: {len(valid_customers)}")
    print(f"Flagged (skipped): {flagged_customers}")

    if not args.dry_run and not args.process:
        print("\nCustomers whose sites will get one draft published:")
        for i, c in enumerate(valid_customers, 1):
            print(f"  {i:3}. {c.business_name:<45} | {c.duda_site_code} | {c.industry}")
        print(f"\nUse --dry-run to preview drafts or --process to publish.")
        return

    duda = DudaClient()
    successes = 0
    failures = 0
    no_drafts = 0

    for i, customer in enumerate(valid_customers, 1):
        print(f"\n[{i}/{len(valid_customers)}] {customer.business_name} ({customer.duda_site_code})")

        try:
            # Get all blog posts for this site
            posts_result = await duda.get_blog_posts(customer.duda_site_code)

            if not posts_result.get("success"):
                print(f"  -> Failed to fetch posts: {posts_result.get('error')}")
                failures += 1
                continue

            all_posts = posts_result.get("posts", [])

            # Filter to unpublished posts only
            unpublished = [p for p in all_posts if p.get("status", "").upper() == "UNPUBLISHED"]

            if not unpublished:
                print(f"  -> No unpublished posts available (total posts: {len(all_posts)})")
                no_drafts += 1
                continue

            # Pick the first unpublished post to publish
            draft = unpublished[0]
            post_id = draft.get("id")
            post_title = draft.get("title", "Unknown")

            if args.dry_run:
                print(f"  -> Would publish: \"{post_title}\" (ID: {post_id})")
                print(f"     ({len(unpublished)} unpublished, {len(all_posts)} total posts)")
                successes += 1
            else:
                print(f"  -> Publishing: \"{post_title}\" (ID: {post_id})...")
                publish_result = await duda.publish_blog_post(customer.duda_site_code, post_id)

                if publish_result.get("success"):
                    print(f"  -> Published successfully!")
                    successes += 1
                else:
                    print(f"  -> Publish failed: {publish_result.get('error')}")
                    failures += 1

        except Exception as e:
            print(f"  -> Error: {str(e)}")
            failures += 1

        # Rate limiting
        if not args.dry_run and i < len(valid_customers):
            await asyncio.sleep(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"COMPLETE ({mode})")
    print(f"  Published/Would publish: {successes}")
    print(f"  No unpublished posts:     {no_drafts}")
    print(f"  Failures:                {failures}")
    print(f"  Total:                   {len(valid_customers)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())