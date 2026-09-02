"""Local-only text extraction for approved private application source documents.

The application workspace needs textual evidence from the operator's real base CV and
application letter, while the database must keep storing only references, hashes and
approval metadata. This module therefore reads local files on demand and supports the
real source formats used by the product without persisting extracted content.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


class PrivateApplicationSourceTextError(RuntimeError):
    """Raised when a local private application source cannot yield bounded text."""


def extract_private_application_source_text(path: Path) -> str:
    """Extract non-empty text from UTF-8 text files or text-bearing PDFs."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrivateApplicationSourceTextError(
            f"application source file not found: {resolved}"
        )

    if resolved.suffix.casefold() == ".pdf":
        try:
            reader = PdfReader(str(resolved))
            text = "\n\n".join(
                page_text.strip()
                for page in reader.pages
                if (page_text := (page.extract_text() or "")).strip()
            )
        except Exception as exc:
            raise PrivateApplicationSourceTextError(
                f"application source PDF could not be read: {resolved}"
            ) from exc
        if not text.strip():
            raise PrivateApplicationSourceTextError(
                f"application source PDF contains no extractable text: {resolved}"
            )
        return text

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PrivateApplicationSourceTextError(
            f"application source is not UTF-8 text or supported PDF: {resolved}"
        ) from exc
    if not text.strip():
        raise PrivateApplicationSourceTextError(
            f"application source is empty: {resolved}"
        )
    return text


__all__ = [
    "PrivateApplicationSourceTextError",
    "extract_private_application_source_text",
]
