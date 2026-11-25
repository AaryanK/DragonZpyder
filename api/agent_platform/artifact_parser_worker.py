"""Restricted document extraction worker (not an OS security sandbox).

Input is a byte stream, not a path. No macros, external URLs or user code
are executed. Production activation requires sandbox/security qualification.
"""
import io
import json
import resource
import sys
import zipfile

MAX_BYTES=10*1024*1024
MAX_EXTRACTED=32*1024*1024


def check_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries=z.infolist()
        if len(entries)>1500 or sum(x.file_size for x in entries)>MAX_EXTRACTED:
            raise ValueError("Archive expansion limit")
        if any(x.flag_bits&1 or x.file_size>MAX_EXTRACTED or
               (x.file_size>65536 and x.file_size>200*max(1,x.compress_size)) or
               x.filename.startswith("/") or ".." in x.filename.split("/")
               for x in entries):
            raise ValueError("Unsafe document archive")
        if any("vbaproject" in x.filename.lower() or "activex/" in x.filename.lower() for x in entries):
            raise ValueError("Active content unsupported")


def extract(kind,data):
    chunks=[]
    length=0
    def append(value):
        nonlocal length
        text=str(value)
        remaining=60000-length
        if remaining>0:
            text=text[:remaining]
            chunks.append(text)
            length+=len(text)+1

    if kind=="pdf":
        if not data.startswith(b"%PDF"):
            raise ValueError("PDF signature mismatch")
        from pypdf import PdfReader
        pdf=PdfReader(io.BytesIO(data),strict=True)
        if pdf.is_encrypted or len(pdf.pages)>100:
            raise ValueError("Encrypted or oversized PDF")
        for i,page in enumerate(pdf.pages):
            if length>=60000:break
            append("Page "+str(i+1))
            append(page.extract_text() or "")
    else:
        check_zip(data)
        if kind=="docx":
            from docx import Document
            doc=Document(io.BytesIO(data))
            for p in doc.paragraphs:
                if length>=60000:break
                append(p.text)
            for table in doc.tables[:100]:
                for row in table.rows:
                    if length>=60000:break
                    append(" | ".join(cell.text for cell in row.cells[:40]))
        elif kind=="xlsx":
            from openpyxl import load_workbook
            book=load_workbook(io.BytesIO(data),read_only=True,data_only=True,keep_links=False)
            try:
                for sheet in book.worksheets[:20]:
                    append("Sheet: "+sheet.title)
                    for row in sheet.iter_rows(max_row=1000,max_col=40,values_only=True):
                        if length>=60000:break
                        append(json.dumps(row,default=str,ensure_ascii=False))
            finally:
                book.close()
        elif kind=="pptx":
            from pptx import Presentation
            presentation=Presentation(io.BytesIO(data))
            for i,slide in enumerate(presentation.slides):
                if i>=100 or length>=60000:break
                append("Slide "+str(i+1))
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        append(shape.text)
        else:
            raise ValueError("Unsupported parser")
    return {"text":"\n".join(chunks),"truncated":length>=60000,
            "scope":"bounded text extraction; images, layout, formulas and embedded objects may be omitted"}


def main():
    resource.setrlimit(resource.RLIMIT_CPU,(8,9))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    data=sys.stdin.buffer.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("Oversized file")
    print(json.dumps(extract(sys.argv[1],data),ensure_ascii=False))


if __name__=="__main__":
    main()
