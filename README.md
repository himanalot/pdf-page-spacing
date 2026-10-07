# PDF Page Spacing

A local website for adding white space to handwritten homework PDFs. See page breaks while you insert space, push following work to the next page, undo changes, and export a new PDF.

## Run on a Mac

Requires Python 3. Download or clone this repository, then double-click `Open.command`. On first launch it installs the two Python dependencies in a local virtual environment. Your browser opens at http://127.0.0.1:8768.

Or run from a terminal (also works on Linux and Windows):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

On Windows use `.venv\Scripts\python` instead of `.venv/bin/python`.

## Use

1. Choose your PDF. All pages are included, in order.
2. Click a blank gap between lines. The editor tries to snap to a nearby blank row.
3. Choose **Add space** or **Next page**. Green blocks show inserted space; amber dashed lines mark the original page boundaries.
4. Adjust or remove spaces in the sidebar. Use **Undo** or **Reset to original pages** if needed.
5. Choose **Export PDF**. Review the downloaded PDF before submitting it.

The default original page size and zero extra margins reproduce the original page divisions after reset. You can also choose US Letter and extra margins. Changing paper size changes the page divisions.

## Privacy and limitations

Everything runs on your own computer. PDFs are sent only to the server at `127.0.0.1`, held in memory, and cleared when the server stops. The repository contains no homework or sample personal documents. Spacing choices are saved in your browser for each PDF.

Pages are rendered at 144 dpi and joined into a continuous image. This preserves the visible work, including annotations, but exported text is not selectable and PDF links/forms are not retained. Existing printed margins remain part of the image. You choose safe breaks: this is not automatic equation detection or handwriting recognition.

Supports unencrypted PDFs with consistent page dimensions, up to 50 MB and 100 million rendered pixels. For larger files, split them first. Change the port with `PORT=8769 .venv/bin/python server.py` if necessary.

## Dependencies

Python 3, PyMuPDF, and Pillow. The web interface uses plain HTML, CSS, and JavaScript with no external scripts or analytics.
