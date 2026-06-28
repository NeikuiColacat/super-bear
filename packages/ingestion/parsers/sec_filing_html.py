from __future__ import annotations

from html.parser import HTMLParser
import re


_WHITESPACE = re.compile(r"\s+")


class _SecFilingTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._ignore_stack: list[bool] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ignored = (
            self._ignored_depth > 0
            or tag.lower() in {"script", "style", "ix:header", "ix:hidden"}
            or _has_hidden_style(attrs)
        )
        self._ignore_stack.append(ignored)
        if ignored:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._ignore_stack:
            return
        ignored = self._ignore_stack.pop()
        if ignored and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        return None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return _WHITESPACE.sub(" ", " ".join(self._parts)).strip()


def extract_sec_filing_text(content: bytes) -> str:
    parser = _SecFilingTextParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.text()


def _has_hidden_style(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        if name.lower() == "style" and value:
            normalized = value.replace(" ", "").lower()
            if "display:none" in normalized:
                return True
    return False
