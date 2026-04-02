"""Pexels API client for fetching stock images."""
import httpx
import re
from typing import Optional, Dict, List
from openai import OpenAI
from app.config import settings, app_config


class PexelsClient:
    """Client for interacting with Pexels API."""

    def __init__(self):
        """Initialize Pexels client."""
        self.config = app_config
        self.base_url = "https://api.pexels.com/v1"
        self.api_key = settings.pexels_api_key
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    def _get_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for Pexels API.

        Returns:
            Dictionary with Authorization header
        """
        return {
            "Authorization": self.api_key
        }

    def _generate_search_query(self, industry: str, title: str) -> str:
        """
        Use GPT to generate a visually descriptive Pexels search query.

        Args:
            industry: Business industry
            title: Blog post title

        Returns:
            A search query optimized for finding relevant stock photos
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=30,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Generate a short stock photo search query (3-5 words) for a blog post.\n"
                        f"Industry: {industry}\n"
                        f"Blog title: {title}\n\n"
                        f"The query should describe a real, photographable scene that a photographer "
                        f"would tag on a stock photo site. Focus on what the image should visually show, "
                        f"not abstract concepts. Return ONLY the search query, nothing else."
                    )
                }]
            )
            query = response.choices[0].message.content.strip().strip('"')
            print(f"  GPT search query: '{query}'")
            return query
        except Exception as e:
            print(f"  GPT query generation failed ({e}), falling back to keyword extraction")
            words = re.findall(r'\b[a-z]+\b', title.lower())
            stop_words = {'the','a','an','and','or','but','in','on','at','to','for','of','with','by','from','your','you','how','what','when','where','why','which','who','that','this','top','answered','answers','common','guide','faqs','faq','about','questions'}
            keywords = [w for w in words if w not in stop_words][:3]
            return ' '.join(keywords) if keywords else industry

    def _pick_best_image(self, industry: str, title: str, photos: List[Dict]) -> Optional[Dict]:
        """
        Use GPT to select the most relevant image from Pexels results based on alt text.

        Args:
            industry: Business industry
            title: Blog post title
            photos: List of Pexels photo objects with 'alt' and 'src' fields

        Returns:
            The best matching photo dict, or None if all are rejected
        """
        candidates = []
        for i, photo in enumerate(photos):
            alt = photo.get("alt", "No description")
            candidates.append(f"{i+1}. {alt}")

        candidates_text = "\n".join(candidates)

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=30,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Pick the best stock photo for this blog post. If none are relevant, say NONE.\n\n"
                        f"Industry: {industry}\n"
                        f"Blog title: {title}\n\n"
                        f"Photo options (by description):\n{candidates_text}\n\n"
                        f"Reply with ONLY the number of the best match (e.g. '3'), or 'NONE'."
                    )
                }]
            )
            choice = response.choices[0].message.content.strip()

            if choice.upper() == "NONE":
                print(f"  GPT rejected all {len(photos)} image candidates")
                return None

            idx = int(re.search(r'\d+', choice).group()) - 1
            if 0 <= idx < len(photos):
                print(f"  GPT picked image {idx+1}/{len(photos)}: \"{photos[idx].get('alt', '')}\"")
                return photos[idx]

            return None
        except Exception as e:
            print(f"  GPT image selection failed ({e}), using first candidate")
            return photos[0] if photos else None

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

        # Step 1: GPT generates a visually descriptive search query
        query = self._generate_search_query(industry, title)

        # Step 2: Search Pexels with the GPT-generated query
        photos = await self._fetch_pexels_results(query, used_images)

        if photos:
            # Step 3: GPT picks the best image from results
            best = self._pick_best_image(industry, title, photos)
            if best:
                image_url = best["src"]["original"]
                print(f"  Selected image: {image_url}")
                return image_url

            # GPT rejected all results — retry with industry-only query
            print(f"  Retrying with broader query: '{industry}'")
            photos = await self._fetch_pexels_results(industry, used_images)
            if photos:
                best = self._pick_best_image(industry, title, photos)
                if best:
                    image_url = best["src"]["original"]
                    print(f"  Selected image (retry): {image_url}")
                    return image_url

        # Final fallback
        return await self._search_fallback(used_images)

    async def _fetch_pexels_results(self, query: str, used_images: set) -> List[Dict]:
        """
        Fetch photos from Pexels, filtering out already-used images.

        Returns:
            List of unused photo dicts from Pexels
        """
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

                photos = data.get("photos", [])
                # Filter out already-used images
                unused = [p for p in photos if p["src"]["original"] not in used_images]
                return unused

        except Exception as e:
            print(f"  Pexels API error: {str(e)}")
            return []

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
