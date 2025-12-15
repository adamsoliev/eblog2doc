"""CedarDB blog parser."""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from eblog2doc.parsers.base import BaseParser, BlogPost


class CedarDBParser(BaseParser):
    """Parser for cedardb.com/blog/"""
    
    @property
    def name(self) -> str:
        return "CedarDB"
    
    def parse_index(self, html: str, base_url: str) -> list[BlogPost]:
        """
        Parse CedarDB blog index.
        
        CedarDB format: Links contain date inline like "[31/10/2025Title...]"
        The date appears before the title in the link text.
        The title might be followed by a description - we only want the title.
        """
        soup = BeautifulSoup(html, "html5lib")
        posts = []
        
        # Find all links that point to /blog/ subpages
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            
            # Only process links to blog posts (not the main /blog/ page)
            if "/blog/" not in href or href.rstrip("/").endswith("/blog"):
                continue
            
            # Skip newsletter, subscription links, etc.
            if any(skip in href.lower() for skip in ["subscribe", "newsletter", "#"]):
                continue
            
            # Try to get title from h3 inside the link first (cleaner extraction)
            h3_tag = link.find("h3")
            if h3_tag:
                title = h3_tag.get_text(strip=True)
            else:
                # Fallback to full text extraction
                text = link.get_text(strip=True)
                if not text:
                    continue
                
                # Try to extract date from the beginning (DD/MM/YYYY format)
                date_match = re.match(r"(\d{2}/\d{2}/\d{4})", text)
                if date_match:
                    text = text[len(date_match.group(1)):].strip()
                
                title = text
            
            if not title or len(title) < 5:
                continue
            
            # Try to extract date from anywhere in the link or adjacent elements
            full_text = link.get_text(strip=True)
            date = None
            date_match = re.search(r"(\d{2}/\d{2}/\d{4})", full_text)
            if date_match:
                try:
                    date = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                except ValueError:
                    pass
            
            url = urljoin(base_url, href)
            
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
        """Extract article content from a CedarDB post."""
        soup = BeautifulSoup(html, "html5lib")
        
        # Try common article containers
        article = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", class_=re.compile(r"(content|post|article)", re.I))
        )
        
        if article:
            # Remove navigation, headers, footers, asides
            for tag in article.find_all(["nav", "header", "footer", "aside"]):
                tag.decompose()
            
            # Remove author info sections (they duplicate what we show in header)
            for tag in article.find_all(class_=re.compile(r"(author|byline|meta|date)", re.I)):
                tag.decompose()
            
            # Remove CedarDB-specific related posts (listing__item links)
            for tag in article.find_all(class_=re.compile(r"listing", re.I)):
                tag.decompose()
            
            # Remove any "View All" or other button links
            for tag in article.find_all(class_=re.compile(r"button", re.I)):
                tag.decompose()
            
            # Remove any sections that look like "Start Now" CTAs
            for tag in article.find_all(class_=re.compile(r"(cta|start-now|signup|waitlist)", re.I)):
                tag.decompose()
            
            # Remove sections containing links to other blog posts
            # (these often appear as link cards at the end)
            for section in article.find_all(["section", "div"]):
                # Check if this section mainly contains links to /blog/ pages
                links = section.find_all("a", href=re.compile(r"/blog/"))
                if len(links) >= 3:  # Likely a related posts grid
                    section.decompose()
            
            # Remove the first h1 (it's the title, which we already show)
            h1 = article.find("h1")
            if h1:
                h1.decompose()
            
            return str(article)
        
        # Fallback: return body content
        body = soup.find("body")
        return str(body) if body else html
    
    def get_blog_title(self, html: str) -> str:
        return "CedarDB Engineering Blog"
