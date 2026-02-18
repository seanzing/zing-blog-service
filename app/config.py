"""Configuration management for the blog generation service."""
import os
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Environment variables configuration."""
    openai_api_key: str
    duda_api_user: str = ""
    duda_api_password: str = ""
    pexels_api_key: str = ""
    environment: str = "development"
    app_password: str = ""  # Simple password protection for team access

    class Config:
        env_file = ".env"
        extra = "ignore"


class AppConfig:
    """Application configuration from YAML file."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        self.config_path = Path(config_path)
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Blog generation settings
        blog_config = config.get('blog_generation', {})
        self.model = blog_config.get('model', 'gpt-4')
        self.temperature = blog_config.get('temperature', 0.7)
        self.word_count_min = blog_config.get('word_count_min', 1300)
        self.word_count_max = blog_config.get('word_count_max', 1600)
        self.tone = blog_config.get('tone', 'professional')
        self.number_of_blogs = blog_config.get('number_of_blogs', 12)
        self.seo_guidelines = blog_config.get('seo_guidelines', [])

        # Pexels settings
        pexels_config = config.get('pexels', {})
        self.pexels_enabled = pexels_config.get('enabled', True)
        self.pexels_orientation = pexels_config.get('orientation', 'landscape')
        self.pexels_fallback_query = pexels_config.get('fallback_query', 'business professional')
        self.pexels_per_page = pexels_config.get('per_page', 1)

        # Deployment settings
        deployment_config = config.get('deployment', {})
        self.mode = deployment_config.get('mode', 'local')
        self.host = deployment_config.get('host', '0.0.0.0')
        self.port = int(os.environ.get("PORT", deployment_config.get('port', 8000)))

    def reload(self):
        """Reload configuration from file."""
        self._load_config()


# Global configuration instances
settings = Settings()
app_config = AppConfig()


# Hardcoded tenant data for testing phase
HARDCODED_TENANTS = {
    "tenant_001": {
        "tenant_id": "tenant_001",
        "business_name": "ZING Support",
        "industry": "Internet Support Service",
        "location": "Castle Rock, Colorado",
        "duda_site_code": "ed70f6d8"
    }
}


def get_tenant_data(tenant_id: str) -> dict:
    """
    Get tenant data by ID.

    In testing phase: Returns hardcoded data
    In production phase: Will query PostgreSQL database

    Args:
        tenant_id: The tenant identifier

    Returns:
        Dictionary with tenant information

    Raises:
        ValueError: If tenant not found
    """
    tenant = HARDCODED_TENANTS.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")
    return tenant


def get_all_tenant_ids() -> List[str]:
    """Get list of all tenant IDs (for UI dropdown)."""
    return list(HARDCODED_TENANTS.keys())
