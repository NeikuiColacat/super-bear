from packages.ingestion.parsers.sec_filing_html import extract_sec_filing_text


def test_extract_sec_filing_text_removes_markup_and_normalizes_spacing() -> None:
    html = b"""
    <html>
      <head><title>Filing</title><script>ignore()</script></head>
      <body>
        <h1>Apple Inc.</h1>
        <p>Revenue increased&nbsp;year over year.</p>
        <style>.hidden { display: none; }</style>
      </body>
    </html>
    """

    text = extract_sec_filing_text(html)

    assert text == "Filing Apple Inc. Revenue increased year over year."


def test_extract_sec_filing_text_skips_inline_xbrl_hidden_metadata() -> None:
    html = b"""
    <html>
      <body>
        <div style="display:none">
          <ix:header>
            <ix:hidden>aapl-20260328 false 2026 Q2</ix:hidden>
          </ix:header>
        </div>
        <p>Management discusses product demand.</p>
      </body>
    </html>
    """

    text = extract_sec_filing_text(html)

    assert text == "Management discusses product demand."
