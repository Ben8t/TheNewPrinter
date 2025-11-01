"""
Markdown conversion for new-printer.

This module provides HTML to Markdown conversion functionality with
advanced formatting, structure preservation, and cleanup for optimal
PDF generation via Pandoc.
"""

import re
import html
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, urlparse
import markdownify
from markdownify import MarkdownConverter as BaseMarkdownConverter

from ..models import Article
from ..config import get_config


class MarkdownConverter(BaseMarkdownConverter):
    """
    Enhanced Markdown converter for article content.
    
    Extends markdownify with custom formatting, structure preservation,
    and optimizations for print-ready PDF generation.
    """
    
    def __init__(self):
        """Initialize the Markdown converter."""
        self.config = get_config()
        
        # Initialize base converter with our custom settings
        super().__init__(
            heading_style='atx',  # Use # headings
            bullets='-',          # Use - for bullets
            strip=['script', 'style', 'form', 'input', 'button', 'nav', 'aside', 'header', 'footer']
        )
        
        # Custom formatting options
        self.preserve_structure = True
        self.clean_links = True
        self.process_images = True
        self.handle_tables = True
        self.fix_typography = True
        
        # Patterns for cleaning up converted markdown
        self.cleanup_patterns = [
            # Remove excessive whitespace
            (r'\n\s*\n\s*\n+', '\n\n'),
            # Fix heading spacing
            (r'\n(#{1,6})\s*([^\n]+)\n([^\n#])', r'\n\1 \2\n\n\3'),
            # Fix list spacing (escaped dash at end to avoid range interpretation)
            (r'\n(\s*)[-*+]\s*([^\n]+)\n([^\n\s*+\-])', r'\n\1- \2\n\n\3'),
            # Clean up bold/italic formatting
            (r'\*\*\s*\*\*', ''),
            (r'\*\s*\*', ''),
            # Fix link formatting
            (r'\[\s*\]', ''),
            (r'\(\s*\)', ''),
        ]
    
    def convert_article_content(self, content: str, base_url: Optional[str] = None) -> str:
        """
        Convert article HTML content to clean Markdown.
        
        Args:
            content: HTML content to convert
            base_url: Base URL for resolving relative links
            
        Returns:
            Clean Markdown content
        """
        if not content:
            return ""
        
        # Pre-process HTML for better conversion
        processed_html = self._preprocess_html(content, base_url)
        
        # Convert to Markdown using markdownify
        markdown = self.convert(processed_html)
        
        # Post-process the Markdown
        clean_markdown = self._postprocess_markdown(markdown)
        
        return clean_markdown
    
    def convert_article(self, article: Article) -> Article:
        """
        Convert an entire article's content to Markdown.
        
        Args:
            article: Article with HTML content
            
        Returns:
            Article with Markdown content
        """
        if not article or not article.content:
            return article
        
        # Convert content to Markdown
        markdown_content = self.convert_article_content(article.content, article.url)
        article.content = markdown_content
        
        # Also convert description if present
        if article.description:
            markdown_description = self.convert_article_content(article.description, article.url)
            article.description = markdown_description
        
        return article
    
    def _preprocess_html(self, html_content: str, base_url: Optional[str] = None) -> str:
        """
        Pre-process HTML before conversion to improve Markdown output.
        
        Args:
            html_content: Raw HTML content
            base_url: Base URL for link resolution
            
        Returns:
            Processed HTML content
        """
        # Decode HTML entities first
        content = html.unescape(html_content)
        
        # Remove problematic elements that don't convert well
        unwanted_elements = [
            r'<script[^>]*>.*?</script>',
            r'<style[^>]*>.*?</style>',
            r'<noscript[^>]*>.*?</noscript>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<embed[^>]*>.*?</embed>',
            r'<object[^>]*>.*?</object>',
            r'<form[^>]*>.*?</form>',
            r'<button[^>]*>.*?</button>',
            r'<input[^>]*>',
            r'<textarea[^>]*>.*?</textarea>',
            r'<select[^>]*>.*?</select>',
        ]
        
        for pattern in unwanted_elements:
            content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Fix image tags for better Markdown conversion
        if self.process_images:
            content = self._preprocess_images(content, base_url)
        
        # Fix link tags
        if self.clean_links:
            content = self._preprocess_links(content, base_url)
        
        # Improve table structure
        if self.handle_tables:
            content = self._preprocess_tables(content)
        
        # Fix typography elements
        if self.fix_typography:
            content = self._preprocess_typography(content)
        
        # Clean up common problematic patterns
        content = self._clean_html_patterns(content)
        
        return content
    
    def _preprocess_images(self, content: str, base_url: Optional[str] = None) -> str:
        """Preprocess image tags for better Markdown conversion."""
        def replace_img(match):
            img_tag = match.group(0)
            
            # Extract src
            src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not src_match:
                return ''
            
            src = src_match.group(1)
            
            # Resolve relative URLs
            if base_url and not src.startswith(('http://', 'https://', '//')):
                src = urljoin(base_url, src)
            
            # Extract alt text
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
            alt = alt_match.group(1) if alt_match else ''
            
            # Extract title
            title_match = re.search(r'title=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
            title = title_match.group(1) if title_match else ''
            
            # Create clean img tag
            if title and title != alt:
                return f'<img src="{src}" alt="{alt}" title="{title}">'
            else:
                return f'<img src="{src}" alt="{alt}">'
        
        # Replace all img tags
        content = re.sub(r'<img[^>]*>', replace_img, content, flags=re.IGNORECASE)
        
        return content
    
    def _preprocess_links(self, content: str, base_url: Optional[str] = None) -> str:
        """Preprocess link tags for better Markdown conversion."""
        def replace_link(match):
            full_tag = match.group(0)
            href = match.group(1)
            link_text = match.group(2)
            
            # Skip empty links
            if not href or not link_text.strip():
                return link_text
            
            # Resolve relative URLs
            if base_url and not href.startswith(('http://', 'https://', '//', 'mailto:', 'tel:')):
                href = urljoin(base_url, href)
            
            # Clean up link text
            link_text = re.sub(r'<[^>]+>', '', link_text)  # Remove nested tags
            link_text = link_text.strip()
            
            if not link_text:
                return ''
            
            return f'<a href="{href}">{link_text}</a>'
        
        # Replace all links
        content = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', 
                        replace_link, content, flags=re.DOTALL | re.IGNORECASE)
        
        return content
    
    def _preprocess_tables(self, content: str) -> str:
        """Preprocess table elements for better Markdown conversion."""
        # Ensure tables have proper structure
        # Add thead if missing but th elements exist
        def fix_table_structure(match):
            table_content = match.group(1)
            
            # If there are th elements not in thead, wrap them
            if '<th' in table_content and '<thead' not in table_content:
                # Find first row with th elements
                first_row_match = re.search(r'<tr[^>]*>.*?<th.*?</tr>', table_content, re.DOTALL | re.IGNORECASE)
                if first_row_match:
                    first_row = first_row_match.group(0)
                    rest_content = table_content.replace(first_row, '', 1)
                    table_content = f'<thead>{first_row}</thead><tbody>{rest_content}</tbody>'
            
            return f'<table>{table_content}</table>'
        
        content = re.sub(r'<table[^>]*>(.*?)</table>', fix_table_structure, 
                        content, flags=re.DOTALL | re.IGNORECASE)
        
        return content
    
    def _preprocess_typography(self, content: str) -> str:
        """Fix typography elements for better Markdown conversion."""
        # Convert various quote types to standard quotes
        typography_fixes = [
            # Smart quotes
            (r'[\u201c\u201d]', '"'),
            (r'[\u2018\u2019]', "'"),
            # Em and en dashes
            (r'\u2014', ' — '),
            (r'\u2013', ' – '),
            # Ellipsis
            (r'\u2026', '...'),
            # Non-breaking spaces
            (r'\u00a0', ' '),
        ]
        
        for pattern, replacement in typography_fixes:
            content = re.sub(pattern, replacement, content)
        
        return content
    
    def _clean_html_patterns(self, content: str) -> str:
        """Clean up problematic HTML patterns."""
        # Remove empty paragraphs and divs
        content = re.sub(r'<p[^>]*>\s*</p>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<div[^>]*>\s*</div>', '', content, flags=re.IGNORECASE)
        
        # Remove spans that only contain whitespace
        content = re.sub(r'<span[^>]*>\s*</span>', '', content, flags=re.IGNORECASE)
        
        # Clean up nested formatting
        content = re.sub(r'<strong[^>]*><strong[^>]*>(.*?)</strong></strong>', r'<strong>\1</strong>', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r'<em[^>]*><em[^>]*>(.*?)</em></em>', r'<em>\1</em>', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        return content
    
    def _postprocess_markdown(self, markdown: str) -> str:
        """
        Post-process converted Markdown for better formatting.
        
        Args:
            markdown: Raw converted Markdown
            
        Returns:
            Clean, well-formatted Markdown
        """
        if not markdown:
            return ""
        
        # Apply cleanup patterns
        for pattern, replacement in self.cleanup_patterns:
            markdown = re.sub(pattern, replacement, markdown, flags=re.MULTILINE)
        
        # Fix heading formatting
        markdown = self._fix_headings(markdown)
        
        # Fix list formatting
        markdown = self._fix_lists(markdown)
        
        # Fix blockquote formatting
        markdown = self._fix_blockquotes(markdown)
        
        # Fix code block formatting
        markdown = self._fix_code_blocks(markdown)
        
        # Fix table formatting
        markdown = self._fix_tables(markdown)
        
        # Fix link formatting
        markdown = self._fix_links(markdown)
        
        # Final cleanup
        markdown = self._final_markdown_cleanup(markdown)
        
        return markdown.strip()
    
    def _fix_headings(self, markdown: str) -> str:
        """Fix heading formatting in Markdown."""
        # Ensure headings have proper spacing
        markdown = re.sub(r'\n(#{1,6})\s*([^\n]+)\n(?!\n)', r'\n\1 \2\n\n', markdown)
        
        # Fix heading levels (prevent too deep nesting)
        lines = markdown.split('\n')
        fixed_lines = []
        
        for line in lines:
            if line.startswith('#'):
                # Count heading level
                level = len(re.match(r'#+', line).group())
                if level > 6:
                    # Cap at h6
                    line = '######' + line[level:]
                elif level == 0:
                    # Fix malformed heading
                    line = '# ' + line.lstrip('#').strip()
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_lists(self, markdown: str) -> str:
        """Fix list formatting in Markdown."""
        # Standardize bullet points
        markdown = re.sub(r'^(\s*)[\*\+]\s+', r'\1- ', markdown, flags=re.MULTILINE)
        
        # Fix list spacing
        lines = markdown.split('\n')
        fixed_lines = []
        in_list = False
        
        for i, line in enumerate(lines):
            is_list_item = re.match(r'^\s*[-*+]\s+', line) or re.match(r'^\s*\d+\.\s+', line)
            
            if is_list_item:
                if not in_list and i > 0 and fixed_lines[-1].strip():
                    fixed_lines.append('')  # Add blank line before list
                in_list = True
            else:
                if in_list and line.strip() and not line.startswith('  '):
                    in_list = False
                    if line.strip():
                        fixed_lines.append('')  # Add blank line after list
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_blockquotes(self, markdown: str) -> str:
        """Fix blockquote formatting in Markdown."""
        # Ensure blockquotes have proper spacing
        lines = markdown.split('\n')
        fixed_lines = []
        in_blockquote = False
        
        for i, line in enumerate(lines):
            is_blockquote = line.startswith('>')
            
            if is_blockquote:
                if not in_blockquote and i > 0 and fixed_lines[-1].strip():
                    fixed_lines.append('')  # Add blank line before blockquote
                in_blockquote = True
            else:
                if in_blockquote and line.strip():
                    in_blockquote = False
                    fixed_lines.append('')  # Add blank line after blockquote
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_code_blocks(self, markdown: str) -> str:
        """Fix code block formatting in Markdown."""
        # Ensure code blocks have proper spacing
        markdown = re.sub(r'\n(```[^\n]*\n.*?\n```)\n(?!\n)', r'\n\n\1\n\n', markdown, flags=re.DOTALL)
        
        return markdown
    
    def _fix_tables(self, markdown: str) -> str:
        """Fix table formatting in Markdown."""
        # Find tables and ensure they have proper spacing
        table_pattern = r'(\|.*\|\n(?:\|.*\|\n)*)'
        
        def fix_table(match):
            table = match.group(1)
            return f'\n{table}\n'
        
        markdown = re.sub(table_pattern, fix_table, markdown, flags=re.MULTILINE)
        
        return markdown
    
    def _fix_links(self, markdown: str) -> str:
        """Fix link formatting in Markdown."""
        # Remove empty links
        markdown = re.sub(r'\[\s*\]\(\s*\)', '', markdown)
        
        # Fix malformed links
        markdown = re.sub(r'\[([^\]]+)\]\(\s*\)', r'\1', markdown)  # Remove empty URLs
        markdown = re.sub(r'\[\s*\]\(([^)]+)\)', r'<\1>', markdown)  # Fix empty text
        
        return markdown
    
    def _final_markdown_cleanup(self, markdown: str) -> str:
        """Final cleanup pass for Markdown."""
        # Remove excessive whitespace
        markdown = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown)
        
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in markdown.split('\n')]
        markdown = '\n'.join(lines)
        
        # Remove empty lines at start and end
        markdown = markdown.strip()
        
        return markdown
    
    # Override specific conversion methods for better control
    def convert_h1(self, el, text, *args, **kwargs):
        """Convert h1 with proper spacing."""
        return f'\n\n# {text}\n\n'
    
    def convert_h2(self, el, text, *args, **kwargs):
        """Convert h2 with proper spacing."""
        return f'\n\n## {text}\n\n'
    
    def convert_h3(self, el, text, *args, **kwargs):
        """Convert h3 with proper spacing."""
        return f'\n\n### {text}\n\n'
    
    def convert_h4(self, el, text, *args, **kwargs):
        """Convert h4 with proper spacing."""
        return f'\n\n#### {text}\n\n'
    
    def convert_h5(self, el, text, *args, **kwargs):
        """Convert h5 with proper spacing."""
        return f'\n\n##### {text}\n\n'
    
    def convert_h6(self, el, text, *args, **kwargs):
        """Convert h6 with proper spacing."""
        return f'\n\n###### {text}\n\n'
    
    def convert_p(self, el, text, *args, **kwargs):
        """Convert paragraphs with proper spacing."""
        if not text.strip():
            return ''
        return f'\n\n{text}\n\n'
    
    def convert_figcaption(self, el, text, *args, **kwargs):
        """Convert figcaption as italic text."""
        if not text.strip():
            return ''
        return f'\n\n*{text}*\n\n'


# Global instance
_markdown_converter = None


def get_markdown_converter() -> MarkdownConverter:
    """Get the global Markdown converter instance."""
    global _markdown_converter
    if _markdown_converter is None:
        _markdown_converter = MarkdownConverter()
    return _markdown_converter


def convert_html_to_markdown(html_content: str, base_url: Optional[str] = None) -> str:
    """
    Convenience function to convert HTML to Markdown.
    
    Args:
        html_content: HTML content to convert
        base_url: Base URL for resolving relative links
        
    Returns:
        Clean Markdown content
    """
    converter = get_markdown_converter()
    return converter.convert_article_content(html_content, base_url)


def convert_article_to_markdown(article: Article) -> Article:
    """
    Convenience function to convert an article's content to Markdown.
    
    Args:
        article: Article with HTML content
        
    Returns:
        Article with Markdown content
    """
    converter = get_markdown_converter()
    return converter.convert_article(article) 