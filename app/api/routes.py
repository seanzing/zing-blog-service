"""API routes for the blog generation service."""
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from typing import List, Optional
from datetime import datetime, timezone
import secrets

from app.schemas import (
    GenerationRequest,
    GenerationResponse,
    HealthCheck,
    TenantInfo,
    DirectGenerationRequest,
    JobEnqueueResponse,
    JobStatusResponse,
)
from app.config import get_tenant_data, get_all_tenant_ids, app_config, settings
from app.services.blog_generator import BlogGenerator
from app.services.html_formatter import HTMLFormatter
from app.services.duda_client import DudaClient
from app.services.pexels_client import PexelsClient
from app.services.job_manager import job_manager

# Initialize router
router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Initialize services
blog_generator = BlogGenerator()
html_formatter = HTMLFormatter()
duda_client = DudaClient()
pexels_client = PexelsClient()


# Authentication helpers
def verify_auth(auth_token: Optional[str] = Cookie(None)) -> bool:
    """Verify the authentication token from cookie."""
    if not settings.app_password:
        return True  # No password configured, allow access
    return auth_token == settings.app_password


def require_auth(auth_token: Optional[str] = Cookie(None)):
    """Dependency to require authentication."""
    if not verify_auth(auth_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    if not settings.app_password:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, response: Response):
    """Handle login form submission."""
    form = await request.form()
    password = form.get("password", "")

    if password == settings.app_password:
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="auth_token",
            value=settings.app_password,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7  # 7 days
        )
        return response
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid password"}
        )


@router.get("/logout")
async def logout():
    """Handle logout."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("auth_token")
    return response


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, auth_token: Optional[str] = Cookie(None)):
    """Render the home page with blog generation UI."""
    # Check auth if password is configured
    if settings.app_password and not verify_auth(auth_token):
        return RedirectResponse(url="/login", status_code=302)

    tenant_ids = get_all_tenant_ids()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenant_ids": tenant_ids,
            "mode": app_config.mode,
            "environment": settings.environment,
            "auth_enabled": bool(settings.app_password)
        }
    )


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return HealthCheck(
        status="healthy",
        environment=settings.environment,
        mode=app_config.mode,
        timestamp=datetime.utcnow()
    )


@router.get("/tenants", response_model=List[TenantInfo])
async def get_tenants():
    """Get list of all tenants."""
    tenant_ids = get_all_tenant_ids()
    tenants = []
    for tenant_id in tenant_ids:
        tenant_data = get_tenant_data(tenant_id)
        tenants.append(TenantInfo(**tenant_data))
    return tenants


@router.get("/tenants/{tenant_id}", response_model=TenantInfo)
async def get_tenant(tenant_id: str):
    """Get specific tenant information."""
    try:
        tenant_data = get_tenant_data(tenant_id)
        return TenantInfo(**tenant_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/generate", response_model=GenerationResponse)
async def generate_blogs(request: GenerationRequest):
    """
    Generate and send blogs for a specific tenant.

    This endpoint:
    1. Retrieves tenant information
    2. Generates 12 unique blogs using OpenAI
    3. Formats each blog as base64-encoded HTML
    4. Sends each blog to Duda API
    5. Returns generation results
    """
    try:
        # Get tenant data
        tenant_data = get_tenant_data(request.tenant_id)
        business_name = tenant_data['business_name']
        industry = tenant_data['industry']
        location = tenant_data['location']
        duda_site_code = tenant_data['duda_site_code']

        print(f"\n{'='*60}")
        print(f"Starting blog generation for: {business_name}")
        print(f"Industry: {industry} | Location: {location}")
        print(f"Tenant ID: {request.tenant_id}")
        print(f"{'='*60}\n")

        errors = []
        blogs_generated = 0
        blogs_sent = 0
        send_details = []

        # Step 1: Generate blogs
        print(f"Generating {app_config.number_of_blogs} blogs using {app_config.model}...")
        try:
            generated_blogs = blog_generator.generate_multiple_blogs(
                business_name=business_name,
                industry=industry,
                location=location
            )
            blogs_generated = len(generated_blogs)
            print(f"✓ Successfully generated {blogs_generated} blogs\n")
        except Exception as e:
            error_msg = f"Blog generation failed: {str(e)}"
            errors.append(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        # Step 2: Format and send to Duda
        print(f"Formatting and sending blogs to Duda (mode: {app_config.mode})...")
        blog_payloads = []
        used_images = set()  # Track images used in this batch to avoid duplicates

        for i, blog in enumerate(generated_blogs, 1):
            try:
                # Fetch featured image from Pexels
                image_url = None
                if app_config.pexels_enabled:
                    try:
                        print(f"Fetching image for blog {i}: '{blog.get('title', 'Unknown')}'...")
                        image_url = await pexels_client.search_image(
                            industry,
                            blog.get('title', ''),
                            used_images
                        )
                        if image_url:
                            print(f"✓ Image found for blog {i}")
                            used_images.add(image_url)  # Track this image as used
                        else:
                            print(f"⚠ No image found for blog {i}, continuing without image")
                    except Exception as img_error:
                        print(f"⚠ Image fetch failed for blog {i}: {str(img_error)}, continuing without image")

                # Format for Duda API (with or without image)
                payload = html_formatter.prepare_blog_for_duda(blog, business_name, image_url)
                blog_payloads.append(payload)
            except Exception as e:
                error_msg = f"Failed to format blog '{blog.get('title', 'Unknown')}': {str(e)}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")

        # Send all blogs to Duda
        if blog_payloads:
            try:
                send_results = await duda_client.send_multiple_blogs(
                    site_name=duda_site_code,
                    blog_payloads=blog_payloads
                )

                # Process results
                for result in send_results:
                    if result.get('success'):
                        blogs_sent += 1
                    else:
                        errors.append(result.get('error', 'Unknown error'))

                    send_details.append({
                        "blog_number": result.get('blog_number'),
                        "title": result.get('title'),
                        "success": result.get('success'),
                        "error": result.get('error')
                    })

                print(f"\n✓ Successfully sent {blogs_sent}/{blogs_generated} blogs to Duda")

            except Exception as e:
                error_msg = f"Failed to send blogs to Duda: {str(e)}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")

        # Build response
        success = blogs_sent > 0 and len(errors) == 0

        print(f"\n{'='*60}")
        print(f"Generation Complete!")
        print(f"Blogs Generated: {blogs_generated}")
        print(f"Blogs Sent: {blogs_sent}")
        print(f"Errors: {len(errors)}")
        print(f"{'='*60}\n")

        return GenerationResponse(
            message=f"Generated {blogs_generated} blogs, sent {blogs_sent} to Duda",
            tenant_id=request.tenant_id,
            business_name=business_name,
            blogs_generated=blogs_generated,
            blogs_sent_to_duda=blogs_sent,
            success=success,
            errors=errors,
            details=send_details
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# Holds references to in-flight background tasks so the event loop's task
# registry keeps them alive (asyncio only holds weak references to tasks).
_background_tasks: set = set()


async def _run_direct_generation_job(
    job_id: str,
    *,
    business_name: str,
    industry: str,
    location: str,
    duda_site_code: str,
    num_blogs: int,
) -> None:
    """Background worker: generate blogs and send them to Duda, updating job state.

    The heavy, synchronous OpenAI generation is run via asyncio.to_thread so it
    does NOT block the event loop — the /health probe and /generate/status polls
    stay responsive throughout, even for 50-60 blog batches.
    """
    errors: List[str] = []
    try:
        print(f"\n{'='*60}")
        print(f"[job {job_id}] Starting blog generation for: {business_name}")
        print(f"Industry: {industry} | Location: {location}")
        print(f"Duda Site: {duda_site_code} | Num Blogs: {num_blogs}")
        print(f"{'='*60}\n")

        # Step 1: Generate blogs (blocking → offloaded to a worker thread)
        job_manager.update(job_id, status="generating", message=f"Generating {num_blogs} blogs...")
        try:
            generated_blogs = await asyncio.to_thread(
                blog_generator.generate_multiple_blogs,
                business_name=business_name,
                industry=industry,
                location=location,
                count=num_blogs,
            )
        except Exception as e:
            error_msg = f"Blog generation failed: {str(e)}"
            job_manager.update(
                job_id,
                status="failed",
                success=False,
                message=error_msg,
                errors=[error_msg],
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            print(f"✗ [job {job_id}] {error_msg}")
            return

        blogs_generated = len(generated_blogs)
        job_manager.update(
            job_id,
            blogs_generated=blogs_generated,
            status="sending",
            message=f"Generated {blogs_generated} blogs, sending to Duda...",
        )
        print(f"✓ [job {job_id}] Generated {blogs_generated} blogs\n")

        # Step 2: Format and send to Duda
        blog_payloads = []
        used_images = set()
        for i, blog in enumerate(generated_blogs, 1):
            try:
                image_url = None
                if app_config.pexels_enabled:
                    try:
                        image_url = await pexels_client.search_image(
                            industry,
                            blog.get('title', ''),
                            used_images,
                        )
                        if image_url:
                            used_images.add(image_url)
                    except Exception as img_error:
                        print(f"⚠ [job {job_id}] Image fetch failed for blog {i}: {img_error}")

                payload = html_formatter.prepare_blog_for_duda(blog, business_name, image_url)
                blog_payloads.append(payload)
            except Exception as e:
                error_msg = f"Failed to format blog '{blog.get('title', 'Unknown')}': {str(e)}"
                errors.append(error_msg)
                print(f"✗ [job {job_id}] {error_msg}")

        blogs_sent = 0
        if blog_payloads:
            try:
                send_results = await duda_client.send_multiple_blogs(
                    site_name=duda_site_code,
                    blog_payloads=blog_payloads,
                )
                for result in send_results:
                    if result.get('success'):
                        blogs_sent += 1
                    else:
                        errors.append(result.get('error', 'Unknown error'))
            except Exception as e:
                error_msg = f"Failed to send blogs to Duda: {str(e)}"
                errors.append(error_msg)
                print(f"✗ [job {job_id}] {error_msg}")

        success = blogs_sent > 0 and len(errors) == 0
        job_manager.update(
            job_id,
            status="completed",
            blogs_generated=blogs_generated,
            blogs_sent_to_duda=blogs_sent,
            success=success,
            errors=errors,
            message=f"Generated {blogs_generated} blogs, sent {blogs_sent} to Duda",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        print(f"\n[job {job_id}] Complete! Generated {blogs_generated}, sent {blogs_sent}, errors {len(errors)}\n")

    except Exception as e:
        # Catch-all so a background task never dies silently.
        error_msg = f"An error occurred: {str(e)}"
        job_manager.update(
            job_id,
            status="failed",
            success=False,
            message=error_msg,
            errors=errors + [error_msg],
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        print(f"✗ [job {job_id}] {error_msg}")


@router.post("/generate/direct", response_model=JobEnqueueResponse, status_code=202)
async def generate_blogs_direct(request: DirectGenerationRequest):
    """
    Enqueue an asynchronous blog generation job with direct business details.

    Returns a job_id immediately. Poll GET /generate/status/{job_id} for progress
    and the final result. Generation runs in the background so large batches
    (25-60 blogs) don't exceed request/proxy timeouts or starve the healthcheck.
    """
    job_id = job_manager.create(
        business_name=request.business_name,
        num_blogs=request.num_blogs,
    )

    task = asyncio.create_task(
        _run_direct_generation_job(
            job_id,
            business_name=request.business_name,
            industry=request.industry,
            location=request.location,
            duda_site_code=request.duda_site_code,
            num_blogs=request.num_blogs,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return JobEnqueueResponse(
        job_id=job_id,
        status="queued",
        business_name=request.business_name,
        num_blogs=request.num_blogs,
    )


@router.get("/generate/status/{job_id}", response_model=JobStatusResponse)
async def generate_status(job_id: str):
    """Return the status/result of an async generation job."""
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@router.get("/config")
async def get_config():
    """Get current configuration (for debugging)."""
    return {
        "model": app_config.model,
        "temperature": app_config.temperature,
        "word_count_range": f"{app_config.word_count_min}-{app_config.word_count_max}",
        "tone": app_config.tone,
        "number_of_blogs": app_config.number_of_blogs,
        "mode": app_config.mode,
        "environment": settings.environment
    }


@router.post("/config/reload")
async def reload_config():
    """Reload configuration from config.yaml file."""
    try:
        app_config.reload()
        return {"message": "Configuration reloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")
