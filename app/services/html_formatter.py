"""HTML formatting and base64 encoding service."""
import base64
import re
from typing import Dict, List, Optional
from openai import OpenAI
from app.config import settings


# Default colors used when no theme is available
DEFAULT_COLORS = {
    "body_text": "#333",
    "heading": "#34495e",
    "subheading": "#555",
    "accent": "#2c3e50",
    "link": "#3498db",
}


class HTMLFormatter:
    """Handles HTML formatting and base64 encoding for blog content."""

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    @staticmethod
    def _parse_rgba(color_str: str):
        """Extract r, g, b from an rgba/rgb string. Returns (r,g,b) or None."""
        m = re.search(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Try hex
        m = re.search(r'#([0-9a-fA-F]{6})', color_str)
        if m:
            h = m.group(1)
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return None

    @staticmethod
    def _relative_luminance(r, g, b):
        """Calculate relative luminance per WCAG 2.0."""
        def linearize(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

    @staticmethod
    def _contrast_ratio(rgb1, rgb2):
        """Calculate WCAG contrast ratio between two (r,g,b) tuples."""
        l1 = HTMLFormatter._relative_luminance(*rgb1)
        l2 = HTMLFormatter._relative_luminance(*rgb2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def _passes_contrast(self, color_str: str, min_ratio: float = 4.5) -> bool:
        """Check if a color has sufficient contrast against white (WCAG AA)."""
        rgb = self._parse_rgba(color_str)
        if not rgb:
            return False
        return self._contrast_ratio(rgb, (255, 255, 255)) >= min_ratio

    def _map_theme_colors(self, theme_colors: List[Dict]) -> Dict[str, str]:
        """
        Use GPT to map a site's theme colors to blog CSS roles,
        then validate contrast against white and fall back for any that fail.

        Args:
            theme_colors: List of color dicts with 'id', 'label', 'value'

        Returns:
            Dict mapping CSS roles to color values
        """
        # Pre-filter to only colors that pass WCAG AA contrast on white (4.5:1)
        dark_colors = [
            c for c in theme_colors
            if self._passes_contrast(c["value"], 3.0)
        ]

        if not dark_colors:
            print("  No theme colors pass contrast check, using defaults")
            return DEFAULT_COLORS

        color_list = "\n".join(
            f"- {c['label'] or c['id']}: {c['value']}" for c in dark_colors
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Given this website's dark theme colors (pre-filtered for contrast on white), "
                        f"pick the best color for each blog CSS role.\n\n"
                        f"Available dark colors:\n{color_list}\n\n"
                        f"Assign colors for these roles (use the rgba values exactly as given):\n"
                        f"- body_text: main paragraph text (darkest neutral color)\n"
                        f"- heading: h2 headings (brand color if available, otherwise darkest)\n"
                        f"- subheading: h3 headings (slightly different from heading)\n"
                        f"- accent: bold/strong text (darkest available)\n"
                        f"- link: hyperlink color (brand color preferred)\n\n"
                        f"Reply in exactly this format, one per line, nothing else:\n"
                        f"body_text=rgba(...)\nheading=rgba(...)\nsubheading=rgba(...)\naccent=rgba(...)\nlink=rgba(...)"
                    )
                }]
            )
            result = response.choices[0].message.content.strip()
            colors = {}
            for line in result.split("\n"):
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key in DEFAULT_COLORS:
                        colors[key] = val

            # Validate each mapped color passes WCAG AA (4.5:1 for body, 3:1 for large text)
            for role, min_ratio in [("body_text", 4.5), ("heading", 3.0), ("subheading", 3.0), ("accent", 4.5), ("link", 4.5)]:
                if role not in colors or not self._passes_contrast(colors[role], min_ratio):
                    colors[role] = DEFAULT_COLORS[role]

            print(f"  Theme colors mapped: heading={colors['heading']}, link={colors['link']}")
            return colors
        except Exception as e:
            print(f"  Theme color mapping failed ({e}), using defaults")

        return DEFAULT_COLORS

    def format_blog_as_html(self, title: str, content: str, theme_colors: Optional[List[Dict]] = None) -> str:
        """
        Format blog content as a complete HTML document.

        Args:
            title: Blog post title
            content: Blog post content (already contains HTML tags from OpenAI)
            theme_colors: Optional list of color dicts from Duda site theme

        Returns:
            Complete HTML document as string
        """
        if theme_colors:
            colors = self._map_theme_colors(theme_colors)
        else:
            colors = DEFAULT_COLORS

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: {colors['body_text']};
            padding: 0;
            margin: 0;
        }}
        article {{
            width: 100%;
        }}
        h2 {{
            color: {colors['heading']};
            margin-top: 30px;
            margin-bottom: 15px;
            font-weight: bold;
        }}
        h3 {{
            color: {colors['subheading']};
            margin-top: 20px;
            margin-bottom: 10px;
            font-weight: bold;
        }}
        h4 {{
            font-weight: bold;
        }}
        p {{
            margin: 15px 0;
            font-weight: normal;
        }}
        ul, ol {{
            margin: 15px 0;
            padding-left: 30px;
        }}
        li {{
            margin: 8px 0;
        }}
        strong {{
            color: {colors['accent']};
        }}
        a {{
            color: {colors['link']};
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <article>
        {content}
    </article>
</body>
</html>"""
        return html_template

    @staticmethod
    def encode_to_base64(html_content: str) -> str:
        """
        Encode HTML content to base64.

        Args:
            html_content: HTML string to encode

        Returns:
            Base64 encoded string
        """
        html_bytes = html_content.encode('utf-8')
        base64_bytes = base64.b64encode(html_bytes)
        return base64_bytes.decode('utf-8')

    @staticmethod
    def format_rss_item(title: str, description: str, content: str, author: str, pub_date: str = None) -> str:
        """
        Format blog content as an RSS feed item (for reference/future use).

        Args:
            title: Blog post title
            description: Short summary
            content: Full content (HTML)
            author: Author name
            pub_date: Publication date (optional)

        Returns:
            RSS item XML string
        """
        from datetime import datetime
        if pub_date is None:
            pub_date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

        rss_item = f"""<item>
    <title><![CDATA[{title}]]></title>
    <description><![CDATA[{description}]]></description>
    <content:encoded><![CDATA[{content}]]></content:encoded>
    <author>{author}</author>
    <pubDate>{pub_date}</pubDate>
</item>"""
        return rss_item

    def prepare_blog_for_duda(
        self,
        blog_data: Dict[str, str],
        author: str,
        image_url: str = None,
        theme_colors: Optional[List[Dict]] = None
    ) -> Dict[str, str]:
        """
        Prepare a blog post for Duda API submission.

        Args:
            blog_data: Dictionary with 'title', 'description', 'content' from OpenAI
            author: Author name (business name)
            image_url: Optional featured image URL from Pexels
            theme_colors: Optional list of color dicts from Duda site theme

        Returns:
            Dictionary formatted for Duda API payload
        """
        # Format the content as HTML
        html_content = self.format_blog_as_html(blog_data['title'], blog_data['content'], theme_colors)

        # Encode to base64
        encoded_content = self.encode_to_base64(html_content)

        # Build base payload (blogs are created as drafts, published separately)
        payload = {
            "title": blog_data['title'],
            "description": blog_data['description'],
            "content": encoded_content,
            "author": author
        }

        # Add image fields if image URL is provided
        if image_url:
            payload["thumbnail"] = {"url": image_url}
            payload["main_image"] = {"url": image_url}

        return payload
