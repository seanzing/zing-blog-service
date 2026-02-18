#!/usr/bin/env python3
"""
Enrich an onboarding CSV with industry details, business name, and location
pulled from the Duda API + refined by GPT for SEO-optimized blog generation.

Usage:
    python enrich_csv.py --csv BlogOnboardingV2.csv --preview        # Preview enrichment for first 3
    python enrich_csv.py --csv BlogOnboardingV2.csv --process        # Enrich all and write output CSV
    python enrich_csv.py --csv BlogOnboardingV2.csv --process --limit 5
"""
import asyncio
import argparse
import csv
import json
import sys
from pathlib import Path
from openai import OpenAI

from app.services.duda_client import DudaClient
from app.config import settings


def build_gpt_prompt(site_data: dict) -> str:
    """Build a GPT prompt from Duda site data to extract SEO-focused industry details."""
    biz_info = site_data.get("site_business_info", {})
    seo_info = site_data.get("site_seo", {})
    address = biz_info.get("address", {})

    return f"""Based on the following website data, provide a concise, SEO-optimized industry description for blog content generation.

Website Data:
- Business Name: {biz_info.get('business_name', 'Unknown')}
- SEO Title: {seo_info.get('title', 'N/A')}
- SEO Meta Description: {seo_info.get('description', 'N/A')}
- Default Domain: {site_data.get('site_default_domain', 'N/A')}
- Custom Domain: {site_data.get('site_domain', 'N/A')}
- City: {address.get('city', 'N/A')}
- State: {address.get('state', 'N/A')}

Respond with ONLY a JSON object (no markdown, no code fences) with these exact fields:
{{
    "industry": "A concise, SEO-friendly industry description (2-6 words, e.g. 'Residential Plumbing Services', 'Mobile Auto Detailing', 'Custom Home Remodeling'). This should be specific enough to generate targeted blog content.",
    "business_name": "The actual business name (cleaned up, properly capitalized)",
    "city": "City from the site data (or empty string if not available)",
    "state": "Full state name (e.g. 'California' not 'CA', or empty string if not available)"
}}"""


async def enrich_row(row: dict, duda: DudaClient, openai_client: OpenAI) -> dict:
    """Enrich a single CSV row with Duda API + GPT data."""
    site_code = row.get("Duda Site Code", "").strip()
    if not site_code:
        return {**row, "_status": "SKIP: no site code"}

    # Fetch site data from Duda
    status_result = await duda.get_site_status(site_code)
    site_data = status_result.get("site_data", {})

    if not status_result.get("success"):
        return {**row, "_status": f"SKIP: Duda API error - {status_result.get('error', 'unknown')}"}

    # Call GPT to generate SEO-focused industry description
    prompt = build_gpt_prompt(site_data)

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an SEO expert that analyzes business websites and produces concise, search-optimized industry descriptions for blog content generation. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        enriched = dict(row)
        enriched["Industry Details"] = result.get("industry", row.get("Industry Details", ""))
        # Only fill in business name if the deal name looks like a package description
        if result.get("business_name"):
            enriched["_gpt_business_name"] = result["business_name"]
        # Fill in city/state if missing
        if not row.get("City", "").strip() and result.get("city"):
            enriched["City"] = result["city"]
        if not row.get("State", "").strip() and result.get("state"):
            enriched["State"] = result["state"]
        enriched["_status"] = "OK"
        return enriched

    except Exception as e:
        return {**row, "_status": f"GPT error: {str(e)}"}


async def main():
    parser = argparse.ArgumentParser(description="Enrich onboarding CSV with Duda + GPT data")
    parser.add_argument("--csv", type=str, required=True, help="Path to input CSV")
    parser.add_argument("--preview", action="store_true", help="Preview enrichment for first 3 rows")
    parser.add_argument("--process", action="store_true", help="Enrich all rows and write output CSV")
    parser.add_argument("--limit", type=int, help="Limit rows to process")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}")
        sys.exit(1)

    # Read CSV
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Loaded {len(rows)} rows from {csv_path}")

    if args.preview:
        limit = 3
    elif args.limit:
        limit = args.limit
    else:
        limit = len(rows)

    rows_to_process = rows[:limit]
    print(f"Processing {len(rows_to_process)} rows...\n")

    duda = DudaClient()
    openai_client = OpenAI(api_key=settings.openai_api_key)

    enriched_rows = []
    for i, row in enumerate(rows_to_process, 1):
        deal_name = row.get("Deal Name", "Unknown")
        site_code = row.get("Duda Site Code", "N/A")
        print(f"[{i}/{len(rows_to_process)}] {deal_name} ({site_code})...", end=" ", flush=True)

        enriched = await enrich_row(row, duda, openai_client)
        status = enriched.pop("_status", "?")
        gpt_biz_name = enriched.pop("_gpt_business_name", "")
        enriched_rows.append(enriched)

        industry = enriched.get("Industry Details", "")
        city = enriched.get("City", "")
        state = enriched.get("State", "")
        print(f"{status}")
        if status == "OK":
            print(f"     Industry: {industry}")
            if gpt_biz_name:
                print(f"     Biz Name: {gpt_biz_name}")
            if city or state:
                print(f"     Location: {city}, {state}")

        await asyncio.sleep(0.5)  # Rate limit

    if args.process:
        # Write enriched CSV
        output_path = csv_path.stem + "_enriched.csv"
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)
        print(f"\nEnriched CSV written to: {output_path}")
    else:
        print("\n(Preview only — use --process to write output CSV)")


if __name__ == "__main__":
    asyncio.run(main())
