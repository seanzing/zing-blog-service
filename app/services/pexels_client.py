"""Pexels API client for fetching stock images."""
import httpx
import re
from typing import Optional, Dict
from app.config import settings, app_config


class PexelsClient:
    """Client for interacting with Pexels API."""

    def __init__(self):
        """Initialize Pexels client."""
        self.config = app_config
        self.base_url = "https://api.pexels.com/v1"
        self.api_key = settings.pexels_api_key

    def _get_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for Pexels API.

        Returns:
            Dictionary with Authorization header
        """
        return {
            "Authorization": self.api_key
        }

    def _extract_keywords(self, title: str) -> str:
        """
        Extract broad keywords from blog title.

        Removes common stop words and keeps meaningful terms.

        Args:
            title: Blog post title

        Returns:
            Extracted keywords as a string
        """
        # Common words to remove for broader search
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'must', 'can', 'your', 'you',
            'how', 'what', 'when', 'where', 'why', 'which', 'who', 'that', 'this'
        }

        # Convert to lowercase and split into words
        words = re.findall(r'\b[a-z]+\b', title.lower())

        # Filter out stop words and keep first 2-3 meaningful words
        keywords = [word for word in words if word not in stop_words][:2]

        return ' '.join(keywords) if keywords else 'business'

    async def search_image(self, industry: str, title: str, used_images: set = None) -> Optional[str]:
        """
        Search for a relevant stock image on Pexels.

        Creates a broad search query using industry and extracted keywords
        from the title to ensure relevant results. Avoids returning images
        that have already been used in the current batch.

        Args:
            industry: Business industry (e.g., "Internet Support Service")
            title: Blog post title
            used_images: Set of image URLs already used in this batch

        Returns:
            Image URL if found, None otherwise
        """
        if not self.config.pexels_enabled:
            print("Pexels integration is disabled in config")
            return None

        if not self.api_key:
            print("Pexels API key not configured")
            return None

        if used_images is None:
            used_images = set()

        # Extract keywords from title for broader search
        keywords = self._extract_keywords(title)

        # Create search query - combine industry with broad keywords
        query = f"{industry} {keywords}".strip()

        try:
            headers = self._get_headers()
            params = {
                "query": query,
                "per_page": self.config.pexels_per_page,
                "orientation": self.config.pexels_orientation
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    headers=headers,
                    params=params
                )

                response.raise_for_status()
                data = response.json()

                # Check if we have results
                if data.get("photos") and len(data["photos"]) > 0:
                    # Find first unused image from results
                    for photo in data["photos"]:
                        image_url = photo["src"]["original"]
                        if image_url not in used_images:
                            print(f"Found unused Pexels image for query '{query}': {image_url}")
                            return image_url

                    # All images from this search have been used
                    print(f"All images for '{query}' already used, trying fallback query")
                    return await self._search_fallback(used_images)
                else:
                    # Try fallback query if primary search fails
                    print(f"No results for '{query}', trying fallback query")
                    return await self._search_fallback(used_images)

        except httpx.HTTPError as e:
            print(f"Pexels API error: {str(e)}")
            return await self._search_fallback(used_images)
        except Exception as e:
            print(f"Unexpected error searching Pexels: {str(e)}")
            return None

    async def _search_fallback(self, used_images: set = None) -> Optional[str]:
        """
        Search using fallback query if primary search fails.

        Args:
            used_images: Set of image URLs already used in this batch

        Returns:
            Image URL if found, None otherwise
        """
        if used_images is None:
            used_images = set()

        try:
            headers = self._get_headers()
            params = {
                "query": self.config.pexels_fallback_query,
                "per_page": self.config.pexels_per_page,
                "orientation": self.config.pexels_orientation
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    headers=headers,
                    params=params
                )

                response.raise_for_status()
                data = response.json()

                if data.get("photos") and len(data["photos"]) > 0:
                    # Find first unused image from fallback results
                    for photo in data["photos"]:
                        image_url = photo["src"]["original"]
                        if image_url not in used_images:
                            print(f"Found unused fallback image: {image_url}")
                            return image_url

                    # All fallback images already used
                    print("All fallback images already used")
                    return None
                else:
                    print("No fallback images found")
                    return None

        except Exception as e:
            print(f"Fallback search failed: {str(e)}")
            return None

    async def test_connection(self) -> bool:
        """
        Test connection to Pexels API.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if not self.api_key:
                print("Pexels API key not configured")
                return False

            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/search?query=test&per_page=1",
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Pexels connection test failed: {str(e)}")
            return False
