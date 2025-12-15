"""Sirupsen blog parser."""

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from eblog2doc.parsers.base import BaseParser, BlogPost


# Month name to number mapping
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class SirupsenParser(BaseParser):
    """Parser for sirupsen.com"""
    
    @property
    def name(self) -> str:
        return "Sirupsen"
    
    def parse_index(self, html: str, base_url: str) -> list[BlogPost]:
        """
        Parse Sirupsen blog index.
        
        Sirupsen format: Simple list with "Title - Mon YYYY" pattern
        Some links are external (YouTube, etc.) - we filter those out.
        """
        soup = BeautifulSoup(html, "html5lib")
        posts = []
        base_domain = urlparse(base_url).netloc
        
        # Find all list items with links
        for li in soup.find_all("li"):
            link = li.find("a", href=True)
            if not link:
                continue
            
            href = link.get("href", "")
            title = link.get_text(strip=True)
            
            if not title or len(title) < 3:
                continue
            
            # Resolve URL
            url = urljoin(base_url, href)
            parsed_url = urlparse(url)
            
            # Only include sirupsen.com posts (skip external links)
            if base_domain not in parsed_url.netloc:
                continue
            
            # Skip the homepage itself
            if parsed_url.path in ["/", ""]:
                continue
            
            # Try to extract date from the list item text (after the link)
            li_text = li.get_text()
            date = self._extract_date(li_text)
            
            # Avoid duplicates
            if any(p.url == url for p in posts):
                continue
            
            posts.append(BlogPost(
                title=title,
                url=url,
                date=date,
            ))
        
        return posts
    
    def _extract_date(self, text: str) -> datetime | None:
        """Extract date from text like 'Title Dec 2016' or 'Title - Mar 2016'."""
        # Pattern: Month Year (e.g., "Dec 2016", "Mar 2016")
        match = re.search(r"\b([A-Za-z]{3})\s+(\d{4})\b", text)
        if match:
            month_str = match.group(1).lower()
            year = int(match.group(2))
            month = MONTH_MAP.get(month_str)
            if month:
                return datetime(year, month, 1)
        return None
    
    def parse_post(self, html: str, url: str) -> str:
        """Extract article content from a Sirupsen post."""
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
            
            # Remove author info sections
            for tag in article.find_all(class_=re.compile(r"(author|byline|meta)", re.I)):
                tag.decompose()
            
            # Remove subscribe/newsletter elements
            for tag in article.find_all(class_=re.compile(r"(subscribe|newsletter|signup)", re.I)):
                tag.decompose()
            
            # Remove "you might also like" sections
            for tag in article.find_all(class_=re.compile(r"(related|also-like|recommended)", re.I)):
                tag.decompose()
            
            # Remove forms (usually subscribe forms)
            for form in article.find_all("form"):
                form.decompose()
            
            # Remove the first h1 (title duplication)
            h1 = article.find("h1")
            if h1:
                h1.decompose()
            
            return str(article)
        
        # Fallback: return body content
        body = soup.find("body")
        return str(body) if body else html
    
    def get_blog_title(self, html: str) -> str:
        return "Simon Eskildsen's Blog"
