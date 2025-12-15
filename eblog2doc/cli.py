"""CLI interface for eblog2doc using Click and Rich."""

import sys
from pathlib import Path
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from eblog2doc import scraper
from eblog2doc.scraper import ScraperError
from eblog2doc import document


console = Console()


def get_default_output_name(url: str) -> str:
    """Generate a default output filename from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_")
    return f"{domain}_blog.pdf"


@click.command()
@click.argument("url")
@click.option(
    "--output", "-o",
    default=None,
    help="Output PDF filename. Defaults to {domain}_blog.pdf"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show verbose output"
)
def main(url: str, output: str | None, verbose: bool) -> None:
    """
    Convert an engineering blog to a printable PDF.
    
    URL should be the main blog index page, e.g., https://cedardb.com/blog/
    
    Examples:
    
        eblog2doc https://cedardb.com/blog/
        
        eblog2doc https://tigerbeetle.com/blog/ -o tiger.pdf
    """
    # Determine output path
    if output is None:
        output = get_default_output_name(url)
    
    output_path = Path(output)
    
    console.print()
    console.print(Panel.fit(
        f"[bold blue]eblog2doc[/bold blue] - Blog to PDF Converter\n"
        f"[dim]Converting: {url}[/dim]",
        border_style="blue"
    ))
    console.print()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            
            # Step 1: Discover posts
            discover_task = progress.add_task(
                "[cyan]Discovering blog posts...",
                total=None
            )
            
            posts, parser, blog_title = scraper.discover_posts(url)
            
            if not posts:
                progress.stop()
                console.print("[red]❌ No blog posts found at this URL[/red]")
                console.print(f"[dim]Parser used: {parser.name}[/dim]")
                sys.exit(1)
            
            progress.remove_task(discover_task)
            console.print(f"[green]✓[/green] Found [bold]{len(posts)}[/bold] posts using [dim]{parser.name}[/dim] parser")
            
            # Step 2: Fetch each post's content
            fetch_task = progress.add_task(
                "[cyan]Fetching post content...",
                total=len(posts)
            )
            
            failed_posts = []
            for i, post in enumerate(posts):
                try:
                    if verbose:
                        progress.console.print(f"  [dim]Fetching: {post.title[:50]}...[/dim]")
                    scraper.fetch_post_content(post, parser)
                except ScraperError as e:
                    failed_posts.append((post, str(e)))
                    if verbose:
                        progress.console.print(f"  [yellow]⚠ Failed: {post.title[:50]}[/yellow]")
                
                progress.update(fetch_task, completed=i + 1)
            
            progress.remove_task(fetch_task)
            
            if failed_posts:
                console.print(f"[yellow]⚠[/yellow] {len(failed_posts)} posts failed to fetch")
            
            successful_posts = [p for p in posts if p.content_html]
            console.print(f"[green]✓[/green] Fetched [bold]{len(successful_posts)}[/bold] posts successfully")
            
            if not successful_posts:
                console.print("[red]❌ No posts were successfully fetched[/red]")
                sys.exit(1)
            
            # Step 3: Generate PDF
            pdf_task = progress.add_task(
                "[cyan]Generating PDF...",
                total=None
            )
            
            document.generate_pdf(successful_posts, str(output_path), blog_title)
            
            progress.remove_task(pdf_task)
            console.print(f"[green]✓[/green] Generated PDF: [bold]{output_path}[/bold]")
        
        # Final summary
        console.print()
        console.print(Panel.fit(
            f"[green]✅ Success![/green]\n\n"
            f"📄 Output: [bold]{output_path.absolute()}[/bold]\n"
            f"📝 Posts: {len(successful_posts)}\n"
            f"📚 Blog: {blog_title}",
            border_style="green"
        ))
        
    except ScraperError as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
