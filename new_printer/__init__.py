"""
New Printer - Transform web articles into print-ready PDFs with classic magazine styling.

A lightweight CLI tool with optional web interface that transforms web articles 
into beautifully formatted PDFs using pandoc's robust document conversion pipeline.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your@email.com"

from .models import Article

__all__ = ["Article"] 