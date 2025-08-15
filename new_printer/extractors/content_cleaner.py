"""
Content cleaning and preprocessing for new-printer.

This module provides comprehensive content cleaning, preprocessing, and
quality enhancement utilities for extracted article content.
"""

import re
import string
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import unicodedata

from ..models import Article
from ..config import get_config


class ContentCleaner:
    """
    Comprehensive content cleaner for extracted articles.
    
    Cleans and preprocesses article content to improve readability
    and formatting for PDF generation.
    """
    
    def __init__(self):
        """Initialize the content cleaner."""
        self.config = get_config()
        
        # Common unwanted patterns to remove
        self.unwanted_patterns = [
            # Social media and sharing
            r'Share this article.*?$',
            r'Follow us on.*?$',
            r'Like us on.*?$',
            r'Subscribe to.*?$',
            r'Sign up for.*?newsletter.*?$',
            r'Get our.*?newsletter.*?$',
            
            # Advertisement patterns
            r'Advertisement.*?$',
            r'Sponsored content.*?$',
            r'Promoted content.*?$',
            r'\[?Ad\]?.*?$',
            
            # Navigation and UI elements
            r'Click here.*?$',
            r'Read more.*?$',
            r'Continue reading.*?$',
            r'Next page.*?$',
            r'Previous page.*?$',
            r'Back to top.*?$',
            
            # Related content
            r'Related articles?.*?$',
            r'You might also like.*?$',
            r'Recommended for you.*?$',
            r'More from.*?$',
            r'Also read.*?$',
            
            # Comments and engagement
            r'Leave a comment.*?$',
            r'Comments? \(\d+\).*?$',
            r'Join the conversation.*?$',
            r'What do you think\?.*?$',
            
            # Copyright and legal
            r'Copyright.*?\d{4}.*?$',
            r'All rights reserved.*?$',
            r'Terms of use.*?$',
            r'Privacy policy.*?$',
            
            # Time stamps and metadata (when not useful)
            r'Published.*?ago.*?$',
            r'Updated.*?ago.*?$',
            r'\d+ min read.*?$',
            r'Reading time:.*?$',
        ]
        
        # Patterns for cleaning quotes and formatting
        self.quote_patterns = [
            (r'"([^"]*)"', r'"\1"'),  # Smart quotes
            (r''([^']*)'', r'"\1"'),  # Single to double quotes
            (r'`([^`]*)`', r'"\1"'),  # Backticks to quotes
        ]
        
        # Common abbreviations that shouldn't be sentence-split
        self.abbreviations = {
            'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr',
            'inc', 'ltd', 'corp', 'co', 'vs', 'etc', 'e.g', 'i.e',
            'jan', 'feb', 'mar', 'apr', 'may', 'jun',
            'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
        }
    
    def clean_content(self, content: str) -> str:
        """
        Clean and preprocess article content.
        
        Args:
            content: Raw article content
            
        Returns:
            Cleaned and preprocessed content
        """
        if not content:
            return ""
        
        # Step 1: Basic whitespace and encoding cleanup
        content = self._clean_encoding(content)
        content = self._normalize_whitespace(content)
        
        # Step 2: Remove unwanted patterns
        content = self._remove_unwanted_patterns(content)
        
        # Step 3: Fix formatting issues
        content = self._fix_punctuation(content)
        content = self._fix_quotes(content)
        content = self._fix_paragraphs(content)
        
        # Step 4: Clean up lists and structure
        content = self._clean_lists(content)
        content = self._fix_sentence_spacing(content)
        
        # Step 5: Final cleanup
        content = self._final_cleanup(content)
        
        return content.strip()
    
    def clean_title(self, title: str) -> str:
        """
        Clean and format article title.
        
        Args:
            title: Raw title
            
        Returns:
            Cleaned title
        """
        if not title:
            return ""
        
        # Remove common title cruft
        title = re.sub(r'\s*\|\s*.*$', '', title)  # Remove site name after |
        title = re.sub(r'\s*-\s*.*$', '', title)  # Remove site name after -
        title = re.sub(r'\s*—\s*.*$', '', title)  # Remove site name after em dash
        
        # Clean encoding and whitespace
        title = self._clean_encoding(title)
        title = self._normalize_whitespace(title)
        
        # Fix quotes
        title = self._fix_quotes(title)
        
        # Remove unwanted patterns
        unwanted_title_patterns = [
            r'\[?\s*UPDATED?\s*\]?',
            r'\[?\s*BREAKING\s*\]?',
            r'\[?\s*EXCLUSIVE\s*\]?',
            r'\[?\s*VIDEO\s*\]?',
            r'\[?\s*PHOTOS?\s*\]?',
        ]
        
        for pattern in unwanted_title_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        return title.strip()
    
    def clean_author(self, author: str) -> Optional[str]:
        """
        Clean and format author name.
        
        Args:
            author: Raw author name
            
        Returns:
            Cleaned author name or None if invalid
        """
        if not author:
            return None
        
        # Clean encoding and whitespace
        author = self._clean_encoding(author)
        author = self._normalize_whitespace(author)
        
        # Remove common prefixes
        author = re.sub(r'^By\s+', '', author, flags=re.IGNORECASE)
        author = re.sub(r'^Author:\s+', '', author, flags=re.IGNORECASE)
        author = re.sub(r'^Written by\s+', '', author, flags=re.IGNORECASE)
        
        # Remove email addresses
        author = re.sub(r'\S+@\S+\.\S+', '', author)
        
        # Remove social media handles
        author = re.sub(r'@\w+', '', author)
        
        # Clean up
        author = author.strip()
        
        # Validate author (should be reasonable length and contain letters)
        if not author or len(author) < 2 or len(author) > 100:
            return None
        
        if not re.search(r'[a-zA-Z]', author):
            return None
        
        return author
    
    def _clean_encoding(self, text: str) -> str:
        """Clean text encoding issues."""
        if not text:
            return ""
        
        # Normalize unicode
        text = unicodedata.normalize('NFKD', text)
        
        # Fix common encoding issues
        replacements = {
            '\u00a0': ' ',  # Non-breaking space
            '\u2019': "'",  # Right single quote
            '\u2018': "'",  # Left single quote
            '\u201c': '"',  # Left double quote
            '\u201d': '"',  # Right double quote
            '\u2013': '-',  # En dash
            '\u2014': ' - ',  # Em dash
            '\u2026': '...',  # Ellipsis
            '\u00e2\u20ac\u2122': "'",  # Common encoding error
            '\u00e2\u20ac\u201c': '"',  # Common encoding error
            '\u00e2\u20ac\u201d': '"',  # Common encoding error
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        if not text:
            return ""
        
        # Replace multiple spaces with single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove trailing whitespace from lines
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        
        return text
    
    def _remove_unwanted_patterns(self, content: str) -> str:
        """Remove unwanted patterns from content."""
        for pattern in self.unwanted_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        return content
    
    def _fix_punctuation(self, content: str) -> str:
        """Fix common punctuation issues."""
        # Fix spacing around punctuation
        content = re.sub(r'\s+([.!?])', r'\1', content)  # Remove space before punctuation
        content = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', content)  # Add space after punctuation
        
        # Fix multiple punctuation
        content = re.sub(r'\.{3,}', '...', content)  # Multiple dots to ellipsis
        content = re.sub(r'[!]{2,}', '!', content)    # Multiple exclamations
        content = re.sub(r'[?]{2,}', '?', content)    # Multiple questions
        
        # Fix comma spacing
        content = re.sub(r'\s*,\s*', ', ', content)
        content = re.sub(r',([A-Za-z])', r', \1', content)
        
        return content
    
    def _fix_quotes(self, content: str) -> str:
        """Fix quote formatting."""
        for pattern, replacement in self.quote_patterns:
            content = re.sub(pattern, replacement, content)
        
        return content
    
    def _fix_paragraphs(self, content: str) -> str:
        """Fix paragraph formatting."""
        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', content)
        
        cleaned_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Skip very short paragraphs (likely navigation elements)
            if len(para) < 20:
                continue
            
            # Skip paragraphs that are mostly punctuation
            if len(re.sub(r'[^\w\s]', '', para)) < len(para) * 0.5:
                continue
            
            cleaned_paragraphs.append(para)
        
        return '\n\n'.join(cleaned_paragraphs)
    
    def _clean_lists(self, content: str) -> str:
        """Clean up list formatting."""
        # Fix bullet points
        content = re.sub(r'^[\u2022\u2023\u25E6\u2043\u2219]\s*', '• ', content, flags=re.MULTILINE)
        content = re.sub(r'^[-*]\s+', '• ', content, flags=re.MULTILINE)
        
        # Fix numbered lists
        content = re.sub(r'^(\d+)\.\s+', r'\1. ', content, flags=re.MULTILINE)
        
        return content
    
    def _fix_sentence_spacing(self, content: str) -> str:
        """Fix spacing between sentences."""
        # Ensure single space after sentence-ending punctuation
        for abbrev in self.abbreviations:
            # Protect abbreviations from sentence splitting
            content = content.replace(f'{abbrev}.', f'{abbrev}〰')
        
        # Fix sentence spacing
        content = re.sub(r'([.!?])\s+([A-Z])', r'\1 \2', content)
        
        # Restore abbreviations
        content = content.replace('〰', '.')
        
        return content
    
    def _final_cleanup(self, content: str) -> str:
        """Final cleanup pass."""
        # Remove empty lines at start and end
        content = content.strip()
        
        # Remove excessive line breaks
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Remove lines that are just punctuation or whitespace
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                cleaned_lines.append('')
                continue
            
            # Skip lines that are mostly special characters
            if len(re.sub(r'[^\w\s]', '', line)) < len(line) * 0.3:
                continue
            
            cleaned_lines.append(line)
        
        # Remove consecutive empty lines
        final_lines = []
        prev_empty = False
        
        for line in cleaned_lines:
            if not line.strip():
                if not prev_empty:
                    final_lines.append('')
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False
        
        return '\n'.join(final_lines).strip()


class ContentProcessor:
    """
    High-level content processor that coordinates cleaning and enhancement.
    """
    
    def __init__(self):
        """Initialize the content processor."""
        self.cleaner = ContentCleaner()
    
    def process_article(self, article: Article) -> Article:
        """
        Process and clean an entire article.
        
        Args:
            article: Article to process
            
        Returns:
            Processed article with cleaned content
        """
        if not article:
            return article
        
        # Clean title
        if article.title:
            article.title = self.cleaner.clean_title(article.title)
        
        # Clean author
        if article.author:
            article.author = self.cleaner.clean_author(article.author)
        
        # Clean content
        if article.content:
            article.content = self.cleaner.clean_content(article.content)
        
        # Clean description
        if article.description:
            article.description = self.cleaner.clean_content(article.description)
            # Keep description shorter
            if len(article.description) > 500:
                article.description = article.description[:497] + '...'
        
        # Update word count after cleaning
        if article.content:
            article.word_count = len(article.content.split())
        
        return article
    
    def validate_content_quality(self, article: Article) -> Tuple[bool, List[str]]:
        """
        Validate the quality of processed content.
        
        Args:
            article: Article to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if not article:
            return False, ["Article is None"]
        
        # Check title
        if not article.title or len(article.title.strip()) < 5:
            issues.append("Title is too short or missing")
        
        # Check content
        if not article.content or len(article.content.strip()) < 100:
            issues.append("Content is too short (less than 100 characters)")
        
        if article.content:
            # Check word count
            words = article.content.split()
            if len(words) < 50:
                issues.append("Content has too few words (less than 50)")
            
            # Check for reasonable sentence structure
            sentences = re.split(r'[.!?]+', article.content)
            valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            if len(valid_sentences) < 3:
                issues.append("Content lacks proper sentence structure")
            
            # Check for excessive repetition
            if self._has_excessive_repetition(article.content):
                issues.append("Content appears to have excessive repetition")
        
        return len(issues) == 0, issues
    
    def _has_excessive_repetition(self, content: str) -> bool:
        """Check if content has excessive repetition."""
        if not content or len(content) < 100:
            return False
        
        # Simple check for repeated phrases
        words = content.lower().split()
        if len(words) < 20:
            return False
        
        # Check for repeated 3-word phrases
        phrases = []
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            phrases.append(phrase)
        
        # If more than 30% of phrases are repeated, consider it excessive
        unique_phrases = len(set(phrases))
        repetition_rate = 1 - (unique_phrases / len(phrases))
        
        return repetition_rate > 0.3


# Global instances
_content_cleaner = None
_content_processor = None


def get_content_cleaner() -> ContentCleaner:
    """Get the global content cleaner instance."""
    global _content_cleaner
    if _content_cleaner is None:
        _content_cleaner = ContentCleaner()
    return _content_cleaner


def get_content_processor() -> ContentProcessor:
    """Get the global content processor instance."""
    global _content_processor
    if _content_processor is None:
        _content_processor = ContentProcessor()
    return _content_processor


def clean_article_content(article: Article) -> Article:
    """
    Convenience function to clean article content.
    
    Args:
        article: Article to clean
        
    Returns:
        Article with cleaned content
    """
    processor = get_content_processor()
    return processor.process_article(article) 