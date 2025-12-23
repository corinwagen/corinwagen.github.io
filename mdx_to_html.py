#!/usr/bin/env python3
"""A more complete Markdown to HTML converter."""

import re
import sys


def esc(s: str) -> str:
    """Escape HTML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(s: str) -> str:
    """Escape for use in HTML attributes."""
    return esc(s).replace('"', "&quot;")


def inline(s: str) -> str:
    """Process inline markdown: links, bold, italic, code, strikethrough."""
    # First, handle code spans (to protect their contents from other processing)
    code_spans = []
    def save_code(m):
        code_spans.append(f"<code>{esc(m.group(1))}</code>")
        return f"\x00CODE{len(code_spans)-1}\x00"
    
    s = re.sub(r"`([^`]+)`", save_code, s)
    
    # Escape HTML in remaining text (but we need to do this carefully)
    # Process in chunks between code placeholders
    parts = re.split(r"(\x00CODE\d+\x00)", s)
    for i, part in enumerate(parts):
        if not part.startswith("\x00CODE"):
            parts[i] = esc(part)
    s = "".join(parts)
    
    # Links: [text](url)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{esc_attr(m.group(2))}">{m.group(1)}</a>',
        s
    )
    
    # Images: ![alt](url)
    s = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: f'<img src="{esc_attr(m.group(2))}" alt="{esc_attr(m.group(1))}"/>',
        s
    )
    
    # Bold + Italic: ***text*** or ___text___
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", s)
    s = re.sub(r"___(.+?)___", r"<strong><em>\1</em></strong>", s)
    
    # Bold: **text** or __text__
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"__(.+?)__", r"<strong>\1</strong>", s)
    
    # Italic: *text* or _text_
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", s)
    
    # Strikethrough: ~~text~~
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    
    # Restore code spans
    for i, code in enumerate(code_spans):
        s = s.replace(f"\x00CODE{i}\x00", code)
    
    return s


def md_to_html(txt: str) -> str:
    """Convert markdown text to HTML."""
    lines = txt.splitlines()
    html = []
    buf = []
    i = 0
    
    def flush_p():
        nonlocal buf
        if buf:
            html.append(f"<p>{inline(' '.join(buf).strip())}</p>")
            buf = []
    
    def parse_list(start_idx: int, indent: int = 0):
        """Parse ordered or unordered lists, handling nesting."""
        nonlocal i
        items = []
        current_item = []
        list_type = None
        
        while i < len(lines):
            ln = lines[i]
            stripped = ln.lstrip()
            current_indent = len(ln) - len(stripped)
            
            # Check for list item
            ul_match = re.match(r"^[-*+]\s+(.*)$", stripped)
            ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
            
            if current_indent < indent and stripped:
                # Dedented non-empty line, end this list level
                break
            
            if current_indent == indent:
                if ul_match:
                    if list_type is None:
                        list_type = "ul"
                    if current_item:
                        items.append(current_item)
                        current_item = []
                    current_item.append(ul_match.group(1))
                    i += 1
                elif ol_match:
                    if list_type is None:
                        list_type = "ol"
                    if current_item:
                        items.append(current_item)
                        current_item = []
                    current_item.append(ol_match.group(1))
                    i += 1
                elif not stripped:
                    # Empty line
                    i += 1
                else:
                    # Non-list line at same indent, end list
                    break
            elif current_indent > indent and current_item:
                # Could be continuation or nested list
                nested_ul = re.match(r"^[-*+]\s+", stripped)
                nested_ol = re.match(r"^\d+\.\s+", stripped)
                if nested_ul or nested_ol:
                    # Nested list - parse it
                    nested = parse_list(i, current_indent)
                    current_item.append(nested)
                else:
                    # Continuation of current item
                    current_item.append(stripped)
                    i += 1
            else:
                i += 1
        
        if current_item:
            items.append(current_item)
        
        if not items or list_type is None:
            return ""
        
        # Build HTML
        tag = list_type
        result = [f"<{tag}>"]
        for item in items:
            content_parts = []
            for part in item:
                if isinstance(part, str):
                    content_parts.append(inline(part))
                else:
                    content_parts.append(part)
            result.append(f"<li>{' '.join(content_parts)}</li>")
        result.append(f"</{tag}>")
        return "\n".join(result)
    
    while i < len(lines):
        ln = lines[i].rstrip()
        stripped = ln.lstrip()
        
        # Empty line
        if not stripped:
            flush_p()
            i += 1
            continue
        
        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", stripped) and len(set(stripped)) == 1:
            flush_p()
            html.append("<hr/>")
            i += 1
            continue
        
        # Fenced code block
        if stripped.startswith("```"):
            flush_p()
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].rstrip().startswith("```"):
                code_lines.append(esc(lines[i].rstrip()))
                i += 1
            i += 1  # Skip closing ```
            lang_attr = f' class="language-{esc_attr(lang)}"' if lang else ""
            html.append(f"<pre><code{lang_attr}>{chr(10).join(code_lines)}</code></pre>")
            continue
        
        # Blockquote
        if stripped.startswith(">"):
            flush_p()
            bq_lines = []
            while i < len(lines):
                ln2 = lines[i].rstrip()
                if ln2.lstrip().startswith(">"):
                    text = ln2.lstrip()[1:].lstrip()
                    bq_lines.append(text)
                    i += 1
                elif not ln2.strip() and bq_lines:
                    # Empty line might continue blockquote
                    if i + 1 < len(lines) and lines[i + 1].lstrip().startswith(">"):
                        bq_lines.append("")
                        i += 1
                    else:
                        break
                else:
                    break
            # Recursively process blockquote content
            inner = md_to_html("\n".join(bq_lines))
            html.append(f"<blockquote>{inner}</blockquote>")
            continue
        
        # Headers
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            flush_p()
            n = len(m.group(1))
            text = m.group(2).strip()
            # Remove trailing # if present
            text = re.sub(r"\s*#+\s*$", "", text)
            html.append(f"<h{n}>{inline(text)}</h{n}>")
            i += 1
            continue
        
        # Setext-style headers (underlined)
        if i + 1 < len(lines):
            next_ln = lines[i + 1].rstrip()
            if re.match(r"^=+$", next_ln):
                flush_p()
                html.append(f"<h1>{inline(stripped)}</h1>")
                i += 2
                continue
            if re.match(r"^-+$", next_ln) and len(next_ln) >= 2:
                flush_p()
                html.append(f"<h2>{inline(stripped)}</h2>")
                i += 2
                continue
        
        # Lists
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            flush_p()
            list_html = parse_list(i, len(ln) - len(stripped))
            if list_html:
                html.append(list_html)
            continue
        
        # Regular paragraph text
        buf.append(stripped)
        i += 1
    
    flush_p()
    return "\n".join(html)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            src = f.read()
    else:
        src = sys.stdin.read()
    
    print(md_to_html(src))
