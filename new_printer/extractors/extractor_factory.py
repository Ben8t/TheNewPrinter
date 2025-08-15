"""
Extractor factory for new-printer.

This module provides a factory pattern for managing content extractors,
automatically choosing between primary and fallback extractors with
intelligent retry logic.
"""

import time
from typing import Optional, List, Type
from enum import Enum

from .trafilatura_extractor import TrafilaturaExtractor
from .readability_fallback import ReadabilityFallback
from ..models import Article, ExtractionResult
from ..config import get_config


class ExtractorType(Enum):
    """Available extractor types."""
    TRAFILATURA = "trafilatura"
    READABILITY = "readability"


class ExtractorFactory:
    """
    Factory for managing content extractors with intelligent fallback.
    
    This factory automatically tries the primary extractor first, then
    falls back to the secondary extractor if the primary fails.
    """
    
    def __init__(self, config=None):
        """Initialize the extractor factory."""
        self.config = config if config is not None else get_config()
        self.extractor_config = self.config.get_extractor_config()
        
        # Determine extractor order from config
        primary = self.extractor_config.get('primary', 'trafilatura')
        fallback = self.extractor_config.get('fallback', 'readability')
        
        self.extractors = self._setup_extractors(primary, fallback)
        
        # Cache extractor instances for reuse
        self._extractor_cache = {}
    
    def _setup_extractors(self, primary: str, fallback: str) -> List[ExtractorType]:
        """
        Set up the extractor order based on configuration.
        
        Args:
            primary: Primary extractor name
            fallback: Fallback extractor name
            
        Returns:
            List of extractor types in order of preference
        """
        extractors = []
        
        # Add primary extractor
        if primary.lower() == 'trafilatura':
            extractors.append(ExtractorType.TRAFILATURA)
        elif primary.lower() == 'readability':
            extractors.append(ExtractorType.READABILITY)
        else:
            # Default to trafilatura if unknown primary
            extractors.append(ExtractorType.TRAFILATURA)
        
        # Add fallback extractor if different from primary
        if fallback.lower() == 'readability' and ExtractorType.READABILITY not in extractors:
            extractors.append(ExtractorType.READABILITY)
        elif fallback.lower() == 'trafilatura' and ExtractorType.TRAFILATURA not in extractors:
            extractors.append(ExtractorType.TRAFILATURA)
        
        return extractors
    
    def _get_extractor(self, extractor_type: ExtractorType):
        """
        Get an extractor instance, using cache for efficiency.
        
        Args:
            extractor_type: Type of extractor to get
            
        Returns:
            Extractor instance
        """
        if extractor_type not in self._extractor_cache:
            if extractor_type == ExtractorType.TRAFILATURA:
                self._extractor_cache[extractor_type] = TrafilaturaExtractor()
            elif extractor_type == ExtractorType.READABILITY:
                self._extractor_cache[extractor_type] = ReadabilityFallback()
        
        return self._extractor_cache[extractor_type]
    
    def extract(self, url: str, preferred_extractor: Optional[str] = None) -> ExtractionResult:
        """
        Extract content from URL using the best available extractor.
        
        Args:
            url: URL to extract content from
            preferred_extractor: Optional preferred extractor name to try first
            
        Returns:
            ExtractionResult with the extracted article or error information
        """
        # Determine extractor order
        extractor_order = self.extractors.copy()
        
        # If preferred extractor is specified, try it first
        if preferred_extractor:
            preferred_type = self._get_extractor_type(preferred_extractor)
            if preferred_type and preferred_type in extractor_order:
                extractor_order.remove(preferred_type)
                extractor_order.insert(0, preferred_type)
        
        last_result = None
        extraction_attempts = []
        
        # Try each extractor in order
        for extractor_type in extractor_order:
            try:
                extractor = self._get_extractor(extractor_type)
                result = extractor.extract(url)
                
                extraction_attempts.append({
                    'extractor': extractor_type.value,
                    'success': result.success,
                    'time': result.extraction_time_seconds,
                    'error': result.error_message if not result.success else None
                })
                
                if result.success and result.article:
                    # Validate the extracted content
                    if self._is_valid_extraction(result.article):
                        return self._enhance_result(result, extraction_attempts)
                    else:
                        # Content doesn't meet quality standards, try next extractor
                        result.success = False
                        result.error_message = "Extracted content failed quality validation"
                
                last_result = result
                
            except Exception as e:
                extraction_attempts.append({
                    'extractor': extractor_type.value,
                    'success': False,
                    'time': None,
                    'error': f"Extractor failed: {str(e)}"
                })
                
                # Create a failure result if we don't have one yet
                if last_result is None:
                    last_result = ExtractionResult(
                        success=False,
                        error_message=f"Extractor {extractor_type.value} failed: {str(e)}",
                        extractor_used=extractor_type.value
                    )
        
        # All extractors failed, return the last result with attempt history
        if last_result:
            return self._enhance_result(last_result, extraction_attempts)
        
        # Fallback error result
        return ExtractionResult(
            success=False,
            error_message="All extractors failed to process the URL",
            extractor_used="factory"
        )
    
    def _get_extractor_type(self, extractor_name: str) -> Optional[ExtractorType]:
        """
        Convert extractor name to ExtractorType.
        
        Args:
            extractor_name: Name of the extractor
            
        Returns:
            ExtractorType or None if not found
        """
        name_lower = extractor_name.lower()
        if name_lower == 'trafilatura':
            return ExtractorType.TRAFILATURA
        elif name_lower == 'readability':
            return ExtractorType.READABILITY
        return None
    
    def _is_valid_extraction(self, article: Article) -> bool:
        """
        Validate that the extracted article meets quality standards.
        
        Args:
            article: Article to validate
            
        Returns:
            True if article is valid, False otherwise
        """
        if not article or not article.title or not article.content:
            return False
        
        # Check minimum title length
        if len(article.title.strip()) < 3:
            return False
        
        # Check minimum content length (at least 100 characters)
        if len(article.content.strip()) < 100:
            return False
        
        # Check that content is not just whitespace or repeated characters
        content_words = article.content.split()
        if len(content_words) < 20:  # At least 20 words
            return False
        
        # Check for reasonable word length variation (avoid spam/generated content)
        word_lengths = [len(word) for word in content_words[:50]]  # Check first 50 words
        if word_lengths and max(word_lengths) - min(word_lengths) < 2:
            # All words are very similar length, might be spam
            return False
        
        return True
    
    def _enhance_result(self, result: ExtractionResult, attempts: List[dict]) -> ExtractionResult:
        """
        Enhance extraction result with additional metadata.
        
        Args:
            result: Original extraction result
            attempts: List of extraction attempts
            
        Returns:
            Enhanced extraction result
        """
        # Add extraction attempt history to the result
        if hasattr(result, 'extraction_attempts'):
            result.extraction_attempts = attempts
        else:
            # Create a new result with additional metadata
            enhanced_result = ExtractionResult(
                article=result.article,
                success=result.success,
                error_message=result.error_message,
                extractor_used=result.extractor_used,
                extraction_time_seconds=result.extraction_time_seconds
            )
            enhanced_result.extraction_attempts = attempts
            return enhanced_result
        
        return result
    
    def get_available_extractors(self) -> List[str]:
        """
        Get list of available extractor names.
        
        Returns:
            List of extractor names
        """
        return [extractor.value for extractor in self.extractors]
    
    def extract_with_specific_extractor(self, url: str, extractor_name: str) -> ExtractionResult:
        """
        Extract content using a specific extractor only.
        
        Args:
            url: URL to extract content from
            extractor_name: Name of the extractor to use
            
        Returns:
            ExtractionResult from the specified extractor
        """
        extractor_type = self._get_extractor_type(extractor_name)
        if not extractor_type:
            return ExtractionResult(
                success=False,
                error_message=f"Unknown extractor: {extractor_name}",
                extractor_used=extractor_name
            )
        
        try:
            extractor = self._get_extractor(extractor_type)
            return extractor.extract(url)
        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Extractor {extractor_name} failed: {str(e)}",
                extractor_used=extractor_name
            )
    
    def test_extractors(self, test_url: str) -> dict:
        """
        Test all available extractors on a URL for comparison.
        
        Args:
            test_url: URL to test with
            
        Returns:
            Dictionary with results from each extractor
        """
        results = {}
        
        for extractor_type in [ExtractorType.TRAFILATURA, ExtractorType.READABILITY]:
            try:
                extractor = self._get_extractor(extractor_type)
                start_time = time.time()
                result = extractor.extract(test_url)
                
                results[extractor_type.value] = {
                    'success': result.success,
                    'title': result.article.title if result.article else None,
                    'content_length': len(result.article.content) if result.article else 0,
                    'word_count': result.article.word_count if result.article else 0,
                    'images': len(result.article.images) if result.article else 0,
                    'extraction_time': result.extraction_time_seconds,
                    'error': result.error_message if not result.success else None
                }
            except Exception as e:
                results[extractor_type.value] = {
                    'success': False,
                    'error': str(e),
                    'extraction_time': None
                }
        
        return results


# Global factory instance
_factory = None


def get_extractor_factory() -> ExtractorFactory:
    """Get the global extractor factory instance."""
    global _factory
    if _factory is None:
        _factory = ExtractorFactory()
    return _factory


def extract_article(url: str, preferred_extractor: Optional[str] = None) -> ExtractionResult:
    """
    Convenience function to extract an article using the factory.
    
    Args:
        url: URL to extract content from
        preferred_extractor: Optional preferred extractor name
        
    Returns:
        ExtractionResult with the extracted article
    """
    factory = get_extractor_factory()
    return factory.extract(url, preferred_extractor) 