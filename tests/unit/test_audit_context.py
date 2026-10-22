"""Regressions for service-business audits; fixtures are synthetic, not live sites."""

import json

import pytest

from ranq.analysis import pagetype as pt
from ranq.analysis.aeo import analyze as analyze_aeo
from ranq.analysis.aeo import site_eeat
from ranq.analysis.performance import PerfResult
from ranq.analysis.structured_data import analyze_page
from ranq.checks.aeo import answers, eeat_site
from ranq.checks.base import AuditContext
from ranq.checks.geo import (
    ai_crawler_access,
    brand_consistency,
    contact_visibility,
    entity_signals,
    llms_txt,
)
from ranq.checks.onpage import content_depth, headings, internal_linking
from ranq.checks.performance import core_web_vitals
from ranq.config import Config, EntityConfig
from ranq.crawler.crawler import CrawlResult
from ranq.crawler.parser import parse_html
from ranq.generators.schema import organization
from ranq.geo.ai_bots import current_access
from ranq.geo.analysis import GeoReport
from ranq.geo.citation import score_pages
from ranq.geo.entity import analyze, fact_sheet
from ranq.models import PageData, Severity
from ranq.robots import RobotsTxt

URL = "https://studio.test/"


def context(html: str = "", schema: dict | None = None) -> AuditContext:
    if schema:
        html += '<script type="application/ld+json">' + json.dumps(schema) + "</script>"
    page = parse_html(PageData(URL, URL, 200, content_type="text/html"), html, URL)
    return AuditContext(
        Config(), CrawlResult(site=URL.rstrip("/"), start_url=URL, pages={URL: page})
    )


def business() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": ["LocalBusiness", "ExerciseGym"],
        "name": "Example Studio",
        "description": "Yoga classes in Chennai.",
        "foundingDate": "2020",
        "logo": {"@type": "ImageObject", "url": URL + "logo.png"},
        "sameAs": ["https://instagram.com/example-studio"],
        "address": {"@type": "PostalAddress", "addressLocality": "Chennai"},
        "founder": {"@type": "Person", "name": "Instructor", "description": "Founder bio"},
    }


@pytest.mark.parametrize(
    "types",
    [
        ["LocalBusiness", "ExerciseGym"],
        "LocalBusiness",
        "ExerciseGym",
        ["https://schema.org/LocalBusiness", "https://schema.org/ExerciseGym"],
    ],
)
def test_entity_recognizes_business_types_and_existing_facts(types: str | list[str]) -> None:
    doc = business()
    doc["@type"] = types
    ctx = context(schema=doc)
    ent = analyze(ctx.crawl, EntityConfig())
    assert ent.name == "Example Studio"
    assert ent.same_as == ["https://instagram.com/example-studio"]
    assert ent.missing_facts == ["category"]
    _, facts = fact_sheet(ctx.crawl, EntityConfig(), ent)
    assert facts["description"] == "Yoga classes in Chennai."
    assert facts["founded"] == "2020"
    ctx.extras["geo"] = GeoReport(entity=ent)
    assert "entity-no-sameas" not in {i.check_id for i in entity_signals(ctx)}


def test_fact_sheet_config_wins_and_missing_facts_remain_missing() -> None:
    ctx = context(schema=business())
    cfg = EntityConfig(description="Updated description", founded="2021", category="Yoga studio")
    ent = analyze(ctx.crawl, cfg)
    _, facts = fact_sheet(ctx.crawl, cfg, ent)
    assert facts["description"] == "Updated description"
    assert facts["founded"] == "2021"
    assert ent.missing_facts == []
    doc = business()
    del doc["description"]
    del doc["foundingDate"]
    ent = analyze(context(schema=doc).crawl, EntityConfig())
    assert {"description", "founded"} <= set(ent.missing_facts)


def test_generator_preserves_multi_type_business() -> None:
    ctx = context(schema=business())
    generated = organization(ctx.crawl, EntityConfig())
    assert generated.data["@type"] == ["LocalBusiness", "ExerciseGym"]
    assert generated.data["name"] == "Example Studio"
    assert generated.data["sameAs"] == ["https://instagram.com/example-studio"]
    assert not any(t.startswith("name:") for t in generated.todo)


@pytest.mark.parametrize("alternate", ["Example Studio", ["Example Studio", "Example Yoga"]])
def test_declared_alias_is_not_a_brand_conflict(alternate: str | list[str]) -> None:
    doc = business()
    doc.update(name="Example Wellness Studio", alternateName=alternate)
    ctx = context('<meta property="og:site_name" content="Example Studio">', doc)
    ent = analyze(ctx.crawl, EntityConfig())
    assert ent.name_variants == {"Example Studio": 1}
    ctx.extras["geo"] = GeoReport(entity=ent)
    assert "brand-name-inconsistent" not in {i.check_id for i in entity_signals(ctx)}
    del doc["alternateName"]
    ent = analyze(
        context('<meta property="og:site_name" content="Example Studio">', doc).crawl,
        EntityConfig(),
    )
    assert len(ent.name_variants) == 2


def test_section_navigation_with_real_targets() -> None:
    ctx = context("""
        <a href="#about">About</a><a href="/#contact">Contact</a>
        <a href="#privacy">Privacy</a><a href="#terms">Terms</a>
        <section id="about"><h2>About</h2><p>Our studio and instructors.</p></section>
        <section id="contact"><h2>Contact</h2><p>Contact our team.</p></section>
        <div id="terms"></div>
    """)
    page = ctx.pages[0]
    assert page.section_links == [URL + "#about", URL + "#contact"]
    assert page.internal_links == []  # fragments must not inflate the page graph
    site = site_eeat(ctx.pages)
    assert site.about == URL + "#about" and site.contact == URL + "#contact"
    assert site.privacy is None and site.terms is None
    ctx.extras["aeo"] = analyze_aeo(ctx.pages, None)
    assert {i.check_id for i in eeat_site(ctx)} == {"eeat-no-privacy"}
    assert "no-outlinks" not in {i.check_id for i in internal_linking(ctx)}


def test_sections_respect_base_url_and_percent_encoding() -> None:
    ctx = context('<a href="#%61bout">About</a><section id="about">About the studio</section>')
    assert site_eeat(ctx.pages).about == URL + "#%61bout"
    ctx = context(
        '<base href="/other/"><a href="#about">About</a><section id="about">About us</section>'
    )
    assert ctx.pages[0].section_links == []
    assert site_eeat(ctx.pages).about is None


def test_separate_pages_and_broken_fragment_still_reported() -> None:
    ctx = context('<a href="/about">About</a><a href="/contact.html">Contact</a>')
    assert site_eeat(ctx.pages).about == URL + "about"
    assert site_eeat(ctx.pages).contact == URL + "contact.html"
    ctx = context('<a href="#about">About</a>')
    assert site_eeat(ctx.pages).about is None
    assert "no-outlinks" in {i.check_id for i in internal_linking(ctx)}


def test_service_offer_catalog_has_no_product_price_errors() -> None:
    doc = business()
    doc["hasOfferCatalog"] = {
        "@type": "OfferCatalog",
        "name": "Classes",
        "itemListElement": [
            {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Yoga"}}
        ],
    }
    problems = [p for i in analyze_page(context(schema=doc).pages[0]).items for p in i.problems]
    assert not [p for p in problems if p.type == "Offer" and p.level == "error"]


def test_graph_product_offer_reference_still_requires_price() -> None:
    doc = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Product", "name": "Mat", "offers": {"@id": "#offer"}},
            {"@type": "Offer", "@id": "#offer", "priceCurrency": "INR"},
        ],
    }
    problems = [p for i in analyze_page(context(schema=doc).pages[0]).items for p in i.problems]
    assert any(p.type == "Offer" and p.level == "error" and "price" in p.message for p in problems)


def test_equivalent_business_types_do_not_duplicate_problems() -> None:
    doc = business()
    del doc["address"]
    problems = [p for i in analyze_page(context(schema=doc).pages[0]).items for p in i.problems]
    assert len([p for p in problems if p.message == "missing required 'address'"]) == 1


@pytest.mark.parametrize(
    "offer,missing",
    [
        ({"@type": "Offer"}, True),
        ({"@type": "Offer", "priceSpecification": {"x": 1}}, True),
        ({"@type": "Offer", "price": 0}, False),
        ({"@type": "Offer", "priceSpecification": {"price": 20, "priceCurrency": "INR"}}, False),
    ],
)
def test_product_offers_still_require_real_price(offer: dict, missing: bool) -> None:
    doc = {"@context": "https://schema.org", "@type": "Product", "name": "Mat", "offers": offer}
    problems = [p for i in analyze_page(context(schema=doc).pages[0]).items for p in i.problems]
    errors = [p for p in problems if p.type == "Offer" and p.level == "error"]
    assert bool(errors) is missing
    assert all("priceSpecification.price" in p.message for p in errors)
    assert not any("priceCurrency" in p.message for p in errors)


@pytest.mark.parametrize(
    "lab,label,fix",
    [
        ({"LCP": 13026, "CLS": 0.0002}, "Lab LCP is poor", "Optimize the largest element"),
        ({"LCP": 2000, "CLS": 0.4}, "Lab CLS is poor", "Reserve space"),
        ({"LCP": 5000, "CLS": 0.4}, "Lab LCP/CLS are poor", "Reserve space"),
    ],
)
def test_lab_warning_names_only_failed_metrics(lab: dict, label: str, fix: str) -> None:
    ctx = context()
    ctx.extras["performance"] = [PerfResult(URL, "pagespeed", lab=lab)]
    issue = next(i for i in core_web_vitals(ctx) if i.check_id == "lab-cwv-poor")
    assert issue.title.startswith(label)
    assert fix in issue.fix
    assert "too little traffic" not in issue.description
    assert issue.estimate


def test_implicit_policy_is_information_but_blocked_search_is_flagged() -> None:
    ctx = context()
    for rules, blocked in [
        ("User-agent: *\nAllow: /", False),
        ("User-agent: *\nDisallow: /", True),
    ]:
        ctx.crawl.robots = RobotsTxt(rules)
        ctx.extras["geo"] = GeoReport(bots=current_access(ctx.crawl.robots, URL))
        issues = {i.check_id: i for i in ai_crawler_access(ctx)}
        assert issues["ai-policy-implicit"].severity == Severity.INFO
        assert ("ai-search-bots-blocked" in issues) is blocked


def test_description_word_overlap_is_unscored_review_advice() -> None:
    ctx = context(schema=business())
    ctx.extras["geo"] = GeoReport(
        llms_txt_live="> Personal wellness coaching and mindful movement."
    )
    issue = next(brand_consistency(ctx))
    assert issue.severity == Severity.INFO
    assert issue.estimate
    assert "verbatim" not in issue.fix


@pytest.mark.parametrize("org_type", ["Organization", "LocalBusiness"])
def test_graph_entity_facts_and_fact_sheet(org_type: str) -> None:
    ctx = context(
        schema={
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "name": "Example"},
                {
                    "@type": org_type,
                    "name": "Example",
                    "description": "Full company description.",
                    "foundingDate": "2026",
                },
            ],
        }
    )
    # The supplied graph has no logo; preserve that independent finding.
    assert analyze(ctx.crawl, EntityConfig()).missing_facts == ["logo", "category"]
    cfg = EntityConfig(logo=URL + "logo.png")
    ent = analyze(ctx.crawl, cfg)
    assert ent.missing_facts == ["category"]
    md, facts = fact_sheet(ctx.crawl, cfg, ent)
    assert facts["description"] == "Full company description."
    assert facts["founded"] == "2026"
    assert "**Description:** Full company description." in md
    assert "**Founded:** 2026" in md


def page_context(path: str, html: str = "") -> AuditContext:
    ctx = context()
    url = URL.rstrip("/") + path
    page = parse_html(PageData(url, url, 200, content_type="text/html"), html, URL)
    ctx.crawl.pages = {url: page}
    return ctx


@pytest.mark.parametrize(
    "path",
    [
        "/work",
        "/events",
        "/event/",
        "/portfolio",
        "/projects",
        "/project",
        "/gallery",
        "/case-studies",
        "/WORK/?page=2",
    ],
)
def test_collection_exempts_only_content_heuristics(path: str) -> None:
    ctx = page_context(
        path,
        '<h1 style="opacity:0">Our work</h1><h3>Projects</h3><p>'
        + "Example project description. " * 20
        + "</p>"
        '<a href="/cdn-cgi/l/email-protection">Email</a>',
    )
    assert 30 <= ctx.pages[0].word_count <= 100
    assert "thin-content" not in {i.check_id for i in content_depth(ctx)}
    assert score_pages(ctx.pages, {}) == []
    assert {"h1-hidden-in-html", "heading-skip"} <= {i.check_id for i in headings(ctx)}
    assert "email-obfuscated" in {i.check_id for i in contact_visibility(ctx)}
    ctx.extras["performance"] = [PerfResult(ctx.pages[0].url, "pagespeed", lab={"LCP": 9000})]
    assert "lab-cwv-poor" in {i.check_id for i in core_web_vitals(ctx)}


@pytest.mark.parametrize(
    "path",
    [
        "/services/foo",
        "/events/some-event",
        "/projects/example",
        "/work/example",
        "/blog/example",
        "/guides/example",
        "/products/example",
        "/information",
    ],
)
def test_ordinary_pages_still_checked(path: str) -> None:
    ctx = page_context(path, "<p>" + "Useful information. " * 30 + "</p>")
    assert "thin-content" in {i.check_id for i in content_depth(ctx)}
    assert [s.url for s in score_pages(ctx.pages, {})] == [ctx.pages[0].url]


def test_collection_schema_is_page_level_and_article_takes_precedence() -> None:
    ctx = context(schema={"@graph": [{"@type": "CollectionPage"}]})
    assert pt.is_collection(ctx.pages[0])
    ctx = context(schema={"@type": "WebPage", "isPartOf": {"@type": "CollectionPage"}})
    assert not pt.is_collection(ctx.pages[0])
    ctx = page_context("/work")
    ctx.pages[0].json_ld = ['{"@type": "Article"}']
    assert not pt.is_collection(ctx.pages[0])


@pytest.mark.parametrize(
    "path,legal",
    [
        ("/privacy", True),
        ("/privacy-policy/", True),
        ("/privacy.html", True),
        ("/terms-of-service", True),
        ("/terms-of-use.htm", True),
        ("/tos", True),
        ("/legal", True),
        ("/imprint", True),
        ("/impressum", True),
        ("/cookie-policy", True),
        ("/faq", False),
        ("/privacy/tools", False),
    ],
)
def test_legal_answer_length_and_citation_scope(path: str, legal: bool) -> None:
    ctx = page_context(
        path,
        "<h2>How do we use data?</h2><p>"
        + "We process information to provide services. " * 20
        + "</p>",
    )
    ctx.extras["aeo"] = analyze_aeo(ctx.pages, None)
    assert ctx.extras["aeo"].pages[0].qa
    assert ("aeo-answer-length" in {i.check_id for i in answers(ctx)}) is not legal
    assert bool(score_pages(ctx.pages, {})) is not legal
    assert "h1-missing" in {i.check_id for i in headings(ctx)}


def test_optional_geo_guidance_is_info() -> None:
    ctx = context()
    ctx.crawl.robots = RobotsTxt("User-agent: *\nAllow: /\n")
    ctx.extras["geo"] = GeoReport(
        bots=current_access(ctx.crawl.robots, URL),
        llms_txt_status=404,
        entity=analyze(ctx.crawl, EntityConfig()),
    )
    issues = {
        i.check_id: i for check in (ai_crawler_access, llms_txt, entity_signals) for i in check(ctx)
    }
    for name in (
        "ai-policy-implicit",
        "llms-txt-missing",
        "entity-no-sameas",
        "entity-facts-missing",
    ):
        assert issues[name].severity == Severity.INFO
    assert "ai-search-bots-blocked" not in issues


def test_substantive_sections_without_fragment_navigation() -> None:
    ctx = context("""
        <a href="/">About</a><button>Contact</button>
        <section id="about"><h2>Our studio</h2>
          <p>We are an independent studio building secure products for local businesses.</p>
        </section>
        <section id="contact"><h2>Contact us</h2>
          <p>Discuss your project with our team by emailing hello@example.test today.</p>
        </section>
    """)
    assert ctx.pages[0].section_links == []
    assert site_eeat(ctx.pages).about == URL + "#about"
    assert site_eeat(ctx.pages).contact == URL + "#contact"
    ctx.extras["aeo"] = analyze_aeo(ctx.pages, None)
    assert {i.check_id for i in eeat_site(ctx)} == {"eeat-no-privacy"}


@pytest.mark.parametrize(
    "html",
    [
        '<section id="about"></section>',
        '<section id="about"><h2>About our talented and experienced local team today</h2></section>',
        '<nav id="about">About our talented and experienced local team today</nav>',
        '<section id="about"><script>About our talented and experienced local team today</script></section>',
        '<section id="about" hidden><p>We build secure products for local businesses around the world.</p></section>',
        '<div aria-hidden="true"><section id="about"><p>We build secure products for local businesses around the world.</p></section></div>',
        '<section id="about-more"><p>We build secure products for local businesses around the world.</p></section>',
    ],
)
def test_section_labels_and_hidden_content_are_not_trust_evidence(html: str) -> None:
    assert site_eeat(context(html).pages).about is None
