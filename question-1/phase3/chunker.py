"""Chunk SOP HTML files by H3/H2 sections, saving to data/chunks/."""
import os
import re
from bs4 import BeautifulSoup, NavigableString

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHUNK_DIR = os.path.join(DATA_DIR, "chunks")


def chunk_file(filepath: str) -> list[dict]:
    """Split an SOP HTML file into chunks by H3/H4 sections."""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else "Untitled"
    header_html = str(soup.header) if soup.header else ""

    # Find content container — try main, article, body in that order
    container = soup.find("main") or soup.find("article") or soup.find("body")
    if not container:
        return _fallback(html, title)

    # Find all headings
    headings = container.find_all(["h2", "h3", "h4"])
    if len(headings) <= 1:
        return _fallback(html, title)

    chunks = []
    chunk_idx = 0
    current_h2 = ""
    current_h3 = ""
    content_buf = []

    # Walk container descendants in document order
    for el in container.descendants:
        if not hasattr(el, "name") or el.name is None:
            continue
        if el.name in ("h2", "h3", "h4"):
            # Flush current chunk
            content_text = "\n".join(content_buf).strip()
            if current_h3 and content_text:
                chunks.append({
                    "id": f"chunk-{chunk_idx:03d}",
                    "html": _build_chunk(title, header_html, current_h2, current_h3, content_text),
                    "h2": current_h2, "h3": current_h3, "title": title,
                })
                chunk_idx += 1
            elif current_h2 and not current_h3 and content_text and el.name != "h3":
                # H2 without sub-headings: save if next heading isn't H3
                chunks.append({
                    "id": f"chunk-{chunk_idx:03d}",
                    "html": _build_chunk(title, header_html, current_h2, current_h2, content_text),
                    "h2": current_h2, "h3": current_h2, "title": title,
                })
                chunk_idx += 1

            content_buf = []
            if el.name == "h2":
                current_h2 = el.get_text(strip=True)
                current_h3 = ""
            else:
                current_h3 = el.get_text(strip=True)
        elif el.name in ("p", "ul", "ol", "table", "pre", "code", "div", "span", "li"):
            text = el.get_text(strip=True)
            if text and len(text) > 2:
                content_buf.append(str(el))

    # Last chunk
    content_text = "\n".join(content_buf).strip()
    if content_text:
        h_label = current_h3 or current_h2
        chunks.append({
            "id": f"chunk-{chunk_idx:03d}",
            "html": _build_chunk(title, header_html, current_h2, h_label, content_text),
            "h2": current_h2, "h3": h_label, "title": title,
        })

    if not chunks:
        return _fallback(html, title)
    return chunks


def _build_chunk(title, header_html, h2, h3, content):
    h3_line = f"<h3>{h3}</h3>" if h3 else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{title} — {h3 or h2}</title></head>
<body>
{header_html}
<main>
<h2>{h2}</h2>
{h3_line}
{content}
</main>
</body>
</html>"""


def _fallback(html, title):
    return [{"id": "chunk-000", "html": html, "h2": "", "h3": title, "title": title}]


def chunk_all(data_dir: str = DATA_DIR, chunk_dir: str = CHUNK_DIR) -> dict[str, list[str]]:
    """Chunk all SOP files. Returns {doc_id: [chunk_filenames]}."""
    os.makedirs(chunk_dir, exist_ok=True)
    mapping = {}

    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".html") or "chunk" in fname:
            continue
        doc_id = fname.replace(".html", "")
        filepath = os.path.join(data_dir, fname)
        chunks = chunk_file(filepath)

        chunk_files = []
        for c in chunks:
            c_fname = f"{doc_id}_{c['id']}.html"
            c_path = os.path.join(chunk_dir, c_fname)
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(c["html"])
            chunk_files.append(c_fname)

        mapping[doc_id] = chunk_files
        print(f"  {doc_id}: {len(chunks)} chunks")

    return mapping
