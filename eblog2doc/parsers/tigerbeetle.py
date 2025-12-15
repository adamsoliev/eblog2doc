"""TigerBeetle blog parser."""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from eblog2doc.parsers.base import BaseParser, BlogPost


class TigerBeetleParser(BaseParser):
    """Parser for tigerbeetle.com/blog/"""
    
    @property
    def name(self) -> str:
        return "TigerBeetle"
    
    def parse_index(self, html: str, base_url: str) -> list[BlogPost]:
        """
        Parse TigerBeetle blog index.
        
        TigerBeetle format: 
        - Posts are in <a class="post" href="2024-12-19-enum-of-arrays">
        - URLs are relative and contain dates like YYYY-MM-DD-slug
        - Title is in <h2> inside the link
        - Date may also be in <time> tag
        """
        soup = BeautifulSoup(html, "html5lib")
        posts = []
        
        # Find all anchor tags with class="post"
        for link in soup.find_all("a", class_="post", href=True):
            href = link.get("href", "")
            
            # Skip empty hrefs
            if not href:
                continue
            
            # Extract date from href pattern YYYY-MM-DD-slug
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})-", href)
            if not date_match:
                # Also try if the full URL has the pattern
                date_match = re.search(r"/(\d{4}-\d{2}-\d{2})-", href)
            
            date = None
            if date_match:
                try:
                    date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass
            
            # Get title from h2 inside the link, or fallback to link text
            h2 = link.find("h2")
            if h2:
                title = h2.get_text(strip=True)
            else:
                title = link.get_text(strip=True)
            
            if not title or len(title) < 5:
                continue
            
            # Build full URL - href is relative like "2024-12-19-slug"
            # Need to join with base_url which ends with /blog/
            url = urljoin(base_url.rstrip("/") + "/", href)
            
            # Avoid duplicates
            if any(p.url == url for p in posts):
                continue
            
            posts.append(BlogPost(
                title=title,
                url=url,
                date=date,
            ))
        
        return posts
    
    def parse_post(self, html: str, url: str) -> str:
        """Extract article content from a TigerBeetle post."""
        soup = BeautifulSoup(html, "html5lib")
        
        # Try common article containers
        article = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", class_=re.compile(r"(content|post|article|prose)", re.I))
        )
        
        if article:
            # Remove navigation, headers, footers, asides
            for tag in article.find_all(["nav", "header", "footer", "aside"]):
                tag.decompose()
            
            # Remove author info sections
            for tag in article.find_all(class_=re.compile(r"(author|byline|meta)", re.I)):
                tag.decompose()
            
            # Remove the first h1 (title duplication)
            h1 = article.find("h1")
            if h1:
                h1.decompose()
            
            return str(article)
        
        # Fallback: return body content
        body = soup.find("body")
        return str(body) if body else html
    
    def get_blog_title(self, html: str) -> str:
        return "TigerBeetle Engineering Blog"
