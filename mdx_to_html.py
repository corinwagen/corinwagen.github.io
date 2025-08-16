import re, sys


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(s):
    return esc(s).replace('"', "&quot;")


def inline(s):
    out, i = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", s):
        out.append(esc(s[i : m.start()]))
        out.append(f'<a href="{esc_attr(m.group(2))}">{esc(m.group(1))}</a>')
        i = m.end()
    out.append(esc(s[i:]))
    return "".join(out)


def md_to_html(txt):
    lines, html, buf, i = txt.splitlines(), [], [], 0

    def flush_p():
        nonlocal buf
        if buf:
            html.append(f"<p>{inline(' '.join(buf).strip())}</p>")
            buf = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush_p()
            i += 1
            continue
        if ln.lstrip().startswith(">"):
            flush_p()
            bq = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                t = lines[i].lstrip()[1:].lstrip()
                bq.append(inline(t))
                i += 1
            html.append(f"<blockquote>{'<br/>'.join(bq).strip()}</blockquote>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            flush_p()
            n, t = len(m.group(1)), m.group(2).strip()
            html.append(f"<h{n}>{inline(t)}</h{n}>")
            i += 1
            continue
        buf.append(ln.strip())
        i += 1
    flush_p()
    return "\n".join(html)


if __name__ == "__main__":
    src = (
        open(sys.argv[1], encoding="utf-8").read()
        if len(sys.argv) > 1
        else sys.stdin.read()
    )
    print(md_to_html(src))
