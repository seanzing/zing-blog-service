"""OpenAI blog generation service."""
from openai import OpenAI
from typing import List, Dict
import json
from app.config import settings, app_config


class BlogGenerator:
    """Handles blog content generation using OpenAI."""

    def __init__(self):
        """Initialize the blog generator with OpenAI API key."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.config = app_config

        # Map common model names to their JSON-supporting equivalents
        self.model_mapping = {
            "gpt-4": "gpt-4o",
            "gpt-4-turbo": "gpt-4o",
            "gpt-3.5-turbo": "gpt-3.5-turbo-1106"
        }

    def _get_model_name(self) -> str:
        """Get the appropriate model name, mapping to JSON-supporting variants."""
        configured_model = self.config.model
        return self.model_mapping.get(configured_model, configured_model)

    def _build_prompt(self, business_name: str, industry: str, location: str, blog_number: int) -> str:
        """
        Build the prompt for OpenAI to generate a blog post.

        Args:
            business_name: Name of the business
            industry: Industry/vertical
            location: Geographic location
            blog_number: Which blog in the series (1-12)

        Returns:
            Formatted prompt string
        """
        seo_guidelines_text = "\n".join([f"- {guideline}" for guideline in self.config.seo_guidelines])

        # Define diverse angles to ensure variety across all blogs
        angle_strategies = [
            "Target homeowners/residential customers with beginner-friendly how-to content",
            "Target small business owners with practical guides and best practices",
            "Create a comprehensive listicle (Top 5/10/7 tips or strategies)",
            "Focus on troubleshooting common problems and solutions",
            "Address frequently asked questions in Q&A format",
            "Compare different options or approaches (comparison guide)",
            "Explain technical concepts in simple terms for non-experts",
            "Discuss seasonal or timely considerations",
            "Focus on cost-saving tips and budget considerations",
            "Highlight signs/indicators that customers need professional help",
            "Discuss latest trends or innovations in the industry",
            "Create a beginner's guide or 101-style introduction"
        ]

        # Rotate through angles based on blog number
        angle_index = (blog_number - 1) % len(angle_strategies)
        specific_angle = angle_strategies[angle_index]

        prompt = f"""You are a professional blog writer creating high-quality, SEO-optimized content for {business_name},
a {industry} business located in {location}.

Generate blog post #{blog_number} of 12 total blogs for this business.

REQUIREMENTS:
- Word count: Between {self.config.word_count_min} and {self.config.word_count_max} words
- Tone: {self.config.tone}
- Industry focus: {industry}
- Location relevance: {location}
- Each blog MUST cover a COMPLETELY DIFFERENT topic and angle from others in the series
- Topics should be highly relevant and valuable to potential customers searching for {industry} services in {location}

DIVERSITY REQUIREMENTS (CRITICAL):
This blog should use the following angle/approach:
"{specific_angle}"

Ensure this blog has a DISTINCT:
- Target audience (vary between homeowners, businesses, beginners, experts)
- Content format (how-to, listicle, problem-solution, Q&A, comparison, guide)
- Focus area (different aspect of {industry} services)
- Pain point or need being addressed

AVOID:
- Repeating topics from other blogs in this series
- Generic content that could apply to any business
- Duplicate angles, introductions, or conclusions

SEO GUIDELINES:
{seo_guidelines_text}

FORMAT YOUR RESPONSE AS JSON with exactly these fields:
{{
    "title": "Compelling blog title (60-70 characters)",
    "description": "Meta description / short summary (150-160 characters)",
    "content": "Full blog post content with proper HTML formatting. Start with <h2> sections (NOT <h1>, as the title will serve as H1). Use <h2>, <h3>, <p>, <strong>, <ul>, <li> tags where appropriate. Do not include <html>, <head>, <body>, or <h1> tags."
}}

Make this blog unique, engaging, and valuable for readers searching for {industry} services in {location}.
Follow the specified angle/approach to ensure maximum diversity across all blog posts."""

        return prompt

    def generate_blog(self, business_name: str, industry: str, location: str, blog_number: int) -> Dict[str, str]:
        """
        Generate a single blog post using OpenAI.

        Args:
            business_name: Name of the business
            industry: Industry/vertical
            location: Geographic location
            blog_number: Which blog in the series (1-12)

        Returns:
            Dictionary with 'title', 'description', and 'content' keys

        Raises:
            Exception: If OpenAI API call fails
        """
        prompt = self._build_prompt(business_name, industry, location, blog_number)
        model = self._get_model_name()

        try:
            print(f"Using model: {model} (configured: {self.config.model})")

            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert blog writer specializing in local business content and SEO."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                response_format={"type": "json_object"}
            )

            # Extract the generated content
            content = response.choices[0].message.content

            # Parse the JSON response
            blog_data = json.loads(content)

            return {
                "title": blog_data.get("title", ""),
                "description": blog_data.get("description", ""),
                "content": blog_data.get("content", "")
            }

        except Exception as e:
            raise Exception(f"Failed to generate blog #{blog_number}: {str(e)}")

    def generate_multiple_blogs(
        self,
        business_name: str,
        industry: str,
        location: str,
        count: int = None
    ) -> List[Dict[str, str]]:
        """
        Generate multiple blog posts for a business.

        Args:
            business_name: Name of the business
            industry: Industry/vertical
            location: Geographic location
            count: Number of blogs to generate (defaults to config setting)

        Returns:
            List of blog dictionaries, each with 'title', 'description', and 'content'
        """
        if count is None:
            count = self.config.number_of_blogs

        blogs = []
        for i in range(1, count + 1):
            try:
                blog = self.generate_blog(business_name, industry, location, i)
                blogs.append(blog)
                print(f"Generated blog {i}/{count}: {blog['title']}")
            except Exception as e:
                print(f"Error generating blog {i}/{count}: {str(e)}")
                raise

        return blogs
