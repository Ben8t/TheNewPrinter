"""
Readability-based fallback content extractor for new-printer.

This module provides backup content extraction functionality using
the readability-lxml library when Trafilatura fails to extract content.
"""

import re
import time
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import requests
from readability import Document

from ..models import Article, ExtractionResult
from ..config import get_config


class ReadabilityFallback:
    """
    Fallback content extractor using readability-lxml library.
    
    This extractor is used when Trafilatura fails to extract content.
    Readability is good at extracting the main content area but may
    be less precise than Trafilatura.
    """
    
    def __init__(self, timeout: Optional[int] = None, user_agent: Optional[str] = None):
        """
        Initialize the Readability fallback extractor.
        
        Args:
            timeout: Request timeout in seconds (uses config default if None)
            user_agent: User agent string (uses config default if None)
        """
        config = get_config()
        extractor_config = config.get_extractor_config()
        
        self.timeout = timeout or extractor_config.get('timeout', 30)
        self.user_agent = user_agent or extractor_config.get('user_agent', 'new-printer/1.0.0')
        
        # Configure session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def extract(self, url: str) -> ExtractionResult:
        """
        Extract article content from a URL using readability as fallback.
        
        Args:
            url: URL to extract content from
            
        Returns:
            ExtractionResult containing the extracted article or error information
        """
        start_time = time.time()
        
        try:
            # Validate URL
            if not self._is_valid_url(url):
                return ExtractionResult(
                    success=False,
                    error_message=f"Invalid URL: {url}",
                    extractor_used="readability"
                )
            
            # Download the page
            html_content = self._download_page(url)
            if not html_content:
                return ExtractionResult(
                    success=False,
                    error_message="Failed to download page content",
                    extractor_used="readability",
                    extraction_time_seconds=time.time() - start_time
                )
            
            # Extract content using Readability
            article = self._extract_from_html(html_content, url)
            if not article:
                return ExtractionResult(
                    success=False,
                    error_message="Failed to extract article content",
                    extractor_used="readability",
                    extraction_time_seconds=time.time() - start_time
                )
            
            return ExtractionResult(
                article=article,
                success=True,
                extractor_used="readability",
                extraction_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Extraction failed: {str(e)}",
                extractor_used="readability",
                extraction_time_seconds=time.time() - start_time
            )
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate if the URL is properly formatted.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _download_page(self, url: str) -> Optional[str]:
        """
        Download HTML content from URL.
        
        Args:
            url: URL to download
            
        Returns:
            HTML content as string, or None if download failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return None
            
            return response.text
            
        except requests.exceptions.RequestException as e:
            print(f"Download failed for {url}: {e}")
            return None
    
    def _extract_from_html(self, html_content: str, url: str) -> Optional[Article]:
        """
        Extract article data from HTML content using Readability.
        
        Args:
            html_content: Raw HTML content
            url: Original URL (for context and image resolution)
            
        Returns:
            Article object or None if extraction failed
        """
        try:
            # Use readability to extract the main content
            doc = Document(html_content)
            
            # Get the cleaned content
            article_html = doc.summary()
            if not article_html or not article_html.strip():
                return None
            
            # Extract title from readability
            title = doc.title()
            if not title or len(title.strip()) < 3:
                # Fallback to manual title extraction
                title = self._extract_title_manual(html_content)
            
            if not title:
                return None
            
            # Convert HTML content to plain text
            content = self._html_to_text(article_html)
            if not content or len(content.strip()) < 100:  # Minimum content length
                return None
            
            # Extract additional metadata from original HTML
            author = self._extract_author(html_content)
            date = self._extract_date(html_content)
            description = self._extract_description(html_content)
            language = self._extract_language(html_content)
            images = self._extract_images(article_html, url)
            
            return Article(
                title=self._clean_text(title),
                content=self._clean_content(content),
                author=author,
                date=date,
                images=images,
                url=url,
                description=description,
                language=language
            )
            
        except Exception as e:
            print(f"Readability extraction failed: {e}")
            return None
    
    def _extract_title_manual(self, html_content: str) -> Optional[str]:
        """Extract title manually from HTML when readability fails."""
        title_patterns = [
            r'<title[^>]*>([^<]+)</title>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']title["\']\s+content=["\']([^"\']+)["\']'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                title = self._clean_text(match.group(1))
                if len(title) > 5:  # Reasonable title length
                    return title
        
        return None
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text.
        
        Args:
            html_content: HTML content from readability
            
        Returns:
            Plain text content
        """
        # Remove script and style elements
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common HTML elements to text equivalents
        # Headers
        html_content = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n\n\1\n\n', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Paragraphs
        html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Line breaks
        html_content = re.sub(r'<br[^>]*/?>', '\n', html_content, flags=re.IGNORECASE)
        
        # Lists
        html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'</?[uo]l[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        
        # Blockquotes
        html_content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\n> \1\n', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Strong/bold
        html_content = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Emphasis/italic
        html_content = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Links
        html_content = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'\2 (\1)', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove remaining HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        import html
        html_content = html.unescape(html_content)
        
        return html_content
    
    def _extract_author(self, html_content: str) -> Optional[str]:
        """Extract article author from HTML."""
        author_patterns = [
            r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']article:author["\']\s+content=["\']([^"\']+)["\']',
            r'<span[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</span>',
            r'<div[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</div>',
            r'<p[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</p>'
        ]
        
        for pattern in author_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                author = self._clean_text(match.group(1))
                if len(author) > 2 and len(author) < 100:  # Reasonable author name length
                    return author
        
        return None
    
    def _extract_date(self, html_content: str) -> Optional[datetime]:
        """Extract publication date from HTML."""
        date_patterns = [
            r'<time[^>]+datetime=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']date["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']pubdate["\']\s+content=["\']([^"\']+)["\']'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try parsing common date formats
                    for fmt in [
                        '%Y-%m-%dT%H:%M:%S%z',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d',
                        '%Y/%m/%d',
                        '%d/%m/%Y',
                        '%B %d, %Y',
                        '%b %d, %Y'
                    ]:
                        try:
                            # Handle timezone info
                            clean_date = date_str.replace('Z', '+00:00')
                            if len(clean_date) > len(fmt) - 2:  # Rough length check
                                return datetime.strptime(clean_date[:len(fmt)], fmt)
                        except ValueError:
                            continue
                except Exception:
                    continue
        
        return None
    
    def _extract_description(self, html_content: str) -> Optional[str]:
        """Extract article description from HTML."""
        desc_patterns = [
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']twitter:description["\']\s+content=["\']([^"\']+)["\']'
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                description = self._clean_text(match.group(1))
                if len(description) > 10:  # Reasonable description length
                    return description
        
        return None
    
    def _extract_language(self, html_content: str) -> Optional[str]:
        """Extract article language from HTML."""
        lang_patterns = [
            r'<html[^>]+lang=["\']([^"\']+)["\']',
            r'<meta\s+http-equiv=["\']content-language["\']\s+content=["\']([^"\']+)["\']'
        ]
        
        for pattern in lang_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_images(self, html_content: str, base_url: str) -> List[str]:
        """Extract image URLs from the extracted content."""
        images = []
        
        # Find all img tags in the cleaned content
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        img_matches = re.findall(img_pattern, html_content, re.IGNORECASE)
        
        for img_url in img_matches:
            # Skip small images, icons, and ads
            if any(skip in img_url.lower() for skip in ['icon', 'logo', 'avatar', 'ad-', 'ads/', 'tracking']):
                continue
            
            # Convert relative URLs to absolute
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = urljoin(base_url, img_url)
            elif not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(base_url, img_url)
            
            if img_url not in images:
                images.append(img_url)
        
        return images[:10]  # Limit to 10 images
    
    def _clean_content(self, content: str) -> str:
        """
        Clean and format extracted content.
        
        Args:
            content: Raw extracted content
            
        Returns:
            Cleaned content
        """
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Remove common unwanted patterns
        unwanted_patterns = [
            r'Sign up for our newsletter.*$',
            r'Subscribe to.*$',
            r'Follow us on.*$',
            r'Share this article.*$',
            r'Related articles.*$',
            r'You might also like.*$',
            r'Advertisement.*$',
            r'Continue reading.*$'
        ]
        
        for pattern in unwanted_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        # Clean up markdown-style formatting
        content = re.sub(r'\*\*\s*\*\*', '', content)  # Empty bold
        content = re.sub(r'\*\s*\*', '', content)      # Empty italic
        
        return content.strip()
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and HTML entities."""
        if not text:
            return ""
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text 