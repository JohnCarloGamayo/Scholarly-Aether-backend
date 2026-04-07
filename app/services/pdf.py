from pathlib import Path
from fpdf import FPDF
from datetime import datetime
import re
import tempfile
import os
import httpx
import unicodedata

from ..config import get_settings

settings = get_settings()


def sanitize_pdf_text(text: str) -> str:
    """Normalize text to a representation safe for FPDF core fonts (Latin-1)."""
    if not text:
        return ""

    replacements = {
        "…": "...",
        "•": "-",
        "→": "->",
        "←": "<-",
        "✓": "v",
        "✗": "x",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "\u00a0": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Convert accented/compatibility characters where possible.
    text = unicodedata.normalize("NFKD", text)
    # Drop anything still outside Latin-1 range to avoid FPDFUnicodeEncodingException.
    text = text.encode("latin-1", "ignore").decode("latin-1")
    return text


def convert_svg_to_png(svg_data: bytes, output_path: str, width: int = 800) -> bool:
    """Convert SVG data to PNG file using svglib and reportlab"""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        from PIL import Image
        
        # Save SVG to temporary file (svglib needs a file)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.svg', mode='wb') as svg_file:
            svg_file.write(svg_data)
            svg_path = svg_file.name
        
        try:
            # Convert SVG to ReportLab drawing
            drawing = svg2rlg(svg_path)
            if not drawing:
                return False
            
            # Scale to desired width while maintaining aspect ratio
            scale = width / drawing.width if drawing.width > 0 else 1
            drawing.width = width
            drawing.height = drawing.height * scale
            drawing.scale(scale, scale)
            
            # Render to PNG
            renderPM.drawToFile(drawing, output_path, fmt='PNG')
            
            # Optimize with PIL
            img = Image.open(output_path)
            
            # Convert RGBA to RGB if needed (FPDF doesn't handle transparency well)
            if img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save optimized PNG
            img.save(output_path, 'PNG', optimize=True)
            return True
        finally:
            # Clean up temporary SVG file
            try:
                os.unlink(svg_path)
            except:
                pass
            
    except Exception as e:
        print(f"Error converting SVG to PNG: {e}")
        import traceback
        traceback.print_exc()
        return False


class ProfessionalPDF(FPDF):
    def __init__(self, title: str, source_url: str):
        super().__init__()
        self.title_text = title
        self.source_url = source_url
        self.set_margins(left=20, top=20, right=20)
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, self.title_text[:60], 0, 0, 'L')
            self.ln(15)
            
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def parse_markdown_to_pdf(pdf: ProfessionalPDF, content: str):
    """Parse markdown content and add to PDF with proper formatting"""
    lines = content.split('\n')
    
    for line in lines:
        line_stripped = line.strip()
        
        if not line_stripped:
            pdf.ln(3)
            continue
        
        # Reset X position to left margin before each operation
        pdf.set_x(pdf.l_margin)
        
        line_stripped = sanitize_pdf_text(line_stripped)
        
        # Images (![alt](url))
        img_match = re.match(r'!\[(.*?)\]\((.*?)\)', line_stripped)
        if img_match:
            alt_text = img_match.group(1)
            img_url = img_match.group(2)
            
            # Skip very small data URIs (likely icons)
            if img_url.startswith('data:') and len(img_url) < 500:
                continue
            
            is_svg = img_url.lower().endswith('.svg') or (img_url.startswith('data:image/svg'))
            
            try:
                # Handle base64 data URIs
                if img_url.startswith('data:image/'):
                    import base64
                    # Extract base64 data
                    header, encoded = img_url.split(',', 1)
                    img_data = base64.b64decode(encoded)
                    
                    if 'svg' in header:
                        # Convert SVG to PNG
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_path = tmp_file.name
                        
                        if convert_svg_to_png(img_data, tmp_path):
                            print(f"Converted SVG data URI to PNG")
                        else:
                            # Fallback to showing alt text
                            if alt_text and len(alt_text) > 3:
                                pdf.set_font('Arial', 'I', 9)
                                pdf.set_text_color(128, 128, 128)
                                pdf.multi_cell(0, 5, sanitize_pdf_text(f'[SVG Image: {alt_text}]'))
                                pdf.set_text_color(0, 0, 0)
                            continue
                    else:
                        # Determine file extension from header
                        if 'png' in header:
                            suffix = '.png'
                        elif 'jpeg' in header or 'jpg' in header:
                            suffix = '.jpg'
                        elif 'gif' in header:
                            suffix = '.gif'
                        elif 'webp' in header:
                            suffix = '.webp'
                        else:
                            suffix = '.jpg'
                        
                        # Save to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            tmp_file.write(img_data)
                            tmp_path = tmp_file.name
                else:
                    # Download image from URL
                    print(f"Downloading image: {img_url[:100]}")
                    response = httpx.get(img_url, timeout=20, follow_redirects=True)
                    response.raise_for_status()
                    
                    if is_svg:
                        # Convert SVG to PNG
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_path = tmp_file.name
                        
                        if convert_svg_to_png(response.content, tmp_path):
                            print(f"Converted SVG from URL to PNG")
                        else:
                            # Fallback to showing alt text
                            if alt_text and len(alt_text) > 3:
                                pdf.set_font('Arial', 'I', 9)
                                pdf.set_text_color(128, 128, 128)
                                pdf.multi_cell(0, 5, sanitize_pdf_text(f'[SVG Image: {alt_text}]'))
                                pdf.set_text_color(0, 0, 0)
                            continue
                    else:
                        # Determine file type from content-type or URL
                        content_type = response.headers.get('content-type', '').lower()
                        if 'png' in content_type or img_url.lower().endswith('.png'):
                            suffix = '.png'
                        elif 'gif' in content_type or img_url.lower().endswith('.gif'):
                            suffix = '.gif'
                        elif 'webp' in content_type or img_url.lower().endswith('.webp'):
                            suffix = '.webp'
                        else:
                            suffix = '.jpg'
                        
                        # Save to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            tmp_file.write(response.content)
                            tmp_path = tmp_file.name
                
                # Add image to PDF (max width 140mm for better visibility)
                pdf.ln(5)
                try:
                    # Try to add image with reasonable size
                    pdf.image(tmp_path, w=140)
                    print(f"Successfully added image to PDF")
                    
                    # Add caption if alt text is meaningful
                    if alt_text and len(alt_text) > 3 and not any(x in alt_text.lower() for x in ['icon', 'logo', 'button', 'arrow']):
                        pdf.set_font('Arial', 'I', 8)
                        pdf.set_text_color(100, 100, 100)
                        pdf.multi_cell(0, 4, sanitize_pdf_text(f'Figure: {alt_text}'))
                        pdf.set_text_color(0, 0, 0)
                except Exception as e:
                    print(f"Error adding image to PDF: {e}")
                    # Show alt text for meaningful images
                    if alt_text and len(alt_text) > 3:
                        pdf.set_font('Arial', 'I', 9)
                        pdf.set_text_color(128, 128, 128)
                        pdf.multi_cell(0, 5, sanitize_pdf_text(f'[Image: {alt_text}]'))
                        pdf.set_text_color(0, 0, 0)
                
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                pdf.ln(5)
            except Exception as e:
                print(f"Error processing image {img_url[:100]}: {e}")
                # Show alt text for meaningful images only
                if alt_text and len(alt_text) > 3 and not any(x in alt_text.lower() for x in ['icon', 'logo', 'button', 'arrow']):
                    pdf.set_font('Arial', 'I', 9)
                    pdf.set_text_color(128, 128, 128)
                    pdf.multi_cell(0, 5, sanitize_pdf_text(f'[Image: {alt_text}]'))
                    pdf.set_text_color(0, 0, 0)
            continue
            
        # H1 headers (# Header)
        if line_stripped.startswith('# '):
            text = line_stripped[2:].strip()
            text = sanitize_pdf_text(text)
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(16, 185, 129)  # Emerald color
            pdf.ln(4)
            pdf.multi_cell(0, 8, text)
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            continue
            
        # H2 headers (## Header)
        if line_stripped.startswith('## '):
            text = line_stripped[3:].strip()
            text = sanitize_pdf_text(text)
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(16, 185, 129)
            pdf.ln(3)
            pdf.multi_cell(0, 7, text)
            pdf.ln(1)
            pdf.set_text_color(0, 0, 0)
            continue
            
        # H3 headers (### Header)
        if line_stripped.startswith('### '):
            text = line_stripped[4:].strip()
            text = sanitize_pdf_text(text)
            pdf.set_font('Arial', 'B', 11)
            pdf.ln(2)
            pdf.multi_cell(0, 6, text)
            pdf.ln(1)
            continue
            
        # Bullet points (- item or * item)
        if line_stripped.startswith('- ') or line_stripped.startswith('* '):
            text = line_stripped[2:].strip()
            pdf.set_font('Arial', '', 10)
            # Remove markdown bold/italic markers
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            text = re.sub(r'\*(.*?)\*', r'\1', text)
            text = sanitize_pdf_text(text)
            # Simple indented bullet
            pdf.multi_cell(0, 5, f'   - {text}')
            continue
            
        # Numbered lists (1. item)
        if re.match(r'^\d+\.\s', line_stripped):
            pdf.set_font('Arial', '', 10)
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', line_stripped)
            text = re.sub(r'\*(.*?)\*', r'\1', text)
            text = sanitize_pdf_text(text)
            pdf.multi_cell(0, 5, f'   {text}')
            continue
            
        # Regular paragraph
        pdf.set_font('Arial', '', 10)
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', line_stripped)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Remove links but keep text
        text = sanitize_pdf_text(text)
        
        if text:
            pdf.multi_cell(0, 5, text)
            pdf.ln(1)


def summary_to_pdf(title: str, summary: str, source_url: str, screenshot: str | None = None) -> str:
    output_dir = Path(settings.pdf_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S%f')}.pdf"
    output_path = output_dir / filename

    # Clean title - remove markdown headers
    clean_title = re.sub(r'^#+\s*', '', title).strip()
    clean_title = sanitize_pdf_text(clean_title)
    source_url = sanitize_pdf_text(source_url)
    
    pdf = ProfessionalPDF(clean_title, source_url)
    
    # Title page
    pdf.add_page()
    pdf.ln(40)
    
    # Main title
    pdf.set_font('Arial', 'B', 20)
    pdf.set_text_color(16, 185, 129)  # Emerald color
    pdf.multi_cell(0, 12, clean_title, align='C')
    
    pdf.ln(10)
    
    # Source URL label
    pdf.set_font('Arial', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, 'Source:', ln=True, align='C')
    
    # Source URL value
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, source_url, ln=True, align='C')
    
    pdf.ln(10)
    
    # Generated date
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, f'Generated: {datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")}', ln=True, align='C')
    
    # Add screenshot if available
    if screenshot:
        try:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(16, 185, 129)
            pdf.cell(0, 10, 'Website Preview', ln=True, align='C')
            pdf.ln(5)
            
            # Download screenshot from URL
            response = httpx.get(screenshot, timeout=30, follow_redirects=True)
            response.raise_for_status()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            # Add image to PDF (fit to page width with margins)
            pdf.image(tmp_path, x=20, w=170)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            pdf.ln(5)
        except Exception as e:
            print(f"Error adding screenshot to PDF: {e}")
            # Continue without screenshot
    
    # Content page
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    
    # Parse and add markdown content
    parse_markdown_to_pdf(pdf, summary)
    
    pdf.output(str(output_path))

    # Return public path served by FastAPI static mount
    return f"/pdfs/{filename}"
