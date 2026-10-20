"""JSON-LD generator. Fills values only from crawl data or ranq.yaml; anything unknown is
left out and listed under `todo`, never invented."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from ranq.analysis import aeo
from ranq.analysis import pagetype as pt
from ranq.config import EntityConfig
from ranq.crawler.crawler import CrawlResult
from ranq.models import PageData

CONTEXT = "https://schema.org"


@dataclass(slots=True)
class SchemaDoc:
    url: str
    kind: str
    data: dict[str, Any]
    todo: list[str] = field(default_factory=list)

    def script_tag(self) -> str:
        return script_tag(self.data)


def script_tag(data: dict[str, Any]) -> str:
    # "<\/" keeps crawled text such as "</script>" from closing the tag early.
    body = json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>\n'


def _site_name(crawl: CrawlResult, entity: EntityConfig) -> str | None:
    if entity.name:
        return entity.name
    home = crawl.pages.get(crawl.start_url)
    if home is None:
        return None
    if home.open_graph.get("og:site_name"):
        return home.open_graph["og:site_name"]
    existing = _existing_org(crawl) or _existing(crawl, ("WebSite",))
    if existing.get("name"):
        return str(existing["name"])
    return None


ORG_TYPES = ("Organization", "LocalBusiness", "Corporation", "ProfessionalService", "Person")
WEBPAGE_TYPES = pt.WEBPAGE_TYPES


def _existing(crawl: CrawlResult, types: tuple[str, ...]) -> dict[str, Any]:
    home = crawl.pages.get(crawl.start_url)
    if home is None:
        return {}
    nodes = pt.top_nodes(home)
    for wanted in types:  # in preference order: an Organization beats an author Person
        for node in nodes:
            if wanted in pt.node_types(node):
                return {k: v for k, v in node.items() if k != "@context"}
    return {}


def _existing_org(crawl: CrawlResult) -> dict[str, Any]:
    return _existing(crawl, ORG_TYPES)


def org_id(crawl: CrawlResult) -> str:
    return str(_existing_org(crawl).get("@id") or f"{crawl.site}/#organization")


def website_id(crawl: CrawlResult) -> str:
    return str(_existing(crawl, ("WebSite",)).get("@id") or f"{crawl.site}/#website")


def _same_page(a: Any, b: str) -> bool:
    return isinstance(a, str) and a.rstrip("/") == b.rstrip("/")


def _existing_logo(crawl: CrawlResult) -> str | None:
    home = crawl.pages.get(crawl.start_url)
    if home is None:
        return None
    for node in pt.json_ld_nodes(home):
        logo = node.get("logo")
        if isinstance(logo, str):
            return logo
        if isinstance(logo, dict) and logo.get("url"):
            return str(logo["url"])
    return None


def organization(crawl: CrawlResult, entity: EntityConfig) -> SchemaDoc:
    existing = _existing_org(crawl)
    org_type = entity.type or "Organization"
    if entity.type == "Organization" and pt.node_types(existing) & set(ORG_TYPES[:-1]):
        org_type = next(t for t in ORG_TYPES if t in pt.node_types(existing))
    # Start from what the site already publishes (employee, address, contactPoint...) so the
    # generated node replaces it without losing anything; configured values win.
    data: dict[str, Any] = {"@context": CONTEXT, **existing}
    data.update({"@type": org_type, "@id": org_id(crawl)})
    if entity.type == "Organization" and pt.node_types(existing) & set(ORG_TYPES[:-1]):
        data["@type"] = existing["@type"]  # preserve scalar and multi-type business markup
    todo: list[str] = []
    fields = {
        "name": _site_name(crawl, entity),
        "legalName": entity.legal_name,
        "url": entity.url or crawl.start_url,
        "logo": entity.logo or _existing_logo(crawl),
        "description": entity.description or existing.get("description"),
        "foundingDate": entity.founded or existing.get("foundingDate"),
        "email": entity.email,
        "telephone": entity.telephone,
    }
    for key, value in fields.items():
        if value:
            data[key] = value
        elif key in ("name", "logo", "description"):
            todo.append(f"{key}: set entity.{key} in ranq.yaml")
    if entity.founders and org_type != "Person":
        data["founder"] = [{"@type": "Person", "name": n} for n in entity.founders]
    if entity.address:
        data["address"] = {"@type": "PostalAddress", **entity.address}
    elif "address" in data:
        pass  # kept from the site's existing markup
    elif org_type == "LocalBusiness" or org_type.endswith("Business"):
        todo.append(
            "address: required for LocalBusiness - set entity.address (streetAddress, addressLocality, postalCode, addressCountry)"
        )
    existing_same_as = existing.get("sameAs") or []
    if isinstance(existing_same_as, str):
        existing_same_as = [existing_same_as]
    same_as = list(dict.fromkeys(entity.same_as + list(existing_same_as)))
    if same_as:
        data["sameAs"] = same_as
    else:
        todo.append("sameAs: list your official profiles (entity.same_as)")
    return SchemaDoc(crawl.start_url, org_type, data, todo)


def website(crawl: CrawlResult, entity: EntityConfig) -> SchemaDoc:
    data: dict[str, Any] = {"@context": CONTEXT, **_existing(crawl, ("WebSite",))}
    data.update(
        {
            "@type": "WebSite",
            "@id": website_id(crawl),
            "url": data.get("url") or crawl.start_url,
            "publisher": {"@id": org_id(crawl)},
        }
    )
    todo = []
    name = _site_name(crawl, entity)
    if name:
        data["name"] = name
    else:
        todo.append("name: set entity.name")
    if entity.site_search_url and "{search_term_string}" in entity.site_search_url:
        data["potentialAction"] = {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": entity.site_search_url},
            "query-input": "required name=search_term_string",
        }
        todo.append(
            "note: Google retired the sitelinks search box (Nov 2024); SearchAction "
            "remains valid schema.org for other consumers."
        )
    return SchemaDoc(crawl.start_url, "WebSite", data, todo)


def _title_for(crawl: CrawlResult, url: str) -> str | None:
    page = crawl.pages.get(url) or crawl.pages.get(url.rstrip("/")) or crawl.pages.get(url + "/")
    if page is None or page.status != 200:
        return None
    return (page.h1s[0] if page.h1s else None) or page.title


def breadcrumbs(crawl: CrawlResult, page: PageData) -> SchemaDoc | None:
    parts = [p for p in urlsplit(page.url).path.split("/") if p]
    if len(parts) < 2:
        return None
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": crawl.start_url}]
    todo = []
    for i in range(1, len(parts) + 1):
        url = f"{crawl.site}/{'/'.join(parts[:i])}"
        if i < len(parts):
            # Intermediate levels: prefer the crawled page title for '/a/' or '/a'.
            name = _title_for(crawl, url + "/") or _title_for(crawl, url)
            if name is None:
                continue  # no real page at this level: skip rather than invent one
            item_url = url + "/" if (url + "/") in crawl.pages else url
        else:
            name = _title_for(crawl, page.url) or parts[-1]
            item_url = page.url
        items.append(
            {"@type": "ListItem", "position": len(items) + 1, "name": name, "item": item_url}
        )
    if len(items) < 2:
        return None
    todo.append("Only use this if the page shows matching visible breadcrumbs.")
    return SchemaDoc(
        page.url,
        "BreadcrumbList",
        {"@context": CONTEXT, "@type": "BreadcrumbList", "itemListElement": items},
        todo,
    )


def webpage(crawl: CrawlResult, page: PageData) -> SchemaDoc:
    own = next(
        (
            {k: v for k, v in n.items() if k != "@context"}
            for n in pt.top_nodes(page)
            if pt.node_types(n) & set(WEBPAGE_TYPES) and _same_page(n.get("url"), page.url)
        ),
        {},
    )
    page_type = next((t for t in WEBPAGE_TYPES if t in pt.node_types(own)), "WebPage")
    data: dict[str, Any] = {"@context": CONTEXT, **own}
    data.update(
        {
            "@type": page_type,
            "@id": own.get("@id") or f"{page.url}#webpage",
            "url": page.url,
            "isPartOf": {"@id": website_id(crawl)},
        }
    )
    if page.title:
        data["name"] = page.title
    if page.meta_description:
        data["description"] = page.meta_description
    if page.url.rstrip("/") == crawl.start_url.rstrip("/"):
        data.setdefault("about", {"@id": org_id(crawl)})
    if page.lang:
        data["inLanguage"] = page.lang
    modified = pt.modified_date(page)
    if modified:
        data["dateModified"] = modified
    return SchemaDoc(page.url, "WebPage", data)


def article(crawl: CrawlResult, page: PageData, entity: EntityConfig) -> SchemaDoc:
    data: dict[str, Any] = {"@context": CONTEXT, "@type": "Article", "mainEntityOfPage": page.url}
    todo: list[str] = []
    headline = page.h1s[0] if page.h1s else page.title
    if headline:
        data["headline"] = headline[:110]
    author = pt.author_name(page)
    if author:
        data["author"] = {"@type": "Person", "name": author}
        if pt.author_url(page):
            data["author"]["url"] = pt.author_url(page)
    else:
        todo.append("author: add a visible byline, then author {name, url}")
    published, modified = pt.published_date(page), pt.modified_date(page)
    if published:
        data["datePublished"] = published
    else:
        todo.append("datePublished: show a publish date on the page and add it here (ISO 8601)")
    if modified:
        data["dateModified"] = modified
    image = page.open_graph.get("og:image") or next(
        (i.src for i in page.images if i.src.startswith("http")), None
    )
    if image:
        data["image"] = [image]
    else:
        todo.append("image: add a representative image (min 50K pixels)")
    name = _site_name(crawl, entity)
    if name:
        data["publisher"] = {
            "@type": "Organization",
            "name": name,
            "@id": org_id(crawl),
        }
    return SchemaDoc(page.url, "Article", data, todo)


def faq(page: PageData) -> SchemaDoc | None:
    """FAQPage from visible question headings and the text that follows them."""
    result = aeo.analyze_page(page, None, "unknown")
    pairs = [(q.question, q.answer) for q in result.qa if q.answer and q.words >= 5]
    if len(pairs) < 2:
        return None
    entities = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in pairs
    ]
    return SchemaDoc(
        page.url,
        "FAQPage",
        {"@context": CONTEXT, "@type": "FAQPage", "mainEntity": entities},
        [
            "Google shows FAQ rich results only for well-known government/health sites; "
            "the markup still helps other engines. Keep questions visible on the page."
        ],
    )


HOWTO_HEADING = re.compile(r"^how (to|do you|do i|can i)\b", re.I)


def howto(page: PageData) -> SchemaDoc | None:
    steps: list[str] = []
    name = None
    capture = False
    for tag, text in page.outline:
        if tag.startswith("h"):
            if capture and steps:
                break
            capture = bool(HOWTO_HEADING.match(text))
            name = text if capture else name
        elif capture and tag == "li":
            steps.append(text)
    if len(steps) < 2 or not name:
        return None
    data = {
        "@context": CONTEXT,
        "@type": "HowTo",
        "name": name.rstrip("?"),
        "step": [{"@type": "HowToStep", "position": i + 1, "text": s} for i, s in enumerate(steps)],
    }
    return SchemaDoc(
        page.url,
        "HowTo",
        data,
        ["Google no longer shows HowTo rich results (2023); kept for other consumers."],
    )


def product(page: PageData) -> SchemaDoc:
    data: dict[str, Any] = {"@context": CONTEXT, "@type": "Product"}
    name = page.h1s[0] if page.h1s else page.title
    if name:
        data["name"] = name
    if page.meta_description:
        data["description"] = page.meta_description
    image = page.open_graph.get("og:image") or next(
        (i.src for i in page.images if i.src.startswith("http")), None
    )
    if image:
        data["image"] = [image]
    todo = [
        'offers: add {"@type": "Offer", "price": ..., "priceCurrency": ..., '
        '"availability": "https://schema.org/InStock", "url": ...} with your real price',
        "brand, sku/gtin: add if you have them",
        "aggregateRating/review: only with genuine reviews shown on the page (never fabricate)",
    ]
    return SchemaDoc(page.url, "Product", data, todo)


def person(name: str, url: str | None, same_as: list[str] | None = None) -> SchemaDoc:
    data: dict[str, Any] = {"@context": CONTEXT, "@type": "Person", "name": name}
    if url:
        data["url"] = url
    if same_as:
        data["sameAs"] = same_as
    return SchemaDoc(
        url or "",
        "Person",
        data,
        ["jobTitle, image, sameAs (LinkedIn, GitHub, etc.): add for author pages"],
    )


def _complete_product(page: PageData) -> bool:
    return any(
        n.get("@type") == "Product"
        and n.get("name")
        and (n.get("offers") or n.get("aggregateRating"))
        for n in pt.json_ld_nodes(page)
    )


def generate_all(crawl: CrawlResult, entity: EntityConfig) -> list[SchemaDoc]:
    docs: list[SchemaDoc] = [organization(crawl, entity), website(crawl, entity)]
    authors: dict[str, str | None] = {}
    for page in crawl.html_pages:
        if not page.is_indexable:
            continue
        existing = pt.schema_types(page)
        docs.append(webpage(crawl, page))
        crumb = breadcrumbs(crawl, page)
        if crumb and "BreadcrumbList" not in existing:
            docs.append(crumb)
        if pt.is_article(page) and not existing & {
            "Article",
            "BlogPosting",
            "NewsArticle",
            "TechArticle",
        }:
            docs.append(article(crawl, page, entity))
        if pt.is_product(page) and not _complete_product(page):
            docs.append(product(page))
        if "FAQPage" not in existing and (f := faq(page)):
            docs.append(f)
        if "HowTo" not in existing and (h := howto(page)):
            docs.append(h)
        if pt.is_article(page) and (name := pt.author_name(page)):
            authors.setdefault(name, pt.author_url(page))
    docs.extend(person(n, u) for n, u in authors.items())
    return docs


@dataclass(slots=True)
class Graph:
    """One ready-to-paste <script> holding an @graph."""

    url: str | None  # None = site-wide graph for the shared layout
    nodes: list[dict[str, Any]]
    replaces_existing: bool

    def script_tag(self) -> str:
        graph = [{k: v for k, v in n.items() if k != "@context"} for n in self.nodes]
        return script_tag({"@context": CONTEXT, "@graph": graph})

    @property
    def kinds(self) -> list[str]:
        return list(dict.fromkeys(t for n in self.nodes for t in sorted(pt.node_types(n))))


def _key(node: dict[str, Any]) -> str:
    return json.dumps(node, sort_keys=True)


def build_graphs(crawl: CrawlResult, docs: list[SchemaDoc]) -> list[Graph]:
    """Group generated docs into one site-wide @graph (Organization, WebSite, authors, plus
    existing nodes repeated on several pages, i.e. layout markup) and one @graph per page.
    Existing nodes that were not regenerated are carried over, so each graph can replace the
    JSON-LD already on the page without losing anything. Another page's WebPage node (a
    layout bug) is dropped."""
    site_ids = {org_id(crawl), website_id(crawl)}
    site_types = set(ORG_TYPES[:-1]) | {"WebSite"}
    site_docs = [d for d in docs[:2]] + [d for d in docs[2:] if d.kind == "Person"]
    page_docs: dict[str, list[SchemaDoc]] = {}
    for d in docs[2:]:
        if d.kind != "Person":
            page_docs.setdefault(d.url, []).append(d)

    pages = [p for p in crawl.html_pages if p.is_indexable]
    seen: dict[str, int] = {}
    for page in pages:
        for key in {_key(n) for n in pt.top_nodes(page)}:
            seen[key] = seen.get(key, 0) + 1

    site_nodes = [d.data for d in site_docs]
    layout_keys: set[str] = set()
    graphs: list[Graph] = []
    for page in pages:
        generated = page_docs.get(page.url, [])
        regenerated = {d.kind for d in generated} | set(WEBPAGE_TYPES) | site_types
        carried = []
        for node in pt.top_nodes(page):
            if node.get("@id") in site_ids or pt.node_types(node) & regenerated:
                continue
            key = _key(node)
            if seen.get(key, 0) > 1:
                if key not in layout_keys:
                    layout_keys.add(key)
                    site_nodes.append(node)
            else:
                carried.append(node)
        nodes = [d.data for d in generated] + carried
        if nodes:
            graphs.append(Graph(page.url, nodes, bool(page.json_ld)))
    home = crawl.pages.get(crawl.start_url)
    graphs.insert(0, Graph(None, site_nodes, bool(home and home.json_ld)))
    return graphs
