"""Generic fallback parser for unknown blogs."""

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from eblog2doc.parsers.base import BaseParser, BlogPost


# Common date patterns to try
DATE_PATTERNS = [
    (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),           # 2024-12-15
    (r"(\d{2}/\d{2}/\d{4})", "%d/%m/%Y"),           # 15/12/2024
    (r"(\d{2}/\d{2}/\d{4})", "%m/%d/%Y"),           # 12/15/2024
    (r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", "%B %d, %Y"),    # December 15, 2024
    (r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", "%B %d %Y"),     # December 15 2024
    (r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})", "%d %B %Y"),       # 15 December 2024
    (r"(\d{1,2}\s+[A-Z][a-z]+,?\s+\d{4})", "%d %B, %Y"),    # 15 December, 2024
    # Short month names
    (r"([A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4})", "%b %d, %Y"),  # Dec 15, 2024
    (r"([A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4})", "%b %d %Y"),   # Dec 15 2024
    (r"(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})", "%d %b %Y"),     # 15 Dec 2024
]


class GenericParser(BaseParser):
    """Generic fallback parser that tries to auto-detect blog structure."""
    
    @property
    def name(self) -> str:
        return "Generic"
    
    def parse_index(self, html: str, base_url: str) -> list[BlogPost]:
        """
        Parse a generic blog index page.
        
        Attempts to find blog post links by looking for common patterns.
        """
        soup = BeautifulSoup(html, "html5lib")
        posts = []
        base_domain = urlparse(base_url).netloc
        base_path = urlparse(base_url).path.rstrip("/")
        
        # Find all links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            
            if not title or len(title) < 10:
                continue
            
            # Resolve URL
            url = urljoin(base_url, href)
            parsed_url = urlparse(url)
            
            # Only include same-domain links
            if base_domain not in parsed_url.netloc:
                continue
            
            # Must be under the base path (if specified)
            if base_path and not parsed_url.path.startswith(base_path):
                continue
            
            # Skip the index page itself
            if parsed_url.path.rstrip("/") == base_path:
                continue
            
            # Skip common non-post patterns
            if any(skip in parsed_url.path.lower() for skip in [
                "/tag/", "/tags/", "/category/", "/author/", "/page/",
                "/search", "/about", "/contact", "/subscribe",
                ".xml", ".rss", ".json"
            ]):
                continue
            
            # Try to extract date from surrounding context more thoroughly
            date = self._find_date_near_link(link) or self._extract_date_from_url(url)
            
            # Avoid duplicates
            if any(p.url == url for p in posts):
                continue
            
            posts.append(BlogPost(
                title=title,
                url=url,
                date=date,
            ))
        
        return posts
    
    def _find_date_near_link(self, link) -> datetime | None:
        """
        Look for dates near the link by traversing up the DOM tree.
        
        Common patterns:
        1. Date as text node immediately after the link
        2. Date in a sibling element of the link's parent 
        3. Date in a sibling element of ancestor containers (article, div, li)
        """
        # Strategy: walk up the tree and at each level, search siblings for dates
        current = link
        levels_checked = 0
        max_levels = 5
        
        while current and levels_checked < max_levels:
            # Check siblings of current element
            date = self._search_siblings_for_date(current)
            if date:
                return date
            
            # Move up to parent
            current = current.parent
            levels_checked += 1
            
            # Also check the current container's text (might have date inline)
            if current and hasattr(current, 'get_text'):
                # Skip very large containers (body, html)
                if current.name in ['body', 'html', 'main']:
                    break
                    
                text = current.get_text(separator=' ')
                # Only check if container text is reasonably sized
                if len(text) < 500:
                    date = self._extract_date(text)
                    if date:
                        return date
        
        return None
    
    def _search_siblings_for_date(self, element) -> datetime | None:
        """Search next and previous siblings of an element for dates."""
        # Check next siblings first (dates often come after titles)
        sibling_count = 0
        for sibling in element.next_siblings:
            if sibling_count > 5:
                break
            sibling_count += 1
            
            if hasattr(sibling, 'get_text'):
                text = sibling.get_text()
            else:
                text = str(sibling).strip()
            
            if not text or len(text) > 200:  # Skip empty or very long text
                continue
            
            date = self._extract_date(text)
            if date:
                return date
        
        # Check previous siblings
        sibling_count = 0
        for sibling in element.previous_siblings:
            if sibling_count > 3:
                break
            sibling_count += 1
            
            if hasattr(sibling, 'get_text'):
                text = sibling.get_text()
            else:
                text = str(sibling).strip()
            
            if not text or len(text) > 200:
                continue
            
            date = self._extract_date(text)
            if date:
                return date
        
        return None
    
    
    def _extract_date(self, text: str) -> datetime | None:
        """Try various date patterns to extract a date from text."""
        if not text:
            return None
        
        for pattern, date_format in DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                # Clean up the date string (remove extra commas/spaces)
                date_str = re.sub(r'\s+', ' ', date_str).strip()
                date_str = date_str.replace(', ', ' ').replace(',', '')
                
                try:
                    # Try with the exact format first
                    return datetime.strptime(date_str, date_format.replace(', ', ' ').replace(',', ''))
                except ValueError:
                    pass
                
                try:
                    return datetime.strptime(match.group(1), date_format)
                except ValueError:
                    continue
        return None
    
    def _extract_date_from_url(self, url: str) -> datetime | None:
        """Try to extract date from URL path."""
        # Common patterns: /2024/12/15/..., /2024-12-15-...
        patterns = [
            r"/(\d{4})/(\d{2})/(\d{2})/",
            r"/(\d{4})-(\d{2})-(\d{2})-",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                try:
                    return datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3))
                    )
                except ValueError:
                    continue
        return None
    
    def parse_post(self, html: str, url: str) -> str:
        """Extract article content using common patterns."""
        soup = BeautifulSoup(html, "html5lib")
        
        # Try common article containers in order of preference
        selectors = [
            ("article", {}),
            ("main", {}),
            ("div", {"class": re.compile(r"post-content|article-content|entry-content", re.I)}),
            ("div", {"class": re.compile(r"content|post|article", re.I)}),
            ("div", {"id": re.compile(r"content|post|article", re.I)}),
        ]
        
        for tag, attrs in selectors:
            article = soup.find(tag, attrs) if attrs else soup.find(tag)
            if article:
                # Remove navigation, headers, footers
                for remove_tag in article.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                    remove_tag.decompose()
                return str(article)
        
        # Fallback: return body content
        body = soup.find("body")
        if body:
            for remove_tag in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                remove_tag.decompose()
            return str(body)
        
        return html
