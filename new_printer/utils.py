#!/usr/bin/env python3
"""
Utility functions for New Printer.

This module provides common utility functions used across the application,
including URL handling, file operations, text processing, and validation.
"""

import re
import os
import hashlib
import unicodedata
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse, urljoin, quote, unquote
import mimetypes


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a string to be safe for use as a filename.
    
    Args:
        filename: The original filename string
        max_length: Maximum length for the filename
        
    Returns:
        A sanitized filename safe for filesystem use
    """
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    
    # Remove or replace unsafe characters
    # Keep alphanumeric, spaces, hyphens, underscores, and dots
    safe_chars = re.sub(r'[^\w\s\-_.]', '', filename)
    
    # Replace multiple spaces with single space
    safe_chars = re.sub(r'\s+', ' ', safe_chars).strip()
    
    # Replace spaces with underscores
    safe_chars = safe_chars.replace(' ', '_')
    
    # Remove leading dots to avoid hidden files
    safe_chars = safe_chars.lstrip('.')
    
    # Ensure we don't have empty filename
    if not safe_chars:
        safe_chars = 'unnamed_file'
    
    # Truncate if too long, preserving extension
    if len(safe_chars) > max_length:
        if '.' in safe_chars:
            name, ext = safe_chars.rsplit('.', 1)
            max_name_length = max_length - len(ext) - 1
            safe_chars = f"{name[:max_name_length]}.{ext}"
        else:
            safe_chars = safe_chars[:max_length]
    
    return safe_chars


def generate_unique_filename(base_path: Union[str, Path], 
                           desired_name: str, 
                           extension: str = '') -> Path:
    """
    Generate a unique filename by appending numbers if file exists.
    
    Args:
        base_path: Directory where the file will be created
        desired_name: Desired filename (without extension)
        extension: File extension (with or without leading dot)
        
    Returns:
        A Path object for a unique filename
    """
    base_path = Path(base_path)
    
    # Ensure extension starts with dot
    if extension and not extension.startswith('.'):
        extension = f'.{extension}'
    
    # Sanitize the desired name
    safe_name = sanitize_filename(desired_name)
    
    # Start with the original name
    counter = 0
    while True:
        if counter == 0:
            filename = f"{safe_name}{extension}"
        else:
            filename = f"{safe_name}_{counter}{extension}"
        
        full_path = base_path / filename
        if not full_path.exists():
            return full_path
        
        counter += 1
        
        # Safety check to avoid infinite loop
        if counter > 1000:
            # Use a hash-based name as fallback
            hash_name = hashlib.md5(desired_name.encode()).hexdigest()[:8]
            return base_path / f"file_{hash_name}{extension}"


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent processing.
    
    Args:
        url: The URL to normalize
        
    Returns:
        A normalized URL string
    """
    url = url.strip()
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    
    # Parse and reconstruct to normalize
    parsed = urlparse(url)
    
    # Normalize path (remove double slashes, etc.)
    normalized_path = quote(unquote(parsed.path), safe='/')
    
    # Reconstruct URL
    normalized = f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
    
    if parsed.query:
        normalized += f"?{parsed.query}"
    
    # Remove fragment (anchor) for article processing
    # as it's typically not relevant for content extraction
    
    return normalized


def extract_domain(url: str) -> str:
    """
    Extract domain name from URL.
    
    Args:
        url: The URL to extract domain from
        
    Returns:
        Domain name without subdomain prefixes
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Remove www. prefix
    if domain.startswith('www.'):
        domain = domain[4:]
    
    return domain


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL.
    
    Args:
        url: String to validate
        
    Returns:
        True if the string appears to be a valid URL
    """
    try:
        parsed = urlparse(url)
        return all([
            parsed.scheme in ('http', 'https'),
            parsed.netloc,
            '.' in parsed.netloc
        ])
    except Exception:
        return False


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """
    Resolve a relative URL against a base URL.
    
    Args:
        base_url: The base URL
        relative_url: The relative URL to resolve
        
    Returns:
        The resolved absolute URL
    """
    return urljoin(base_url, relative_url)


def guess_content_type(url_or_path: str) -> str:
    """
    Guess content type from URL or file path.
    
    Args:
        url_or_path: URL or file path
        
    Returns:
        MIME type string
    """
    content_type, _ = mimetypes.guess_type(url_or_path)
    return content_type or 'application/octet-stream'


def truncate_text(text: str, max_length: int = 100, 
                  suffix: str = '...') -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    truncate_length = max_length - len(suffix)
    return text[:truncate_length].rstrip() + suffix


def clean_whitespace(text: str) -> str:
    """
    Clean and normalize whitespace in text.
    
    Args:
        text: Text to clean
        
    Returns:
        Text with normalized whitespace
    """
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_numbers(text: str) -> List[int]:
    """
    Extract all numbers from text.
    
    Args:
        text: Text to search for numbers
        
    Returns:
        List of integers found in the text
    """
    return [int(match) for match in re.findall(r'\d+', text)]


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
        
    Raises:
        OSError: If directory cannot be created
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size(path: Union[str, Path]) -> int:
    """
    Get file size in bytes.
    
    Args:
        path: File path
        
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    try:
        return Path(path).stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def split_text_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using simple heuristics.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    # Simple sentence splitting - could be improved with nltk
    sentences = re.split(r'[.!?]+\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def calculate_reading_time(word_count: int, 
                         words_per_minute: int = 200) -> int:
    """
    Calculate estimated reading time in minutes.
    
    Args:
        word_count: Number of words
        words_per_minute: Average reading speed
        
    Returns:
        Estimated reading time in minutes
    """
    if word_count <= 0:
        return 0
    
    minutes = max(1, round(word_count / words_per_minute))
    return minutes


def validate_file_extension(filename: str, 
                          allowed_extensions: List[str]) -> bool:
    """
    Validate if file has an allowed extension.
    
    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions (with or without dots)
        
    Returns:
        True if extension is allowed
    """
    file_ext = Path(filename).suffix.lower()
    
    # Normalize extensions to include dots
    normalized_extensions = []
    for ext in allowed_extensions:
        if not ext.startswith('.'):
            ext = f'.{ext}'
        normalized_extensions.append(ext.lower())
    
    return file_ext in normalized_extensions


def merge_dictionaries(base_dict: Dict[str, Any], 
                      override_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries recursively.
    
    Args:
        base_dict: Base dictionary
        override_dict: Dictionary with override values
        
    Returns:
        Merged dictionary
    """
    result = base_dict.copy()
    
    for key, value in override_dict.items():
        if (key in result and 
            isinstance(result[key], dict) and 
            isinstance(value, dict)):
            result[key] = merge_dictionaries(result[key], value)
        else:
            result[key] = value
    
    return result


def retry_with_backoff(func, max_attempts: int = 3, 
                      initial_delay: float = 1.0,
                      backoff_factor: float = 2.0):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Factor to multiply delay by each attempt
        
    Returns:
        Function result if successful
        
    Raises:
        Last exception if all attempts fail
    """
    import time
    
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                raise last_exception


def hash_content(content: str, algorithm: str = 'md5') -> str:
    """
    Generate hash of content.
    
    Args:
        content: Content to hash
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')
        
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(content.encode('utf-8'))
    return hash_obj.hexdigest()


class TemporaryDirectory:
    """
    Context manager for temporary directories with automatic cleanup.
    """
    
    def __init__(self, prefix: str = 'new_printer_', cleanup: bool = True):
        """
        Initialize temporary directory.
        
        Args:
            prefix: Prefix for temporary directory name
            cleanup: Whether to cleanup on exit
        """
        import tempfile
        self.cleanup = cleanup
        self.temp_dir = None
        self.prefix = prefix
        
    def __enter__(self) -> Path:
        """Create and return temporary directory path."""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary directory."""
        if self.cleanup and self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True) 