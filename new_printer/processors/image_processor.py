"""
Image processing for new-printer.

This module provides comprehensive image downloading, optimization, and
resizing functionality for preparing images for PDF generation.
"""

import os
import io
import hashlib
import mimetypes
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import tempfile
import requests
from requests.exceptions import RequestException
from PIL import Image, ImageOps, ImageFilter

from ..models import Article
from ..extractors.image_extractor import ImageInfo
from ..config import get_config


class ImageProcessor:
    """
    Comprehensive image processor for PDF generation.
    
    Handles downloading, optimization, resizing, and format conversion
    of images for optimal inclusion in PDFs.
    """
    
    def __init__(self):
        """Initialize the image processor."""
        self.config = get_config()
        self.extractor_config = self.config.get_extractor_config()
        
        # Image processing settings
        self.max_width = 1200      # Max width for 2-column layout at 300 DPI
        self.max_height = 1600     # Max height for A4 page
        self.min_width = 100       # Minimum usable width
        self.min_height = 100      # Minimum usable height
        self.jpeg_quality = 85     # JPEG compression quality
        self.png_optimize = True   # Enable PNG optimization
        self.max_file_size = 5 * 1024 * 1024  # 5MB limit for processed images
        
        # Output formats (in order of preference)
        self.preferred_formats = ['JPEG', 'PNG', 'WEBP']
        
        # Session for downloading
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.extractor_config.get('user_agent', 'new-printer/1.0.0'),
            'Accept': 'image/*,*/*;q=0.8',
        })
    
    def process_images(self, images: List[ImageInfo], output_dir: str, 
                      target_width: Optional[int] = None) -> List[ImageInfo]:
        """
        Process a list of images for PDF generation.
        
        Args:
            images: List of ImageInfo objects to process
            output_dir: Directory to save processed images
            target_width: Target width for resizing (uses default if None)
            
        Returns:
            List of processed ImageInfo objects with local paths
        """
        if not images:
            return []
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        processed_images = []
        
        for i, image_info in enumerate(images):
            try:
                # Download and process the image
                processed_info = self._download_and_process_image(
                    image_info, output_dir, target_width, index=i
                )
                
                if processed_info and processed_info.local_path:
                    processed_images.append(processed_info)
                    
            except Exception as e:
                print(f"Failed to process image {image_info.url}: {e}")
                # Mark as invalid but keep in list for reference
                image_info.is_valid = False
                image_info.error_message = f"Processing failed: {str(e)}"
                processed_images.append(image_info)
        
        return processed_images
    
    def _download_and_process_image(self, image_info: ImageInfo, output_dir: str,
                                   target_width: Optional[int] = None, 
                                   index: int = 0) -> Optional[ImageInfo]:
        """
        Download and process a single image.
        
        Args:
            image_info: ImageInfo object
            output_dir: Output directory
            target_width: Target width for resizing
            index: Image index for filename generation
            
        Returns:
            Processed ImageInfo object or None if failed
        """
        try:
            # Download the image
            image_data = self._download_image(image_info.url)
            if not image_data:
                image_info.is_valid = False
                image_info.error_message = "Failed to download image"
                return image_info
            
            # Open and process the image
            with Image.open(io.BytesIO(image_data)) as img:
                # Store original format before processing
                original_format = img.format or 'JPEG'  # Default to JPEG if format is None
                
                # Process the image
                processed_img = self._process_image(img, target_width)
                
                if not processed_img:
                    image_info.is_valid = False
                    image_info.error_message = "Image processing failed"
                    return image_info
                
                # Set format on processed image since it gets lost during processing
                processed_img.format = original_format
                
                # Generate filename
                filename = self._generate_filename(image_info.url, processed_img.format, index)
                local_path = os.path.join(output_dir, filename)
                
                # Save the processed image
                self._save_image(processed_img, local_path)
                
                # Update image info
                image_info.local_path = local_path
                image_info.width = processed_img.width
                image_info.height = processed_img.height
                image_info.file_size = os.path.getsize(local_path)
                image_info.mime_type = f"image/{processed_img.format.lower()}"
                
                return image_info
                
        except Exception as e:
            image_info.is_valid = False
            image_info.error_message = f"Processing error: {str(e)}"
            return image_info
    
    def _download_image(self, url: str) -> Optional[bytes]:
        """
        Download image data from URL.
        
        Args:
            url: Image URL
            
        Returns:
            Image data as bytes or None if failed
        """
        try:
            response = self.session.get(
                url,
                timeout=self.extractor_config.get('timeout', 30),
                stream=True
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                return None
            
            # Read image data
            image_data = b''
            for chunk in response.iter_content(chunk_size=8192):
                image_data += chunk
                # Prevent downloading extremely large files
                if len(image_data) > self.max_file_size * 2:  # 10MB limit for download
                    return None
            
            return image_data
            
        except RequestException:
            return None
    
    def _process_image(self, img: Image.Image, target_width: Optional[int] = None) -> Optional[Image.Image]:
        """
        Process an image for PDF generation.
        
        Args:
            img: PIL Image object
            target_width: Target width for resizing
            
        Returns:
            Processed PIL Image object or None if failed
        """
        try:
            # Handle EXIF rotation
            img = self._fix_image_orientation(img)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                else:
                    background.paste(img)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Check minimum size requirements
            if img.width < self.min_width or img.height < self.min_height:
                return None
            
            # Resize if necessary
            img = self._resize_image(img, target_width)
            
            # Apply optimization filters
            img = self._optimize_image_quality(img)
            
            return img
            
        except Exception:
            return None
    
    def _fix_image_orientation(self, img: Image.Image) -> Image.Image:
        """
        Fix image orientation based on EXIF data.
        
        Args:
            img: PIL Image object
            
        Returns:
            Oriented image
        """
        try:
            # Use ImageOps.exif_transpose which handles orientation automatically
            return ImageOps.exif_transpose(img)
        except Exception:
            # If EXIF processing fails, return original image
            return img
    
    def _resize_image(self, img: Image.Image, target_width: Optional[int] = None) -> Image.Image:
        """
        Resize image for optimal PDF inclusion.
        
        Args:
            img: PIL Image object
            target_width: Target width (uses default if None)
            
        Returns:
            Resized image
        """
        # Determine target width
        if target_width is None:
            target_width = self.max_width
        
        # Don't resize if image is already smaller
        if img.width <= target_width and img.height <= self.max_height:
            return img
        
        # Calculate scaling factor
        width_scale = target_width / img.width if img.width > target_width else 1.0
        height_scale = self.max_height / img.height if img.height > self.max_height else 1.0
        scale = min(width_scale, height_scale)
        
        # Calculate new dimensions
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        
        # Resize using high-quality algorithm
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return img_resized
    
    def _optimize_image_quality(self, img: Image.Image) -> Image.Image:
        """
        Apply quality optimization to the image.
        
        Args:
            img: PIL Image object
            
        Returns:
            Optimized image
        """
        # Apply subtle sharpening for print quality
        if img.mode == 'RGB':
            try:
                # Very light unsharp mask for print clarity
                img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            except Exception:
                # If filtering fails, use original
                pass
        
        return img
    
    def _save_image(self, img: Image.Image, file_path: str) -> None:
        """
        Save image with optimal settings for PDF generation.
        
        Args:
            img: PIL Image object
            file_path: Output file path
        """
        # Determine format from file extension
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.jpg', '.jpeg']:
            # Save as JPEG with high quality
            img.save(
                file_path,
                format='JPEG',
                quality=self.jpeg_quality,
                optimize=True,
                dpi=(300, 300)  # Set DPI for print quality
            )
        elif file_ext == '.png':
            # Save as PNG with optimization
            img.save(
                file_path,
                format='PNG',
                optimize=self.png_optimize,
                dpi=(300, 300)
            )
        elif file_ext == '.webp':
            # Save as WebP (if supported)
            img.save(
                file_path,
                format='WEBP',
                quality=self.jpeg_quality,
                method=6  # Best compression
            )
        else:
            # Default to JPEG
            jpg_path = str(Path(file_path).with_suffix('.jpg'))
            img.save(
                jpg_path,
                format='JPEG',
                quality=self.jpeg_quality,
                optimize=True,
                dpi=(300, 300)
            )
    
    def _generate_filename(self, url: str, format: str, index: int) -> str:
        """
        Generate a filename for the processed image.
        
        Args:
            url: Original image URL
            format: Image format
            index: Image index
            
        Returns:
            Generated filename
        """
        # Create hash from URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Determine file extension
        format_lower = format.lower()
        if format_lower == 'jpeg':
            ext = '.jpg'
        else:
            ext = f'.{format_lower}'
        
        return f"image_{index:02d}_{url_hash}{ext}"
    
    def calculate_optimal_layout(self, images: List[ImageInfo], 
                                page_width: int = 1200, columns: int = 2) -> Dict[str, Any]:
        """
        Calculate optimal layout parameters for images in PDF.
        
        Args:
            images: List of processed images
            page_width: Available page width in pixels
            columns: Number of columns in layout
            
        Returns:
            Dictionary with layout recommendations
        """
        if not images:
            return {'recommended_width': page_width // columns}
        
        # Calculate column width
        column_width = page_width // columns
        
        # Analyze image dimensions
        widths = [img.width for img in images if img.width]
        heights = [img.height for img in images if img.height]
        
        if not widths:
            return {'recommended_width': column_width}
        
        # Calculate statistics
        avg_width = sum(widths) / len(widths)
        avg_height = sum(heights) / len(heights) if heights else 0
        avg_aspect_ratio = avg_width / avg_height if avg_height > 0 else 1.0
        
        # Determine optimal width
        optimal_width = min(column_width, int(avg_width * 1.2))  # 20% larger than average
        optimal_width = max(optimal_width, column_width // 2)     # At least half column width
        
        return {
            'recommended_width': optimal_width,
            'average_width': int(avg_width),
            'average_height': int(avg_height),
            'average_aspect_ratio': avg_aspect_ratio,
            'column_width': column_width,
            'total_images': len(images),
            'valid_images': len([img for img in images if img.is_valid])
        }
    
    def get_processing_statistics(self, images: List[ImageInfo]) -> Dict[str, Any]:
        """
        Get statistics about processed images.
        
        Args:
            images: List of processed images
            
        Returns:
            Dictionary with processing statistics
        """
        if not images:
            return {
                'total_images': 0,
                'processed_images': 0,
                'failed_images': 0,
                'total_size_bytes': 0,
                'average_width': 0,
                'average_height': 0
            }
        
        processed = [img for img in images if img.is_valid and img.local_path]
        failed = [img for img in images if not img.is_valid]
        
        # Calculate totals
        total_size = sum(img.file_size for img in processed if img.file_size)
        widths = [img.width for img in processed if img.width]
        heights = [img.height for img in processed if img.height]
        
        return {
            'total_images': len(images),
            'processed_images': len(processed),
            'failed_images': len(failed),
            'total_size_bytes': total_size,
            'average_width': int(sum(widths) / len(widths)) if widths else 0,
            'average_height': int(sum(heights) / len(heights)) if heights else 0,
            'compression_ratio': self._calculate_compression_ratio(images),
            'error_types': self._categorize_errors(failed)
        }
    
    def _calculate_compression_ratio(self, images: List[ImageInfo]) -> float:
        """Calculate average compression ratio achieved."""
        # This is a simplified calculation - in practice you'd need original sizes
        processed_images = [img for img in images if img.is_valid and img.local_path and img.file_size]
        if not processed_images:
            return 0.0
        
        # Estimate based on common compression rates
        avg_size = sum(img.file_size for img in processed_images) / len(processed_images)
        estimated_original = avg_size * 2.5  # Rough estimate
        
        return avg_size / estimated_original if estimated_original > 0 else 0.0
    
    def _categorize_errors(self, failed_images: List[ImageInfo]) -> Dict[str, int]:
        """Categorize processing errors."""
        error_counts = {}
        for img in failed_images:
            if img.error_message:
                # Simplified error categorization
                if 'download' in img.error_message.lower():
                    category = 'Download Failed'
                elif 'processing' in img.error_message.lower():
                    category = 'Processing Failed'
                elif 'format' in img.error_message.lower():
                    category = 'Format Error'
                else:
                    category = 'Other Error'
                
                error_counts[category] = error_counts.get(category, 0) + 1
        
        return error_counts


# Global instance
_image_processor = None


def get_image_processor() -> ImageProcessor:
    """Get the global image processor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor


def process_article_images(images: List[ImageInfo], output_dir: str,
                          target_width: Optional[int] = None) -> List[ImageInfo]:
    """
    Convenience function to process article images.
    
    Args:
        images: List of ImageInfo objects
        output_dir: Output directory for processed images
        target_width: Target width for resizing
        
    Returns:
        List of processed ImageInfo objects
    """
    processor = get_image_processor()
    return processor.process_images(images, output_dir, target_width) 