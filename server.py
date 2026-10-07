"""Local-only PDF page-spacing editor. No source documents are stored on disk."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import hashlib
import io
import json
import math
import os
import threading
import webbrowser

import pymupdf as fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCES = {}
MAX_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 100_000_000


def import_pdf(raw, name):
    identifier = hashlib.sha256(raw).hexdigest()
    if identifier in SOURCES:
        return SOURCES[identifier][1]
    doc = fitz.open(stream=raw, filetype='pdf')
    try:
        if doc.needs_pass or not len(doc):
            raise ValueError('Use an unencrypted PDF with at least one page.')
        width, height = doc[0].rect.width, doc[0].rect.height
        if any(abs(p.rect.width-width) > 1 or abs(p.rect.height-height) > 1 for p in doc):
            raise ValueError('Use a PDF whose pages all have the same size.')
        # Render full pages in order. Reset therefore reproduces original page boundaries.
        pixel_width = max(1, round(width * 2))
        pixel_height = max(1, round(height * 2))
        if pixel_width * pixel_height * len(doc) > MAX_PIXELS:
            raise ValueError('This PDF is too large. Split it into smaller PDFs first.')
        image = Image.new('RGB', (pixel_width, pixel_height * len(doc)), 'white')
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False, colorspace=fitz.csRGB)
            rendered = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            if rendered.size != (pixel_width, pixel_height):
                rendered = rendered.resize((pixel_width, pixel_height))
            image.paste(rendered, (0, i * pixel_height))
        metadata = {'id': identifier, 'name': Path(name).name, 'paper': [width, height],
                    'cuts': [i * pixel_height for i in range(1, len(doc))]}
        # Bound memory if many different files are loaded in one session.
        if len(SOURCES) >= 3:
            SOURCES.pop(next(iter(SOURCES)))
        SOURCES[identifier] = (image, metadata)
        return metadata
    finally:
        doc.close()


def export_pdf(data):
    image, metadata = SOURCES[data['source']]
    width, height = (612, 792) if data.get('paper') == 'letter' else metadata['paper']
    margin = float(data.get('margin', 0))
    if not math.isfinite(margin) or not 0 <= margin < min(width, height) / 3:
        raise ValueError('Invalid margin.')
    scale = (width - 2 * margin) / image.width
    usable = height - 2 * margin
    gaps = sorted(data.get('gaps', []), key=lambda gap: gap['y'])
    if len(gaps) > 1000:
        raise ValueError('Too many inserted spaces.')
    doc = fitz.open()
    position, previous = 0., 0

    def page(index):
        if index > 500:
            raise ValueError('Export exceeds 500 pages.')
        while len(doc) <= index:
            doc.new_page(width=width, height=height)
        return doc[index]

    try:
        for gap in gaps + [{'y': image.height, 'amount': 0}]:
            y = max(previous, min(image.height, int(gap['y'])))
            amount = float(gap['amount'])
            if not math.isfinite(amount) or not 0 <= amount <= 1500:
                raise ValueError('Invalid space size.')
            end = position + (y - previous) * scale
            if y > previous:
                buf = io.BytesIO()
                image.crop((0, previous, image.width, y)).save(buf, format='PNG')
                source = fitz.open()
                try:
                    source_page = source.new_page(width=width-2*margin, height=(y-previous)*scale)
                    source_page.insert_image(source_page.rect, stream=buf.getvalue())
                    cursor = position
                    while cursor < end - 1e-7:
                        index = int((cursor + 1e-7) // usable)
                        offset = cursor - index * usable
                        take = min(end-cursor, usable-offset)
                        page(index).show_pdf_page(
                            fitz.Rect(margin, margin+offset, width-margin, margin+offset+take),
                            source, 0, clip=fitz.Rect(0, cursor-position, width-2*margin, cursor-position+take))
                        cursor += take
                finally:
                    source.close()
            position = end + amount
            previous = y
        return doc.tobytes(deflate=True, garbage=4)
    finally:
        doc.close()


class Handler(BaseHTTPRequestHandler):
    def reply(self, content, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self.reply((ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path.startswith('/image/') and path[7:] in SOURCES:
            buf = io.BytesIO()
            SOURCES[path[7:]][0].save(buf, format='PNG')
            self.reply(buf.getvalue(), 'image/png')
        else:
            self.send_error(404)

    def do_POST(self):
        # Only the local editor may send state-changing requests.
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{self.headers.get("Host")}':
            self.send_error(403)
            return
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= MAX_BYTES:
                raise ValueError('Maximum PDF size is 50 MB.')
            raw = self.rfile.read(size)
            parsed = urlparse(self.path)
            if parsed.path == '/import':
                name = parse_qs(parsed.query).get('name', ['document.pdf'])[0]
                self.reply(json.dumps(import_pdf(raw, name)).encode(), 'application/json')
            elif parsed.path == '/export':
                self.reply(export_pdf(json.loads(raw)), 'application/pdf')
            else:
                self.send_error(404)
        except Exception as error:
            self.reply(str(error).encode(), 'text/plain; charset=utf-8', 400)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8768'))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = f'http://127.0.0.1:{port}/'
    print(f'PDF spacing editor: {url}', flush=True)
    if '--no-browser' not in __import__('sys').argv:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()
