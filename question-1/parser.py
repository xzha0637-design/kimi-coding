import re
from bs4 import BeautifulSoup


def parse_html(html: str) -> dict:
    """Parse HTML document, extract title and clean text (excluding script/style)."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style tags
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Extract title
    title = soup.title.get_text(strip=True) if soup.title else "Untitled"

    # Extract text from body (or whole document if no body)
    body = soup.body if soup.body else soup
    text = body.get_text(separator=" ", strip=True)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    return {"title": title, "text": text}
