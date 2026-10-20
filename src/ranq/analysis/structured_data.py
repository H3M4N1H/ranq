"""JSON-LD extraction and validation against schema.org / Google rich result requirements.

Requirement tables summarize Google's structured data documentation
(https://developers.google.com/search/docs/appearance/structured-data/search-gallery).
"Required" means Google won't show the rich result without it; "recommended" improves
eligibility or completeness. Types Google does not use for rich results are still checked
for basic completeness because other engines and AI systems read them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ranq.analysis.pagetype import json_ld_nodes
from ranq.models import PageData

ARTICLE_TYPES = {"Article", "NewsArticle", "BlogPosting", "TechArticle", "Report"}
BUSINESS_SUFFIXES = ("Business", "Store", "Restaurant", "Dentist", "Physician", "Attorney")

# type -> (required, recommended)
RULES: dict[str, tuple[list[str], list[str]]] = {
    "Article": ([], ["headline", "image", "datePublished", "dateModified", "author"]),
    "Product": (
        ["name"],
        ["image", "description", "offers|review|aggregateRating", "brand", "sku"],
    ),
    "Offer": (
        [],  # Generic service offers do not inherit Product rich-result requirements.
        ["availability", "url"],
    ),
    "FAQPage": (["mainEntity"], []),
    "Question": (["name", "acceptedAnswer"], []),
    "Answer": (["text"], []),
    "HowTo": (["name", "step"], ["image", "totalTime", "supply", "tool"]),
    "Organization": ([], ["name", "url", "logo", "sameAs", "description"]),
    "LocalBusiness": (
        ["name", "address"],
        ["telephone", "url", "geo", "openingHoursSpecification", "image", "priceRange"],
    ),
    "WebSite": (["name", "url"], []),
    "WebPage": ([], ["name", "url"]),
    "BreadcrumbList": (["itemListElement"], []),
    "ListItem": (["position"], ["name", "item"]),
    "Person": (["name"], ["url", "sameAs", "jobTitle", "image"]),
    "Event": (
        ["name", "startDate", "location"],
        ["endDate", "eventStatus", "image", "description", "offers", "organizer"],
    ),
    "JobPosting": (
        [
            "title",
            "description",
            "datePosted",
            "hiringOrganization",
            "jobLocation|applicantLocationRequirements",
        ],
        ["validThrough", "employmentType", "baseSalary"],
    ),
    "Recipe": (
        ["name", "image"],
        ["author", "datePublished", "recipeIngredient", "recipeInstructions", "totalTime"],
    ),
    "VideoObject": (
        ["name", "thumbnailUrl", "uploadDate"],
        ["description", "duration", "contentUrl|embedUrl"],
    ),
    "Review": (["itemReviewed|@parent", "author", "reviewRating"], []),
    "AggregateRating": (["ratingValue", "ratingCount|reviewCount"], ["bestRating"]),
    "SoftwareApplication": (
        ["name", "offers|aggregateRating|review"],
        ["applicationCategory", "operatingSystem"],
    ),
    "Course": (["name", "description"], ["provider"]),
}


def canonical_type(t: str) -> str:
    t = t.split("/")[-1].split(":")[-1]
    if t in ARTICLE_TYPES:
        return "Article"
    if t in {"ExerciseGym", "HealthClub", "ProfessionalService"} or (
        t not in RULES and t.endswith(BUSINESS_SUFFIXES)
    ):
        return "LocalBusiness"
    return t


@dataclass(slots=True)
class SchemaProblem:
    type: str
    message: str
    level: str  # "error" | "warning"


@dataclass(slots=True)
class SchemaItem:
    types: list[str]
    data: dict[str, Any]
    problems: list[SchemaProblem] = field(default_factory=list)


@dataclass(slots=True)
class PageSchema:
    url: str
    items: list[SchemaItem] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    has_microdata: bool = False
    has_rdfa: bool = False

    @property
    def types(self) -> set[str]:
        return {canonical_type(t) for item in self.items for t in item.types}

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "types": sorted(self.types),
            "parse_errors": self.parse_errors,
            "problems": [
                {"type": p.type, "level": p.level, "message": p.message}
                for item in self.items
                for p in item.problems
            ],
            "microdata": self.has_microdata,
            "rdfa": self.has_rdfa,
        }


def _types_of(node: dict[str, Any]) -> list[str]:
    t = node.get("@type", [])
    return [str(x) for x in (t if isinstance(t, list) else [t])]


def _walk(node: Any, parent_has_type: bool = False) -> list[dict[str, Any]]:
    """Top-level typed entities (including @graph members). Nested ones are validated recursively."""
    out: list[dict[str, Any]] = []
    if isinstance(node, list):
        for n in node:
            out.extend(_walk(n))
    elif isinstance(node, dict):
        if "@graph" in node:
            out.extend(_walk(node["@graph"]))
        elif "@type" in node:
            out.append(node)
    return out


def _has(node: dict[str, Any], spec: str) -> bool:
    for key in spec.split("|"):
        if key == "@parent":
            continue
        value: Any = node
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, "", [], {}):
            return True
    return False


def validate_node(
    node: dict[str, Any],
    problems: list[SchemaProblem],
    nested: bool = False,
    offer_context: bool = False,
) -> None:
    for t in dict.fromkeys(canonical_type(t) for t in _types_of(node)):
        required, recommended = RULES.get(t, ([], []))
        if t == "Offer":
            offered = node.get("itemOffered")
            is_product = isinstance(offered, dict) and "Product" in {
                canonical_type(t) for t in _types_of(offered)
            }
            if offer_context or is_product:
                required = ["price|priceSpecification.price"]
                # Currency is recommended for Product snippets, required for merchant
                # listings. This validator does not infer merchant-listing intent.
                if not _has(node, "priceCurrency|priceSpecification.priceCurrency"):
                    problems.append(
                        SchemaProblem(
                            t,
                            "missing recommended 'priceCurrency or priceSpecification.priceCurrency'",
                            "warning",
                        )
                    )
        for spec in required:
            if "@parent" in spec and nested:
                continue
            if not _has(node, spec):
                problems.append(
                    SchemaProblem(t, f"missing required '{spec.replace('|', ' or ')}'", "error")
                )
        if not nested:
            for spec in recommended:
                if not _has(node, spec):
                    problems.append(
                        SchemaProblem(
                            t, f"missing recommended '{spec.replace('|', ' or ')}'", "warning"
                        )
                    )
        if t == "BreadcrumbList":
            items = node.get("itemListElement") or []
            for i, li in enumerate(items if isinstance(items, list) else []):
                if isinstance(li, dict) and li.get("position") != i + 1:
                    problems.append(
                        SchemaProblem(
                            t, f"itemListElement[{i}] position should be {i + 1}", "warning"
                        )
                    )
        for date_key in ("datePublished", "dateModified", "startDate", "uploadDate", "datePosted"):
            value = node.get(date_key)
            if isinstance(value, str) and not re.match(r"^\d{4}-\d{2}-\d{2}", value):
                problems.append(SchemaProblem(t, f"{date_key} '{value}' is not ISO 8601", "error"))
    for key, value in node.items():
        if key.startswith("@"):
            continue
        for child in value if isinstance(value, list) else [value]:
            if isinstance(child, dict) and "@type" in child:
                validate_node(
                    child,
                    problems,
                    nested=True,
                    offer_context=key == "offers"
                    and bool(
                        {canonical_type(t) for t in _types_of(node)}
                        & {"Product", "SoftwareApplication"}
                    ),
                )


def analyze_page(page: PageData) -> PageSchema:
    result = PageSchema(url=page.url, has_microdata=page.has_microdata, has_rdfa=page.has_rdfa)
    # Graph-based Product markup can reference an Offer in another graph node/script.
    product_offer_ids = set()
    for node in json_ld_nodes(page):
        if {canonical_type(t) for t in _types_of(node)} & {"Product", "SoftwareApplication"}:
            offers = node.get("offers") or []
            for offer in offers if isinstance(offers, list) else [offers]:
                if isinstance(offer, dict) and isinstance(offer.get("@id"), str):
                    product_offer_ids.add(offer["@id"])
    for raw in page.json_ld:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            result.parse_errors.append(
                f"Invalid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno})"
            )
            continue
        for node in _walk(data):
            item = SchemaItem(types=_types_of(node), data=node)
            context = node.get("@context") or (
                data.get("@context") if isinstance(data, dict) else None
            )
            if not context or "schema.org" not in json.dumps(context):
                item.problems.append(
                    SchemaProblem(
                        item.types[0] if item.types else "?",
                        "missing or non-schema.org @context",
                        "error",
                    )
                )
            validate_node(
                node,
                item.problems,
                offer_context=isinstance(node.get("@id"), str) and node["@id"] in product_offer_ids,
            )
            result.items.append(item)
    return result


def faq_questions(schema: PageSchema) -> list[str]:
    out = []
    for item in schema.items:
        if "FAQPage" in item.types:
            entities = item.data.get("mainEntity") or []
            for q in entities if isinstance(entities, list) else [entities]:
                if isinstance(q, dict) and q.get("name"):
                    out.append(str(q["name"]))
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def invisible_faq_questions(page: PageData, schema: PageSchema) -> list[str]:
    """FAQ questions marked up but absent from the visible text (violates Google's policy)."""
    visible = _norm(page.text + " " + " ".join(h.text for h in page.headings))
    return [q for q in faq_questions(schema) if _norm(q) not in visible]


@dataclass(slots=True)
class StructuredDataReport:
    pages: list[PageSchema] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"pages": [p.to_dict() for p in self.pages]}


def analyze(pages: list[PageData]) -> StructuredDataReport:
    return StructuredDataReport([analyze_page(p) for p in pages])
