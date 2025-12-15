"""Document generator for creating printable PDFs."""

import html
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from weasyprint import HTML, CSS

from eblog2doc.parsers.base import BlogPost


def convert_superscripts_to_html(text: str) -> str:
    """
    Convert Unicode superscript and subscript characters to HTML <sup> and <sub> tags.
    Must be called BEFORE NFKC normalization which flattens these characters.
    """
    # Unicode superscript characters and their normal equivalents
    superscripts = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
        '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
        'ⁿ': 'n', 'ⁱ': 'i',
    }
    
    # Unicode subscript characters and their normal equivalents
    subscripts = {
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
        '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
    }
    
    # Convert consecutive superscript characters to <sup> tags
    result = []
    i = 0
    while i < len(text):
        # Check for superscript run
        if text[i] in superscripts:
            sup_chars = []
            while i < len(text) and text[i] in superscripts:
                sup_chars.append(superscripts[text[i]])
                i += 1
            result.append(f'<sup>{"".join(sup_chars)}</sup>')
        # Check for subscript run
        elif text[i] in subscripts:
            sub_chars = []
            while i < len(text) and text[i] in subscripts:
                sub_chars.append(subscripts[text[i]])
                i += 1
            result.append(f'<sub>{"".join(sub_chars)}</sub>')
        else:
            result.append(text[i])
            i += 1
    
    return ''.join(result)


def normalize_text(text: str) -> str:
    """
    Normalize text to handle encoding issues.
    Fixes mojibake patterns and replaces problematic characters with ASCII equivalents.
    """
    if not text:
        return text
    
    # FIRST: Convert Unicode superscripts/subscripts to HTML before NFKC normalization
    text = convert_superscripts_to_html(text)
    
    # Fix common mojibake patterns (UTF-8 decoded as Latin-1)
    # These are the byte sequences that appear when UTF-8 is misread
    mojibake_fixes = {
        'â€™': "'",      # Right single quote
        'â€˜': "'",      # Left single quote
        'â€œ': '"',      # Left double quote
        'â€': '"',       # Right double quote (partial)
        'â€"': '-',      # Em dash
        'â€"': '-',      # En dash
        'â€¦': '...',    # Ellipsis
        'Ã¢': 'a',       # â misencoded
        'â\x80\x99': "'",  # Another form
        'â\x80\x9c': '"',
        'â\x80\x9d': '"',
        'â\x80\x93': '-',
        'â\x80\x94': '-',
        # Common patterns with replacement chars
        'â□□': "'",      # Visible replacement
        'â\ufffd\ufffd': "'",
    }
    
    for old, new in mojibake_fixes.items():
        text = text.replace(old, new)
    
    # Also fix patterns using regex for more robustness
    # Pattern: â followed by any non-letter chars that look like encoding garbage
    text = re.sub(r'â[\x80-\xbf][\x80-\xbf]', "'", text)
    text = re.sub(r'â[^\w\s]{1,2}', "'", text)
    
    # Normalize unicode to composed form (but superscripts are now HTML tags)
    # We need to be careful not to break the HTML tags we just added
    # So we'll skip NFKC since it would break other things - use NFC instead
    text = unicodedata.normalize('NFC', text)
    
    # Replace common problematic characters
    replacements = {
        '\u2018': "'",   # Left single quote
        '\u2019': "'",   # Right single quote
        '\u201c': '"',   # Left double quote
        '\u201d': '"',   # Right double quote
        '\u2013': '-',   # En dash
        '\u2014': '-',   # Em dash
        '\u2026': '...',  # Ellipsis
        '\u00a0': ' ',   # Non-breaking space
        '\u200b': '',    # Zero-width space
        '\u2022': '*',   # Bullet
        '\u00ab': '"',   # Left guillemet
        '\u00bb': '"',   # Right guillemet
        '\ufffd': '',    # Replacement character
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def clean_html_content(html_content: str) -> str:
    """
    Clean HTML content by removing unwanted sections like:
    - Subscribe forms
    - Related posts / "You might also like"
    - Author bios that duplicate the header
    - Social sharing buttons
    - Newsletter signup
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, "html5lib")
    
    # Remove elements by common class/id patterns for unwanted content
    unwanted_patterns = [
        # Subscribe/newsletter
        r'subscribe',
        r'newsletter',
        r'signup',
        r'sign-up',
        r'email-form',
        r'mailchimp',
        # Related posts / Read more
        r'related',
        r'you-might',
        r'also-like',
        r'recommended',
        r'more-posts',
        r'suggested',
        r'read-more',
        r'readmore',
        r'more-from',
        r'other-posts',
        r'next-posts',
        r'previous-posts',
        # Social/sharing
        r'share',
        r'social',
        r'twitter',
        r'facebook',
        r'linkedin',
        # Author bio (when it's separate from main content)
        r'author-bio',
        r'author-info',
        r'about-author',
        r'post-author',
        r'byline',
        # Comments
        r'comment',
        r'disqus',
        # Navigation
        r'prev-next',
        r'pagination',
        r'nav-post',
        r'post-nav',
        # Interactive elements / Editor UI
        r'editor',
        r'playground',
        r'interactive',
        r'code-runner',
        r'run-button',
        r'try-it',
        r'demo-controls',
        r'toolbar',
        r'action-bar',
        r'query-stats',
        r'execution-stats',
        # CTA / promotional
        r'cta',
        r'call-to-action',
        r'promo',
        r'banner',
        r'waitlist',
    ]
    
    pattern = re.compile('|'.join(unwanted_patterns), re.IGNORECASE)
    
    # Collect elements to remove first (to avoid mutation during iteration)
    elements_to_remove = []
    
    for element in soup.find_all(True):
        if element.parent is None:
            continue  # Already removed
        
        classes = element.get('class', [])
        if isinstance(classes, list):
            class_str = ' '.join(classes)
        else:
            class_str = str(classes) if classes else ''
        
        element_id = element.get('id', '') or ''
        
        if pattern.search(class_str) or pattern.search(element_id):
            elements_to_remove.append(element)
    
    for element in elements_to_remove:
        try:
            element.decompose()
        except Exception:
            pass
    
    # Remove form elements (usually subscribe forms)
    for form in soup.find_all('form'):
        try:
            form.decompose()
        except Exception:
            pass
    
    # Remove iframes (usually embeds we don't want)
    for iframe in soup.find_all('iframe'):
        try:
            iframe.decompose()
        except Exception:
            pass
    
    # Remove button elements (interactive UI)
    for btn in soup.find_all(['button', 'input']):
        try:
            btn.decompose()
        except Exception:
            pass
    
    # Remove elements with onclick or other interactive attributes
    for element in soup.find_all(True, attrs={'onclick': True}):
        try:
            element.decompose()
        except Exception:
            pass
    
    # Remove elements that contain unwanted text patterns
    unwanted_text_patterns = [
        'subscribe', 
        'subscribe to newsletter', 
        'sign up', 
        'you might also like', 
        'read more in the',
        'read more in',
        'view all',
        'close editor',
        'run query',
        'query stats',
        'try it in',
        'sign up for our waitlist',
    ]
    
    for element in soup.find_all(['div', 'section', 'aside', 'p', 'h1', 'h2', 'h3', 'span']):
        if element.parent is None:
            continue
        text = element.get_text(strip=True).lower()
        
        # Remove if text starts with any unwanted pattern
        for pattern_text in unwanted_text_patterns:
            if text.startswith(pattern_text) or text == pattern_text:
                try:
                    element.decompose()
                except Exception:
                    pass
                break
    
    # Remove the first h1 if it exists (avoid title duplication)
    first_h1 = soup.find('h1')
    if first_h1:
        try:
            first_h1.decompose()
        except Exception:
            pass
    
    return str(soup)


# CSS for the generated PDF
PDF_STYLES = """
@page {
    size: A4;
    margin: 2cm;
    
    @top-center {
        content: string(blog-title);
        font-size: 10pt;
        color: #666;
    }
    
    @bottom-center {
        content: counter(page);
        font-size: 10pt;
        color: #666;
    }
}

@page :first {
    @top-center {
        content: none;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333;
    max-width: 100%;
}

h1 {
    string-set: blog-title content();
    font-size: 20pt;
    font-weight: bold;
    color: #1a1a1a;
    margin-bottom: 0.5em;
    text-align: center;
}

h2 {
    font-size: 14pt;
    font-weight: bold;
    color: #2a2a2a;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    color: #3a3a3a;
    margin-top: 1em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}

h4, h5, h6 {
    font-size: 11pt;
    font-weight: bold;
    color: #3a3a3a;
    margin-top: 0.8em;
    margin-bottom: 0.4em;
    page-break-after: avoid;
}

p {
    margin-bottom: 1em;
    text-align: justify;
    orphans: 3;
    widows: 3;
}

a {
    color: #0066cc;
    text-decoration: none;
}

code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    word-break: break-all;
    overflow-wrap: break-word;
}

pre {
    font-family: 'Courier New', Courier, monospace;
    font-size: 8pt;
    background-color: #f5f5f5;
    padding: 1em;
    border-radius: 5px;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-wrap: break-word;
    word-break: break-all;
    page-break-inside: avoid;
    max-width: 100%;
}

pre code {
    background: none;
    padding: 0;
    font-size: 8pt;
    word-break: break-all;
}

img {
    max-width: 100%;
    max-height: 12cm;  /* Limit to roughly half page height */
    width: auto;
    height: auto;
    display: block;
    margin: 1em auto;
    object-fit: contain;
}

blockquote {
    border-left: 3px solid #ddd;
    margin-left: 0;
    padding-left: 1em;
    color: #666;
    font-style: italic;
}

table {
    width: auto;  /* Fit to content, not full width */
    max-width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    page-break-inside: avoid;
    font-size: 9pt;
}

th, td {
    border: 1px solid #ddd;
    padding: 0.3em 0.5em;  /* Reduced padding */
    text-align: left;
    white-space: nowrap;  /* Prevent unnecessary wrapping */
}

/* Allow wrapping for cells with longer content */
td:last-child, th:last-child {
    white-space: normal;
}

th {
    background-color: #f5f5f5;
    font-weight: bold;
}

/* Ensure superscripts render properly */
sup, sub {
    font-size: 0.75em;
    line-height: 0;
    position: relative;
    vertical-align: baseline;
}

sup {
    top: -0.5em;
}

sub {
    bottom: -0.25em;
}

ul, ol {
    margin-bottom: 1em;
    padding-left: 2em;
}

li {
    margin-bottom: 0.3em;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 2em 0;
}

/* Cover page */
.cover {
    text-align: center;
    padding-top: 30%;
    page-break-after: always;
}

.cover h1 {
    font-size: 24pt;
    margin-bottom: 0.5em;
}

.cover .subtitle {
    font-size: 12pt;
    color: #666;
    margin-bottom: 2em;
}

.cover .generated {
    font-size: 11pt;
    color: #888;
}

/* Table of Contents */
.toc {
    page-break-after: always;
}

.toc h2 {
    text-align: center;
    margin-bottom: 1em;
    font-size: 16pt;
}

.toc-list {
    list-style-type: disc;
    padding-left: 2em;
}

.toc-list li {
    margin-bottom: 0.6em;
    line-height: 1.4;
}

.toc-list .title {
    font-weight: normal;
}

.toc-list .date {
    color: #666;
    margin-left: 0.5em;
}

.toc-list a {
    color: inherit;
    text-decoration: none;
}

/* Individual posts */
.post {
    page-break-before: always;
}

.post:first-of-type {
    page-break-before: auto;
}

.post-header {
    margin-bottom: 1.5em;
    border-bottom: 2px solid #333;
    padding-bottom: 0.5em;
}

.post-header h2 {
    margin-top: 0;
    margin-bottom: 0.25em;
    font-size: 16pt;
}

.post-meta {
    color: #666;
    font-size: 10pt;
}

.post-content {
    /* Content from the blog */
    overflow-wrap: break-word;
    word-wrap: break-word;
    max-width: 100%;
}

/* Ensure all elements respect container width */
.post-content * {
    max-width: 100%;
    overflow-wrap: break-word;
}

/* Remove any unwanted elements from scraped content */
.post-content nav,
.post-content .navigation,
.post-content .comments,
.post-content .share-buttons,
.post-content .related-posts,
.post-content .read-more,
.post-content .editor,
.post-content .playground,
.post-content .toolbar,
.post-content .action-bar,
.post-content footer,
.post-content button,
.post-content input,
.post-content form,
.post-content iframe {
    display: none !important;
}
"""


def format_date(date: datetime | None) -> str:
    """Format a date for display, or return 'No date' if None."""
    if date is None:
        return "No date"
    return date.strftime("%B %d, %Y")


def build_html_document(posts: list[BlogPost], blog_title: str) -> str:
    """
    Build an HTML document from blog posts.
    
    Args:
        posts: List of BlogPost objects with content
        blog_title: Title of the blog
        
    Returns:
        Complete HTML document as string
    """
    import html as html_module
    
    # Sort posts by date (newest first)
    sorted_posts = sorted(posts)
    
    # Build TOC entries as bullet list
    toc_entries = []
    for i, post in enumerate(sorted_posts):
        # Normalize and escape the title
        title = normalize_text(post.title)
        title = html_module.escape(title)
        date_str = format_date(post.date)
        
        toc_entries.append(
            f'<li><a href="#post-{i}"><span class="title">{title}</span></a> '
            f'<span class="date">({date_str})</span></li>'
        )
    
    # Build post sections
    post_sections = []
    for i, post in enumerate(sorted_posts):
        # Normalize the title for display
        title = normalize_text(post.title)
        title = html_module.escape(title)
        
        # Clean and normalize content - remove unwanted sections and fix encoding
        content = clean_html_content(post.content_html)
        content = normalize_text(content)
        
        post_sections.append(f'''
        <section class="post" id="post-{i}">
            <div class="post-header">
                <h2>{title}</h2>
                <div class="post-meta">
                    {format_date(post.date)}
                    {f' - {post.author}' if post.author else ''}
                </div>
            </div>
            <div class="post-content">
                {content}
            </div>
        </section>
        ''')
    
    # Generate date
    generated_date = datetime.now().strftime("%B %d, %Y")
    
    # Normalize blog title
    blog_title_safe = html_module.escape(normalize_text(blog_title))
    
    # Build complete HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{blog_title_safe}</title>
</head>
<body>
    <div class="cover">
        <h1>{blog_title_safe}</h1>
        <p class="subtitle">{len(sorted_posts)} articles</p>
        <p class="generated">Generated on {generated_date}</p>
    </div>
    
    <div class="toc">
        <h2>Table of Contents</h2>
        <ul class="toc-list">
            {''.join(toc_entries)}
        </ul>
    </div>
    
    {''.join(post_sections)}
</body>
</html>
'''
    
    return html


def generate_pdf(posts: list[BlogPost], output_path: str, blog_title: str) -> Path:
    """
    Generate a PDF document from blog posts.
    
    Args:
        posts: List of BlogPost objects with content
        output_path: Path to write the PDF
        blog_title: Title of the blog
        
    Returns:
        Path to the generated PDF
    """
    # Build HTML
    html_content = build_html_document(posts, blog_title)
    
    # Convert to PDF
    html = HTML(string=html_content)
    css = CSS(string=PDF_STYLES)
    
    output = Path(output_path)
    html.write_pdf(output, stylesheets=[css])
    
    return output
