#!/usr/bin/env python3
"""
FastAPI web server for New Printer web interface.

This module provides a modern web interface for converting articles to PDFs,
including real-time conversion status, file upload for batch processing,
and configuration management.
"""

import os
import tempfile
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
import mimetypes
import time

from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl

from ..extractors.extractor_factory import ExtractorFactory
from ..processors.pandoc_runner import PandocRunner
from ..models import ConversionOptions, ExtractionResult
from ..config import Config
from ..utils import sanitize_filename, generate_unique_filename


class ConversionRequest(BaseModel):
    """Request model for article conversion."""
    url: HttpUrl
    columns: int = 2
    font_size: str = "11pt"
    template: str = "magazine"
    include_images: bool = True
    margins: str = "2cm"
    font_family: str = "times"


class ConversionResponse(BaseModel):
    """Response model for conversion results."""
    success: bool
    message: str
    download_url: Optional[str] = None
    article_title: Optional[str] = None
    word_count: Optional[int] = None
    processing_time: Optional[float] = None


class BatchConversionRequest(BaseModel):
    """Request model for batch conversion."""
    urls: List[str]
    columns: int = 2
    font_size: str = "11pt"
    template: str = "magazine"
    include_images: bool = True


# Global storage for conversion status
conversion_status: Dict[str, Dict[str, Any]] = {}


def create_app(config: Optional[Config] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        config: Application configuration
        
    Returns:
        Configured FastAPI application
    """
    if config is None:
        from ..config import get_config
        config = get_config()
    
    app = FastAPI(
        title="New Printer Web Interface",
        description="Transform web articles into print-ready PDFs",
        version="1.0.0"
    )
    
    # Setup static files and templates
    static_dir = Path(__file__).parent / "static"
    templates_dir = Path(__file__).parent / "templates"
    
    # Create directories if they don't exist
    static_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Setup templates
    templates = Jinja2Templates(directory=str(templates_dir))
    
    # Store config in app state
    app.state.config = config
    app.state.temp_files = {}  # Track temporary files for cleanup
    
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Main interface page."""
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "New Printer"
        })
    
    @app.post("/api/convert", response_model=ConversionResponse)
    async def convert_article(
        background_tasks: BackgroundTasks,
        url: str = Form(...),
        columns: int = Form(2),
        font_size: str = Form("11pt"),
        template: str = Form("magazine"),
        include_images: bool = Form(True),
        margins: str = Form("2cm"),
        font_family: str = Form("times")
    ):
        """Convert a single article to PDF."""
        
        import time
        import uuid
        
        start_time = time.time()
        conversion_id = str(uuid.uuid4())
        
        try:
            # Validate parameters
            if columns not in [1, 2, 3]:
                raise HTTPException(status_code=400, detail="Columns must be 1, 2, or 3")
            
            if font_size not in ["9pt", "10pt", "11pt", "12pt", "14pt"]:
                raise HTTPException(status_code=400, detail="Invalid font size")
            
            if template not in ["article", "magazine"]:
                raise HTTPException(status_code=400, detail="Invalid template")
            
            # Update conversion status
            conversion_status[conversion_id] = {
                "status": "extracting",
                "message": "Extracting article content...",
                "progress": 25
            }
            
            # Extract article content
            factory = ExtractorFactory(app.state.config)
            result: ExtractionResult = factory.extract(url)
            
            if not result.success:
                raise HTTPException(status_code=400, detail=f"Failed to extract article: {result.error_message}")
            
            article = result.article
            
            # Update status
            conversion_status[conversion_id] = {
                "status": "converting",
                "message": f"Converting '{article.title[:50]}...' to PDF",
                "progress": 75
            }
            
            # Build conversion options
            options = ConversionOptions(
                columns=columns,
                font_size=font_size,
                template=template,
                include_images=include_images,
                margins=margins,
                fontfamily=font_family,
                timeout=120
            )
            
            # Generate PDF
            runner = PandocRunner()  # Fixed: removed app.state.config parameter
            
            # Create temporary file for PDF
            temp_dir = Path(tempfile.gettempdir()) / "new_printer_web"
            temp_dir.mkdir(exist_ok=True)
            
            safe_title = sanitize_filename(article.title[:50])
            pdf_filename = f"{safe_title}_{conversion_id[:8]}.pdf"
            temp_pdf_path = temp_dir / pdf_filename
            
            options.output = str(temp_pdf_path)
            
            pdf_path = runner.convert_to_pdf(article, options)
            
            # Store file reference for later cleanup
            app.state.temp_files[conversion_id] = {
                "path": pdf_path,
                "filename": f"{safe_title}.pdf",
                "created": time.time()
            }
            
            # Schedule cleanup after 1 hour
            background_tasks.add_task(cleanup_temp_file, conversion_id, 3600)
            
            processing_time = time.time() - start_time
            
            # Update final status
            conversion_status[conversion_id] = {
                "status": "completed",
                "message": "PDF generated successfully",
                "progress": 100
            }
            
            return ConversionResponse(
                success=True,
                message="Article converted successfully",
                download_url=f"/api/download/{conversion_id}",
                article_title=article.title,
                word_count=article.word_count,
                processing_time=processing_time
            )
            
        except HTTPException:
            raise
        except Exception as e:
            conversion_status[conversion_id] = {
                "status": "error",
                "message": str(e),
                "progress": 0
            }
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/status/{conversion_id}")
    async def get_conversion_status(conversion_id: str):
        """Get conversion status for real-time updates."""
        status = conversion_status.get(conversion_id, {
            "status": "not_found",
            "message": "Conversion not found",
            "progress": 0
        })
        return status
    
    @app.get("/api/download/{conversion_id}")
    async def download_pdf(conversion_id: str):
        """Download generated PDF file."""
        
        if conversion_id not in app.state.temp_files:
            raise HTTPException(status_code=404, detail="File not found or expired")
        
        file_info = app.state.temp_files[conversion_id]
        pdf_path = Path(file_info["path"])
        
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=str(pdf_path),
            filename=file_info["filename"],
            media_type="application/pdf"
        )
    
    @app.post("/api/batch-convert")
    async def batch_convert_articles(
        background_tasks: BackgroundTasks,
        urls_file: UploadFile = File(...),
        columns: int = Form(2),
        font_size: str = Form("11pt"),
        template: str = Form("magazine"),
        include_images: bool = Form(True)
    ):
        """Process multiple URLs from uploaded file."""
        
        import uuid
        import zipfile
        
        batch_id = str(uuid.uuid4())
        
        try:
            # Validate file type
            if not urls_file.filename.endswith(('.txt', '.csv')):
                raise HTTPException(status_code=400, detail="File must be .txt or .csv")
            
            # Read URLs from file
            content = await urls_file.read()
            urls_text = content.decode('utf-8')
            
            urls = []
            for line in urls_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
            
            if not urls:
                raise HTTPException(status_code=400, detail="No valid URLs found in file")
            
            # Start batch processing in background
            background_tasks.add_task(
                process_batch_conversion,
                batch_id, urls, columns, font_size, template, include_images
            )
            
            return {
                "success": True,
                "batch_id": batch_id,
                "total_urls": len(urls),
                "status_url": f"/api/batch-status/{batch_id}"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/batch-status/{batch_id}")
    async def get_batch_status(batch_id: str):
        """Get batch conversion status."""
        status = conversion_status.get(f"batch_{batch_id}", {
            "status": "not_found",
            "message": "Batch not found",
            "progress": 0,
            "completed": 0,
            "total": 0,
            "failed": 0
        })
        return status
    
    @app.get("/api/batch-download/{batch_id}")
    async def download_batch_results(batch_id: str):
        """Download batch results as ZIP file."""
        
        batch_key = f"batch_{batch_id}"
        if batch_key not in app.state.temp_files:
            raise HTTPException(status_code=404, detail="Batch results not found or expired")
        
        file_info = app.state.temp_files[batch_key]
        zip_path = Path(file_info["path"])
        
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="Batch results file not found")
        
        return FileResponse(
            path=str(zip_path),
            filename=file_info["filename"],
            media_type="application/zip"
        )
    
    @app.get("/api/templates")
    async def get_available_templates():
        """Get list of available LaTeX templates."""
        try:
            runner = PandocRunner()  # Fixed: removed app.state.config parameter
            templates = runner.get_available_templates()
            
            template_info = []
            for name, path in templates.items():
                description = {
                    'article': 'Clean article layout with professional typography',
                    'magazine': 'New Yorker-style magazine layout with elegant design'
                }.get(name, 'Custom template')
                
                template_info.append({
                    "name": name,
                    "description": description,
                    "path": str(path)
                })
            
            return {"templates": template_info}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving templates: {e}")
    
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        try:
            # Check if Pandoc is available
            runner = PandocRunner()  # Fixed: removed app.state.config parameter
            pandoc_info = runner.get_pandoc_info()
            
            return {
                "status": "healthy",
                "pandoc_version": pandoc_info.get("version", "unknown"),
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def cleanup_temp_file(conversion_id: str, delay: int):
        """Clean up temporary files after delay."""
        await asyncio.sleep(delay)
        
        if conversion_id in app.state.temp_files:
            file_info = app.state.temp_files[conversion_id]
            try:
                Path(file_info["path"]).unlink(missing_ok=True)
            except Exception:
                pass  # Ignore cleanup errors
            
            del app.state.temp_files[conversion_id]
        
        # Also clean up conversion status
        if conversion_id in conversion_status:
            del conversion_status[conversion_id]
    
    async def process_batch_conversion(
        batch_id: str, urls: List[str], columns: int, 
        font_size: str, template: str, include_images: bool
    ):
        """Process batch conversion in background."""
        
        import time
        import zipfile
        
        batch_key = f"batch_{batch_id}"
        total_urls = len(urls)
        completed = 0
        failed = 0
        
        # Initialize batch status
        conversion_status[batch_key] = {
            "status": "processing",
            "message": "Processing batch conversion...",
            "progress": 0,
            "completed": 0,
            "total": total_urls,
            "failed": 0
        }
        
        # Create temporary directory for batch results
        temp_dir = Path(tempfile.gettempdir()) / "new_printer_batch" / batch_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        factory = ExtractorFactory(app.state.config)
        runner = PandocRunner()  # Fixed: removed app.state.config parameter
        
        options = ConversionOptions(
            columns=columns,
            font_size=font_size,
            template=template,
            include_images=include_images,
            margins="2cm",
            fontfamily="times",
            timeout=120
        )
        
        successful_files = []
        
        for i, url in enumerate(urls):
            try:
                # Update progress
                progress = int((i / total_urls) * 100)
                conversion_status[batch_key].update({
                    "progress": progress,
                    "message": f"Processing {i+1}/{total_urls}: {url[:50]}...",
                    "completed": completed,
                    "failed": failed
                })
                
                # Extract and convert
                result = factory.extract(url)
                if not result.success:
                    failed += 1
                    continue
                
                article = result.article
                safe_title = sanitize_filename(f"{i+1:03d}_{article.title[:50]}")
                pdf_path = temp_dir / f"{safe_title}.pdf"
                
                options.output = str(pdf_path)
                runner.convert_to_pdf(article, options)
                
                successful_files.append(pdf_path)
                completed += 1
                
            except Exception:
                failed += 1
                continue
        
        # Create ZIP file with results
        if successful_files:
            zip_path = temp_dir.parent / f"batch_{batch_id}_results.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pdf_path in successful_files:
                    zipf.write(pdf_path, pdf_path.name)
            
            # Store ZIP file reference
            app.state.temp_files[batch_key] = {
                "path": str(zip_path),
                "filename": f"batch_results_{batch_id[:8]}.zip",
                "created": time.time()
            }
        
        # Update final status
        conversion_status[batch_key].update({
            "status": "completed" if successful_files else "failed",
            "message": f"Batch completed: {completed} successful, {failed} failed",
            "progress": 100,
            "completed": completed,
            "failed": failed,
            "download_url": f"/api/batch-download/{batch_id}" if successful_files else None
        })
        
        # Schedule cleanup
        asyncio.create_task(cleanup_batch_files(batch_id, temp_dir, 3600))
    
    async def cleanup_batch_files(batch_id: str, temp_dir: Path, delay: int):
        """Clean up batch processing files."""
        await asyncio.sleep(delay)
        
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Clean up ZIP file
            batch_key = f"batch_{batch_id}"
            if batch_key in app.state.temp_files:
                file_info = app.state.temp_files[batch_key]
                Path(file_info["path"]).unlink(missing_ok=True)
                del app.state.temp_files[batch_key]
            
            # Clean up status
            if batch_key in conversion_status:
                del conversion_status[batch_key]
                
        except Exception:
            pass  # Ignore cleanup errors
    
    return app


if __name__ == "__main__":
    import uvicorn
    
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=3000) 