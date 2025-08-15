"""
Pandoc PDF generation for new-printer.

This module provides comprehensive PDF generation functionality using
Pandoc with LaTeX backend, custom templates, and advanced formatting options.
"""

import os
import subprocess
import tempfile
import shutil
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import time

from ..models import Article, ConversionOptions
from ..config import get_config


class PandocRunner:
    """
    Comprehensive Pandoc runner for PDF generation.
    
    Handles PDF generation using Pandoc with LaTeX backend, including
    custom templates, filters, and advanced formatting options.
    """
    
    def __init__(self):
        """Initialize the Pandoc runner."""
        self.config = get_config()
        self.pandoc_config = self.config.get_pandoc_config()
        self.templates_dir = Path(__file__).parent.parent / 'templates'
        
        # PDF generation settings
        self.default_engine = self.pandoc_config.get('pdf_engine', 'xelatex')
        self.default_timeout = 120  # 2 minutes
        self.temp_cleanup = True
        
        # Supported LaTeX engines
        self.supported_engines = ['xelatex', 'pdflatex', 'lualatex']
        
        # Default Pandoc options
        self.default_pandoc_options = {
            'standalone': True,
            'toc': False,  # Table of contents
            'number_sections': False,
            'highlight_style': 'kate',
            'pdf_engine': self.default_engine,
        }
    
    def convert_to_pdf(self, article: Article, options: ConversionOptions) -> str:
        """
        Convert article to PDF using Pandoc.
        
        Args:
            article: Article object with content
            options: Conversion options
            
        Returns:
            Path to generated PDF file
        """
        if not article or not article.content:
            raise ValueError("Article content is required for PDF generation")
        
        start_time = time.time()
        
        # Validate Pandoc availability
        self._check_pandoc_availability()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Process images first so we can update the markdown content
                processed_images = []
                if options.include_images and article.images:
                    processed_images = self._process_article_images(article, temp_path)
                    # Update article content to reference local images
                    article = self._update_article_with_local_images(article, processed_images)
                
                # Create markdown file with updated content
                markdown_file = self._create_markdown_file(article, options, temp_path)
                
                # Determine output path
                output_path = self._determine_output_path(options.output, article)
                
                # Build Pandoc command
                pandoc_args = self._build_pandoc_command(
                    markdown_file, output_path, options, temp_path
                )
                
                # Execute Pandoc
                result = self._execute_pandoc(pandoc_args, options.timeout, str(Path.cwd()))
                
                # Validate output
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise Exception("PDF generation failed: Empty or missing output file")
                
                generation_time = time.time() - start_time
                print(f"PDF generated successfully in {generation_time:.2f} seconds: {output_path}")
                
                return str(Path(output_path).resolve())
                
            except Exception as e:
                generation_time = time.time() - start_time
                error_msg = f"PDF generation failed after {generation_time:.2f}s: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
    
    def _check_pandoc_availability(self) -> None:
        """Check if Pandoc is available and properly configured."""
        try:
            result = subprocess.run(
                ['pandoc', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise Exception("Pandoc is not responding properly")
                
            # Check for LaTeX engine
            engine_result = subprocess.run(
                [self.default_engine, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if engine_result.returncode != 0:
                raise Exception(f"LaTeX engine '{self.default_engine}' is not available")
                
        except FileNotFoundError:
            raise Exception("Pandoc is not installed or not in PATH")
        except subprocess.TimeoutExpired:
            raise Exception("Pandoc or LaTeX engine check timed out")
    
    def _create_markdown_file(self, article: Article, options: ConversionOptions, 
                             temp_path: Path) -> Path:
        """
        Create markdown file with YAML frontmatter.
        
        Args:
            article: Article object
            options: Conversion options
            temp_path: Temporary directory path
            
        Returns:
            Path to created markdown file
        """
        # Create metadata for YAML frontmatter
        metadata = self._build_document_metadata(article, options)
        
        # Create markdown content with frontmatter
        markdown_content = self._format_markdown_document(article, metadata)
        
        # Write to file
        markdown_file = temp_path / 'article.md'
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return markdown_file
    
    def _build_document_metadata(self, article: Article, options: ConversionOptions) -> Dict[str, Any]:
        """
        Build document metadata for YAML frontmatter.
        
        Args:
            article: Article object
            options: Conversion options
            
        Returns:
            Metadata dictionary
        """
        # Get template-specific configuration
        template_config = self.config.get_template_config(options.template)
        
        # Base metadata
        metadata = {
            'title': article.title or 'Untitled Article',
            'author': article.author or '',
            'date': article.formatted_date or '',
            'documentclass': 'article',
            'geometry': options.margins,
            'fontsize': options.font_size,
            'fontfamily': options.fontfamily,
            'mainfont': 'Times New Roman',  # Fallback font
            'colorlinks': True,
            'linkcolor': 'blue',
            'urlcolor': 'blue',
            'lang': article.language or 'en-US',
        }
        
        # Only add columns variable if > 1 (for LaTeX template conditional)
        if options.columns > 1:
            metadata['columns'] = options.columns
        
        # Add template-specific settings
        if template_config:
            metadata.update(template_config)
        
        # Add LaTeX packages for multi-column support
        header_includes = [
            '\\usepackage{multicol}',
            '\\usepackage{graphicx}',
            '\\usepackage{float}',
            '\\usepackage{fancyhdr}',
            '\\usepackage{geometry}',
        ]
        
        # Multi-column specific settings
        if options.columns > 1:
            header_includes.extend([
                f'\\setlength{{\\columnsep}}{{1cm}}',
                f'\\setlength{{\\columnseprule}}{{0pt}}',
            ])
        
        metadata['header-includes'] = header_includes
        
        # Page style settings
        if article.title:
            metadata['header-left'] = article.title[:50] + ('...' if len(article.title) > 50 else '')
            metadata['header-right'] = '\\thepage'
        
        return metadata
    
    def _format_markdown_document(self, article: Article, metadata: Dict[str, Any]) -> str:
        """
        Format the complete markdown document with frontmatter.
        
        Args:
            article: Article object
            metadata: Document metadata
            
        Returns:
            Complete markdown document
        """
        # Convert metadata to YAML frontmatter
        yaml_metadata = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
        
        # Build document sections
        sections = []
        
        # Add article metadata as subtitle if available
        if article.author or article.date:
            subtitle_parts = []
            if article.author:
                subtitle_parts.append(f"By {article.author}")
            if article.date:
                subtitle_parts.append(article.formatted_date)
            
            if subtitle_parts:
                sections.append(f"*{' • '.join(subtitle_parts)}*\n")
        
        # Add description if available
        if article.description and article.description != article.title:
            sections.append(f"*{article.description}*\n")
        
        # Add main content
        sections.append(article.content)
        
        # Add reading information
        if article.word_count and article.word_count > 0:
            reading_time = article.reading_time_minutes
            word_info = f"\n---\n\n*Word count: {article.word_count:,}"
            if reading_time > 0:
                word_info += f" • Estimated reading time: {reading_time} minute{'s' if reading_time != 1 else ''}*"
            else:
                word_info += "*"
            sections.append(word_info)
        
        # Add source URL if available
        if article.url:
            sections.append(f"\n*Source: {article.url}*")
        
        # Combine all sections
        document_body = '\n\n'.join(sections)
        
        # Create complete document
        return f"---\n{yaml_metadata}---\n\n{document_body}"
    
    def _process_article_images(self, article: Article, temp_path: Path) -> List:
        """
        Process and prepare images for PDF inclusion.
        
        Args:
            article: Article object
            temp_path: Temporary directory path
            
        Returns:
            List of processed ImageInfo objects
        """
        if not article.images:
            return []
        
        # Use local tmp_images directory instead of temp directory
        images_dir = Path.cwd() / 'tmp_images'
        images_dir.mkdir(exist_ok=True)
        
        # Use image processor to download and optimize images
        try:
            from ..extractors.image_extractor import get_image_extractor
            from .image_processor import get_image_processor
            
            # Extract image info
            extractor = get_image_extractor()
            image_infos = extractor.extract_images_from_article(article)
            
            # Process images
            processor = get_image_processor()
            processed_images = processor.process_images(image_infos, str(images_dir))
            
            print(f"Processed {len(processed_images)} images for PDF inclusion")
            print(f"Images saved to: {images_dir}")
            
            return processed_images
            
        except Exception as e:
            print(f"Warning: Image processing failed: {e}")
            # Continue without images rather than failing completely
            return []
    
    def _update_article_with_local_images(self, article: Article, processed_images: List) -> Article:
        """
        Update the article object to include processed local images.
        
        Args:
            article: Article object
            processed_images: List of processed ImageInfo objects
            
        Returns:
            Updated article object with local image references inserted
        """
        if not processed_images:
            return article
        
        # Create a copy of the article to avoid modifying the original
        from copy import deepcopy
        updated_article = deepcopy(article)
        
        # Filter to only valid images with local paths
        valid_images = [img for img in processed_images if img.is_valid and img.local_path]
        
        if not valid_images:
            return updated_article
        
        # Prepare image markdown references
        image_refs = []
        for img_info in valid_images:
            # Create relative path from current working directory
            local_filename = Path(img_info.local_path).name
            local_path = f"tmp_images/{local_filename}"
            
            # Create markdown image syntax
            alt_text = img_info.alt_text or "Article image"
            caption = img_info.caption or ""
            
            if caption and caption != alt_text:
                # Use figure syntax with caption
                image_md = f"![{alt_text}]({local_path})\n*{caption}*"
            else:
                image_md = f"![{alt_text}]({local_path})"
            
            image_refs.append(image_md)
        
        # Insert images into the content
        content = updated_article.content
        lines = content.split('\n')
        
        # Find a good insertion point - after the first few paragraphs or heading
        insertion_point = 0
        lines_seen = 0
        
        for i, line in enumerate(lines):
            if line.strip():
                lines_seen += 1
                # Insert after 2-3 content lines to put images near the beginning
                # but after the intro/title
                if lines_seen >= 3:
                    insertion_point = i + 1
                    break
        
        # If we didn't find a good spot, insert after the title/heading
        if insertion_point == 0:
            for i, line in enumerate(lines):
                if line.strip().startswith('#') or (line.strip() and len(line.strip()) > 20):
                    insertion_point = i + 1
                    break
        
        # Insert all images at the determined point
        if image_refs:
            images_section = '\n\n' + '\n\n'.join(image_refs) + '\n\n'
            lines.insert(insertion_point, images_section)
        
        updated_article.content = '\n'.join(lines)
        return updated_article
    
    def _determine_output_path(self, output_option: Optional[str], article: Article) -> str:
        """
        Determine the output file path for the PDF.
        
        Args:
            output_option: User-specified output path
            article: Article object
            
        Returns:
            Output file path
        """
        if output_option:
            output_path = Path(output_option)
            if output_path.suffix.lower() != '.pdf':
                output_path = output_path.with_suffix('.pdf')
            return str(output_path.resolve())
        
        # Generate filename from article title
        if article.title:
            # Clean title for filename
            clean_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_title = clean_title.replace(' ', '_')[:50]  # Limit length
        else:
            clean_title = "article"
        
        # Add timestamp to prevent overwrites
        timestamp = int(time.time())
        filename = f"{clean_title}_{timestamp}.pdf"
        
        return str(Path.cwd() / filename)
    
    def _build_pandoc_command(self, markdown_file: Path, output_path: str, 
                             options: ConversionOptions, temp_path: Path) -> List[str]:
        """
        Build the Pandoc command line arguments.
        
        Args:
            markdown_file: Path to markdown input file
            output_path: Output PDF path
            options: Conversion options
            temp_path: Temporary directory path
            
        Returns:
            List of command arguments
        """
        args = [
            'pandoc',
            str(markdown_file),
            '--from', 'markdown',
            '--to', 'pdf',
            '--pdf-engine', options.pdf_engine,
            '--output', output_path,
        ]
        
        # Add template if available
        template_path = self.templates_dir / f'{options.template}.latex'
        if template_path.exists():
            args.extend(['--template', str(template_path)])
        
        # Add filters if available
        filters_dir = self.templates_dir
        
        # Column filter for multi-column support
        if options.columns > 1:
            columns_filter = filters_dir / 'columns.lua'
            if columns_filter.exists():
                args.extend(['--lua-filter', str(columns_filter)])
        
        # Resource path - tell Pandoc where to find images in the current working directory
        images_dir = Path.cwd() / 'tmp_images'
        if images_dir.exists() and list(images_dir.glob('*')):
            # Use resource-path to help Pandoc find images in current directory
            args.extend(['--resource-path', str(Path.cwd())])
            print(f"Using resource path: {Path.cwd()}")
        
        # Standard Pandoc options
        if self.default_pandoc_options.get('standalone', True):
            args.append('--standalone')
        
        if self.default_pandoc_options.get('toc', False):
            args.append('--toc')
        
        if self.default_pandoc_options.get('number_sections', False):
            args.append('--number-sections')
        
        # Highlight style for code blocks
        highlight_style = self.default_pandoc_options.get('highlight_style', 'kate')
        args.extend(['--highlight-style', highlight_style])
        
        # Additional LaTeX variables
        variables = [
            f'fontsize={options.font_size}',
            f'fontfamily={options.fontfamily}',
            'linkcolor=blue',
            'urlcolor=blue',
            'colorlinks=true',
            'lang=en',  # Set default language to English
            'babel-lang=english',  # Set babel language
        ]
        
        for variable in variables:
            args.extend(['--variable', variable])
        
        # Verbose output for debugging
        args.append('--verbose')
        
        return args
    
    def _execute_pandoc(self, args: List[str], timeout: int, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        """
        Execute Pandoc command with proper error handling.
        
        Args:
            args: Pandoc command arguments
            timeout: Execution timeout in seconds
            cwd: Working directory for the command (default: current directory)
            
        Returns:
            Completed process result
        """
        try:
            print(f"Executing Pandoc: {' '.join(args[:5])}...")  # Show first few args
            
            # Use provided working directory or default to current directory
            working_dir = Path(cwd) if cwd else Path.cwd()
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir
            )
            
            if result.returncode != 0:
                error_output = result.stderr or result.stdout or "Unknown error"
                raise Exception(f"Pandoc failed with exit code {result.returncode}: {error_output}")
            
            return result
            
        except subprocess.TimeoutExpired:
            raise Exception(f"PDF generation timed out after {timeout} seconds")
        except Exception as e:
            raise Exception(f"Pandoc execution failed: {str(e)}")
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of available LaTeX templates.
        
        Returns:
            List of template information dictionaries
        """
        templates = []
        
        if not self.templates_dir.exists():
            return templates
        
        for template_file in self.templates_dir.glob('*.latex'):
            template_name = template_file.stem
            template_config = self.config.get_template_config(template_name)
            
            template_info = {
                'name': template_name,
                'file': str(template_file),
                'description': template_config.get('description', f'{template_name.title()} template'),
                'config': template_config
            }
            
            templates.append(template_info)
        
        return templates
    
    def validate_options(self, options: ConversionOptions) -> Tuple[bool, List[str]]:
        """
        Validate conversion options.
        
        Args:
            options: Conversion options to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Validate PDF engine
        if options.pdf_engine not in self.supported_engines:
            issues.append(f"Unsupported PDF engine: {options.pdf_engine}")
        
        # Validate columns
        if not 1 <= options.columns <= 3:
            issues.append("Columns must be between 1 and 3")
        
        # Validate font size
        if not options.font_size.endswith('pt'):
            issues.append("Font size must end with 'pt'")
        else:
            try:
                size = int(options.font_size[:-2])
                if not 8 <= size <= 24:
                    issues.append("Font size must be between 8pt and 24pt")
            except ValueError:
                issues.append("Invalid font size format")
        
        # Validate timeout
        if not 10 <= options.timeout <= 600:  # 10 seconds to 10 minutes
            issues.append("Timeout must be between 10 and 600 seconds")
        
        # Validate template
        template_path = self.templates_dir / f'{options.template}.latex'
        if not template_path.exists():
            available_templates = [t['name'] for t in self.get_available_templates()]
            if available_templates:
                issues.append(f"Template '{options.template}' not found. Available: {', '.join(available_templates)}")
            else:
                issues.append("No LaTeX templates found")
        
        return len(issues) == 0, issues
    
    def get_pandoc_info(self) -> Dict[str, Any]:
        """
        Get information about Pandoc installation.
        
        Returns:
            Dictionary with Pandoc information
        """
        try:
            # Get Pandoc version
            result = subprocess.run(
                ['pandoc', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            version_info = result.stdout.split('\n')[0] if result.returncode == 0 else "Unknown"
            
            # Check LaTeX engines
            engines = {}
            for engine in self.supported_engines:
                try:
                    engine_result = subprocess.run(
                        [engine, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    engines[engine] = engine_result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    engines[engine] = False
            
            return {
                'pandoc_version': version_info,
                'pandoc_available': result.returncode == 0,
                'engines': engines,
                'default_engine': self.default_engine,
                'templates_dir': str(self.templates_dir),
                'available_templates': [t['name'] for t in self.get_available_templates()]
            }
            
        except Exception as e:
            return {
                'error': f"Failed to get Pandoc info: {str(e)}",
                'pandoc_available': False
            }


# Global instance
_pandoc_runner = None


def get_pandoc_runner() -> PandocRunner:
    """Get the global Pandoc runner instance."""
    global _pandoc_runner
    if _pandoc_runner is None:
        _pandoc_runner = PandocRunner()
    return _pandoc_runner


def generate_pdf(article: Article, options: ConversionOptions) -> str:
    """
    Convenience function to generate PDF from article.
    
    Args:
        article: Article to convert
        options: Conversion options
        
    Returns:
        Path to generated PDF
    """
    runner = get_pandoc_runner()
    return runner.convert_to_pdf(article, options) 