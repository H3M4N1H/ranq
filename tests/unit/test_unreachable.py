from ranq.checks.base import AuditContext
from ranq.checks.crawl import site_unreachable
from ranq.config import Config
from ranq.crawler.crawler import CrawlResult
from ranq.models import Issue, PageData, Severity
from ranq.report.builder import health_score


def _ctx(home: PageData | None) -> AuditContext:
    pages = {home.url: home} if home else {}
    crawl = CrawlResult(site="https://s.test", start_url="https://s.test/", pages=pages)
    return AuditContext(config=Config(), crawl=crawl)


def test_dead_deployment_is_critical() -> None:
    home = PageData(url="https://s.test/", final_url="https://s.test/", status=404)
    home.headers = {"x-vercel-error": "DEPLOYMENT_NOT_FOUND", "server": "Vercel"}
    (issue,) = site_unreachable(_ctx(home))
    assert issue.severity == Severity.CRITICAL
    assert "HTTP 404" in issue.title
    assert issue.evidence["https://s.test/"]["x-vercel-error"] == "DEPLOYMENT_NOT_FOUND"


def test_robots_blocked_and_live_site() -> None:
    ctx = _ctx(None)
    ctx.crawl.blocked.append("https://s.test/")
    assert "robots.txt" in next(iter(site_unreachable(ctx))).title
    live = PageData(
        url="https://s.test/", final_url="https://s.test/", status=200, content_type="text/html"
    )
    assert list(site_unreachable(_ctx(live))) == []


def test_empty_crawl_scores_zero() -> None:
    low = Issue("x", "x", Severity.LOW, "crawl", "", "", urls=["https://s.test/"])
    assert health_score([low], 0) == 0
    assert health_score([low], 1) > 90
    many = [
        Issue(f"x{i}", "x", Severity.HIGH, "crawl", "", "", urls=["https://s.test/"])
        for i in range(40)
    ]
    assert (
        0 < health_score(many[:6], 1) < health_score(many[:3], 1) < 100
    )  # retains resolution for several severe findings


def test_site_wide_issues_are_not_diluted_by_page_count() -> None:
    about = Issue(
        "eeat-no-about", "x", Severity.MEDIUM, "e-e-a-t", "", "", urls=["https://s.test/"]
    )
    assert about.site_wide
    assert health_score([about], 2) == health_score([about], 200)
    h1 = Issue("h1-missing", "x", Severity.MEDIUM, "on-page", "", "", urls=["https://s.test/a"])
    assert not h1.site_wide
    assert health_score([h1], 2) < health_score([h1], 200)  # one bad page in 200 matters less
    assert Issue("robots-blocks-googlebot", "x", Severity.CRITICAL, "technical", "", "").site_wide


def test_page_scores() -> None:
    from ranq.report.builder import page_scores

    pages = ["https://s.test/", "https://s.test/a"]
    issues = [
        Issue("eeat-no-about", "about", Severity.MEDIUM, "e-e-a-t", "", "", urls=[pages[0]]),
        Issue("h1-missing", "h1", Severity.MEDIUM, "on-page", "", "", urls=[pages[1]]),
        Issue("thin-content", "thin", Severity.LOW, "on-page", "", "", urls=pages),
    ]
    worst, best = page_scores(issues, pages)
    assert worst["url"] == "https://s.test/a"
    assert [i["check_id"] for i in worst["issues"]] == ["h1-missing", "thin-content"]
    assert best["url"] == "https://s.test/" and [i["check_id"] for i in best["issues"]] == [
        "thin-content"
    ]  # the site-wide About issue is not charged to the home page
    assert worst["score"] < best["score"] < 100


def test_platform_subdomain_flagged() -> None:
    from ranq.checks.technical import custom_domain, platform_subdomain

    assert platform_subdomain("https://hi-res-lossless-website.vercel.app") == "vercel.app"
    assert platform_subdomain("https://me.github.io/blog/") == "github.io"
    assert platform_subdomain("https://brightworks.example") is None
    assert platform_subdomain("https://notvercel.app") is None  # a real domain, not a subdomain
    assert platform_subdomain("https://lightblue-x-123.hostingersite.com") == "hostingersite.com"
    assert platform_subdomain("https://shop.netlify.app") == "netlify.app"
    assert platform_subdomain("https://b.s3-website.eu-west-1.amazonaws.com") == "amazonaws.com"
    ctx = _ctx(None)
    ctx.crawl.site = "https://x.vercel.app"
    (issue,) = custom_domain(ctx)
    assert issue.severity == Severity.HIGH and issue.site_wide
    assert issue.title.startswith("Site runs on a Vercel subdomain (*.vercel.app)")
    ctx.crawl.site = "https://app.azurewebsites.net"
    assert next(iter(custom_domain(ctx))).title.startswith("Site runs on an Azure App Service")
    ctx.crawl.site = "https://brightworks.example"
    assert list(custom_domain(ctx)) == []


def test_og_url_mismatch() -> None:
    from ranq.checks.onpage import social_tags

    def page(path: str, og_url: str) -> PageData:
        p = PageData(
            url=f"https://s.test{path}",
            final_url=f"https://s.test{path}",
            status=200,
            content_type="text/html",
        )
        p.open_graph = {"og:url": og_url}
        return p

    home, work = page("/", "https://s.test"), page("/work", "https://s.test")
    rel = page("/about", "/about/")
    crawl = CrawlResult(
        site="https://s.test",
        start_url="https://s.test/",
        pages={p.url: p for p in (home, work, rel)},
    )
    issues = {i.check_id: i for i in social_tags(AuditContext(config=Config(), crawl=crawl))}
    assert issues["og-url-mismatch"].urls == ["https://s.test/work"]


def test_brand_description_and_email_obfuscation() -> None:
    import json

    from ranq.checks.geo import brand_consistency, contact_visibility
    from ranq.config import EntityConfig
    from ranq.geo.analysis import GeoReport

    home = PageData(url="https://s.test/", final_url="https://s.test/", status=200)
    home.content_type = "text/html"
    org = {
        "@type": "Organization",
        "name": "NK",
        "description": "Chennai-based digital services agency specializing in web development, "
        "AI integration, and software consulting.",
    }
    home.json_ld = [json.dumps({"@context": "https://schema.org", "@graph": [org]})]
    home.html = '<a href="/cdn-cgi/l/email-protection#abc">Email</a>'
    ctx = _ctx(home)
    ctx.config.entity = EntityConfig(name="NK")
    ctx.extras["geo"] = GeoReport(
        llms_txt_live="# NK\n\n> NK is a full-service digital agency based in Chennai, India. We "
        "build websites, digital products, and brands with a security-first mindset.\n"
    )
    (issue,) = brand_consistency(ctx)
    assert issue.site_wide and set(issue.evidence) == {
        "JSON-LD Organization.description",
        "llms.txt summary",
    }
    ctx.extras["geo"].llms_txt_live = f"# NK\n\n> {org['description']}\n"
    assert list(brand_consistency(ctx)) == []
    assert next(iter(contact_visibility(ctx))).check_id == "email-obfuscated"
