"""
Data models for new-printer.

This module contains the core data structures used throughout the application.
"""

from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Article:
    """
    Represents an extracted article with metadata and content.
    
    This is the core data structure that flows through the extraction
    and processing pipeline.
    """
    
    title: str
    content: str
    author: Optional[str] = None
    date: Optional[datetime] = None
    images: List[str] = field(default_factory=list)
    url: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    word_count: Optional[int] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Calculate word count if not provided
        if self.word_count is None and self.content:
            self.word_count = len(self.content.split())
        
        # Ensure images is always a list
        if self.images is None:
            self.images = []
    
    @property
    def reading_time_minutes(self) -> int:
        """
        Estimate reading time in minutes (assuming 200 words per minute).
        
        Returns:
            Estimated reading time in minutes
        """
        if not self.word_count:
            return 0
        return max(1, self.word_count // 200)
    
    @property
    def has_images(self) -> bool:
        """Check if the article has any images."""
        return bool(self.images)
    
    @property
    def formatted_date(self) -> str:
        """Get formatted date string."""
        if self.date:
            return self.date.strftime("%B %d, %Y")
        return ""
    
    def get_short_title(self, max_length: int = 50) -> str:
        """
        Get a shortened version of the title for filename generation.
        
        Args:
            max_length: Maximum length of the shortened title
            
        Returns:
            Shortened title suitable for filenames
        """
        if len(self.title) <= max_length:
            return self.title
        
        # Try to cut at word boundary
        shortened = self.title[:max_length]
        last_space = shortened.rfind(' ')
        if last_space > max_length * 0.7:  # Only cut at word if it's not too short
            shortened = shortened[:last_space]
        
        return shortened + "..."
    
    def to_dict(self) -> dict:
        """
        Convert article to dictionary format.
        
        Returns:
            Dictionary representation of the article
        """
        return {
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'date': self.date.isoformat() if self.date else None,
            'images': self.images,
            'url': self.url,
            'description': self.description,
            'language': self.language,
            'word_count': self.word_count,
            'reading_time_minutes': self.reading_time_minutes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Article':
        """
        Create Article from dictionary.
        
        Args:
            data: Dictionary containing article data
            
        Returns:
            Article instance
        """
        # Handle date parsing
        date = None
        if data.get('date'):
            if isinstance(data['date'], str):
                try:
                    date = datetime.fromisoformat(data['date'])
                except ValueError:
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                        try:
                            date = datetime.strptime(data['date'], fmt)
                            break
                        except ValueError:
                            continue
            elif isinstance(data['date'], datetime):
                date = data['date']
        
        return cls(
            title=data['title'],
            content=data['content'],
            author=data.get('author'),
            date=date,
            images=data.get('images', []),
            url=data.get('url'),
            description=data.get('description'),
            language=data.get('language'),
            word_count=data.get('word_count')
        )


@dataclass
class ExtractionResult:
    """
    Result of content extraction process.
    
    Contains the extracted article and metadata about the extraction process.
    """
    
    article: Optional[Article] = None
    success: bool = False
    error_message: Optional[str] = None
    extractor_used: Optional[str] = None
    extraction_time_seconds: Optional[float] = None
    
    @property
    def failed(self) -> bool:
        """Check if extraction failed."""
        return not self.success or self.article is None


@dataclass
class ConversionOptions:
    """
    Options for PDF conversion process.
    
    Contains all the settings that control how the article is converted to PDF.
    """
    
    output: Optional[str] = None
    columns: int = 2
    font_size: str = "11pt"
    template: str = "article"
    include_images: bool = True
    margins: str = "2cm"
    fontfamily: str = "times"
    pdf_engine: str = "xelatex"
    timeout: int = 120
    
    def to_dict(self) -> dict:
        """Convert options to dictionary."""
        return {
            'output': self.output,
            'columns': self.columns,
            'font_size': self.font_size,
            'template': self.template,
            'include_images': self.include_images,
            'margins': self.margins,
            'fontfamily': self.fontfamily,
            'pdf_engine': self.pdf_engine,
            'timeout': self.timeout
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConversionOptions':
        """Create ConversionOptions from dictionary."""
        return cls(
            output=data.get('output'),
            columns=data.get('columns', 2),
            font_size=data.get('font_size', "11pt"),
            template=data.get('template', "article"),
            include_images=data.get('include_images', True),
            margins=data.get('margins', "2cm"),
            fontfamily=data.get('fontfamily', "times"),
            pdf_engine=data.get('pdf_engine', "xelatex"),
            timeout=data.get('timeout', 120)
        ) 