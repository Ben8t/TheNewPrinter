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
            # First, use trafilatura to identify the main content region
            # but we need to preserve images in their positions
            extracted_html = trafilatura.extract(
                html_content,
                config=self.trafilatura_config,
                include_comments=False,
                include_tables=True,
                include_formatting=True,
                output_format='html'
            )
            
            if not extracted_html or not extracted_html.strip():
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
            
            # Extract images with sequential order and context
            images, image_contexts = self._extract_images_with_order_and_context(html_content, url)
            
            # Extract description
            description = self._extract_description(metadata, html_content)
            
            # Extract language
            language = self._extract_language(metadata, html_content)
            
            # Inject images back into the extracted HTML using context matching
            html_with_images = self._inject_images_by_context(extracted_html, image_contexts)
            
            # Convert HTML to Markdown
            content = self._html_to_markdown_with_images(html_with_images, url, images)
            
            return Article(
                title=title,
                content=content,
                author=author,
                date=date,
                images=images,
                url=url,
                description=description,
                language=language,
                metadata={'image_contexts': image_contexts}
            )
            
        except Exception as e:
            print(f"Content extraction failed: {e}")
            return None
    
    def _inject_images_at_original_positions(self, original_html: str, extracted_html: str, base_url: str, image_urls: List[str]) -> str:
        """
        Inject images at their original positions by matching surrounding text.
        
        This method finds images in the original HTML and inserts them into
        the extracted content at positions that match their original context.
        
        Args:
            original_html: Original full HTML content
            extracted_html: Cleaned HTML from trafilatura
            base_url: Base URL for resolving relative image URLs
            image_urls: List of image URLs to inject (from _extract_images)
            
        Returns:
            HTML content with images inserted at original positions
        """
        from bs4 import BeautifulSoup, NavigableString
        
        try:
            if not image_urls:
                return extracted_html
            
            # Parse both HTMLs
            original_soup = BeautifulSoup(original_html, 'html.parser')
            extracted_soup = BeautifulSoup(extracted_html, 'html.parser')
            
            # Convert image_urls to a set for faster lookup
            image_url_set = set(image_urls)
            
            # Find all images in original HTML with their context
            image_contexts = []
            for img in original_soup.find_all('img'):
                src = img.get('src', '')
                
                # Resolve URLs
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    elif not src.startswith(('http://', 'https://')):
                        src = urljoin(base_url, src)
                    
                    # Only include approved images
                    if src in image_url_set:
                        # Get context: text before and after the image
                        context_before = self._get_text_context_before(img, original_soup, max_chars=100)
                        context_after = self._get_text_context_after(img, original_soup, max_chars=100)
                        
                        image_contexts.append({
                            'src': src,
                            'alt': img.get('alt', ''),
                            'before': context_before,
                            'after': context_after
                        })
            
            if not image_contexts:
                return extracted_html
            
            # Get all text elements from extracted content
            extracted_text = extracted_soup.get_text()
            all_elements = extracted_soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div'])
            
            # For each image, find the best insertion point
            images_to_insert = []
            for img_ctx in image_contexts:
                best_element = None
                best_score = 0
                
                # Try to find matching context in extracted content
                for element in all_elements:
                    elem_text = element.get_text()
                    score = 0
                    
                    # Check if context before matches
                    if img_ctx['before'] and img_ctx['before'] in elem_text:
                        score += 10
                    
                    # Check if context after matches
                    if img_ctx['after'] and img_ctx['after'] in extracted_text:
                        # Find position of this element's text in full text
                        elem_pos = extracted_text.find(elem_text)
                        after_pos = extracted_text.find(img_ctx['after'], elem_pos)
                        if 0 < after_pos - elem_pos < 200:  # Within reasonable distance
                            score += 5
                    
                    if score > best_score:
                        best_score = score
                        best_element = element
                
                # If we found a good match, mark it for insertion
                if best_element and best_score > 0:
                    images_to_insert.append((best_element, img_ctx))
                else:
                    # Fallback: add to list for even distribution
                    images_to_insert.append((None, img_ctx))
            
            # Insert images at matched positions
            matched_images = [(elem, ctx) for elem, ctx in images_to_insert if elem is not None]
            unmatched_images = [ctx for elem, ctx in images_to_insert if elem is None]
            
            # Insert matched images
            for element, img_ctx in matched_images:
                figure = extracted_soup.new_tag('figure')
                new_img = extracted_soup.new_tag('img')
                new_img['src'] = img_ctx['src']
                new_img['alt'] = img_ctx['alt']
                figure.append(new_img)
                
                try:
                    element.insert_after(figure)
                except:
                    pass  # Skip if insertion fails
            
            # Distribute unmatched images evenly
            if unmatched_images:
                paragraphs = extracted_soup.find_all(['p', 'h2', 'h3'])
                if paragraphs:
                    step = max(1, len(paragraphs) // (len(unmatched_images) + 1))
                    for idx, img_ctx in enumerate(unmatched_images):
                        insert_after_idx = min((idx + 1) * step, len(paragraphs) - 1)
                        if insert_after_idx < len(paragraphs):
                            figure = extracted_soup.new_tag('figure')
                            new_img = extracted_soup.new_tag('img')
                            new_img['src'] = img_ctx['src']
                            new_img['alt'] = img_ctx['alt']
                            figure.append(new_img)
                            
                            try:
                                paragraphs[insert_after_idx].insert_after(figure)
                            except:
                                pass
            
            return str(extracted_soup)
            
        except Exception as e:
            print(f"Warning: Failed to inject images: {e}")
            return extracted_html
    
    def _get_text_context_before(self, element, soup, max_chars=100):
        """Get text content before an element."""
        try:
            text_parts = []
            current = element
            
            while current and len(''.join(text_parts)) < max_chars:
                # Get previous sibling
                prev = current.previous_sibling
                if prev:
                    if isinstance(prev, NavigableString):
                        text_parts.insert(0, str(prev).strip())
                    elif hasattr(prev, 'get_text'):
                        text_parts.insert(0, prev.get_text().strip())
                    current = prev
                else:
                    # Move to parent's previous sibling
                    current = current.parent
                    if not current or current.name == 'body':
                        break
            
            text = ' '.join(text_parts)
            return text[-max_chars:] if len(text) > max_chars else text
        except:
            return ""
    
    def _get_text_context_after(self, element, soup, max_chars=100):
        """Get text content after an element."""
        try:
            text_parts = []
            current = element
            
            while current and len(''.join(text_parts)) < max_chars:
                # Get next sibling
                next_elem = current.next_sibling
                if next_elem:
                    if isinstance(next_elem, NavigableString):
                        text_parts.append(str(next_elem).strip())
                    elif hasattr(next_elem, 'get_text'):
                        text_parts.append(next_elem.get_text().strip())
                    current = next_elem
                else:
                    # Move to parent's next sibling
                    current = current.parent
                    if not current or current.name == 'body':
                        break
            
            text = ' '.join(text_parts)
            return text[:max_chars] if len(text) > max_chars else text
        except:
            return ""
    
    def _is_likely_ui_image_tag(self, src: str, alt: str) -> bool:
        """Check if an image tag is likely a UI element."""
        if not src:
            return True
            
        src_lower = src.lower()
        alt_lower = alt.lower() if alt else ''
        
        # Check for common UI image patterns
        ui_patterns = [
            'icon', 'logo', 'avatar', 'profile', 'thumbnail',
            'button', 'arrow', 'social', 'share', 'tracking',
            'pixel', 'beacon', 'ad-', 'ads/', '16x16', '32x32',
            '24x24', '48x48', 'favicon'
        ]
        
        for pattern in ui_patterns:
            if pattern in src_lower or pattern in alt_lower:
                return True
        
        return False
    
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
    
    def _inject_images_by_context(self, extracted_html: str, image_contexts: dict) -> str:
        """
        Inject images into extracted HTML using context matching (3 words before/after).
        Falls back to sequential order if context doesn't match.
        
        Args:
            extracted_html: Clean HTML from trafilatura
            image_contexts: Dict mapping image number to {url, before, after, alt}
            
        Returns:
            HTML with images injected in correct positions
        """
        from bs4 import BeautifulSoup
        
        try:
            if not image_contexts:
                return extracted_html
            
            soup = BeautifulSoup(extracted_html, 'html.parser')
            all_paragraphs = soup.find_all(['p', 'h2', 'h3'])
            
            if not all_paragraphs:
                return extracted_html
            
            # Get full text for context searching
            full_text = soup.get_text().lower()
            
            # For each image (in order), find where to insert it
            placements = []
            
            for img_num in sorted(image_contexts.keys()):
                ctx = image_contexts[img_num]
                before = ctx['before'].lower()
                after = ctx['after'].lower()
                
                best_para = None
                best_score = 0
                
                # Try to find the context in the extracted text
                for para in all_paragraphs:
                    para_text = para.get_text().lower()
                    
                    score = 0
                    # Check if "before" words appear
                    if before and before in para_text:
                        score += 10
                    # Check if "after" words appear  
                    if after and after in para_text:
                        score += 10
                    # Check if both appear in sequence
                    if before and after:
                        combined = f"{before} {after}"
                        if combined in full_text:
                            # Find position
                            pos = full_text.find(combined)
                            para_pos = full_text.find(para_text.lower())
                            if para_pos >= 0 and abs(pos - para_pos) < 200:
                                score += 20
                    
                    if score > best_score:
                        best_score = score
                        best_para = para
                
                # Create image tag
                img_tag = f'<img src="{ctx["url"]}" alt="{ctx["alt"]}" data-img-num="{img_num}" />'
                
                if best_para and best_score > 5:
                    placements.append((img_num, best_para, img_tag))
                else:
                    # No good match - use fallback position
                    fallback_idx = min(img_num, len(all_paragraphs) - 1)
                    placements.append((img_num, all_paragraphs[fallback_idx], img_tag))
            
            # Insert images in reverse order (by number) to avoid position shifts
            placements.sort(key=lambda x: x[0], reverse=True)
            
            for img_num, para, img_tag in placements:
                figure = soup.new_tag('figure')
                img_elem = BeautifulSoup(img_tag, 'html.parser').find('img')
                figure.append(img_elem)
                para.insert_after(figure)
            
            return str(soup)
            
        except Exception as e:
            print(f"Image injection by context failed: {e}")
            return extracted_html
    
    def _inject_images_into_html(self, original_html: str, extracted_html: str, base_url: str, image_urls: List[str]) -> str:
        """
        Inject images from original HTML into extracted HTML, PRESERVING ORIGINAL ORDER.
        
        Args:
            original_html: Original HTML with images
            extracted_html: Clean HTML from trafilatura (no images)
            base_url: Base URL for resolving relative URLs
            image_urls: List of image URLs to inject
            
        Returns:
            HTML with images injected in their original sequential order
        """
        from bs4 import BeautifulSoup
        
        try:
            # Parse both HTMLs
            original_soup = BeautifulSoup(original_html, 'html.parser')
            extracted_soup = BeautifulSoup(extracted_html, 'html.parser')
            
            # Get images in their original order with position markers
            all_elements = original_soup.find_all(['p', 'h1', 'h2', 'h3', 'img'])
            
            images_in_order = []  # List of (position, anchor_text, img_tag)
            
            for i, elem in enumerate(all_elements):
                if elem.name != 'img':
                    continue
                
                src = elem.get('src', '')
                if not src:
                    continue
                
                # Resolve URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                # Only include if in our image list
                if src not in image_urls:
                    continue
                
                # Find the paragraph right before this image
                anchor_text = None
                for j in range(i - 1, max(0, i - 10), -1):
                    prev_elem = all_elements[j]
                    if prev_elem.name in ['p', 'h2', 'h3']:
                        text = prev_elem.get_text(strip=True)
                        if len(text) >= 30:
                            anchor_text = text[:100]
                            break
                
                if anchor_text:
                    img_tag = f'<img src="{src}" alt="{elem.get("alt", "")}" />'
                    images_in_order.append((i, anchor_text, img_tag))
            
            if not images_in_order:
                return extracted_html
            
            # Match each image to its anchor paragraph, preserving original order
            # Get all paragraphs with their document positions
            all_paragraphs = extracted_soup.find_all(['p', 'h2', 'h3'])
            
            if not all_paragraphs:
                return extracted_html
            
            # Match each image to its best paragraph (allow reuse)
            image_insertions = []
            
            for orig_pos, anchor_text, img_tag in images_in_order:
                anchor_lower = anchor_text.lower()
                best_match = None
                best_score = 0
                best_match_idx = -1
                
                # Find best matching paragraph
                for idx, para in enumerate(all_paragraphs):
                    para_text = para.get_text(strip=True)
                    if len(para_text) < 20:
                        continue
                    
                    para_lower = para_text.lower()
                    
                    # Calculate match score
                    score = 0
                    if anchor_lower[:50] in para_lower:
                        score = 100
                    elif para_lower[:50] in anchor_lower:
                        score = 80
                    else:
                        # Word overlap
                        anchor_words = set(anchor_lower.split())
                        para_words = set(para_lower.split())
                        common = anchor_words & para_words
                        if common:
                            score = len(common) * 5
                    
                    if score > best_score:
                        best_score = score
                        best_match = para
                        best_match_idx = idx
                
                if best_match and best_score > 20:
                    image_insertions.append((orig_pos, best_match_idx, best_match, img_tag))
                else:
                    # No match - use proportional position
                    fallback_idx = int((orig_pos / len(images_in_order)) * len(all_paragraphs))
                    image_insertions.append((orig_pos, fallback_idx, None, img_tag))
            
            # Group images by their matched paragraph index, maintaining original order within groups
            from collections import defaultdict
            para_to_images = defaultdict(list)
            for orig_pos, para_idx, para_elem, img_tag in image_insertions:
                para_to_images[para_idx].append((orig_pos, para_elem, img_tag))
            
            # Sort paragraph indices in reverse to insert from end to start
            for para_idx in sorted(para_to_images.keys(), reverse=True):
                images_for_para = para_to_images[para_idx]
                # Sort by original position to maintain order
                images_for_para.sort(key=lambda x: x[0])
                
                # Insert all images for this paragraph in reverse original order
                for orig_pos, para_elem, img_tag in reversed(images_for_para):
                    figure_tag = extracted_soup.new_tag('figure')
                    img_soup_tag = BeautifulSoup(img_tag, 'html.parser').find('img')
                    figure_tag.append(img_soup_tag)
                    
                    if para_elem:
                        para_elem.insert_after(figure_tag)
                    else:
                        # Fallback position
                        insert_idx = min(para_idx, len(all_paragraphs) - 1)
                        all_paragraphs[insert_idx].insert_after(figure_tag)
            
            return str(extracted_soup)
            
        except Exception as e:
            print(f"Image injection failed: {e}")
            return extracted_html
    
    def _html_to_markdown_with_images(self, html_content: str, base_url: str, image_list: List[str]) -> str:
        """
        Convert HTML to Markdown while preserving images in their original positions.
        
        Args:
            html_content: HTML content with images
            base_url: Base URL for resolving relative image URLs
            image_list: List of image URLs we've extracted
            
        Returns:
            Markdown content with images
        """
        from markdownify import markdownify as md
        
        try:
            # Convert HTML to Markdown
            markdown = md(
                html_content,
                heading_style='ATX',
                bullets='-',
                strong_em_symbol='*',
                strip=['script', 'style']
            )
            
            return markdown.strip()
            
        except Exception as e:
            print(f"HTML to Markdown conversion failed: {e}")
            # Fallback to basic conversion
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text()
    
    def _extract_images_with_order_and_context(self, html_content: str, base_url: str) -> tuple[List[str], dict]:
        """
        Extract images with sequential naming and surrounding context.
        
        Returns: (image_urls, contexts) where contexts maps sequential number to context
        """
        from bs4 import BeautifulSoup, NavigableString
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            article = soup.find('article') or soup.find('main') or soup
            
            images = []
            contexts = {}
            
            all_elements = article.find_all(['p', 'h1', 'h2', 'h3', 'img'])
            
            img_number = 1
            for i, elem in enumerate(all_elements):
                if elem.name != 'img':
                    continue
                
                src = elem.get('src', '')
                if not src:
                    continue
                
                # Skip UI images
                if any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'ad-', 'ads/', 'tracking', 'pixel']):
                    continue
                
                # Resolve URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                if src and src not in images:
                    images.append(src)
                    
                    # Extract 3 words before and 3 words after
                    words_before = []
                    words_after = []
                    
                    # Get words before
                    for j in range(i - 1, max(0, i - 5), -1):
                        prev_elem = all_elements[j]
                        if prev_elem.name in ['p', 'h2', 'h3']:
                            text = prev_elem.get_text(strip=True)
                            words = text.split()
                            words_before = words[-3:] + words_before
                            if len(words_before) >= 3:
                                break
                    
                    # Get words after
                    for j in range(i + 1, min(len(all_elements), i + 5)):
                        next_elem = all_elements[j]
                        if next_elem.name in ['p', 'h2', 'h3']:
                            text = next_elem.get_text(strip=True)
                            words = text.split()
                            words_after.extend(words[:3])
                            if len(words_after) >= 3:
                                break
                    
                    contexts[img_number] = {
                        'url': src,
                        'alt': elem.get('alt', ''),
                        'before': ' '.join(words_before[-3:]),
                        'after': ' '.join(words_after[:3]),
                        'number': img_number
                    }
                    img_number += 1
            
            return images[:10], contexts
            
        except Exception as e:
            print(f"Image extraction with context failed: {e}")
            return [], {}
    
    def _extract_images_simple(self, html_content: str, base_url: str) -> List[str]:
        """Simple image extraction for download list."""
        images = []
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        img_matches = re.findall(img_pattern, html_content, re.IGNORECASE)
        
        for img_url in img_matches:
            # Skip UI images
            if any(skip in img_url.lower() for skip in ['icon', 'logo', 'avatar', 'ad-', 'ads/', 'tracking', 'pixel']):
                continue
            
            # Convert to absolute URL
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                img_url = urljoin(base_url, img_url)
            elif not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(base_url, img_url)
            
            if img_url and img_url not in images:
                images.append(img_url)
        
        return images[:10]
    
    def _extract_images_with_context(self, html_content: str, base_url: str) -> tuple[List[str], dict]:
        """
        Extract image URLs with exact paragraph anchors for accurate positioning.
        
        Returns: (image_urls, context_dict) where context_dict maps URL to anchor paragraphs
        """
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find main content area
            article = soup.find('article') or soup.find(class_='post') or soup.find('main') or soup
            
            images = []
            contexts = {}
            
            # Build a map of content elements
            all_elements = article.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'img'])
            
            for i, elem in enumerate(all_elements):
                if elem.name != 'img':
                    continue
                    
                src = elem.get('src', '')
                
                # Skip UI images
                if any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'ad-', 'ads/', 'tracking', 'pixel']):
                    continue
                
                # Convert to absolute URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                if src and src not in images:
                    images.append(src)
                    
                    # Find the nearest substantial paragraph BEFORE this image
                    anchor_para = None
                    for j in range(i - 1, max(0, i - 10), -1):
                        prev_elem = all_elements[j]
                        if prev_elem.name in ['p', 'h2', 'h3']:
                            text = prev_elem.get_text(strip=True)
                            # Use paragraphs with at least 30 chars as anchors
                            if len(text) >= 30:
                                anchor_para = text
                                break
                    
                    # Also check next paragraph for additional context
                    next_para = None
                    for j in range(i + 1, min(len(all_elements), i + 5)):
                        next_elem = all_elements[j]
                        if next_elem.name in ['p', 'h2', 'h3']:
                            text = next_elem.get_text(strip=True)
                            if len(text) >= 30:
                                next_para = text
                                break
                    
                    contexts[src] = {
                        'anchor_paragraph': anchor_para,
                        'next_paragraph': next_para,
                        'position_hint': i  # Relative position in content
                    }
            
            return images[:10], contexts
            
        except Exception as e:
            print(f"Image context extraction failed: {e}")
            # Fallback to simple extraction
            images = []
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
            img_matches = re.findall(img_pattern, html_content, re.IGNORECASE)
            
            for img_url in img_matches:
                if any(skip in img_url.lower() for skip in ['icon', 'logo', 'avatar', 'ad-', 'ads/', 'tracking']):
                    continue
                
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = urljoin(base_url, img_url)
                elif not img_url.startswith(('http://', 'https://')):
                    img_url = urljoin(base_url, img_url)
                
                if img_url not in images:
                    images.append(img_url)
            
            return images[:10], {}
    
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