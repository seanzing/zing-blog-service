"""Duda API client with local/production mode support."""
import httpx
import base64
from typing import Dict, List
from app.config import settings, app_config


class DudaClient:
    """Client for interacting with Duda API."""

    def __init__(self):
        """Initialize Duda client."""
        self.config = app_config
        self.base_url = "https://api.duda.co/api"
        self.mode = self.config.mode

    def _get_auth_header(self) -> Dict[str, str]:
        """
        Generate authentication header for Duda API.

        Returns:
            Dictionary with Authorization header
        """
        # Combine user:password and encode to base64
        credentials = f"{settings.duda_api_user}:{settings.duda_api_password}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json"
        }

    async def send_blog_to_duda_local(self, site_name: str, blog_payload: Dict[str, str]) -> Dict:
        """
        Send a blog post directly to Duda API (local mode).

        Args:
            site_name: Duda site code
            blog_payload: Blog data formatted for Duda API

        Returns:
            API response dictionary

        Raises:
            httpx.HTTPError: If API request fails
        """
        endpoint = f"{self.base_url}/sites/multiscreen/{site_name}/blog/posts/import"
        headers = self._get_auth_header()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json=blog_payload,
                headers=headers
            )

            # Raise exception for bad status codes
            response.raise_for_status()

            response_data = response.json() if response.text else {}
            return {
                "success": True,
                "status_code": response.status_code,
                "post_id": response_data.get("id"),
                "response": response_data
            }

    async def send_blog_to_duda_production(self, site_name: str, blog_payload: Dict[str, str]) -> Dict:
        """
        Send a blog post via Duda Integration Service (production mode).

        This method will be implemented to call your separate Duda Integration Service.

        Args:
            site_name: Duda site code
            blog_payload: Blog data formatted for Duda API

        Returns:
            API response dictionary

        Raises:
            NotImplementedError: Until integration service is connected
        """
        # TODO: Replace with actual integration service endpoint
        integration_service_url = "http://localhost:9000/api/duda/blog/import"

        payload = {
            "site_name": site_name,
            "blog_data": blog_payload
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                integration_service_url,
                json=payload
            )

            response.raise_for_status()

            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.json() if response.text else {}
            }

    async def send_blog(self, site_name: str, blog_payload: Dict[str, str]) -> Dict:
        """
        Send a blog post to Duda (automatically chooses local or production mode).

        Args:
            site_name: Duda site code
            blog_payload: Blog data formatted for Duda API

        Returns:
            API response dictionary
        """
        if self.mode == "local":
            return await self.send_blog_to_duda_local(site_name, blog_payload)
        elif self.mode == "production":
            return await self.send_blog_to_duda_production(site_name, blog_payload)
        else:
            raise ValueError(f"Invalid deployment mode: {self.mode}. Must be 'local' or 'production'")

    async def send_multiple_blogs(
        self,
        site_name: str,
        blog_payloads: List[Dict[str, str]]
    ) -> List[Dict]:
        """
        Send multiple blog posts to Duda sequentially.

        Args:
            site_name: Duda site code
            blog_payloads: List of blog data dictionaries

        Returns:
            List of API response dictionaries
        """
        results = []

        for i, payload in enumerate(blog_payloads, 1):
            try:
                result = await self.send_blog(site_name, payload)
                result['blog_number'] = i
                result['title'] = payload.get('title', 'Unknown')
                results.append(result)
                print(f"Successfully sent blog {i}/{len(blog_payloads)}: {payload.get('title')}")
            except Exception as e:
                error_result = {
                    "success": False,
                    "blog_number": i,
                    "title": payload.get('title', 'Unknown'),
                    "error": str(e)
                }
                results.append(error_result)
                print(f"Failed to send blog {i}/{len(blog_payloads)}: {str(e)}")

        return results

    async def test_connection(self) -> bool:
        """
        Test connection to Duda API.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if self.mode == "local":
                headers = self._get_auth_header()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Test with a simple GET request to Duda API
                    response = await client.get(
                        f"{self.base_url}/accounts/authenticated",
                        headers=headers
                    )
                    return response.status_code == 200
            else:
                # For production mode, test integration service
                return True  # TODO: Implement when integration service is ready
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False

    async def get_blog_posts(self, site_name: str) -> Dict:
        """
        Get all blog posts for a site.

        Args:
            site_name: Duda site code

        Returns:
            Dictionary with success status and list of posts
        """
        try:
            if self.mode == "local":
                headers = self._get_auth_header()
                endpoint = f"{self.base_url}/sites/multiscreen/{site_name}/blog/posts"

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(endpoint, headers=headers)
                    response.raise_for_status()

                    posts = response.json()
                    return {
                        "success": True,
                        "posts": posts if isinstance(posts, list) else posts.get("results", [])
                    }
            else:
                return {"success": False, "error": "Not implemented for production mode"}

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "posts": [],
                "error": f"HTTP {e.response.status_code}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "posts": [],
                "error": str(e)
            }

    async def publish_blog_post(self, site_name: str, post_id: str) -> Dict:
        """
        Publish a blog post that was created as a draft.

        Args:
            site_name: Duda site code
            post_id: The blog post ID returned from import

        Returns:
            Dictionary with success status
        """
        try:
            if self.mode == "local":
                headers = self._get_auth_header()
                endpoint = f"{self.base_url}/sites/multiscreen/{site_name}/blog/posts/{post_id}/publish"

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(endpoint, headers=headers)
                    response.raise_for_status()

                    return {
                        "success": True,
                        "post_id": post_id,
                        "status_code": response.status_code
                    }
            else:
                # Production mode - would call integration service
                return {"success": True, "post_id": post_id}

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "post_id": post_id,
                "error": f"HTTP {e.response.status_code}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "post_id": post_id,
                "error": str(e)
            }

    async def get_site_status(self, site_name: str) -> Dict:
        """
        Get the publication status of a Duda site.

        Args:
            site_name: Duda site code

        Returns:
            Dictionary with site status info including 'is_published'
        """
        try:
            if self.mode == "local":
                headers = self._get_auth_header()
                endpoint = f"{self.base_url}/sites/multiscreen/{site_name}"

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(endpoint, headers=headers)
                    response.raise_for_status()

                    site_data = response.json()
                    # Duda returns 'publish_status' field: 'PUBLISHED', 'UNPUBLISHED', etc.
                    publish_status = site_data.get('publish_status', 'UNKNOWN')

                    return {
                        "success": True,
                        "site_name": site_name,
                        "is_published": publish_status == "PUBLISHED",
                        "publish_status": publish_status,
                        "site_data": site_data
                    }
            else:
                # Production mode - assume published for now
                return {
                    "success": True,
                    "site_name": site_name,
                    "is_published": True,
                    "publish_status": "ASSUMED_PUBLISHED"
                }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "site_name": site_name,
                "is_published": False,
                "error": f"HTTP {e.response.status_code}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "site_name": site_name,
                "is_published": False,
                "error": str(e)
            }
