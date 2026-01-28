import pytesseract
import cv2
import fitz  # PyMuPDF
import numpy as np
from typing import Tuple, Optional

# For Windows users: specify Tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def preprocess_image_enhanced(image_path: str) -> np.ndarray:
    """Enhanced image preprocessing for better OCR."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Denoise
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    
    # Enhance contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Bilateral filter to reduce noise while keeping edges sharp
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    
    return gray


def extract_text_from_image(image_path: str, lang: str = 'eng', get_confidence: bool = False) -> Tuple[str, Optional[float]]:
    """Enhanced text extraction from image with confidence scores."""
    try:
        # Use enhanced preprocessing
        processed = preprocess_image_enhanced(image_path)
        
        # Extract text with detailed data
        text = pytesseract.image_to_string(processed, lang=lang)
        
        if get_confidence:
            # Get confidence scores
            data = pytesseract.image_to_data(processed, lang=lang, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = np.mean(confidences) if confidences else 0.0
            return text.strip(), avg_confidence
        
        return text.strip(), None
    
    except Exception as e:
        # Fallback to simple method
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        text = pytesseract.image_to_string(gray, lang=lang)
        return text.strip(), None


def extract_text_from_pdf(pdf_path: str, use_ocr: bool = False) -> str:
    """Enhanced PDF text extraction with optional OCR fallback."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Try to extract text directly first
            page_text = page.get_text()
            
            # If no text found and OCR is enabled, use OCR
            if not page_text.strip() and use_ocr:
                # Convert page to image and OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                img_data = pix.tobytes("png")
                
                # Save temporarily and OCR
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(img_data)
                    tmp_path = tmp.name
                
                try:
                    page_text, _ = extract_text_from_image(tmp_path)
                finally:
                    os.unlink(tmp_path)
            
            if page_text.strip():
                text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
        
        doc.close()
        return text.strip()
    
    except Exception as e:
        return f"Error processing PDF: {str(e)}"


def clean_text(text: str) -> str:
    """Enhanced text cleaning with better normalization."""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove common OCR artifacts
    text = text.replace('|', 'I')  # Common OCR mistake
    text = text.replace('0', 'O') if len([c for c in text if c.isdigit()]) / max(len(text), 1) < 0.1 else text
    
    # Remove multiple consecutive newlines
    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
