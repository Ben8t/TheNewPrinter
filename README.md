# 📰 New Printer

Transform web articles into beautifully formatted PDFs with classic magazine styling.

A lightweight CLI tool with optional web interface that converts web articles into print-ready PDFs using pandoc's robust document conversion pipeline - bringing the classic magazine aesthetic to digital content.

## ✨ Features

- **Simple & Fast**: Minimal dependencies, maximum performance
- **Beautiful Output**: Professional typography with LaTeX backend
- **Flexible Layouts**: Single, double, or triple column formats
- **Multiple Templates**: Article, academic, and magazine styles
- **Smart Extraction**: Trafilatura with readability fallback
- **Image Processing**: Automatic optimization for print
- **Web Interface**: Optional FastAPI server for browser-based conversion
- **Batch Processing**: Convert multiple articles at once

## 🚀 Quick Start

### One-time Use (No Installation)

```bash
# Convert a single article
uvx new-printer https://example.com/article

# With custom options
uvx new-printer https://example.com/article \
  --columns 2 \
  --font-size 11pt \
  --template magazine \
  --output article.pdf
```

### Installation

#### Prerequisites

**Required:**
- Python 3.8+
- [Pandoc](https://pandoc.org/installing.html) 3.0+
- LaTeX distribution (TeX Live recommended)

**Optional:**
- [uv](https://docs.astral.sh/uv/) (recommended for installation)

#### Install with uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install new-printer as a tool
uv tool install new-printer

# Or run without installing
uvx new-printer --help
```

#### Install with pip

```bash
pip install new-printer
```

#### System Dependencies

**macOS:**
```bash
brew install pandoc
brew install --cask mactex  # Or mactex-no-gui for smaller install
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install pandoc texlive-latex-recommended texlive-latex-extra
```

**Windows:**
- Install [Pandoc](https://pandoc.org/installing.html)
- Install [MiKTeX](https://miktex.org/) or [TeX Live](https://tug.org/texlive/)

## 📖 Usage

### Command Line Interface

#### Basic Conversion

```bash
# Convert article with defaults (2 columns, 11pt font)
new-printer https://longform.aeon.co/essays/future-of-work

# Specify output file
new-printer https://example.com/article --output my-article.pdf
```

#### Formatting Options

```bash
# Single column layout
new-printer https://example.com/article --columns 1

# Magazine style with 3 columns
new-printer https://example.com/article \
  --columns 3 \
  --template magazine \
  --font-size 10pt

# Academic paper format
new-printer https://example.com/article \
  --template academic \
  --font-size 12pt \
  --columns 1
```

#### Batch Processing

```bash
# Create a file with URLs
echo "https://site1.com/article1" > urls.txt
echo "https://site2.com/article2" >> urls.txt

# Convert all articles
new-printer --batch urls.txt --output-dir ./articles
```

#### Web Interface

```bash
# Start web server
new-printer serve --port 3000

# Then open http://localhost:3000 in your browser
```

### Available Templates

- **article**: Clean, readable layout (default)
- **magazine**: New Yorker-style multi-column format
- **academic**: Academic paper styling with larger margins

### Configuration

Create a configuration file to set your preferred defaults:

```bash
# Copy the template
cp new_printer/templates/config.yaml ~/.new-printer.yml

# Edit with your preferences
editor ~/.new-printer.yml
```

Example configuration:
```yaml
default:
  columns: 2
  font_size: "11pt"
  template: "magazine"
  output_dir: "~/Documents/Articles"
  include_images: true
```

## 🏗️ Architecture

```
Web Article → Content Extraction → Markdown → Pandoc → LaTeX → PDF
              (Trafilatura)                   (Filters)  (Templates)
```

### Core Components

- **Extractors**: Trafilatura (primary) + Readability (fallback)
- **Processors**: Markdown conversion, image optimization
- **Templates**: Custom LaTeX templates with multi-column support
- **CLI**: Click-based interface with rich output
- **Web UI**: Optional FastAPI server

## 🔧 Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/new-printer.git
cd new-printer

# Install development dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=new_printer
```

### Code Quality

```bash
# Format code
black new_printer tests

# Lint code
flake8 new_printer tests

# Type checking
mypy new_printer
```

## 📝 Examples

### Article Extraction

```python
from new_printer.extractors.trafilatura_extractor import TrafilaturaExtractor

extractor = TrafilaturaExtractor()
article = extractor.extract("https://example.com/article")
print(f"Title: {article.title}")
print(f"Author: {article.author}")
```

### PDF Generation

```python
from new_printer.processors.pandoc_runner import PandocRunner

runner = PandocRunner()
pdf_path = runner.convert_to_pdf(article, {
    "columns": 2,
    "template": "magazine",
    "output": "article.pdf"
})
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Pandoc](https://pandoc.org/) for excellent document conversion
- [Trafilatura](https://trafilatura.readthedocs.io/) for reliable content extraction
- [LaTeX](https://www.latex-project.org/) for beautiful typography
- Inspired by classic magazine and newspaper layouts

## 🔗 Links

- [Documentation](https://github.com/yourusername/new-printer/wiki)
- [Issue Tracker](https://github.com/yourusername/new-printer/issues)
- [Changelog](https://github.com/yourusername/new-printer/releases)

---

**New Printer** - Because sometimes the best way to read online is offline. 📰✨ 