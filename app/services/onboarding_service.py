"""Batch onboarding service for processing multiple customers."""
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from app.services.onboarding_parser import CustomerData, parse_onboarding_csv, generate_validation_report
from app.services.blog_generator import BlogGenerator
from app.services.html_formatter import HTMLFormatter
from app.services.duda_client import DudaClient
from app.services.pexels_client import PexelsClient
from app.config import app_config


@dataclass
class OnboardingResult:
    """Result of processing a single customer."""
    customer: CustomerData
    success: bool
    blogs_generated: int
    blogs_sent: int
    first_blog_published: bool
    site_is_published: bool
    errors: List[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class BatchOnboardingResult:
    """Result of processing a batch of customers."""
    total_customers: int
    processed: int
    successful: int
    failed: int
    skipped: int
    flagged_for_review: int
    results: List[OnboardingResult] = field(default_factory=list)
    flagged_customers: List[CustomerData] = field(default_factory=list)
    start_time: datetime = None
    end_time: datetime = None


class OnboardingService:
    """Service for batch customer onboarding."""

    def __init__(self):
        self.blog_generator = BlogGenerator()
        self.html_formatter = HTMLFormatter()
        self.duda_client = DudaClient()
        self.pexels_client = PexelsClient()

    async def process_single_customer(
        self,
        customer: CustomerData,
        dry_run: bool = False
    ) -> OnboardingResult:
        """
        Process a single customer: check site status, generate blogs, send to Duda.

        Args:
            customer: Customer data to process
            dry_run: If True, don't actually send to Duda

        Returns:
            OnboardingResult with processing details
        """
        result = OnboardingResult(
            customer=customer,
            success=False,
            blogs_generated=0,
            blogs_sent=0,
            first_blog_published=False,
            site_is_published=False
        )

        print(f"\n{'='*60}")
        print(f"Processing: {customer.business_name}")
        print(f"Site Code: {customer.duda_site_code}")
        print(f"Industry: {customer.industry}")
        print(f"Location: {customer.location}")
        print(f"Blogs to generate: {customer.blog_count}")
        print(f"{'='*60}")

        # Step 1: Check if site is published
        print("Checking site publication status...")
        site_status = await self.duda_client.get_site_status(customer.duda_site_code)

        if not site_status.get('success'):
            error_msg = f"Could not check site status: {site_status.get('error', 'Unknown error')}"
            result.errors.append(error_msg)
            print(f"Warning: {error_msg}")
            # Continue anyway, but won't publish first blog

        result.site_is_published = site_status.get('is_published', False)
        print(f"Site published: {result.site_is_published}")

        # Fetch site theme colors for blog styling
        print("Fetching site theme colors...")
        theme_result = await self.duda_client.get_site_theme(customer.duda_site_code)
        theme_colors = theme_result.get("colors") if theme_result.get("success") else None
        if theme_colors:
            print(f"Found {len(theme_colors)} theme colors")
        else:
            print("No theme colors found, using defaults")

        # Step 2: Generate blogs
        print(f"\nGenerating {customer.blog_count} blogs...")
        try:
            generated_blogs = self.blog_generator.generate_multiple_blogs(
                business_name=customer.business_name,
                industry=customer.industry,
                location=customer.location,
                count=customer.blog_count
            )
            result.blogs_generated = len(generated_blogs)
            print(f"Generated {result.blogs_generated} blogs")
        except Exception as e:
            error_msg = f"Blog generation failed: {str(e)}"
            result.errors.append(error_msg)
            print(f"Error: {error_msg}")
            return result

        if dry_run:
            print("\n[DRY RUN] Would send blogs to Duda:")
            for i, blog in enumerate(generated_blogs, 1):
                publish_status = "PUBLISHED" if (i == 1 and result.site_is_published) else "DRAFT"
                print(f"  {i}. [{publish_status}] {blog.get('title', 'Unknown')}")
            result.success = True
            result.blogs_sent = result.blogs_generated
            result.first_blog_published = result.site_is_published
            return result

        # Step 3: Format and send blogs to Duda
        print("\nFormatting and sending blogs to Duda...")
        blog_payloads = []
        used_images = set()

        for i, blog in enumerate(generated_blogs, 1):
            try:
                # Fetch featured image from Pexels
                image_url = None
                if app_config.pexels_enabled:
                    try:
                        image_url = await self.pexels_client.search_image(
                            customer.industry,
                            blog.get('title', ''),
                            used_images
                        )
                        if image_url:
                            used_images.add(image_url)
                    except Exception as img_error:
                        print(f"Warning: Image fetch failed for blog {i}: {str(img_error)}")

                # Format for Duda API (all created as drafts initially)
                payload = self.html_formatter.prepare_blog_for_duda(
                    blog,
                    customer.business_name,
                    image_url,
                    theme_colors
                )
                blog_payloads.append(payload)

            except Exception as e:
                error_msg = f"Failed to format blog '{blog.get('title', 'Unknown')}': {str(e)}"
                result.errors.append(error_msg)
                print(f"Error: {error_msg}")

        # Send all blogs to Duda
        first_post_id = None
        if blog_payloads:
            try:
                send_results = await self.duda_client.send_multiple_blogs(
                    site_name=customer.duda_site_code,
                    blog_payloads=blog_payloads
                )

                for i, send_result in enumerate(send_results):
                    if send_result.get('success'):
                        result.blogs_sent += 1
                        # Capture first post ID for publishing
                        if i == 0:
                            first_post_id = send_result.get('post_id')
                    else:
                        result.errors.append(send_result.get('error', 'Unknown error'))

                print(f"\nSent {result.blogs_sent}/{result.blogs_generated} blogs to Duda")

            except Exception as e:
                error_msg = f"Failed to send blogs to Duda: {str(e)}"
                result.errors.append(error_msg)
                print(f"Error: {error_msg}")

        # Step 4: Publish first blog if site is published
        if first_post_id and result.site_is_published:
            print(f"\nPublishing first blog (ID: {first_post_id})...")
            try:
                publish_result = await self.duda_client.publish_blog_post(
                    customer.duda_site_code,
                    first_post_id
                )
                if publish_result.get('success'):
                    result.first_blog_published = True
                    print("First blog published successfully!")
                else:
                    print(f"Warning: Failed to publish first blog: {publish_result.get('error')}")
            except Exception as e:
                print(f"Warning: Failed to publish first blog: {str(e)}")

        result.success = result.blogs_sent > 0 and len(result.errors) == 0

        return result

    async def process_batch(
        self,
        csv_path: str,
        dry_run: bool = False,
        limit: Optional[int] = None
    ) -> BatchOnboardingResult:
        """
        Process a batch of customers from CSV file.

        Args:
            csv_path: Path to the onboarding CSV file
            dry_run: If True, don't actually send to Duda
            limit: Optional limit on number of customers to process

        Returns:
            BatchOnboardingResult with all processing details
        """
        batch_result = BatchOnboardingResult(
            total_customers=0,
            processed=0,
            successful=0,
            failed=0,
            skipped=0,
            flagged_for_review=0,
            start_time=datetime.now()
        )

        # Parse CSV
        print(f"\n{'#'*60}")
        print("BATCH ONBOARDING STARTED")
        print(f"{'#'*60}")
        print(f"\nParsing CSV: {csv_path}")

        try:
            valid_customers, flagged_customers = parse_onboarding_csv(csv_path)
        except Exception as e:
            print(f"Error parsing CSV: {str(e)}")
            batch_result.end_time = datetime.now()
            return batch_result

        batch_result.total_customers = len(valid_customers) + len(flagged_customers)
        batch_result.flagged_for_review = len(flagged_customers)
        batch_result.flagged_customers = flagged_customers

        print(f"Total customers in CSV: {batch_result.total_customers}")
        print(f"Ready for processing: {len(valid_customers)}")
        print(f"Flagged for manual review: {len(flagged_customers)}")

        if dry_run:
            print("\n[DRY RUN MODE] - No actual API calls will be made")

        # Apply limit if specified
        customers_to_process = valid_customers[:limit] if limit else valid_customers

        print(f"\nProcessing {len(customers_to_process)} customers...")

        # Process each customer
        for i, customer in enumerate(customers_to_process, 1):
            print(f"\n[{i}/{len(customers_to_process)}] Processing {customer.business_name}...")

            try:
                result = await self.process_single_customer(customer, dry_run=dry_run)
                batch_result.results.append(result)
                batch_result.processed += 1

                if result.success:
                    batch_result.successful += 1
                elif result.skipped:
                    batch_result.skipped += 1
                else:
                    batch_result.failed += 1

            except Exception as e:
                print(f"Error processing {customer.business_name}: {str(e)}")
                error_result = OnboardingResult(
                    customer=customer,
                    success=False,
                    blogs_generated=0,
                    blogs_sent=0,
                    first_blog_published=False,
                    site_is_published=False,
                    errors=[str(e)]
                )
                batch_result.results.append(error_result)
                batch_result.failed += 1

            # Small delay between customers to avoid rate limiting
            if not dry_run and i < len(customers_to_process):
                await asyncio.sleep(2)

        batch_result.end_time = datetime.now()

        # Print summary
        self._print_batch_summary(batch_result)

        return batch_result

    def _print_batch_summary(self, result: BatchOnboardingResult):
        """Print a summary of batch processing results."""
        duration = (result.end_time - result.start_time).total_seconds()

        print(f"\n{'#'*60}")
        print("BATCH ONBOARDING COMPLETE")
        print(f"{'#'*60}")
        print(f"\nDuration: {duration:.1f} seconds")
        print(f"\nSummary:")
        print(f"  Total Customers: {result.total_customers}")
        print(f"  Processed: {result.processed}")
        print(f"  Successful: {result.successful}")
        print(f"  Failed: {result.failed}")
        print(f"  Skipped: {result.skipped}")
        print(f"  Flagged for Review: {result.flagged_for_review}")

        if result.flagged_customers:
            print(f"\nCustomers Needing Manual Review:")
            for c in result.flagged_customers:
                print(f"  - Record ID: {c.record_id}")
                print(f"    Site Code: {c.duda_site_code}")
                print(f"    Issue: {c.parse_notes}")

        # Show any errors
        failed_results = [r for r in result.results if not r.success and not r.skipped]
        if failed_results:
            print(f"\nFailed Customers:")
            for r in failed_results:
                print(f"  - {r.customer.business_name}")
                for error in r.errors:
                    print(f"    Error: {error}")


async def run_validation_report(csv_path: str) -> str:
    """
    Generate and return a validation report for the CSV without processing.

    Args:
        csv_path: Path to the onboarding CSV file

    Returns:
        Validation report as a string
    """
    valid_customers, flagged_customers = parse_onboarding_csv(csv_path)
    report = generate_validation_report(valid_customers, flagged_customers)
    return report
