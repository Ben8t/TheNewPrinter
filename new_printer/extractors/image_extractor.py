"""
Image extraction and cataloging for new-printer.

This module provides comprehensive image extraction, validation, and
cataloging functionality for article images.
"""

import re
import os
import hashlib
import mimetypes
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
from pathlib import Path
import requests
from requests.exceptions import RequestException
from dataclasses import dataclass

from ..models import Article
from ..config import get_config


@dataclass
class ImageInfo:
    """Information about an extracted image."""
    url: str
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    is_valid: bool = True
    error_message: Optional[str] = None
    local_path: Optional[str] = None


class ImageExtractor:
    """
    Comprehensive image extractor for articles.
    
    Extracts, validates, and catalogs images from article content
    with support for filtering and quality assessment.
    """
    
    def __init__(self):
        """Initialize the image extractor."""
        self.config = get_config()
        self.extractor_config = self.config.get_extractor_config()
        
        # Image validation settings
        self.min_width = 100
        self.min_height = 100
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.supported_formats = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/webp', 'image/svg+xml', 'image/bmp'
        }
        
        # Patterns to identify likely article images vs. UI elements
        self.ui_image_patterns = [
            r'icon', r'logo', r'avatar', r'profile', r'thumbnail',
            r'button', r'arrow', r'social', r'share', r'like',
            r'comment', r'tracking', r'pixel', r'beacon',
            r'ad[-_]', r'ads/', r'advertisement', r'promo',
            r'header', r'footer', r'nav', r'menu', r'sidebar'
        ]
        
        # Common image file extensions
        self.image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'
        }
        
        # Session for downloading images
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.extractor_config.get('user_agent', 'new-printer/1.0.0'),
            'Accept': 'image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def extract_images_from_html(self, html_content: str, base_url: str) -> List[ImageInfo]:
        """
        Extract images from HTML content.
        
        Args:
            html_content: HTML content to extract images from
            base_url: Base URL for resolving relative image URLs
            
        Returns:
            List of ImageInfo objects
        """
        images = []
        
        # Find all img tags with various attributes
        img_pattern = r'<img[^>]*?(?:src=["\']([^"\']+)["\'])[^>]*?(?:alt=["\']([^"\']*)["\'])?[^>]*?(?:width=["\']?(\d+)["\']?)?[^>]*?(?:height=["\']?(\d+)["\']?)?[^>]*?>'
        
        for match in re.finditer(img_pattern, html_content, re.IGNORECASE | re.DOTALL):
            src = match.group(1)
            alt = match.group(2) if match.group(2) else None
            width = int(match.group(3)) if match.group(3) else None
            height = int(match.group(4)) if match.group(4) else None
            
            if src:
                # Resolve relative URLs
                image_url = self._resolve_url(src, base_url)
                
                # Skip invalid URLs
                if not image_url:
                    continue
                
                # Check if this looks like a UI element
                if self._is_likely_ui_image(image_url, alt):
                    continue
                
                # Create ImageInfo object
                image_info = ImageInfo(
                    url=image_url,
                    alt_text=alt,
                    width=width,
                    height=height
                )
                
                # Look for captions near the image
                caption = self._extract_image_caption(html_content, src)
                if caption:
                    image_info.caption = caption
                
                images.append(image_info)
        
        # Also check for images in figure tags
        figure_images = self._extract_figure_images(html_content, base_url)
        images.extend(figure_images)
        
        # Remove duplicates and limit count
        unique_images = self._deduplicate_images(images)
        
        return unique_images[:15]  # Limit to 15 images
    
    def extract_images_from_article(self, article: Article) -> List[ImageInfo]:
        """
        Extract and catalog images from an article.
        
        Args:
            article: Article object to extract images from
            
        Returns:
            List of validated ImageInfo objects
        """
        if not article or not article.url:
            return []
        
        # Start with images already found during extraction
        existing_images = article.images if article.images else []
        
        image_infos = []
        for img_url in existing_images:
            image_info = ImageInfo(url=img_url)
            image_infos.append(image_info)
        
        # Validate and enhance image information
        validated_images = []
        for image_info in image_infos:
            enhanced_info = self._validate_and_enhance_image(image_info)
            if enhanced_info and enhanced_info.is_valid:
                validated_images.append(enhanced_info)
        
        return validated_images
    
    def _resolve_url(self, image_url: str, base_url: str) -> Optional[str]:
        """
        Resolve relative image URLs to absolute URLs.
        
        Args:
            image_url: Image URL (may be relative)
            base_url: Base URL for resolution
            
        Returns:
            Absolute URL or None if invalid
        """
        if not image_url:
            return None
        
        try:
            # Handle protocol-relative URLs
            if image_url.startswith('//'):
                parsed_base = urlparse(base_url)
                return f"{parsed_base.scheme}:{image_url}"
            
            # Handle absolute URLs
            if image_url.startswith(('http://', 'https://')):
                return image_url
            
            # Handle relative URLs
            return urljoin(base_url, image_url)
            
        except Exception:
            return None
    
    def _is_likely_ui_image(self, image_url: str, alt_text: Optional[str] = None) -> bool:
        """
        Check if an image is likely a UI element rather than article content.
        
        Args:
            image_url: URL of the image
            alt_text: Alt text of the image
            
        Returns:
            True if likely a UI element
        """
        # Check URL patterns
        url_lower = image_url.lower()
        for pattern in self.ui_image_patterns:
            if re.search(pattern, url_lower):
                return True
        
        # Check alt text patterns
        if alt_text:
            alt_lower = alt_text.lower()
            for pattern in self.ui_image_patterns:
                if re.search(pattern, alt_lower):
                    return True
        
        # Check for very small images (likely icons)
        if any(size_indicator in url_lower for size_indicator in ['16x16', '32x32', '24x24', '48x48']):
            return True
        
        # Check file extension
        parsed_url = urlparse(image_url)
        path = parsed_url.path.lower()
        if not any(path.endswith(ext) for ext in self.image_extensions):
            # If no clear image extension, might be a tracking pixel
            return True
        
        return False
    
    def _extract_image_caption(self, html_content: str, image_src: str) -> Optional[str]:
        """
        Extract caption text for an image.
        
        Args:
            html_content: HTML content containing the image
            image_src: Source URL of the image
            
        Returns:
            Caption text if found
        """
        # Escape special regex characters in image_src
        escaped_src = re.escape(image_src)
        
        # Look for captions in common patterns
        caption_patterns = [
            # Figure with figcaption
            rf'<figure[^>]*>.*?<img[^>]*src=["\'][^"\']*{escaped_src}[^"\']*["\'][^>]*>.*?<figcaption[^>]*>(.*?)</figcaption>.*?</figure>',
            
            # Image followed by caption paragraph
            rf'<img[^>]*src=["\'][^"\']*{escaped_src}[^"\']*["\'][^>]*>.*?<p[^>]*class=["\'][^"\']*caption[^"\']*["\'][^>]*>(.*?)</p>',
            
            # Image with title attribute
            rf'<img[^>]*src=["\'][^"\']*{escaped_src}[^"\']*["\'][^>]*title=["\']([^"\']+)["\'][^>]*>',
        ]
        
        for pattern in caption_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if match:
                caption = match.group(1).strip()
                # Clean up caption
                caption = re.sub(r'<[^>]+>', '', caption)  # Remove HTML tags
                caption = re.sub(r'\s+', ' ', caption)     # Normalize whitespace
                if len(caption) > 10 and len(caption) < 500:  # Reasonable length
                    return caption
        
        return None
    
    def _extract_figure_images(self, html_content: str, base_url: str) -> List[ImageInfo]:
        """
        Extract images specifically from figure elements.
        
        Args:
            html_content: HTML content
            base_url: Base URL for resolution
            
        Returns:
            List of ImageInfo objects from figures
        """
        images = []
        
        # Find figure elements
        figure_pattern = r'<figure[^>]*>(.*?)</figure>'
        
        for figure_match in re.finditer(figure_pattern, html_content, re.IGNORECASE | re.DOTALL):
            figure_content = figure_match.group(1)
            
            # Extract image from figure
            img_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', figure_content, re.IGNORECASE)
            if img_match:
                src = img_match.group(0)
                image_url = self._resolve_url(img_match.group(1), base_url)
                
                if not image_url or self._is_likely_ui_image(image_url):
                    continue
                
                # Extract alt text
                alt_match = re.search(r'alt=["\']([^"\']*)["\']', src, re.IGNORECASE)
                alt_text = alt_match.group(1) if alt_match else None
                
                # Extract caption from figcaption
                caption_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', figure_content, re.IGNORECASE | re.DOTALL)
                caption = None
                if caption_match:
                    caption = re.sub(r'<[^>]+>', '', caption_match.group(1)).strip()
                    caption = re.sub(r'\s+', ' ', caption)
                
                image_info = ImageInfo(
                    url=image_url,
                    alt_text=alt_text,
                    caption=caption
                )
                
                images.append(image_info)
        
        return images
    
    def _deduplicate_images(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """
        Remove duplicate images from the list.
        
        Args:
            images: List of ImageInfo objects
            
        Returns:
            Deduplicated list
        """
        seen_urls = set()
        unique_images = []
        
        for image in images:
            # Normalize URL for comparison
            normalized_url = image.url.lower().split('?')[0]  # Remove query parameters
            
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_images.append(image)
        
        return unique_images
    
    def _validate_and_enhance_image(self, image_info: ImageInfo) -> Optional[ImageInfo]:
        """
        Validate an image and enhance it with additional metadata.
        
        Args:
            image_info: ImageInfo object to validate
            
        Returns:
            Enhanced ImageInfo or None if invalid
        """
        try:
            # Make a HEAD request to get image metadata
            response = self.session.head(
                image_info.url,
                timeout=self.extractor_config.get('timeout', 30),
                allow_redirects=True
            )
            
            if response.status_code != 200:
                image_info.is_valid = False
                image_info.error_message = f"HTTP {response.status_code}"
                return image_info
            
            # Get content type
            content_type = response.headers.get('content-type', '').lower()
            if content_type:
                image_info.mime_type = content_type
                
                # Validate MIME type
                if not any(supported in content_type for supported in self.supported_formats):
                    image_info.is_valid = False
                    image_info.error_message = f"Unsupported format: {content_type}"
                    return image_info
            
            # Get file size
            content_length = response.headers.get('content-length')
            if content_length:
                try:
                    file_size = int(content_length)
                    image_info.file_size = file_size
                    
                    # Check file size limits
                    if file_size > self.max_file_size:
                        image_info.is_valid = False
                        image_info.error_message = f"File too large: {file_size} bytes"
                        return image_info
                    
                    # Skip very small files (likely tracking pixels)
                    if file_size < 1000:  # 1KB
                        image_info.is_valid = False
                        image_info.error_message = "File too small (likely tracking pixel)"
                        return image_info
                        
                except ValueError:
                    pass
            
            return image_info
            
        except RequestException as e:
            image_info.is_valid = False
            image_info.error_message = f"Request failed: {str(e)}"
            return image_info
        except Exception as e:
            image_info.is_valid = False
            image_info.error_message = f"Validation failed: {str(e)}"
            return image_info
    
    def download_image(self, image_info: ImageInfo, output_dir: str) -> Optional[str]:
        """
        Download an image to a local directory.
        
        Args:
            image_info: ImageInfo object
            output_dir: Directory to save the image
            
        Returns:
            Local file path if successful, None otherwise
        """
        if not image_info.is_valid:
            return None
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename from URL
            parsed_url = urlparse(image_info.url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or '.' not in filename:
                # Generate filename from URL hash
                url_hash = hashlib.md5(image_info.url.encode()).hexdigest()[:8]
                ext = mimetypes.guess_extension(image_info.mime_type) if image_info.mime_type else '.jpg'
                filename = f"image_{url_hash}{ext}"
            
            local_path = os.path.join(output_dir, filename)
            
            # Download the image
            response = self.session.get(
                image_info.url,
                timeout=self.extractor_config.get('timeout', 30),
                stream=True
            )
            response.raise_for_status()
            
            # Save to file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            image_info.local_path = local_path
            return local_path
            
        except Exception as e:
            print(f"Failed to download image {image_info.url}: {e}")
            return None
    
    def get_image_statistics(self, images: List[ImageInfo]) -> Dict[str, Any]:
        """
        Get statistics about extracted images.
        
        Args:
            images: List of ImageInfo objects
            
        Returns:
            Dictionary with image statistics
        """
        if not images:
            return {
                'total_images': 0,
                'valid_images': 0,
                'invalid_images': 0,
                'total_size_bytes': 0,
                'formats': {},
                'error_types': {}
            }
        
        valid_images = [img for img in images if img.is_valid]
        invalid_images = [img for img in images if not img.is_valid]
        
        # Calculate total size
        total_size = sum(img.file_size for img in valid_images if img.file_size)
        
        # Count formats
        formats = {}
        for img in valid_images:
            if img.mime_type:
                formats[img.mime_type] = formats.get(img.mime_type, 0) + 1
        
        # Count error types
        error_types = {}
        for img in invalid_images:
            if img.error_message:
                error_types[img.error_message] = error_types.get(img.error_message, 0) + 1
        
        return {
            'total_images': len(images),
            'valid_images': len(valid_images),
            'invalid_images': len(invalid_images),
            'total_size_bytes': total_size,
            'formats': formats,
            'error_types': error_types,
            'has_captions': sum(1 for img in valid_images if img.caption),
            'has_alt_text': sum(1 for img in valid_images if img.alt_text)
        }


# Global instance
_image_extractor = None


def get_image_extractor() -> ImageExtractor:
    """Get the global image extractor instance."""
    global _image_extractor
    if _image_extractor is None:
        _image_extractor = ImageExtractor()
    return _image_extractor


def extract_and_catalog_images(article: Article) -> List[ImageInfo]:
    """
    Convenience function to extract and catalog images from an article.
    
    Args:
        article: Article to extract images from
        
    Returns:
        List of validated ImageInfo objects
    """
    extractor = get_image_extractor()
    return extractor.extract_images_from_article(article) 