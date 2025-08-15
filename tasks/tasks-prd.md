## Relevant Files

- `new_printer/__init__.py` - Main package initialization file
- `new_printer/cli.py` - Main CLI entry point with Click commands
- `new_printer/extractors/__init__.py` - Extractors package initialization
- `new_printer/extractors/trafilatura_extractor.py` - Primary content extractor using Trafilatura
- `new_printer/extractors/readability_fallback.py` - Fallback extractor using readability-lxml
- `new_printer/processors/__init__.py` - Processors package initialization
- `new_printer/processors/markdown_converter.py` - HTML to Markdown conversion
- `new_printer/processors/image_processor.py` - Image optimization and processing
- `new_printer/processors/pandoc_runner.py` - Pandoc execution wrapper for PDF generation
- `new_printer/models.py` - Data models for Article and other core structures
- `new_printer/config.py` - Configuration management
- `new_printer/templates/article.latex` - Custom LaTeX template for clean article layout
- `new_printer/templates/magazine.latex` - New Yorker-style magazine template
- `new_printer/templates/columns.lua` - Pandoc Lua filter for multi-column support
- `new_printer/templates/config.yaml` - Default configuration settings
- `web_ui/__init__.py` - Web UI package initialization
- `web_ui/server.py` - FastAPI server for optional web interface
- `web_ui/static/` - Static files directory for web UI
- `web_ui/templates/` - HTML templates directory for web UI
- `setup.py` - Package setup configuration
- `pyproject.toml` - Modern Python project configuration with dependencies
- `requirements.txt` - Python package dependencies
- `README.md` - Project documentation and usage instructions
- `install.sh` - System setup script for prerequisites
- `tests/test_extractors.py` - Unit tests for content extractors
- `tests/test_processors.py` - Unit tests for document processors
- `tests/test_cli.py` - Unit tests for CLI interface
- `tests/test_web_ui.py` - Unit tests for web interface

### Notes

- Unit tests should typically be placed alongside the code files they are testing (e.g., `trafilatura_extractor.py` and `trafilatura_extractor.test.py` in the same directory).
- Use `npx jest [optional/path/to/test/file]` to run tests. Running without a path executes all tests found by the Jest configuration.

## Tasks

- [x] 1.0 Project Structure and Configuration Setup
  - [x] 1.1 Create project directory structure with new_printer, web_ui, tests, and templates folders
  - [x] 1.2 Set up pyproject.toml with all required dependencies and metadata
  - [x] 1.3 Create setup.py for backward compatibility
  - [x] 1.4 Set up requirements.txt for development dependencies
  - [x] 1.5 Create __init__.py files for all Python packages
  - [x] 1.6 Set up configuration management system with config.py
  - [x] 1.7 Create default configuration file templates/config.yaml
  - [x] 1.8 Set up basic project README.md with installation and usage instructions

- [x] 2.0 Core Content Extraction System
  - [x] 2.1 Create Article data model in models.py with title, content, author, date, and images fields
  - [x] 2.2 Implement TrafilaturaExtractor class for primary content extraction
  - [x] 2.3 Implement ReadabilityFallback extractor for backup content extraction
  - [x] 2.4 Create extractor factory pattern to choose between extractors
  - [x] 2.5 Add URL validation and error handling for extraction failures
  - [x] 2.6 Implement content cleaning and preprocessing logic
  - [x] 2.7 Add support for extracting and cataloging images from articles

- [x] 3.0 Document Processing and PDF Generation Pipeline
  - [x] 3.1 Create MarkdownConverter class to convert HTML content to clean Markdown
  - [x] 3.2 Implement ImageProcessor for downloading, optimizing, and resizing images
  - [x] 3.3 Create PandocRunner class with PDF generation using LaTeX backend
  - [x] 3.4 Design and implement article.latex template for clean article layout
  - [x] 3.5 Design and implement magazine.latex template for New Yorker-style layout
  - [x] 3.6 Create columns.lua Pandoc filter for multi-column support
  - [x] 3.7 Add metadata handling for YAML frontmatter in Markdown files
  - [x] 3.8 Implement error handling and timeout management for Pandoc execution
  - [x] 3.9 Add support for multiple output formats and template selection

- [x] 4.0 CLI Interface Implementation
  - [x] 4.1 Set up Click framework and create main CLI entry point
  - [x] 4.2 Implement 'convert' command with URL argument and formatting options
  - [x] 4.3 Add command-line options for columns, font size, template, and output path
  - [x] 4.4 Implement 'serve' command to start the optional web interface
  - [x] 4.5 Add batch processing functionality for multiple URLs from file
  - [x] 4.6 Implement rich console output with progress indicators and status messages
  - [x] 4.7 Add configuration file loading and command-line option overrides
  - [x] 4.8 Create comprehensive help documentation and examples

- [ ] 5.0 Optional Web Interface Development
  - [ ] 5.1 Set up FastAPI application structure with create_app factory
  - [ ] 5.2 Create main HTML interface with form for URL input and options
  - [ ] 5.3 Implement /convert POST endpoint for processing article URLs
  - [ ] 5.4 Add file download functionality for generated PDFs
  - [ ] 5.5 Create responsive CSS styling for clean, magazine-like web interface
  - [ ] 5.6 Add JavaScript for form handling and progress feedback
  - [ ] 5.7 Implement error handling and user feedback for failed conversions
  - [ ] 5.8 Set up static file serving for CSS, JavaScript, and assets 