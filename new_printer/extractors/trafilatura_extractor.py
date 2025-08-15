"""
Trafilatura-based content extractor for new-printer.

This module provides the primary content extraction functionality using
the Trafilatura library, which is excellent at extracting clean content
from web articles.
"""

import re
import time
from datetime import datetime
from typing import Optional, List
from urllib.parse import urljoin, urlparse
import requests
import trafilatura
from trafilatura.settings import use_config

from ..models import Article, ExtractionResult
from ..config import get_config


class TrafilaturaExtractor:
    """
    Primary content extractor using Trafilatura library.
    
    Trafilatura is excellent at extracting clean article content
    from web pages while preserving the text structure.
    """
    
    def __init__(self, timeout: Optional[int] = None, user_agent: Optional[str] = None):
        """
        Initialize the Trafilatura extractor.
        
        Args:
            timeout: Request timeout in seconds (uses config default if None)
            user_agent: User agent string (uses config default if None)
        """
        config = get_config()
        extractor_config = config.get_extractor_config()
        
        self.timeout = timeout or extractor_config.get('timeout', 30)
        self.user_agent = user_agent or extractor_config.get('user_agent', 'new-printer/1.0.0')
        
        # Configure Trafilatura
        self.trafilatura_config = use_config()
        self.trafilatura_config.set('DEFAULT', 'EXTRACTION_TIMEOUT', str(self.timeout))
        
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
        Extract article content from a URL.
        
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
                    extractor_used="trafilatura"
                )
            
            # Download the page
            html_content = self._download_page(url)
            if not html_content:
                return ExtractionResult(
                    success=False,
                    error_message="Failed to download page content",
                    extractor_used="trafilatura",
                    extraction_time_seconds=time.time() - start_time
                )
            
            # Extract content using Trafilatura
            article = self._extract_from_html(html_content, url)
            if not article:
                return ExtractionResult(
                    success=False,
                    error_message="Failed to extract article content",
                    extractor_used="trafilatura",
                    extraction_time_seconds=time.time() - start_time
                )
            
            return ExtractionResult(
                article=article,
                success=True,
                extractor_used="trafilatura",
                extraction_time_seconds=time.time() - start_time
            )
            
        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Extraction failed: {str(e)}",
                extractor_used="trafilatura",
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
        Extract article data from HTML content using Trafilatura.
        
        Args:
            html_content: Raw HTML content
            url: Original URL (for context and image resolution)
            
        Returns:
            Article object or None if extraction failed
        """
        try:
            # Extract main content
            extracted_content = trafilatura.extract(
                html_content,
                config=self.trafilatura_config,
                include_comments=False,
                include_tables=True,
                include_formatting=True,
                output_format='txt'  # We'll process markdown ourselves
            )
            
            if not extracted_content or not extracted_content.strip():
                return None
            
            # Extract metadata
            raw_metadata = trafilatura.extract_metadata(html_content)
            
            # Convert metadata to dictionary if it's not already
            if hasattr(raw_metadata, '__dict__'):
                # If it's an object, try to convert to dict
                metadata = vars(raw_metadata) if raw_metadata else {}
            elif isinstance(raw_metadata, dict):
                metadata = raw_metadata
            else:
                metadata = {}
            
            # Extract title
            title = self._extract_title(html_content, metadata)
            if not title:
                return None
            
            # Extract author
            author = self._extract_author(metadata)
            
            # Extract date
            date = self._extract_date(metadata, html_content)
            
            # Extract images
            images = self._extract_images(html_content, url)
            
            # Extract description
            description = self._extract_description(metadata, html_content)
            
            # Extract language
            language = self._extract_language(metadata, html_content)
            
            # Clean and format content
            cleaned_content = self._clean_content(extracted_content)
            
            return Article(
                title=title,
                content=cleaned_content,
                author=author,
                date=date,
                images=images,
                url=url,
                description=description,
                language=language
            )
            
        except Exception as e:
            print(f"Content extraction failed: {e}")
            return None
    
    def _extract_title(self, html_content: str, metadata: dict) -> Optional[str]:
        """Extract article title."""
        # Try metadata first
        if metadata and isinstance(metadata, dict) and metadata.get('title'):
            return self._clean_text(metadata['title'])
        
        # Try common title patterns
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
    
    def _extract_author(self, metadata: dict) -> Optional[str]:
        """Extract article author."""
        if metadata and isinstance(metadata, dict) and metadata.get('author'):
            return self._clean_text(metadata['author'])
        return None
    
    def _extract_date(self, metadata: dict, html_content: str) -> Optional[datetime]:
        """Extract publication date."""
        # Try metadata first
        if metadata and isinstance(metadata, dict) and metadata.get('date'):
            try:
                return datetime.fromisoformat(metadata['date'].replace('Z', '+00:00'))
            except ValueError:
                pass
        
        # Try common date patterns in HTML
        date_patterns = [
            r'<time[^>]+datetime=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']date["\']\s+content=["\']([^"\']+)["\']'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try parsing common date formats
                    for fmt in [
                        '%Y-%m-%dT%H:%M:%S%z',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d',
                        '%Y/%m/%d',
                        '%d/%m/%Y'
                    ]:
                        try:
                            return datetime.strptime(date_str[:19], fmt[:len(date_str)])
                        except ValueError:
                            continue
                except Exception:
                    continue
        
        return None
    
    def _extract_images(self, html_content: str, base_url: str) -> List[str]:
        """Extract image URLs from the article."""
        images = []
        
        # Find all img tags
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
    
    def _extract_description(self, metadata: dict, html_content: str) -> Optional[str]:
        """Extract article description."""
        # Try metadata first
        if metadata and isinstance(metadata, dict) and metadata.get('description'):
            return self._clean_text(metadata['description'])
        
        # Try meta description
        desc_pattern = r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']'
        match = re.search(desc_pattern, html_content, re.IGNORECASE)
        if match:
            return self._clean_text(match.group(1))
        
        return None
    
    def _extract_language(self, metadata: dict, html_content: str) -> Optional[str]:
        """Extract article language."""
        # Try metadata first
        if metadata and isinstance(metadata, dict) and metadata.get('language'):
            return metadata['language']
        
        # Try html lang attribute
        lang_pattern = r'<html[^>]+lang=["\']([^"\']+)["\']'
        match = re.search(lang_pattern, html_content, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
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
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Remove common footer/header patterns
        unwanted_patterns = [
            r'Sign up for our newsletter.*$',
            r'Subscribe to.*$',
            r'Follow us on.*$',
            r'Share this article.*$',
            r'Related articles.*$',
            r'You might also like.*$'
        ]
        
        for pattern in unwanted_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
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