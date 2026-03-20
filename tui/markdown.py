"""Convert Markdown to Textual markup with clickable links."""

from __future__ import annotations

import re
from markdown_it import MarkdownIt

_BARE_URL_RE = re.compile(r'(https?://[^\s)\]>\"\']+)')


def _escape(text: str) -> str:
    """Escape brackets so Textual doesn't interpret them as markup."""
    return text.replace("[", "\\[").replace("]", "\\]")


def _escape_url(url: str) -> str:
    """Escape single quotes inside a URL for safe embedding in markup."""
    return url.replace("'", "\\'")


def _linkify(text: str) -> str:
    """Wrap bare URLs in escaped text with clickable markup."""
    def _replace(m: re.Match) -> str:
        url = m.group(1).rstrip(".,;:!?)")
        trail = m.group(1)[len(url):]
        return f"[@click=app.open_link('{_escape_url(url)}')]{_escape(url)}[/]{_escape(trail)}"
    return _BARE_URL_RE.sub(_replace, text)


def markdown_to_markup(source: str) -> str:
    """Parse *source* markdown and return a Textual markup string."""
    md = MarkdownIt()
    tokens = md.parse(source)
    return _render_tokens(tokens)


def _render_tokens(tokens: list) -> str:
    parts: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # --- block-level tokens ---

        if tok.type == "heading_open":
            level = int(tok.tag[1])  # h1 -> 1, h2 -> 2
            inline_tok = tokens[i + 1]  # heading content (inline)
            inner = _render_inline(inline_tok.children or [])
            if level == 1:
                parts.append(f"\n[bold #ec4899]{inner}[/]\n")
            elif level == 2:
                parts.append(f"\n[bold #f9a8d4]{inner}[/]\n")
            else:
                parts.append(f"\n[bold #d1c4e9]{inner}[/]\n")
            i += 3  # heading_open, inline, heading_close
            continue

        if tok.type == "paragraph_open":
            inline_tok = tokens[i + 1]
            inner = _render_inline(inline_tok.children or [])
            parts.append(f"{inner}\n")
            i += 3  # paragraph_open, inline, paragraph_close
            continue

        if tok.type == "fence":
            lang = tok.info.strip() if tok.info else ""
            code = _escape(tok.content.rstrip("\n"))
            if lang:
                parts.append(f"\n[#6b5b7b]{_escape(lang)}[/]\n[on #1a1428]{code}[/on #1a1428]\n")
            else:
                parts.append(f"\n[on #1a1428]{code}[/on #1a1428]\n")
            i += 1
            continue

        if tok.type == "code_block":
            code = _escape(tok.content.rstrip("\n"))
            parts.append(f"\n[on #1a1428]{code}[/on #1a1428]\n")
            i += 1
            continue

        if tok.type == "bullet_list_open":
            items, end = _collect_list_items(tokens, i + 1, "bullet_list_close", ordered=False)
            parts.append(items)
            i = end + 1
            continue

        if tok.type == "ordered_list_open":
            items, end = _collect_list_items(tokens, i + 1, "ordered_list_close", ordered=True)
            parts.append(items)
            i = end + 1
            continue

        if tok.type == "blockquote_open":
            inner, end = _collect_blockquote(tokens, i + 1)
            parts.append(inner)
            i = end + 1
            continue

        if tok.type == "hr":
            parts.append("[#272036]─────────────────────────────────────────[/]\n")
            i += 1
            continue

        # Fallback — skip open/close tokens we handle elsewhere
        i += 1

    return "".join(parts)


def _render_inline(children: list) -> str:
    """Render inline tokens to Textual markup."""
    parts: list[str] = []
    in_link = False
    for tok in children:
        if tok.type == "text":
            escaped = _escape(tok.content)
            # Only linkify bare URLs in text outside of explicit markdown links
            if not in_link:
                escaped = _linkify(escaped)
            parts.append(escaped)
        elif tok.type == "code_inline":
            parts.append(f"[bold #f9a8d4 on #1a1428] {_escape(tok.content)} [/]")
        elif tok.type == "strong_open":
            parts.append("[bold]")
        elif tok.type == "strong_close":
            parts.append("[/bold]")
        elif tok.type == "em_open":
            parts.append("[italic]")
        elif tok.type == "em_close":
            parts.append("[/italic]")
        elif tok.type == "link_open":
            in_link = True
            href = ""
            if tok.attrs:
                href = tok.attrs.get("href", "")
            parts.append(f"[@click=app.open_link('{_escape_url(href)}')]")
        elif tok.type == "link_close":
            in_link = False
            parts.append("[/]")
        elif tok.type == "image":
            alt = _escape(tok.content) if tok.content else "image"
            href = ""
            if tok.attrs:
                href = tok.attrs.get("src", "")
            parts.append(f"[@click=app.open_link('{_escape_url(href)}')]{alt}[/]")
        elif tok.type == "softbreak":
            parts.append("\n")
        elif tok.type == "hardbreak":
            parts.append("\n")
        else:
            # Unknown inline token — render content if present
            if tok.content:
                parts.append(_escape(tok.content))
    return "".join(parts)


def _collect_list_items(
    tokens: list, start: int, close_type: str, ordered: bool
) -> tuple[str, int]:
    """Collect list items and return (markup, index_of_close_token)."""
    parts: list[str] = []
    item_num = 1
    i = start
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == close_type:
            return "".join(parts), i

        if tok.type == "list_item_open":
            # Collect inline content of the item
            inner_parts: list[str] = []
            i += 1
            while i < len(tokens) and tokens[i].type != "list_item_close":
                if tokens[i].type == "paragraph_open":
                    inline_tok = tokens[i + 1]
                    text = _render_inline(inline_tok.children or [])
                    inner_parts.append(text)
                    i += 3
                elif tokens[i].type == "bullet_list_open":
                    nested, end = _collect_list_items(tokens, i + 1, "bullet_list_close", ordered=False)
                    inner_parts.append("\n" + _indent(nested, 4))
                    i = end + 1
                elif tokens[i].type == "ordered_list_open":
                    nested, end = _collect_list_items(tokens, i + 1, "ordered_list_close", ordered=True)
                    inner_parts.append("\n" + _indent(nested, 4))
                    i = end + 1
                else:
                    i += 1

            content = "".join(inner_parts)
            if ordered:
                parts.append(f"  {item_num}. {content}\n")
                item_num += 1
            else:
                parts.append(f"  • {content}\n")
            i += 1  # skip list_item_close
            continue

        i += 1

    return "".join(parts), i


def _collect_blockquote(tokens: list, start: int) -> tuple[str, int]:
    """Collect blockquote contents and return (markup, index_of_close_token)."""
    inner_tokens: list = []
    i = start
    depth = 1
    while i < len(tokens):
        if tokens[i].type == "blockquote_open":
            depth += 1
        elif tokens[i].type == "blockquote_close":
            depth -= 1
            if depth == 0:
                break
        inner_tokens.append(tokens[i])
        i += 1

    inner = _render_tokens(inner_tokens)
    # Prefix each line with quote bar
    lines = inner.rstrip("\n").split("\n")
    quoted = "\n".join(f"[#6b5b7b]│ {line}[/]" for line in lines)
    return quoted + "\n", i


def _indent(text: str, spaces: int) -> str:
    """Indent each line of text by *spaces*."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.split("\n"))
