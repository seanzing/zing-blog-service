"""HTML formatting and base64 encoding service."""
import base64
from typing import Dict


class HTMLFormatter:
    """Handles HTML formatting and base64 encoding for blog content."""

    @staticmethod
    def format_blog_as_html(title: str, content: str) -> str:
        """
        Format blog content as a complete HTML document.

        Args:
            title: Blog post title
            content: Blog post content (already contains HTML tags from OpenAI)

        Returns:
            Complete HTML document as string
        """
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
            color: #333;
            padding: 0;
            margin: 0;
        }}
        article {{
            width: 100%;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        h3 {{
            color: #555;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        p {{
            margin: 15px 0;
        }}
        ul, ol {{
            margin: 15px 0;
            padding-left: 30px;
        }}
        li {{
            margin: 8px 0;
        }}
        strong {{
            color: #2c3e50;
        }}
        a {{
            color: #3498db;
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

    def prepare_blog_for_duda(self, blog_data: Dict[str, str], author: str) -> Dict[str, str]:
        """
        Prepare a blog post for Duda API submission.

        Args:
            blog_data: Dictionary with 'title', 'description', 'content' from OpenAI
            author: Author name (business name)

        Returns:
            Dictionary formatted for Duda API payload
        """
        # Format the content as HTML
        html_content = self.format_blog_as_html(blog_data['title'], blog_data['content'])

        # Encode to base64
        encoded_content = self.encode_to_base64(html_content)

        # Return in Duda API format
        return {
            "title": blog_data['title'],
            "description": blog_data['description'],
            "content": encoded_content,
            "author": author
        }
