"""Base parser interface and data models for blog parsing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BlogPost:
    """Represents a single blog post."""
    
    title: str
    url: str
    date: datetime | None = None
    author: str | None = None
    content_html: str = ""
    
    def __lt__(self, other: "BlogPost") -> bool:
        """Sort by date, newest first. Posts without dates go last."""
        if self.date is None and other.date is None:
            return self.title < other.title
        if self.date is None:
            return False
        if other.date is None:
            return True
        return self.date > other.date  # Reverse chronological


class BaseParser(ABC):
    """Abstract base class for site-specific blog parsers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this parser."""
        pass
    
    @abstractmethod
    def parse_index(self, html: str, base_url: str) -> list[BlogPost]:
        """
        Extract post metadata from the blog index page.
        
        Args:
            html: Raw HTML content of the blog index page
            base_url: Base URL for resolving relative links
            
        Returns:
            List of BlogPost objects with title, url, and date
            (content_html will be empty at this stage)
        """
        pass
    
    @abstractmethod
    def parse_post(self, html: str, url: str) -> str:
        """
        Extract article content from a single post page.
        
        Args:
            html: Raw HTML content of the post page
            url: URL of the post (for reference)
            
        Returns:
            HTML string containing just the article content
        """
        pass
    
    def get_blog_title(self, html: str) -> str:
        """Extract the blog title from the index page. Override if needed."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html5lib")
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()
        return "Engineering Blog"
