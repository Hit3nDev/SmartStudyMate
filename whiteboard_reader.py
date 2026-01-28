import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import cv2
import os
import numpy as np
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from typing import Tuple, Optional, List
import math

# --------------------------------------------
# 🧩 Setup with Model Caching
# --------------------------------------------

# Path to Tesseract (auto-detect or use default)
def setup_tesseract():
    """Setup Tesseract path with auto-detection."""
    import platform
    system = platform.system()
    
    # Try common paths
    common_paths = []
    if system == "Windows":
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif system == "Darwin":  # macOS
        common_paths = ["/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"]
    else:  # Linux
        common_paths = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]
    
    # Check if tesseract is already in PATH
    import shutil
    if shutil.which("tesseract"):
        return  # Already available in PATH
    
    # Try common paths
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return
    
    # If not found, try to use default (may fail later)
    print("⚠️ Tesseract not found in common paths. Please install Tesseract OCR.")

setup_tesseract()

# Global model cache to avoid reloading
_trocr_processor = None
_trocr_model = None
_device = None

def get_trocr_model():
    """Lazy load TrOCR model with caching and error handling."""
    global _trocr_processor, _trocr_model, _device
    if _trocr_model is None:
        try:
            print("🔄 Loading TrOCR model (first time only)...")
            _trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
            _trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            _trocr_model.to(_device)
            _trocr_model.eval()  # Set to evaluation mode
            print(f"✅ TrOCR model loaded on {_device}")
        except Exception as e:
            print(f"❌ Failed to load TrOCR model: {e}")
            print("⚠️ Falling back to Tesseract OCR only")
            raise RuntimeError(f"TrOCR model loading failed: {e}")
    return _trocr_processor, _trocr_model, _device

# --------------------------------------------
# 🧹 Enhanced Image Preprocessing
# --------------------------------------------

def deskew_image(image: np.ndarray) -> np.ndarray:
    """Correct image skew/rotation for better OCR."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) == 0:
        return image
    
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    
    if abs(angle) < 0.5:  # Skip if angle is too small
        return image
    
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def denoise_image(image: np.ndarray) -> np.ndarray:
    """Remove noise from image using advanced denoising."""
    if len(image.shape) == 3:
        denoised = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    else:
        denoised = cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
    return denoised


def enhance_contrast_clahe(image: np.ndarray) -> np.ndarray:
    """Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
    if len(image.shape) == 3:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)
    return enhanced


def preprocess_image_for_handwriting(image_path: str) -> str:
    """Specialized preprocessing pipeline optimized for handwritten text."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    
    # Step 1: Resize if too small (TrOCR works better with larger images)
    h, w = gray.shape
    if h < 256 or w < 256:
        scale = max(256 / h, 256 / w)
        new_h, new_w = int(h * scale), int(w * scale)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    # Step 2: Remove noise with advanced denoising
    gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    
    # Step 3: Enhance contrast specifically for handwriting (more aggressive)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    
    # Step 4: Morphological operations to connect broken strokes
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # Step 5: Sharpen the image to make strokes clearer
    sharpen_kernel = np.array([[-1, -1, -1],
                               [-1,  9, -1],
                               [-1, -1, -1]])
    gray = cv2.filter2D(gray, -1, sharpen_kernel)
    
    # Step 6: Normalize brightness
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    
    # Step 7: Apply gentle bilateral filter (preserve edges, reduce noise)
    gray = cv2.bilateralFilter(gray, 5, 50, 50)
    
    # Save processed temporary image
    base, ext = os.path.splitext(image_path)
    processed_path = f"{base}_handwriting_processed{ext}"
    cv2.imwrite(processed_path, gray)
    return processed_path

def preprocess_image(image_path: str, enhanced: bool = True, for_handwriting: bool = False) -> str:
    """Enhanced image preprocessing pipeline for better OCR results."""
    if for_handwriting:
        return preprocess_image_for_handwriting(image_path)
    
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    if enhanced:
        # Step 1: Denoise
        img = denoise_image(img)
        
        # Step 2: Deskew
        img = deskew_image(img)
        
        # Step 3: Enhance contrast
        img = enhance_contrast_clahe(img)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # Additional enhancement for printed text
    # Apply bilateral filter to reduce noise while keeping edges sharp
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Adaptive thresholding for clarity
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Save processed temporary image
    base, ext = os.path.splitext(image_path)
    processed_path = f"{base}_processed{ext}"
    cv2.imwrite(processed_path, gray)
    return processed_path


def is_handwritten_image(image_path: str) -> bool:
    """Enhanced detection of handwritten text using multiple advanced heuristics."""
    img = cv2.imread(image_path, 0)
    if img is None:
        return False
    
    # Resize for faster processing if image is large
    h, w = img.shape
    if h > 1000 or w > 1000:
        scale = min(1000 / h, 1000 / w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    
    # Method 1: Edge density (handwritten has more irregular edges)
    edges = cv2.Canny(img, 50, 150)  # Lower thresholds for better edge detection
    edge_density = np.sum(edges > 0) / edges.size
    
    # Method 2: Contour analysis (handwritten has more varied contours)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contour_areas = [cv2.contourArea(c) for c in contours]
        contour_variance = np.var(contour_areas)
        contour_mean = np.mean(contour_areas)
        # Handwritten text has high variance in contour sizes
        contour_coefficient = contour_variance / (contour_mean + 1e-5)
    else:
        contour_variance = 0
        contour_coefficient = 0
    
    # Method 3: Line thickness variation (handwritten has more variation)
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=1)
    thickness_variation = np.std(dilated - binary)
    
    # Method 4: Stroke direction analysis (handwritten has more varied directions)
    sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    angles = np.arctan2(sobely, sobelx) * 180 / np.pi
    angle_variance = np.var(angles[edges > 0]) if np.any(edges > 0) else 0
    
    # Method 5: Connected component analysis
    num_labels, labels = cv2.connectedComponents(binary)
    # Handwritten text typically has more connected components
    component_density = num_labels / (img.size / 10000)  # Normalize by image size
    
    # Combined heuristic with weighted scoring
    scores = {
        'edge_density': 1.0 if edge_density > 0.03 else 0.0,
        'contour_variance': 1.0 if contour_variance > 500 else 0.0,
        'contour_coefficient': 1.0 if contour_coefficient > 0.5 else 0.0,
        'thickness_variation': 1.0 if thickness_variation > 15 else 0.0,
        'angle_variance': 1.0 if angle_variance > 2000 else 0.0,
        'component_density': 1.0 if component_density > 0.1 else 0.0
    }
    
    total_score = sum(scores.values())
    is_handwritten = total_score >= 3  # At least 3 indicators suggest handwriting
    
    return is_handwritten

# --------------------------------------------
# 🔍 Enhanced OCR Engines
# --------------------------------------------

def extract_with_tesseract(image: Image.Image, lang: str = 'eng', get_confidence: bool = False) -> Tuple[str, Optional[float]]:
    """Extract text using Tesseract with enhanced confidence scores and multi-language support."""
    try:
        # Get detailed data with confidence
        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
        
        # Extract text
        text = pytesseract.image_to_string(image, lang=lang)
        
        # Calculate weighted average confidence (weight by word length)
        confidences = []
        word_lengths = []
        for i, conf in enumerate(data['conf']):
            conf_int = int(conf)
            if conf_int > 0 and i < len(data['text']):
                word = data['text'][i]
                if word and word.strip():
                    confidences.append(conf_int)
                    word_lengths.append(len(word.strip()))
        
        if confidences:
            # Weighted average by word length
            total_length = sum(word_lengths)
            if total_length > 0:
                weighted_conf = sum(c * w for c, w in zip(confidences, word_lengths)) / total_length
            else:
                weighted_conf = np.mean(confidences)
            avg_confidence = float(weighted_conf)
        else:
            avg_confidence = 0.0
        
        if get_confidence:
            return text.strip(), avg_confidence
        return text.strip(), None
    except Exception as e:
        print(f"⚠️ Tesseract error: {e}, trying fallback...")
        # Fallback to simple extraction
        try:
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip(), (50.0 if get_confidence else None)
        except:
            return "", (0.0 if get_confidence else None)


def extract_with_trocr(image: Image.Image, max_length: int = 512, num_beams: int = 5, 
                       temperature: float = 0.7, do_sample: bool = False) -> Tuple[str, Optional[float]]:
    """Extract text using TrOCR with enhanced generation parameters optimized for handwriting."""
    processor, model, device = get_trocr_model()
    
    # Ensure image is in RGB format
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize image if too large (TrOCR works best with certain sizes)
    width, height = image.size
    max_dimension = 384  # Optimal for TrOCR
    if width > max_dimension or height > max_dimension:
        ratio = min(max_dimension / width, max_dimension / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Prepare image
    pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
    
    # Enhanced generation with better parameters for handwriting
    with torch.no_grad():
        generate_kwargs = {
            "max_length": max_length,
            "num_beams": num_beams,
            "early_stopping": True,
            "no_repeat_ngram_size": 3,
            "length_penalty": 1.2,  # Slightly higher for better length control
            "return_dict_in_generate": True,
            "output_scores": True,
        }
        
        if do_sample:
            generate_kwargs.update({
                "do_sample": True,
                "temperature": temperature,
                "top_p": 0.9,
            })
        
        outputs = model.generate(pixel_values, **generate_kwargs)
        
        # Handle different output formats
        if hasattr(outputs, 'sequences'):
            generated_ids = outputs.sequences
        elif isinstance(outputs, torch.Tensor):
            generated_ids = outputs
        else:
            # Try to get sequences from dict-like object
            generated_ids = getattr(outputs, 'sequences', outputs)
    
    # Decode text
    if isinstance(generated_ids, torch.Tensor):
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    elif hasattr(generated_ids, 'sequences'):
        text = processor.batch_decode(generated_ids.sequences, skip_special_tokens=True)[0]
    else:
        # Fallback: try to decode directly
        try:
            text = processor.batch_decode([generated_ids], skip_special_tokens=True)[0]
        except:
            text = ""
    
    # Calculate confidence score from generation scores
    confidence = None
    if hasattr(outputs, 'scores') and outputs.scores:
        try:
            log_probs = []
            for score in outputs.scores:
                if isinstance(score, torch.Tensor):
                    probs = torch.nn.functional.softmax(score, dim=-1)
                    max_probs = torch.max(probs, dim=-1)[0]
                    log_probs.append(max_probs.cpu().numpy().flatten())
            
            if log_probs:
                all_probs = np.concatenate(log_probs)
                avg_prob = np.mean(all_probs)
                # Convert to 0-100 scale with better calibration
                confidence = float(np.clip(avg_prob * 120, 0, 100))  # Scale up slightly
        except Exception as e:
            print(f"Confidence calculation warning: {e}")
    
    return text.strip(), confidence


def extract_with_trocr_batch(images: List[Image.Image], max_length: int = 512, batch_size: int = 4) -> List[str]:
    """Batch process multiple images with TrOCR for efficiency with memory management."""
    processor, model, device = get_trocr_model()
    
    all_texts = []
    
    # Process in smaller batches to avoid memory issues
    for i in range(0, len(images), batch_size):
        batch_images = images[i:i + batch_size]
        
        try:
            # Process batch
            pixel_values = processor(images=batch_images, return_tensors="pt").pixel_values.to(device)
            
            with torch.no_grad():
                generated_ids = model.generate(
                    pixel_values,
                    max_length=max_length,
                    num_beams=5,
                    early_stopping=True,
                    no_repeat_ngram_size=3
                )
            
            batch_texts = processor.batch_decode(generated_ids, skip_special_tokens=True)
            all_texts.extend([text.strip() for text in batch_texts])
            
            # Clear GPU cache if using CUDA
            if device == "cuda":
                torch.cuda.empty_cache()
                
        except Exception as e:
            print(f"⚠️ Batch processing error for batch {i//batch_size + 1}: {e}")
            # Fallback: process individually
            for img in batch_images:
                try:
                    text, _ = extract_with_trocr(img, max_length=max_length)
                    all_texts.append(text)
                except:
                    all_texts.append("")
    
    return all_texts

# --------------------------------------------
# 🧠 Enhanced Main OCR Pipeline
# --------------------------------------------

def clean_extracted_text(text: str) -> str:
    """Clean and normalize extracted text."""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove common OCR artifacts (only if text is mostly letters)
    if text:
        digit_ratio = len([c for c in text if c.isdigit()]) / max(len(text), 1)
        if digit_ratio < 0.1:  # Less than 10% digits
            text = text.replace('|', 'I')  # Common OCR mistake
            # Only replace 0 with O if context suggests it's a letter
            # (simple heuristic: if surrounded by letters)
            import re
            text = re.sub(r'([A-Za-z])0([A-Za-z])', r'\1O\2', text)
    
    return text.strip()


def extract_text_from_image(image_path: str, use_trocr: bool = False, get_confidence: bool = False, lang: str = 'eng') -> Tuple[str, Optional[float]]:
    """Extract text from image with auto-detection, forced model selection, and enhanced error handling."""
    # Detect if handwritten first
    is_handwritten = is_handwritten_image(image_path) if not use_trocr else True
    
    try:
        # Use specialized preprocessing for handwriting
        processed_path = preprocess_image(image_path, enhanced=True, for_handwriting=is_handwritten or use_trocr)
        image = Image.open(processed_path)
    except Exception as e:
        print(f"⚠️ Image preprocessing failed: {e}, trying direct extraction...")
        try:
            image = Image.open(image_path)
            processed_path = image_path
        except Exception as e2:
            raise ValueError(f"Could not read image: {e2}")

    confidence = None
    text = ""
    method_used = ""
    
    # Choose OCR engine with fallback chain
    if use_trocr or is_handwritten:
        print("🖊 Using TrOCR for handwriting recognition...")
        method_used = "TrOCR"
        try:
            # Try with different parameters for better handwriting recognition
            text, confidence = extract_with_trocr(image, max_length=512, num_beams=8, temperature=0.7)
            
            # If result is too short or confidence is low, try with different parameters
            if (not text or len(text.strip()) < 3) or (confidence is not None and confidence < 40):
                print("🔄 Retrying TrOCR with adjusted parameters...")
                text2, confidence2 = extract_with_trocr(image, max_length=512, num_beams=10, temperature=0.5)
                if text2 and len(text2.strip()) > len(text.strip()):
                    text, confidence = text2, confidence2
            
            if not text or len(text.strip()) < 3:
                raise ValueError("TrOCR returned empty or very short text")
        except Exception as e:
            print(f"⚠️ TrOCR failed ({e}), falling back to Tesseract...")
            method_used = "Tesseract (fallback)"
            text, confidence = extract_with_tesseract(image, lang=lang, get_confidence=get_confidence)
    else:
        print(f"🔤 Using Tesseract for printed text (lang: {lang})...")
        method_used = "Tesseract"
        text, confidence = extract_with_tesseract(image, lang=lang, get_confidence=get_confidence)
        
        # If Tesseract confidence is very low, try TrOCR as fallback
        if get_confidence and confidence is not None and confidence < 30 and not use_trocr:
            print(f"⚠️ Low Tesseract confidence ({confidence:.1f}%), trying TrOCR...")
            try:
                trocr_text, trocr_conf = extract_with_trocr(image)
                if trocr_text and len(trocr_text.strip()) > len(text.strip()):
                    text, confidence = trocr_text, trocr_conf
                    method_used = "TrOCR (fallback)"
            except:
                pass  # Keep Tesseract result

    # Clean extracted text
    text = clean_extracted_text(text)
    
    if method_used:
        print(f"✅ Extraction complete using {method_used}")

    # Clean up temp file
    try:
        if processed_path != image_path and os.path.exists(processed_path):
            os.remove(processed_path)
    except:
        pass

    if get_confidence:
        return text, confidence
    return text, None


def extract_text_from_pdf(pdf_path: str, use_trocr: bool = False, batch_process: bool = True, dpi: int = 300) -> str:
    """Extract text from each page of a PDF with enhanced processing and progress tracking."""
    text = ""
    try:
        # Check if Poppler is available
        try:
            pages = convert_from_path(pdf_path, dpi=dpi, thread_count=4)  # Higher DPI and parallel processing
            print(f"📄 Extracted {len(pages)} pages from PDF")
        except Exception as e:
            if "poppler" in str(e).lower() or "pdftoppm" in str(e).lower():
                error_msg = "Poppler is not installed. Please install Poppler to process PDF files.\n" \
                           "Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n" \
                           "macOS: brew install poppler\n" \
                           "Linux: sudo apt-get install poppler-utils"
                print(f"⚠️ {error_msg}")
                return error_msg
            raise
    except Exception as e:
        error_msg = f"Error processing PDF: {e}\nEnsure Poppler is installed and accessible."
        print(f"⚠️ {error_msg}")
        return error_msg

    if not pages:
        return "No pages found in PDF."

    if batch_process and use_trocr and len(pages) > 1:
        # Batch process with TrOCR for efficiency
        print(f"📦 Batch processing {len(pages)} pages with TrOCR...")
        try:
            texts = extract_with_trocr_batch(pages, batch_size=min(4, len(pages)))
            for i, page_text in enumerate(texts):
                if page_text.strip():
                    text += f"\n--- Page {i+1} ---\n{page_text}\n"
                else:
                    text += f"\n--- Page {i+1} ---\n[No text detected]\n"
        except Exception as e:
            print(f"⚠️ Batch processing failed ({e}), falling back to sequential...")
            batch_process = False
    
    if not batch_process:
        # Sequential processing with progress indication
        total_pages = len(pages)
        for i, page in enumerate(pages):
            print(f"   Processing page {i+1}/{total_pages}...")
            temp_img = f"temp_page_{i}_{os.path.basename(pdf_path)}.png"
            try:
                page.save(temp_img, "PNG")
                page_text, _ = extract_text_from_image(temp_img, use_trocr=use_trocr)
                if page_text.strip():
                    text += f"\n--- Page {i+1} ---\n{page_text}\n"
                else:
                    text += f"\n--- Page {i+1} ---\n[No text detected]\n"
            except Exception as e:
                print(f"   ⚠️ Error processing page {i+1}: {e}")
                text += f"\n--- Page {i+1} ---\n[Error: {str(e)}]\n"
            finally:
                try:
                    if os.path.exists(temp_img):
                        os.remove(temp_img)
                except:
                    pass

    return text.strip()


def extract_text(file_path: str, use_trocr: bool = False, get_confidence: bool = False):
    """
    Detect file type (image/PDF) and extract text with enhanced processing.
    
    Args:
        file_path: Path to image or PDF file
        use_trocr: Force use of TrOCR for handwritten text
        get_confidence: If True, return tuple (text, confidence), else return text only
    
    Returns:
        str if get_confidence=False, tuple (str, float) if get_confidence=True
    """
    ext = os.path.splitext(file_path)[1].lower()
    supported_ext = [".jpg", ".jpeg", ".png", ".pdf", ".bmp", ".tiff", ".tif"]

    if ext not in supported_ext:
        raise ValueError(f"Unsupported file type: {ext}. Please upload an image or PDF.")

    if ext == ".pdf":
        result = extract_text_from_pdf(file_path, use_trocr, batch_process=True)
        return (result, None) if get_confidence else result
    else:
        result = extract_text_from_image(file_path, use_trocr, get_confidence=get_confidence)
        if get_confidence:
            return result if isinstance(result, tuple) else (result, None)
        return result[0] if isinstance(result, tuple) else result
