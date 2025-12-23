"""CSS styles for ebook preview and PDF export.

These styles are embedded in the HTML document for both
browser preview and WeasyPrint PDF generation.
"""

# Base styles for both preview and PDF
EBOOK_BASE_CSS = """
/* Base typography */
body {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 12pt;
  line-height: 1.6;
  color: #333;
  max-width: 800px;
  margin: 0 auto;
  padding: 2em;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
  font-family: 'Helvetica Neue', Arial, sans-serif;
  color: #222;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

h1 {
  font-size: 24pt;
  border-bottom: 2px solid #333;
  padding-bottom: 0.3em;
}

h2 {
  font-size: 18pt;
}

h3 {
  font-size: 14pt;
}

/* Paragraphs */
p {
  margin: 1em 0;
  text-align: justify;
}

/* Lists */
ul, ol {
  margin: 1em 0;
  padding-left: 2em;
}

li {
  margin: 0.5em 0;
}

/* Code */
code {
  font-family: 'Courier New', monospace;
  background: #f4f4f4;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
}

pre {
  background: #f4f4f4;
  padding: 1em;
  border-radius: 5px;
  overflow-x: auto;
  font-size: 0.9em;
}

pre code {
  background: none;
  padding: 0;
}

/* Tables */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

th, td {
  border: 1px solid #ddd;
  padding: 0.5em;
  text-align: left;
}

th {
  background: #f4f4f4;
  font-weight: bold;
}

/* Blockquotes */
blockquote {
  border-left: 4px solid #ddd;
  margin: 1em 0;
  padding-left: 1em;
  color: #666;
  font-style: italic;
}

/* Links */
a {
  color: #0066cc;
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}
"""

# Cover page styles
COVER_CSS = """
/* Cover page */
.cover {
  text-align: center;
  padding: 20% 2em 2em;
  min-height: 60vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-bottom: 2px solid #333;
  margin-bottom: 2em;
}

.cover h1 {
  font-size: 32pt;
  margin-bottom: 0.5em;
  border: none;
  color: #111;
}

.cover h2 {
  font-size: 18pt;
  font-weight: normal;
  color: #666;
  margin-top: 0;
}

.cover .credits {
  margin-top: 3em;
  font-size: 10pt;
  color: #888;
}
"""

# Table of Contents styles
TOC_CSS = """
/* Table of Contents */
.toc {
  margin: 2em 0;
  padding-bottom: 2em;
  border-bottom: 1px solid #ddd;
}

.toc h2 {
  font-size: 18pt;
  margin-bottom: 1em;
  border: none;
}

.toc ul {
  list-style-type: none;
  padding-left: 0;
}

.toc li {
  margin: 0.5em 0;
}

.toc li li {
  padding-left: 1.5em;
}

.toc a {
  color: #333;
  text-decoration: none;
}

.toc a:hover {
  color: #0066cc;
}
"""

# Figure/image styles
FIGURE_CSS = """
/* Figures and images */
figure {
  margin: 1.5em 0;
  text-align: center;
}

figure img {
  max-width: 100%;
  height: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}

figcaption {
  font-size: 10pt;
  color: #666;
  margin-top: 0.5em;
  font-style: italic;
}
"""

# PDF-specific styles (page breaks, print formatting)
PDF_CSS = """
/* PDF-specific styles */
@page {
  size: A4;
  margin: 2cm;
}

/* Cover page - full page */
.cover {
  page-break-after: always;
}

/* TOC - full page */
.toc {
  page-break-after: always;
}

/* Chapters start on new page */
.chapter h1:first-child,
article > h1:first-child {
  page-break-before: always;
}

/* First chapter doesn't need break (after TOC) */
.chapter:first-of-type h1:first-child {
  page-break-before: auto;
}

/* Avoid orphans/widows */
p {
  orphans: 3;
  widows: 3;
}

/* Keep figures together */
figure {
  page-break-inside: avoid;
}

/* Keep headings with following content */
h1, h2, h3, h4, h5, h6 {
  page-break-after: avoid;
}
"""

# Preview-specific styles (browser rendering)
PREVIEW_CSS = """
/* Preview-specific styles */
body {
  background: #fff;
}

.preview-container {
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
  background: #fff;
  min-height: 100vh;
}
"""


def get_preview_styles() -> str:
    """Get combined CSS for browser preview."""
    return "\n".join([
        EBOOK_BASE_CSS,
        COVER_CSS,
        TOC_CSS,
        FIGURE_CSS,
        PREVIEW_CSS,
    ])


def get_pdf_styles() -> str:
    """Get combined CSS for PDF export."""
    return "\n".join([
        EBOOK_BASE_CSS,
        COVER_CSS,
        TOC_CSS,
        FIGURE_CSS,
        PDF_CSS,
    ])
