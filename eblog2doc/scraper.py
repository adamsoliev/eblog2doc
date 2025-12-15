"""Scraper module for fetching blog content."""

from urllib.parse import urlparse

import requests

from eblog2doc.parsers import (
    BaseParser,
    BlogPost,
    CedarDBParser,
    TigerBeetleParser,
    SirupsenParser,
    GenericParser,
)


# Registry of domain -> parser class mappings
PARSER_REGISTRY: dict[str, type[BaseParser]] = {
    "cedardb.com": CedarDBParser,
    "tigerbeetle.com": TigerBeetleParser,
    "sirupsen.com": SirupsenParser,
}

# Default request headers
DEFAULT_HEADERS = {
    "User-Agent": "eblog2doc/0.1.0 (Blog to PDF converter)",
    "Accept": "text/html,application/xhtml+xml",
}

# Request timeout in seconds
REQUEST_TIMEOUT = 30


class ScraperError(Exception):
    """Exception raised when scraping fails."""
    pass


def get_parser(url: str) -> BaseParser:
    """
    Auto-detect and return the appropriate parser for a given blog URL.
    
    Args:
        url: Blog URL to parse
        
    Returns:
        Parser instance appropriate for the domain
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    
    parser_class = PARSER_REGISTRY.get(domain, GenericParser)
    return parser_class()


def fetch_url(url: str) -> str:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content as string
        
    Raises:
        ScraperError: If the request fails
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise ScraperError(f"Failed to fetch {url}: {e}") from e


def discover_posts(url: str, parser: BaseParser | None = None) -> tuple[list[BlogPost], BaseParser, str]:
    """
    Discover all blog posts from the index page, following pagination.
    
    Args:
        url: Blog index URL
        parser: Optional parser instance (auto-detected if not provided)
        
    Returns:
        Tuple of (list of BlogPost, parser used, blog title)
        
    Raises:
        ScraperError: If fetching or parsing fails
    """
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    import re
    
    if parser is None:
        parser = get_parser(url)
    
    all_posts = []
    visited_urls = set()
    pages_to_visit = [url]
    blog_title = None
    max_pages = 50  # Safety limit
    pages_visited = 0
    base_url = url  # Keep the original base URL for parsing
    
    while pages_to_visit and pages_visited < max_pages:
        current_url = pages_to_visit.pop(0)
        
        # Skip if already visited
        if current_url in visited_urls:
            continue
        visited_urls.add(current_url)
        pages_visited += 1
        
        try:
            html = fetch_url(current_url)
        except ScraperError:
            continue
        
        # Get blog title from first page
        if blog_title is None:
            blog_title = parser.get_blog_title(html)
        
        # Parse posts from this page
        # IMPORTANT: Use base_url, not current_url for consistent path matching
        posts = parser.parse_index(html, base_url)
        
        # Add new posts (avoiding duplicates by URL)
        existing_urls = {p.url for p in all_posts}
        for post in posts:
            if post.url not in existing_urls:
                all_posts.append(post)
                existing_urls.add(post.url)
        
        # Find pagination links
        soup = BeautifulSoup(html, 'html5lib')
        next_page_url = _find_pagination_link(soup, current_url)
        
        if next_page_url and next_page_url not in visited_urls:
            pages_to_visit.append(next_page_url)
    
    return all_posts, parser, blog_title or "Blog"


def _find_pagination_link(soup, current_url: str) -> str | None:
    """
    Find the 'next page' or 'older posts' pagination link.
    
    Args:
        soup: BeautifulSoup object for the page
        current_url: Current page URL for resolving relative links
        
    Returns:
        URL of the next page, or None if not found
    """
    from urllib.parse import urljoin, urlparse
    import re
    
    page_pattern = re.compile(r'/page/(\d+)/?$')
    
    # Get current page number from URL
    current_page = 1
    match = page_pattern.search(current_url)
    if match:
        current_page = int(match.group(1))
    
    # Look for "Older Posts" link specifically (most reliable for forward pagination)
    for link in soup.find_all('a', href=True):
        text = link.get_text(strip=True).lower()
        href = link.get('href', '')
        
        # Match "Older Posts" or similar text
        if re.search(r'older\s*posts?', text, re.IGNORECASE):
            return urljoin(current_url, href)
    
    # Fallback: Find the highest page number that's greater than current
    highest_page = current_page
    highest_url = None
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        match = page_pattern.search(href)
        if match:
            page_num = int(match.group(1))
            if page_num > highest_page:
                highest_page = page_num
                highest_url = urljoin(current_url, href)
    
    if highest_url:
        return highest_url
    
    # Look for other common 'next page' text patterns
    next_patterns = [
        r'^next\s*page\s*→?$', 
        r'^next\s*→$',
        r'^more\s*posts?\\s*→?$',
        r'^load\\s*more\s*→?$',
    ]
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        text = link.get_text(strip=True).lower()
        
        if len(text) < 4:
            continue
        
        for pattern in next_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return urljoin(current_url, href)
    
    return None


def fetch_post_content(post: BlogPost, parser: BaseParser) -> None:
    """
    Fetch and parse content for a single blog post.
    
    Modifies the post in-place, setting content_html.
    
    Args:
        post: BlogPost to fetch content for
        parser: Parser to use for extracting content
        
    Raises:
        ScraperError: If fetching or parsing fails
    """
    html = fetch_url(post.url)
    post.content_html = parser.parse_post(html, post.url)
