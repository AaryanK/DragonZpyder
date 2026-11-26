"""Structured, bounded document generation; never evaluate user code."""
from io import BytesIO
import json
import zipfile


MIME = {
    "pdf":"application/pdf",
    "docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def render_document(kind: str, spec: dict) -> bytes:
    if kind not in MIME or not isinstance(spec,dict):
        raise ValueError("Unsupported document type or invalid specification")
    if len(json.dumps(spec,ensure_ascii=False).encode())>100_000:
        raise ValueError("Document specification exceeds 100 KB")
    out=BytesIO()
    title=spec.get("title","Untitled")
    if not isinstance(title,str) or len(title)>200:
        raise ValueError("Invalid title")

    def strings(value,limit):
        if not isinstance(value,list) or len(value)>limit or any(not isinstance(x,str) or len(x)>3000 for x in value):
            raise ValueError("Invalid text blocks")
        return value

    if kind=="pdf":
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from xml.sax.saxutils import escape
        from pypdf import PdfReader
        style=getSampleStyleSheet()
        paragraphs=strings(spec.get("paragraphs",[]),100)
        # Base14 fonts are not general Unicode fonts. Fail rather than silently
        # replacing unsupported characters; font embedding is a separate step.
        for value in [title,*paragraphs]:
            value.encode("cp1252")
        story=[Paragraph(escape(title),style["Title"])]
        for paragraph in paragraphs:
            story.extend([Paragraph(escape(paragraph).replace("\n","<br/>"),style["BodyText"]),Spacer(1,8)])
        SimpleDocTemplate(out,title=title).build(story)
        if not len(PdfReader(BytesIO(out.getvalue())).pages):
            raise ValueError("PDF readback failed")
    elif kind=="docx":
        from docx import Document
        doc=Document()
        doc.add_heading(title,0)
        for paragraph in strings(spec.get("paragraphs",[]),100):
            doc.add_paragraph(paragraph)
        doc.save(out)
        if not Document(BytesIO(out.getvalue())).paragraphs:
            raise ValueError("DOCX readback failed")
    elif kind=="xlsx":
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill
        rows=spec.get("rows",[])
        if not isinstance(rows,list) or not rows or len(rows)>500:
            raise ValueError("Expected 1-500 spreadsheet rows")
        book=Workbook()
        ws=book.active
        ws.title="Data"
        for i,row in enumerate(rows,1):
            if not isinstance(row,list) or len(row)>40:
                raise ValueError("Invalid spreadsheet row")
            for j,value in enumerate(row,1):
                if value is not None and type(value) not in (str,int,float,bool):
                    raise ValueError("Invalid spreadsheet value")
                if isinstance(value,str) and len(value)>3000:
                    raise ValueError("Cell exceeds length limit")
                cell=ws.cell(i,j,value)
                # Treat all strings as literal data, not spreadsheet formulas.
                if isinstance(value,str):
                    cell.data_type="s"
                if i==1:
                    cell.font=Font(bold=True,color="FFFFFF")
                    cell.fill=PatternFill("solid",fgColor="263746")
        ws.freeze_panes="A2"
        book.save(out)
        readback=load_workbook(BytesIO(out.getvalue()),read_only=True)
        try:
            if "Data" not in readback.sheetnames:
                raise ValueError("XLSX readback failed")
        finally:
            readback.close()
    else:
        from pptx import Presentation
        from pptx.util import Pt
        slides=spec.get("slides",[])
        if not isinstance(slides,list) or not 1<=len(slides)<=30:
            raise ValueError("Expected 1-30 slides")
        deck=Presentation()
        deck.core_properties.title=title
        for entry in slides:
            if not isinstance(entry,dict) or not isinstance(entry.get("title"),str) or len(entry["title"])>100:
                raise ValueError("Invalid slide title")
            bullets=strings(entry.get("bullets",[]),6)
            if any(len(b)>180 for b in bullets):
                raise ValueError("Slide bullet too long")
            slide=deck.slides.add_slide(deck.slide_layouts[1])
            slide.shapes.title.text=entry["title"]
            tf=slide.placeholders[1].text_frame
            tf.clear()
            for i,bullet in enumerate(bullets):
                p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
                p.text=bullet
                p.font.size=Pt(22)
        deck.save(out)
        if len(Presentation(BytesIO(out.getvalue())).slides)!=len(slides):
            raise ValueError("PPTX readback failed")
    data=out.getvalue()
    if len(data)>10*1024*1024:
        raise ValueError("Generated artifact exceeds limit")
    if kind!="pdf":
        with zipfile.ZipFile(BytesIO(data)) as archive:
            if archive.testzip() is not None:
                raise ValueError("Corrupt document container")
    return data
