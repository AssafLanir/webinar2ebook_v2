"""EPUB stylesheet for e-reader compatible styling.

CSS optimized for e-readers following best practices:
- Use relative units (em, %) not pixels
- Avoid fixed positioning
- Use page-break-* for chapter breaks
- Keep colors simple (some e-readers are grayscale)
- Don't rely on web fonts (may not load)

Source: specs/007-tab4-epub-export/research.md section 5
"""

EPUB_STYLESHEET = """
/* Basic reset and typography */
body {
  font-family: serif;
  line-height: 1.6;
  margin: 1em;
}

/* Headings */
h1 {
  font-size: 1.5em;
  margin-top: 2em;
  margin-bottom: 0.5em;
  page-break-before: always;
}

h2 {
  font-size: 1.2em;
  margin-top: 1.5em;
  margin-bottom: 0.3em;
}

h3 {
  font-size: 1.1em;
  margin-top: 1.2em;
  margin-bottom: 0.2em;
}

/* Cover page */
.cover {
  text-align: center;
  margin-top: 30%;
}

.cover h1 {
  font-size: 2em;
  page-break-before: avoid;
}

.cover .subtitle {
  font-size: 1.2em;
  color: #666;
  margin-top: 0.5em;
}

.cover .credits {
  font-size: 0.9em;
  color: #888;
  margin-top: 3em;
}

/* Images */
figure {
  text-align: center;
  margin: 1.5em 0;
  page-break-inside: avoid;
}

figure img {
  max-width: 100%;
  height: auto;
}

figcaption {
  font-size: 0.85em;
  color: #666;
  margin-top: 0.5em;
  font-style: italic;
}

/* Paragraphs */
p {
  margin: 0.5em 0;
  text-indent: 1em;
}

p:first-of-type {
  text-indent: 0;
}

/* Lists */
ul, ol {
  margin: 1em 0;
  padding-left: 2em;
}

li {
  margin: 0.3em 0;
}

/* Code blocks */
pre, code {
  font-family: monospace;
  font-size: 0.9em;
  background-color: #f5f5f5;
}

pre {
  padding: 0.5em;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* Blockquotes */
blockquote {
  margin: 1em 0;
  padding-left: 1em;
  border-left: 3px solid #ccc;
  font-style: italic;
}

/* Links */
a {
  color: #0066cc;
  text-decoration: underline;
}

/* Horizontal rules */
hr {
  border: none;
  border-top: 1px solid #ccc;
  margin: 2em 0;
}

/* Tables (basic support) */
table {
  border-collapse: collapse;
  margin: 1em 0;
  width: 100%;
}

th, td {
  border: 1px solid #ccc;
  padding: 0.5em;
  text-align: left;
}

th {
  background-color: #f5f5f5;
  font-weight: bold;
}
""".strip()
