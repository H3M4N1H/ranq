"""HTML -> PageData extraction with selectolax."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import quote, unquote, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode as Node

from ranq.models import Heading, Hreflang, Image, Link, PageData
from ranq.urls import normalize, same_site

WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)
WS_RE = re.compile(r"\s+")
NON_CONTENT = "script, style, noscript, template, svg, iframe"
BOILERPLATE = (
    "nav, header, footer, aside, form, [role=navigation], [role=banner], [role=contentinfo]"
)
BLOCKS = "p, li, h1, h2, h3, h4, h5, h6, td, th, dd, dt, blockquote, figcaption, pre, summary"


SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)\]%])")
# Inline styles that make an element invisible. Entrance animations often server-render text
# at opacity:0 and reveal it only after JavaScript runs.
INLINE_HIDDEN_RE = re.compile(
    r"opacity\s*:\s*0(?:\.0+)?\s*(?:;|!|$)|visibility\s*:\s*hidden|display\s*:\s*none", re.I
)


def _inline_hidden(node: Node) -> bool:
    return node.tag not in ("-text", "-comment") and bool(
        INLINE_HIDDEN_RE.search(node.attributes.get("style") or "")
    )


def _visible_text(node: Node) -> str:
    if node.tag == "-text":
        return node.text_content or ""
    if node.tag in ("-comment", "script", "style", "template") or _inline_hidden(node):
        return ""
    parts = []
    child = node.child
    while child is not None:
        parts.append(_visible_text(child))
        child = child.next
    return " ".join(parts)


def hidden_in_html(node: Node) -> bool:
    """True when the element has text but none of it is visible as served: it, an ancestor,
    or every text-bearing descendant is styled invisible inline."""
    if not clean(node.text()):
        return False
    parent = node.parent
    while parent is not None and parent.tag not in ("body", "html"):
        if _inline_hidden(parent):
            return True
        parent = parent.parent
    return not clean(_visible_text(node))


# Tailwind-style fixed sizes: w-10, h-[120px], size-8, md:w-24, aspect-video ...
SIZE_CLASS_RE = re.compile(
    r"^(?:[\w-]+:)*(?:(?P<axis>w|h|size)-(?:\d+(?:\.\d+)?|px|\[[^\]]+\])|(?P<aspect>aspect-\S+))$"
)


def css_sized(style: str | None, classes: str | None) -> bool:
    """True when CSS reserves the image's box, so it cannot cause layout shift on load:
    inline width+height or aspect-ratio (Next.js `fill` images use width/height:100% of a
    sized parent), or fixed-size utility classes."""
    decl = {}
    for part in (style or "").split(";"):
        key, _, value = part.partition(":")
        if value.strip():
            decl[key.strip().lower()] = value.strip()
    if "aspect-ratio" in decl or ("width" in decl and "height" in decl):
        return True
    axes: set[str] = set()
    for token in (classes or "").split():
        match = SIZE_CLASS_RE.match(token)
        if match is None:
            continue
        if match.group("aspect"):
            return True
        axis = match.group("axis")
        axes |= {"w", "h"} if axis == "size" else {axis}
    return axes == {"w", "h"}


def clean(text: str | None) -> str:
    return SPACE_BEFORE_PUNCT.sub(r"\1", WS_RE.sub(" ", text or "")).strip()


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def simhash(text: str, bits: int = 64) -> int:
    """64-bit SimHash over word 3-shingles for near-duplicate detection."""
    tokens = [t.lower() for t in words(text)]
    shingles = [" ".join(tokens[i : i + 3]) for i in range(max(1, len(tokens) - 2))]
    if not tokens:
        return 0
    vector = [0] * bits
    for shingle in shingles:
        h = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for i in range(bits):
            vector[i] += 1 if h >> i & 1 else -1
    return sum(1 << i for i in range(bits) if vector[i] > 0)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def main_content_node(tree: HTMLParser) -> Node | None:
    for selector in ("main", "[role=main]", "article"):
        node = tree.css_first(selector)
        if node is not None and len(clean(node.text(separator=" "))) > 50:
            return node
    return tree.body


def html_to_text(html: str) -> str:
    tree = HTMLParser(html)
    for node in tree.css(NON_CONTENT):
        node.decompose()
    return clean(tree.body.text(separator=" ")) if tree.body else ""


def parse_html(page: PageData, html: str, site: str) -> PageData:
    tree = HTMLParser(html)
    page.html = html
    base = page.final_url
    base_node = tree.css_first("base[href]")
    if base_node is not None:
        base = normalize(base_node.attributes.get("href") or "", page.final_url) or base

    head_titles = tree.css("head title") or tree.css("title")
    page.titles_count = len(head_titles)
    if head_titles:
        page.title = clean(head_titles[0].text())

    html_node = tree.css_first("html")
    if html_node is not None:
        page.lang = html_node.attributes.get("lang")

    for meta in tree.css("meta"):
        attrs = meta.attributes
        name = (attrs.get("name") or "").lower()
        prop = (attrs.get("property") or "").lower()
        content = attrs.get("content") or ""
        if attrs.get("charset"):
            page.charset = attrs.get("charset")
        if (attrs.get("http-equiv") or "").lower() == "content-type" and "charset=" in content:
            page.charset = content.split("charset=", 1)[1]
        if name == "description":
            page.meta_descriptions_count += 1
            if page.meta_description is None:
                page.meta_description = clean(content)
        elif name in ("robots", "googlebot"):
            page.meta_robots = ",".join(filter(None, [page.meta_robots, content]))
        elif name == "viewport":
            page.viewport = content
        elif name.startswith("twitter:"):
            page.twitter[name] = content
        elif name:
            page.meta[name] = content
        if prop.startswith(("og:", "article:")):
            page.open_graph[prop] = content

    for link in tree.css("link[rel]"):
        rel = (link.attributes.get("rel") or "").lower().split()
        href = link.attributes.get("href") or ""
        if "canonical" in rel:
            page.canonicals_count += 1
            if page.canonical is None:
                page.canonical = normalize(href, base) or href
        if "alternate" in rel and link.attributes.get("hreflang"):
            target = normalize(href, base)
            if target:
                page.hreflangs.append(Hreflang(link.attributes.get("hreflang") or "", target))

    page.json_ld = [
        node.text() for node in tree.css('script[type="application/ld+json"]') if node.text()
    ]
    page.has_microdata = tree.css_first("[itemscope]") is not None
    page.has_rdfa = tree.css_first("[typeof]") is not None

    page.times = [
        t.attributes.get("datetime") or clean(t.text())
        for t in tree.css("time")
        if t.attributes.get("datetime") or t.text()
    ]

    # Semantic sections can exist without native fragment navigation (e.g. JS scroll).
    # Require body content beyond headings/link labels; do not infer from an ID alone.
    section_tree = HTMLParser(html)
    for node in section_tree.css(NON_CONTENT + ", nav, [role=navigation]"):
        node.decompose()
    page.content_sections = []
    for node in section_tree.css("section[id], [role=region][id]"):
        ancestor: Node | None = node
        hidden = False
        while ancestor is not None:
            if (
                "hidden" in ancestor.attributes
                or ancestor.attributes.get("aria-hidden") == "true"
                or _inline_hidden(ancestor)
            ):
                hidden = True
                break
            ancestor = ancestor.parent
        body = " ".join(clean(n.text(separator=" ")) for n in node.css("p, li, address, form"))
        section_id = node.attributes.get("id")
        if not hidden and section_id and len(body.split()) >= 8:
            page.content_sections.append(
                f"{normalize(page.final_url)}#{quote(section_id, safe='')}"
            )

    # Mixed content: http:// subresources on an https page
    if page.final_url.startswith("https://"):
        for node in tree.css("img[src], script[src], link[rel=stylesheet][href], iframe[src]"):
            ref = node.attributes.get("src") or node.attributes.get("href") or ""
            if ref.startswith("http://"):
                page.mixed_content.append(ref)

    # Do not turn #section links into extra pages, but retain real section targets for
    # navigation/trust checks. A placeholder #privacy without a target is not evidence.
    section_ids = {
        n.attributes["id"]
        for n in tree.css("[id]")
        if n.attributes.get("id") and clean(n.text(separator=" "))
    }
    page.section_links = []
    for node in tree.css("a[href]"):
        href = node.attributes.get("href") or ""
        resolved = urljoin(base, href)
        fragment = urlsplit(resolved).fragment
        target = normalize(resolved)
        if fragment and target == normalize(page.final_url):
            if unquote(fragment) in section_ids:
                section_url = f"{target}#{fragment}"
                if section_url not in page.section_links:
                    page.section_links.append(section_url)
            continue
        target = normalize(href, base)
        if target is None:
            continue
        page.links.append(
            Link(
                url=target,
                text=clean(node.text(separator=" "))
                or clean(node.attributes.get("aria-label"))
                or clean((node.css_first("img[alt]") or node).attributes.get("alt")),
                rel=node.attributes.get("rel") or "",
                internal=same_site(target, site),
            )
        )

    for node in tree.css("img"):
        attrs = node.attributes
        src = attrs.get("src") or attrs.get("data-src") or ""
        page.images.append(
            Image(
                src=normalize(src, base) or src,
                alt=attrs.get("alt"),
                width=attrs.get("width"),
                height=attrs.get("height"),
                loading=attrs.get("loading"),
                css_sized=css_sized(attrs.get("style"), attrs.get("class")),
            )
        )

    for node in tree.css("h1, h2, h3, h4, h5, h6"):
        page.headings.append(Heading(int((node.tag or "h1")[1]), clean(node.text(separator=" "))))
    h1_nodes = tree.css("h1")
    page.h1_hidden = bool(h1_nodes) and all(hidden_in_html(n) for n in h1_nodes)

    for node in tree.css(NON_CONTENT):
        node.decompose()
    main_node = main_content_node(tree)
    if main_node is not None:
        for node in main_node.css(BOILERPLATE) if main_node.tag in ("body",) else []:
            node.decompose()
        page.text = clean(main_node.text(separator=" "))
        page.paragraphs = [
            p for p in (clean(n.text(separator=" ")) for n in main_node.css("p")) if p
        ]
        page.outline = [
            (n.tag or "", text)
            for n in main_node.css(BLOCKS)
            if (text := clean(n.text(separator=" ")))
        ]
        page.blocks = [text for _, text in page.outline]
        page.has_details = main_node.css_first("details") is not None
        page.lists_count = len(main_node.css("ul, ol"))
        page.tables_count = len(main_node.css("table"))
    page.word_count = len(words(page.text))
    page.content_hash = hashlib.sha256(page.text.lower().encode()).hexdigest() if page.text else ""
    page.simhash = simhash(page.text)
    return page
