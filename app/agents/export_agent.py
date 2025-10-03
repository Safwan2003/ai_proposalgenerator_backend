import os
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from html2docx import html2docx
from .. import schemas
import requests
from io import BytesIO

from xhtml2pdf import pisa

class ExportAgent:
    def export_to_docx(self, proposal: schemas.Proposal) -> str:
        """Export proposal to a professional DOCX format with title page, headers, footers, and images."""
        document = Document()

        # --- Document Setup ---
        # Set margins
        for section in document.sections:
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)

        # --- Header and Footer ---
        header = document.sections[0].header
        header_p = header.paragraphs[0]
        header_p.text = f"Proposal for {proposal.clientName}"
        header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        footer = document.sections[0].footer
        footer_p = footer.paragraphs[0]
        footer_p.text = f"{proposal.companyName} - Confidential"
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # --- Title Page ---
        document.add_heading(f"Proposal for {proposal.clientName}", 0)
        document.add_paragraph()
        p_title = document.add_paragraph()
        p_title.add_run('Prepared for:').bold = True
        document.add_paragraph(proposal.clientName)
        document.add_paragraph()
        p_prepared_by = document.add_paragraph()
        p_prepared_by.add_run('Prepared by:').bold = True
        document.add_paragraph(proposal.companyName)
        document.add_paragraph(proposal.companyContact)
        document.add_paragraph(f"Date: {proposal.startDate.strftime('%B %d, %Y')}")
        document.add_page_break()

        # --- Main Content ---
        document.add_heading("Proposal Details", level=1)

        # Use a table for better formatting of details
        table = document.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Item'
        hdr_cells[1].text = 'Details'
        details = {
            'Total Amount': f"${proposal.totalAmount:,.2f}",
            'Payment Type': proposal.paymentType,
            'Start Date': proposal.startDate.strftime('%Y-%m-%d'),
            'End Date': proposal.endDate.strftime('%Y-%m-%d'),
        }
        for key, value in details.items():
            row_cells = table.add_row().cells
            row_cells[0].text = key
            row_cells[1].text = str(value)

        document.add_paragraph() # Add some space

        # --- Proposal Sections ---
        document.add_heading("Proposal Sections", level=1)
        for section in sorted(proposal.sections, key=lambda s: s.order):
            document.add_heading(section.title, level=2)
            
            # Combine HTML content and images
            section_html = section.contentHtml

            if section.images:
                for image in section.images:
                    # Append img tag to the HTML. html2docx will handle the download and embedding.
                    section_html += f'<img src="{image.url}" />'

            try:
                # Use html2docx to parse the combined HTML
                html2docx(section_html, document)
            except Exception as e:
                print(f"Error parsing HTML for section '{section.title}': {e}")
                document.add_paragraph("Could not render section content.")

            document.add_page_break()

        # --- File Saving ---
        temp_dir = "backend/temp"
        os.makedirs(temp_dir, exist_ok=True)
        file_name = f"proposal_{proposal.id}.docx"
        file_path = os.path.join(temp_dir, file_name)
        document.save(file_path)

        # Return the path relative to the base URL for download
        return f"/exports/{file_name}"

    def export_to_pdf(self, proposal: schemas.Proposal) -> str:
        """Export proposal to a professional PDF format."""
        temp_dir = "backend/temp"
        os.makedirs(temp_dir, exist_ok=True)
        file_name = f"proposal_{proposal.id}.pdf"
        file_path = os.path.join(temp_dir, file_name)

        # Get the HTML content from the preview endpoint
        # This is a bit of a hack, but it's the easiest way to get the fully rendered HTML with CSS
        try:
            response = requests.get(f"http://localhost:8000/api/v1/proposals/{proposal.id}/preview")
            response.raise_for_status()
            html_content = response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching proposal preview: {e}")
            return None

        with open(file_path, "w+b") as pdf_file:
            pisa_status = pisa.CreatePDF(
                BytesIO(html_content.encode('UTF-8')),
                dest=pdf_file,
                encoding='UTF-8'
            )

        if pisa_status.err:
            print(f"Error creating PDF: {pisa_status.err}")
            return None

        return f"/exports/{file_name}"

export_agent = ExportAgent()