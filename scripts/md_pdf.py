"""Render a plain markdown file (headings, tables, lists, bold, code, links) to PDF with headless Chrome.
    python3 scripts/md_pdf.py docs/guide/16-posts-30-days.md out/prod/16-posts-30-days.pdf
"""
import html, re, subprocess, sys, tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CSS = """body{font:10.5px -apple-system,Helvetica,Arial,sans-serif;color:#222;margin:0}
h1{font-size:20px}h2{font-size:16px;margin-top:22px;border-bottom:1px solid #ccc}h3{font-size:13px;margin:16px 0 4px;page-break-after:avoid}
table{border-collapse:collapse;width:100%;margin:4px 0 10px;page-break-inside:auto}tr{page-break-inside:avoid}
th,td{border:1px solid #ccc;padding:3px 5px;vertical-align:top;text-align:left}th{background:#f2f2f2}
code{background:#f3f3f3;padding:0 3px;border-radius:3px;font-size:9.5px}hr{border:0;border-top:1px solid #ddd;margin:18px 0}
td:first-child{white-space:nowrap}"""

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s)
    return s

def convert(md):
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>")
            out += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[2:]]
            out.append("</table>"); continue
        m = re.match(r"(#{1,4}) (.*)", l)
        if m: out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
        elif l.strip() == "---": out.append("<hr>")
        elif re.match(r"\s*[-*] ", l):
            out.append("<ul>")
            while i < len(lines) and re.match(r"\s*[-*] |\s{2,}\S", lines[i]):
                if re.match(r"\s*[-*] ", lines[i]): out.append("<li>" + inline(re.sub(r"^\s*[-*] ", "", lines[i])))
                else: out[-1] += " " + inline(lines[i].strip())
                i += 1
            out.append("</ul>"); continue
        elif l.strip(): out.append(f"<p>{inline(l)}</p>")
        i += 1
    return "\n".join(out)

src, dst = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
page = f"<!doctype html><meta charset=utf-8><title>{src.stem}</title><style>{CSS}</style>{convert(src.read_text())}"
with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
    f.write(page)
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={dst}", f"file://{f.name}"],
               check=True, capture_output=True)
print(dst)
