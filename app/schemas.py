"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TenantInfo(BaseModel):
    """Tenant information schema."""
    tenant_id: str
    business_name: str
    industry: str
    location: str
    duda_site_code: str


class BlogPost(BaseModel):
    """Individual blog post schema."""
    title: str
    description: str  # Short summary
    content: str  # Full blog post content (base64 encoded HTML)
    author: str  # Business name


class GenerationRequest(BaseModel):
    """Request to generate blogs for a tenant."""
    tenant_id: str = Field(..., description="ID of the tenant to generate blogs for")


class DirectGenerationRequest(BaseModel):
    """Request to generate blogs with direct business details."""
    business_name: str = Field(..., description="Name of the business")
    industry: str = Field(..., description="Business industry/category")
    location: str = Field(..., description="Business location (city, state)")
    duda_site_code: str = Field(..., description="Duda website site code")
    num_blogs: int = Field(12, ge=1, le=50, description="Number of blogs to generate")


class GenerationStatus(BaseModel):
    """Status of a blog generation request."""
    tenant_id: str
    business_name: str
    status: str  # "in_progress", "completed", "failed"
    blogs_generated: int
    blogs_sent: int
    errors: List[str] = []
    started_at: datetime
    completed_at: Optional[datetime] = None


class GenerationResponse(BaseModel):
    """Response from blog generation endpoint."""
    message: str
    tenant_id: str
    business_name: str
    blogs_generated: int
    blogs_sent_to_duda: int
    success: bool
    errors: List[str] = []
    details: List[dict] = []  # Individual blog send results


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    environment: str
    mode: str
    timestamp: datetime
