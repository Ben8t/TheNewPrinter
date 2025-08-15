"""
URL validation and error handling for new-printer extractors.

This module provides comprehensive URL validation, normalization, and
error handling utilities for the content extraction system.
"""

import re
import socket
import ssl
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse, urlunparse, urljoin
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, SSLError

from ..config import get_config


class URLValidationError(Exception):
    """Custom exception for URL validation errors."""
    pass


class ExtractionError(Exception):
    """Custom exception for extraction-related errors."""
    pass


class URLValidator:
    """
    Comprehensive URL validator with normalization and error handling.
    
    Provides URL validation, normalization, accessibility checking,
    and detailed error reporting for extraction failures.
    """
    
    def __init__(self):
        """Initialize the URL validator."""
        self.config = get_config()
        self.extractor_config = self.config.get_extractor_config()
        
        # Common blocked domains/patterns
        self.blocked_domains = {
            'localhost', '127.0.0.1', '0.0.0.0', '::1',
            'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
            'linkedin.com', 'tiktok.com', 'snapchat.com', 'pinterest.com'
        }
        
        # File extensions that are likely not articles
        self.non_article_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.rar', '.tar', '.gz', '.exe', '.dmg', '.pkg',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
            '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.mp3', '.wav', '.flac', '.aac', '.ogg',
            '.css', '.js', '.json', '.xml', '.rss'
        }
        
        # Common article URL patterns
        self.article_patterns = [
            r'/article/',
            r'/post/',
            r'/blog/',
            r'/news/',
            r'/story/',
            r'/\d{4}/\d{2}/',  # Date-based URLs
            r'/p/',
            r'/read/',
            r'/content/',
        ]
    
    def validate_url(self, url: str, check_accessibility: bool = True) -> Tuple[str, Optional[str]]:
        """
        Validate and normalize a URL.
        
        Args:
            url: URL to validate
            check_accessibility: Whether to check if URL is accessible
            
        Returns:
            Tuple of (normalized_url, error_message)
            If error_message is None, the URL is valid
        """
        try:
            # Basic format validation
            normalized_url = self._normalize_url(url)
            if not normalized_url:
                return url, "Invalid URL format"
            
            # Parse the URL
            parsed = urlparse(normalized_url)
            
            # Validate scheme
            if parsed.scheme not in ('http', 'https'):
                return normalized_url, f"Unsupported URL scheme: {parsed.scheme}"
            
            # Validate domain
            if not parsed.netloc:
                return normalized_url, "URL missing domain"
            
            # Check for blocked domains
            domain = parsed.netloc.lower()
            if any(blocked in domain for blocked in self.blocked_domains):
                return normalized_url, f"Domain not supported for article extraction: {domain}"
            
            # Check for non-article file extensions
            path = parsed.path.lower()
            for ext in self.non_article_extensions:
                if path.endswith(ext):
                    return normalized_url, f"URL appears to be a {ext} file, not an article"
            
            # Check accessibility if requested
            if check_accessibility:
                accessibility_error = self._check_accessibility(normalized_url)
                if accessibility_error:
                    return normalized_url, accessibility_error
            
            return normalized_url, None
            
        except Exception as e:
            return url, f"URL validation failed: {str(e)}"
    
    def _normalize_url(self, url: str) -> Optional[str]:
        """
        Normalize a URL to a standard format.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL or None if invalid
        """
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        if not url:
            return None
        
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('www.'):
                url = 'https://' + url
            else:
                url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            
            # Ensure we have a valid netloc
            if not parsed.netloc:
                return None
            
            # Clean up the URL
            cleaned_url = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            
            return cleaned_url
            
        except Exception:
            return None
    
    def _check_accessibility(self, url: str) -> Optional[str]:
        """
        Check if a URL is accessible.
        
        Args:
            url: URL to check
            
        Returns:
            Error message if URL is not accessible, None if accessible
        """
        try:
            timeout = self.extractor_config.get('timeout', 30)
            user_agent = self.extractor_config.get('user_agent', 'new-printer/1.0.0')
            
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            # Use HEAD request first to avoid downloading content
            response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            
            # If HEAD is not allowed, try GET
            if response.status_code == 405:  # Method Not Allowed
                response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
                # Close the connection immediately to avoid downloading content
                response.close()
            
            # Check status code
            if response.status_code >= 400:
                return f"HTTP {response.status_code}: {response.reason}"
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if content_type and 'text/html' not in content_type:
                return f"URL does not serve HTML content (Content-Type: {content_type})"
            
            return None
            
        except Timeout:
            return f"Request timed out after {timeout} seconds"
        except ConnectionError:
            return "Could not connect to the server"
        except SSLError:
            return "SSL certificate verification failed"
        except RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            return f"Accessibility check failed: {str(e)}"
    
    def is_likely_article_url(self, url: str) -> bool:
        """
        Check if a URL is likely to contain an article.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL likely contains an article
        """
        try:
            parsed = urlparse(url.lower())
            path = parsed.path
            
            # Check for article patterns
            for pattern in self.article_patterns:
                if re.search(pattern, path):
                    return True
            
            # Check for news/blog domains
            domain = parsed.netloc
            if any(keyword in domain for keyword in ['news', 'blog', 'post', 'article', 'medium', 'substack']):
                return True
            
            # Check path length (articles often have meaningful paths)
            if len(path) > 10 and '/' in path[1:]:
                return True
            
            return False
            
        except Exception:
            return False
    
    def extract_domain_info(self, url: str) -> Dict[str, Any]:
        """
        Extract domain information from a URL.
        
        Args:
            url: URL to analyze
            
        Returns:
            Dictionary with domain information
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www prefix
            if domain.startswith('www.'):
                clean_domain = domain[4:]
            else:
                clean_domain = domain
            
            # Extract domain parts
            domain_parts = clean_domain.split('.')
            
            return {
                'full_domain': domain,
                'clean_domain': clean_domain,
                'subdomain': domain_parts[0] if len(domain_parts) > 2 else None,
                'domain_name': domain_parts[-2] if len(domain_parts) > 1 else domain_parts[0],
                'tld': domain_parts[-1] if len(domain_parts) > 1 else '',
                'likely_news_site': any(keyword in clean_domain for keyword in 
                                      ['news', 'times', 'post', 'herald', 'journal', 'gazette', 'tribune']),
                'likely_blog': any(keyword in clean_domain for keyword in 
                                 ['blog', 'medium', 'substack', 'ghost', 'wordpress']),
            }
            
        except Exception:
            return {'error': 'Could not parse domain information'}


class ExtractionErrorHandler:
    """
    Handles and categorizes extraction errors with helpful error messages.
    """
    
    def __init__(self):
        """Initialize the error handler."""
        pass
    
    def categorize_error(self, error: Exception, url: str) -> Dict[str, Any]:
        """
        Categorize an extraction error and provide helpful information.
        
        Args:
            error: Exception that occurred
            url: URL that caused the error
            
        Returns:
            Dictionary with error category and helpful information
        """
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'url': url,
            'category': 'unknown',
            'user_message': 'An unknown error occurred during extraction.',
            'retry_recommended': False,
            'suggestions': []
        }
        
        # Network-related errors
        if isinstance(error, (ConnectionError, Timeout, URLError)):
            error_info.update({
                'category': 'network',
                'user_message': 'Could not connect to the website. Please check your internet connection.',
                'retry_recommended': True,
                'suggestions': [
                    'Check your internet connection',
                    'Try again in a few moments',
                    'Verify the URL is correct'
                ]
            })
        
        # HTTP errors
        elif isinstance(error, HTTPError):
            status_code = getattr(error, 'code', 'unknown')
            if status_code == 404:
                error_info.update({
                    'category': 'not_found',
                    'user_message': 'The requested article was not found (404 error).',
                    'retry_recommended': False,
                    'suggestions': ['Verify the URL is correct', 'Check if the article has been moved or deleted']
                })
            elif status_code == 403:
                error_info.update({
                    'category': 'forbidden',
                    'user_message': 'Access to this article is forbidden (403 error).',
                    'retry_recommended': False,
                    'suggestions': ['The website may block automated access', 'Try accessing the article manually first']
                })
            elif status_code >= 500:
                error_info.update({
                    'category': 'server_error',
                    'user_message': f'The website is experiencing server problems ({status_code} error).',
                    'retry_recommended': True,
                    'suggestions': ['Try again later', 'The website may be temporarily down']
                })
        
        # SSL errors
        elif isinstance(error, SSLError):
            error_info.update({
                'category': 'ssl',
                'user_message': 'SSL certificate verification failed for this website.',
                'retry_recommended': False,
                'suggestions': [
                    'The website may have an invalid SSL certificate',
                    'Try using http:// instead of https:// if available'
                ]
            })
        
        # Content extraction errors
        elif 'extraction' in str(error).lower() or 'content' in str(error).lower():
            error_info.update({
                'category': 'extraction',
                'user_message': 'Could not extract readable content from this webpage.',
                'retry_recommended': False,
                'suggestions': [
                    'The webpage may not contain article content',
                    'The website may use a format that is difficult to extract',
                    'Try a different URL from the same website'
                ]
            })
        
        # Validation errors
        elif isinstance(error, URLValidationError):
            error_info.update({
                'category': 'validation',
                'user_message': 'The provided URL is not valid or supported.',
                'retry_recommended': False,
                'suggestions': [
                    'Check the URL format',
                    'Ensure the URL starts with http:// or https://',
                    'Verify the URL is accessible in a web browser'
                ]
            })
        
        return error_info
    
    def get_user_friendly_message(self, error_info: Dict[str, Any]) -> str:
        """
        Get a user-friendly error message.
        
        Args:
            error_info: Error information dictionary
            
        Returns:
            User-friendly error message
        """
        message = error_info.get('user_message', 'An error occurred during extraction.')
        
        suggestions = error_info.get('suggestions', [])
        if suggestions:
            message += '\n\nSuggestions:\n'
            for suggestion in suggestions:
                message += f'• {suggestion}\n'
        
        if error_info.get('retry_recommended'):
            message += '\nYou may want to try again.'
        
        return message.strip()


# Global instances
_url_validator = None
_error_handler = None


def get_url_validator() -> URLValidator:
    """Get the global URL validator instance."""
    global _url_validator
    if _url_validator is None:
        _url_validator = URLValidator()
    return _url_validator


def get_error_handler() -> ExtractionErrorHandler:
    """Get the global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ExtractionErrorHandler()
    return _error_handler


def validate_and_normalize_url(url: str, check_accessibility: bool = True) -> Tuple[str, Optional[str]]:
    """
    Convenience function to validate and normalize a URL.
    
    Args:
        url: URL to validate
        check_accessibility: Whether to check if URL is accessible
        
    Returns:
        Tuple of (normalized_url, error_message)
    """
    validator = get_url_validator()
    return validator.validate_url(url, check_accessibility)


def handle_extraction_error(error: Exception, url: str) -> Dict[str, Any]:
    """
    Convenience function to handle extraction errors.
    
    Args:
        error: Exception that occurred
        url: URL that caused the error
        
    Returns:
        Dictionary with error information
    """
    handler = get_error_handler()
    return handler.categorize_error(error, url) 