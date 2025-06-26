import os
import re
import cv2
import pytesseract
import pdfplumber
import numpy as np
import logging
from PIL import Image

# --- Setup Logging ---
# Set up a basic logger to provide better feedback and diagnostics.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def handle_errors(func):
    """
    Error handling decorator that logs errors before raising them.
    This provides better insight into failures during document processing.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the detailed error message for debugging purposes.
            logging.error(f"An error occurred in function '{func.__name__}': {e}", exc_info=True)
            # Raise a new exception to halt execution but with clear context.
            raise RuntimeError(f"Error in {func.__name__}: {str(e)}")
    return wrapper


def _correct_skew(image: np.ndarray) -> np.ndarray:
    """
    Corrects the skew of an image, which significantly improves OCR accuracy.
    This function detects the text orientation and rotates the image to be level.
    """
    # Convert to grayscale and invert the image for contour detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    
    # Find all non-zero pixel coordinates
    coords = np.column_stack(np.where(gray > 0))
    
    # Get the minimum area bounding box of the text block
    angle = cv2.minAreaRect(coords)[-1]
    
    # The `cv2.minAreaRect` angle can be between -90 and 0.
    # We adjust it to get the correct rotation angle.
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    # Get the image center and compute the rotation matrix
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Apply the rotation to straighten the image
    rotated = cv2.warpAffine(image, rotation_matrix, (w, h), 
                             flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                             
    logging.info(f"Corrected image skew by {angle:.2f} degrees.")
    return rotated


def _process_image_for_ocr(image: np.ndarray) -> str:
    """
    Internal function to handle the OCR process on an image object.
    This includes preprocessing and text extraction using pytesseract.
    """
    # 1. Correct skew
    deskewed_image = _correct_skew(image)
    
    # 2. Convert to grayscale for better OCR results
    gray = cv2.cvtColor(deskewed_image, cv2.COLOR_BGR2GRAY)
    
    # 3. Apply adaptive thresholding to handle varied lighting and shadows
    threshold = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
    
    # 4. Use pytesseract to extract text with an optimized configuration
    #    PSM 6: Assume a single uniform block of text.
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(threshold, config=custom_config).strip()
    
    # Fallback to the grayscale image if thresholding yields no text
    if not text:
        logging.warning("Thresholding produced no text. Retrying with grayscale image.")
        text = pytesseract.image_to_string(gray, config=custom_config).strip()
        
    return text


@handle_errors
def extract_text_from_image(image_path: str) -> str:
    """Extract text from images using an enhanced OCR pipeline."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image from path: {image_path}")
    
    return _process_image_for_ocr(image)


@handle_errors
def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF documents.
    Handles both text-based and image-based (scanned) PDFs.
    """
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        # First, try to extract digital text
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        
        full_text = "\n".join(text_parts).strip()
        
        # If no digital text is found, treat it as a scanned PDF
        if not full_text:
            logging.warning("No digital text found. Attempting OCR on PDF pages as images.")
            image_text_parts = []
            for i, page in enumerate(pdf.pages):
                logging.info(f"Processing page {i+1} as an image...")
                # Render page as a high-resolution image
                pil_image = page.to_image(resolution=300).original
                # Convert PIL image to OpenCV format (NumPy array)
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                # Run the enhanced OCR process on the image
                image_text_parts.append(_process_image_for_ocr(cv_image))
            
            full_text = "\n\n--- Page Break ---\n\n".join(image_text_parts)
            
    return full_text


@handle_errors
def process_upload(file_path: str) -> tuple[dict, str]:
    """
    Process uploaded documents, extract text, and parse relevant information
    using more robust and flexible patterns.
    """
    # Validate file path and existence
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file was not found at: {file_path}")

    if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
        raise ValueError("Unsupported file format. Supported types: PDF, PNG, JPG, JPEG")

    # Extract text based on file type
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        try:
            with Image.open(file_path) as img:
                img.verify()  # Verify the image is not corrupted
        except Exception as e:
            raise ValueError(f"Invalid or corrupted image file: {str(e)}")
        
        text = extract_text_from_image(file_path)
    else:
        text = extract_text_from_pdf(file_path)

    if not text.strip():
        raise ValueError("No text could be extracted from the document.")

    # Define more flexible extraction patterns for different fields
    # These patterns handle optional words and multi-line values.
    patterns = {
        "name": r"(?:Patient\s)?Name\s*:\s*([^\n]+)",
        "age": r"Age\s*:\s*(\d+)",
        "patient_id": r"(?:Insurance|Patient|Record)?\s*ID\s*[:\s]*([A-Z0-9-]+)",
        "disease": r"(?:Disease|Diagnosis)\s*(?:Name)?\s*:\s*([^\n]+)",
        "gender": r"Gender\s*:\s*([^\n]+)",
        "blood": r"Blood(?:\sGroup)?\s*:\s*([^\n]+)",
        # This pattern captures multi-line addresses by looking ahead for the next known field
        "address": r"Address\s*:\s*([\s\S]+?)(?=\n(?:Phone|Contact|Gender|Blood|Medication)|$)",
        "phone": r"(?:Phone|Contact)\s*(?:Number)?\s*:\s*([^\n]+)",
        # This pattern captures a multi-line list of medications
        "medicines": r"Medication[s]?\s*:\s*([\s\S]+?)(?=\n\n|\n[A-Z][a-z]+:|$) "
    }
    
    fields = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean up the extracted value: remove extra whitespace and newlines
            value = match.group(1).strip().replace('\n', ' ')
            fields[key] = re.sub(r'\s+', ' ', value) # Consolidate whitespace
        else:
            fields[key] = "Not found"
    
    # Consolidate Patient ID check
    if fields.get("patient_id") == "Not found":
        raise ValueError("Could not find a valid Insurance ID, Patient ID, or Record ID in the document.")
            
    return fields, text
