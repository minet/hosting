"""
Charter PDF generation service.

Generates a PDF version of the hosting charter (CHARTE.md) using fpdf2,
including the user's name and the signature date in a footer.
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

_CHARTE_PATH = Path("/charte/CHARTE.md")
_HEADING_PREFIX = "#"

# Characters outside latin-1 that appear in the charter — map to safe equivalents
_UNICODE_MAP = str.maketrans({
    "\u2014": "--",   # em dash —
    "\u2013": "-",    # en dash –
    "\u2022": "-",    # bullet •
    "\u2019": "'",    # right single quote '
    "\u2018": "'",    # left single quote '
    "\u201c": '"',    # left double quote "
    "\u201d": '"',    # right double quote "
    "\u2026": "...",  # ellipsis …
    "\u00ab": '"',    # «
    "\u00bb": '"',    # »
})


def _safe(text: str) -> str:
    """Replace characters outside latin-1 with safe ASCII equivalents."""
    return text.translate(_UNICODE_MAP).encode("latin-1", errors="replace").decode("latin-1")


def _parse_charte() -> list[tuple[str, str]]:
    """Parse CHARTE.md into a list of (heading, body) tuples."""
    text = _CHARTE_PATH.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for line in text.splitlines():
        if line.startswith(_HEADING_PREFIX):
            if current_heading or current_body:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line)

    if current_heading or current_body:
        sections.append((current_heading, "\n".join(current_body).strip()))

    return sections


class _CharterPDF(FPDF):
    def __init__(self, prenom: str, nom: str, signed_at: str) -> None:
        super().__init__()
        self._user_name = _safe(f"{prenom} {nom}")
        self._signed_at = _safe(signed_at)

    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-18)
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, _safe(f"Signe par {self._user_name} le {self._signed_at}"), align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def generate_charter_pdf(prenom: str, nom: str, signed_at: str) -> bytes:
    """Generate a PDF of the hosting charter with the user's signature info.

    :param prenom: User's first name.
    :param nom: User's last name.
    :param signed_at: ISO date string of signature.
    :returns: Raw PDF bytes.
    :rtype: bytes
    """
    pdf = _CharterPDF(prenom=prenom, nom=nom, signed_at=signed_at)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    for heading, body in _parse_charte():
        if not heading and not body:
            continue

        if heading:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)
            pdf.multi_cell(0, 7, _safe(heading))
            pdf.ln(1)

        if body:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    pdf.set_x(pdf.l_margin + 5)
                    pdf.multi_cell(0, 6, _safe(f"- {stripped[2:]}"), new_x="LMARGIN")
                elif stripped == "":
                    pdf.ln(2)
                else:
                    pdf.multi_cell(0, 6, _safe(stripped))
            pdf.ln(2)

    # Signature block
    pdf.ln(6)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, _safe("Signature electronique"))
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _safe(
        f"Je soussigne(e) {prenom} {nom} declare avoir pris connaissance de la presente "
        "charte d'utilisation et m'engage a en respecter les termes."
    ))
    pdf.ln(4)
    pdf.cell(0, 6, _safe(f"Date de signature : {signed_at}"))

    return bytes(pdf.output())
