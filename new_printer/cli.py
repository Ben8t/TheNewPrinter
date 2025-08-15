#!/usr/bin/env python3
"""
CLI interface for New Printer - Transform web articles into print-ready PDFs.

This module provides the main command-line interface using Click framework,
supporting single article conversion, batch processing, and web server mode.
"""

import sys
import os
from pathlib import Path
from typing import Optional, List
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from .extractors.extractor_factory import ExtractorFactory
from .processors.pandoc_runner import PandocRunner
from .config import get_config
from .models import ConversionOptions, ExtractionResult

console = Console()


def validate_url(ctx, param, value):
    """Validate URL parameter."""
    if not value:
        return value
    
    from .extractors.url_validator import URLValidator
    validator = URLValidator()
    
    try:
        normalized_url, error_message = validator.validate_url(value)
        if error_message:
            raise click.BadParameter(f"Invalid URL: {error_message}")
        return normalized_url
    except Exception as e:
        raise click.BadParameter(f"Invalid URL: {e}")


def validate_output_path(ctx, param, value):
    """Validate output path parameter."""
    if not value:
        return value
        
    path = Path(value)
    
    # Check if parent directory exists or can be created
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise click.BadParameter(f"Cannot create output directory: {e}")
    
    # Check if we can write to the location
    if path.exists() and not os.access(path, os.W_OK):
        raise click.BadParameter(f"Cannot write to output file: {value}")
    
    return str(path)


@click.group(help="Convert web articles to print-ready PDFs with classic magazine styling")
@click.version_option(version="1.0.0", prog_name="new-printer")
@click.option('--config', '-c', 'config_file', 
              type=click.Path(exists=True, readable=True),
              help="Path to custom configuration file")
@click.pass_context
def main(ctx, config_file):
    """Main CLI entry point."""
    ctx.ensure_object(dict)
    
    # Load configuration
    config = get_config()
    if config_file:
        config.load_user_config(config_file)
    
    ctx.obj['config'] = config


@main.command("convert")
@click.argument("url", callback=validate_url)
@click.option("-o", "--output", "output_file", 
              callback=validate_output_path,
              help="Output PDF filename (auto-generated if not specified)")
@click.option("-c", "--columns", type=click.IntRange(1, 3), 
              help="Number of columns (1-3)")
@click.option("-s", "--font-size", "font_size", 
              type=click.Choice(['9pt', '10pt', '11pt', '12pt', '14pt']),
              help="Font size for the document")
@click.option("-t", "--template", 
              type=click.Choice(['article', 'magazine']),
              help="LaTeX template to use")
@click.option("--no-images", "include_images", is_flag=True, flag_value=False, 
              default=True, help="Exclude images from PDF")
@click.option("-m", "--margins", 
              help="Page margins (e.g., '2cm' or '1in')")
@click.option("--font-family", 
              type=click.Choice(['times', 'helvetica', 'palatino']),
              help="Font family for the document")
@click.option("--timeout", type=int, 
              help="Timeout for PDF generation in seconds")
@click.option("-v", "--verbose", is_flag=True, 
              help="Enable verbose output")
@click.pass_context
def convert_cmd(ctx, url: str, output_file: Optional[str], columns: Optional[int], 
                font_size: Optional[str], template: Optional[str], 
                include_images: bool, margins: Optional[str], 
                font_family: Optional[str], timeout: Optional[int], verbose: bool):
    """Convert a single URL to PDF."""
    
    config = ctx.obj['config']
    
    # Build conversion options from CLI args and config defaults
    options = ConversionOptions(
        output=output_file,
        columns=columns or config.get('default.columns', 2),
        font_size=font_size or config.get('default.font_size', '11pt'),
        template=template or config.get('default.template', 'article'),
        include_images=include_images,
        margins=margins or config.get('default.margins', '2cm'),
        fontfamily=font_family or config.get('default.font_family', 'times'),
        timeout=timeout or config.get('pandoc.timeout', 120)
    )
    
    if verbose:
        rprint(f"[blue]Converting:[/blue] {url}")
        rprint(f"[blue]Options:[/blue] {options}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        # Extract article content
        extract_task = progress.add_task("Extracting article content...", total=None)
        
        try:
            factory = ExtractorFactory(config)
            result: ExtractionResult = factory.extract(url)
            
            if not result.success:
                console.print(f"[red]Extraction failed:[/red] {result.error_message}")
                sys.exit(1)
                
            article = result.article
            progress.update(extract_task, description=f"✅ Extracted: {article.title[:50]}...")
            
        except Exception as e:
            console.print(f"[red]Error during extraction:[/red] {e}")
            if verbose:
                console.print_exception()
            sys.exit(1)
        
        # Generate PDF
        convert_task = progress.add_task("Generating PDF...", total=None)
        
        try:
            runner = PandocRunner()  # Fixed: removed config parameter
            
            # Auto-generate output filename if not provided
            if not options.output:
                safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')
                options.output = f"{safe_title}.pdf"
            
            pdf_path = runner.convert_to_pdf(article, options)
            progress.update(convert_task, description=f"✅ PDF generated: {pdf_path}")
            
        except Exception as e:
            console.print(f"[red]Error during PDF generation:[/red] {e}")
            if verbose:
                console.print_exception()
            sys.exit(1)
    
    # Success message
    console.print(f"\n[green]✅ Successfully converted article to PDF![/green]")
    console.print(f"[blue]Title:[/blue] {article.title}")
    console.print(f"[blue]Author:[/blue] {article.author or 'Unknown'}")
    console.print(f"[blue]Word count:[/blue] {article.word_count:,}")
    console.print(f"[blue]Output:[/blue] {pdf_path}")
    
    if article.images and include_images:
        console.print(f"[blue]Images:[/blue] {len(article.images)} included")


@main.command("batch")
@click.argument("urls_file", type=click.File('r'))
@click.option("-d", "--output-dir", "output_dir", 
              type=click.Path(file_okay=False, writable=True),
              default="./pdfs", show_default=True,
              help="Directory to save PDF files")
@click.option("-c", "--columns", type=click.IntRange(1, 3),
              help="Number of columns (1-3)")
@click.option("-s", "--font-size", "font_size",
              type=click.Choice(['9pt', '10pt', '11pt', '12pt', '14pt']),
              help="Font size for documents")
@click.option("-t", "--template",
              type=click.Choice(['article', 'magazine']),
              help="LaTeX template to use")
@click.option("--no-images", "include_images", is_flag=True, flag_value=False,
              default=True, help="Exclude images from PDFs")
@click.option("--continue-on-error", is_flag=True,
              help="Continue processing other URLs if one fails")
@click.option("-v", "--verbose", is_flag=True,
              help="Enable verbose output")
@click.pass_context
def batch_cmd(ctx, urls_file, output_dir: str, columns: Optional[int],
              font_size: Optional[str], template: Optional[str],
              include_images: bool, continue_on_error: bool, verbose: bool):
    """Process multiple URLs from a file."""
    
    config = ctx.obj['config']
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Read URLs from file
    urls = []
    for line_num, line in enumerate(urls_file, 1):
        line = line.strip()
        if line and not line.startswith('#'):
            try:
                from .extractors.url_validator import URLValidator
                validator = URLValidator()
                validated_url = validator.validate_url(line)
                urls.append((line_num, validated_url))
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Invalid URL at line {line_num}: {e}")
                if not continue_on_error:
                    sys.exit(1)
    
    if not urls:
        console.print("[red]No valid URLs found in file[/red]")
        sys.exit(1)
    
    console.print(f"[blue]Processing {len(urls)} URLs...[/blue]")
    
    # Build base options
    base_options = ConversionOptions(
        columns=columns or config.get('default.columns', 2),
        font_size=font_size or config.get('default.font_size', '11pt'),
        template=template or config.get('default.template', 'article'),
        include_images=include_images,
        margins=config.get('default.margins', '2cm'),
        fontfamily=config.get('default.font_family', 'times'),
        timeout=config.get('pandoc.timeout', 120)
    )
    
    # Process URLs
    factory = ExtractorFactory(config)
    runner = PandocRunner()  # Fixed: removed config parameter
    
    success_count = 0
    failed_urls = []
    
    with Progress(console=console) as progress:
        main_task = progress.add_task("Processing URLs...", total=len(urls))
        
        for line_num, url in urls:
            progress.update(main_task, description=f"Processing line {line_num}...")
            
            try:
                # Extract article
                result = factory.extract(url)
                if not result.success:
                    raise Exception(f"Extraction failed: {result.error_message}")
                
                article = result.article
                
                # Generate safe filename
                safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_title = safe_title.replace(' ', '_')
                output_file = output_path / f"{safe_title}.pdf"
                
                # Handle duplicate filenames
                counter = 1
                while output_file.exists():
                    stem = safe_title
                    output_file = output_path / f"{stem}_{counter}.pdf"
                    counter += 1
                
                # Convert to PDF
                options = base_options.copy()
                options.output = str(output_file)
                
                runner.convert_to_pdf(article, options)
                success_count += 1
                
                if verbose:
                    console.print(f"[green]✅[/green] Line {line_num}: {article.title[:50]}...")
                
            except Exception as e:
                failed_urls.append((line_num, url, str(e)))
                if verbose:
                    console.print(f"[red]❌[/red] Line {line_num}: {e}")
                
                if not continue_on_error:
                    console.print(f"[red]Stopping due to error at line {line_num}[/red]")
                    break
            
            progress.advance(main_task)
    
    # Summary
    console.print(f"\n[green]✅ Successfully processed: {success_count}/{len(urls)} URLs[/green]")
    
    if failed_urls:
        console.print(f"[red]❌ Failed: {len(failed_urls)} URLs[/red]")
        if verbose:
            table = Table(title="Failed URLs")
            table.add_column("Line", style="cyan")
            table.add_column("URL", style="blue")
            table.add_column("Error", style="red")
            
            for line_num, url, error in failed_urls[:10]:  # Show first 10 errors
                table.add_row(str(line_num), url[:50] + "..." if len(url) > 50 else url, error[:50] + "...")
            
            console.print(table)
            
            if len(failed_urls) > 10:
                console.print(f"[yellow]... and {len(failed_urls) - 10} more errors[/yellow]")


@main.command("serve")
@click.option("-p", "--port", type=int, default=3000, show_default=True,
              help="Port to run the web server on")
@click.option("--host", default="127.0.0.1", show_default=True,
              help="Host to bind the web server to")
@click.option("--reload", is_flag=True,
              help="Enable auto-reload for development")
@click.option("-v", "--verbose", is_flag=True,
              help="Enable verbose output")
@click.pass_context
def serve_cmd(ctx, port: int, host: str, reload: bool, verbose: bool):
    """Start the optional web interface."""
    
    try:
        import uvicorn
        from .web_ui.server import create_app
    except ImportError as e:
        console.print(f"[red]Web UI dependencies not available:[/red] {e}")
        console.print("[yellow]Install web dependencies with:[/yellow] pip install 'new-printer[web]'")
        sys.exit(1)
    
    config = ctx.obj['config']
    
    console.print(f"[blue]Starting web server on[/blue] http://{host}:{port}")
    console.print("[blue]Press Ctrl+C to stop[/blue]")
    
    # Create the FastAPI app with configuration
    app = create_app(config)
    
    # Configure logging level
    log_level = "debug" if verbose else "info"
    
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level,
            reload=reload
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Server error:[/red] {e}")
        sys.exit(1)


@main.command("info")
@click.option("--check-deps", is_flag=True,
              help="Check system dependencies")
@click.option("--templates", is_flag=True,
              help="List available templates")
@click.pass_context
def info_cmd(ctx, check_deps: bool, templates: bool):
    """Show system information and configuration."""
    
    config = ctx.obj['config']
    
    if check_deps:
        console.print("[blue]Checking system dependencies...[/blue]\n")
        
        # Check Python version
        console.print(f"[green]✅[/green] Python: {sys.version.split()[0]}")
        
        # Check Pandoc
        try:
            runner = PandocRunner()  # Fixed: removed config parameter
            pandoc_info = runner.get_pandoc_info()
            console.print(f"[green]✅[/green] Pandoc: {pandoc_info.get('version', 'Unknown')}")
        except Exception as e:
            console.print(f"[red]❌[/red] Pandoc: {e}")
        
        # Check LaTeX
        import subprocess
        try:
            result = subprocess.run(['xelatex', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                console.print(f"[green]✅[/green] XeLaTeX: {version_line}")
            else:
                console.print("[red]❌[/red] XeLaTeX: Not found or not working")
        except Exception:
            console.print("[red]❌[/red] XeLaTeX: Not found")
        
        # Check optional dependencies
        optional_deps = [
            ('trafilatura', 'Content extraction'),
            ('readability', 'Fallback extraction'),
            ('PIL', 'Image processing'),
            ('fastapi', 'Web interface'),
            ('uvicorn', 'Web server')
        ]
        
        console.print("\n[blue]Optional dependencies:[/blue]")
        for dep_name, description in optional_deps:
            try:
                __import__(dep_name)
                console.print(f"[green]✅[/green] {dep_name}: Available ({description})")
            except ImportError:
                console.print(f"[yellow]⚠️[/yellow] {dep_name}: Not available ({description})")
    
    if templates:
        console.print("[blue]Available templates:[/blue]\n")
        
        try:
            runner = PandocRunner()  # Fixed: removed config parameter
            available_templates = runner.get_available_templates()
            
            if available_templates:
                table = Table(title="LaTeX Templates")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="blue")
                table.add_column("Path", style="dim")
                
                for template_name, template_path in available_templates.items():
                    description = {
                        'article': 'Clean article layout with professional typography',
                        'magazine': 'New Yorker-style magazine layout'
                    }.get(template_name, 'Custom template')
                    
                    table.add_row(template_name, description, str(template_path))
                
                console.print(table)
            else:
                console.print("[yellow]No templates found[/yellow]")
                
        except Exception as e:
            console.print(f"[red]Error checking templates:[/red] {e}")
    
    if not check_deps and not templates:
        # Default info display
        console.print("[blue]New Printer v1.0.0[/blue]")
        console.print("Transform web articles into print-ready PDFs\n")
        
        console.print("[blue]Configuration:[/blue]")
        console.print(f"  Default columns: {config.get('default.columns', 2)}")
        console.print(f"  Default font size: {config.get('default.font_size', '11pt')}")
        console.print(f"  Default template: {config.get('default.template', 'article')}")
        console.print(f"  Include images: {config.get('default.include_images', True)}")
        
        console.print("\n[blue]Usage examples:[/blue]")
        console.print("  new-printer convert https://example.com/article")
        console.print("  new-printer batch urls.txt -d ./pdfs")
        console.print("  new-printer serve --port 8080")
        console.print("  new-printer info --check-deps --templates")


if __name__ == "__main__":
    main() 