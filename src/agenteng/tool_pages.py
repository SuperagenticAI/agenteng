"""Small crawlable directory pages, rendered from the same offline listings."""

from html import escape
import json
from urllib.parse import urlencode


def tool_page(service, result, request):
    data = result.data
    detail = data.get("tool")
    title = (
        (detail["name"] + " | AgentEng tools")
        if detail
        else "Agent-engineering tools | Agent Engineering HQ"
    )
    path = "/tools/" + detail["id"] if detail else "/tools"
    canonical = service.settings.public_url + path
    rows = [detail] if detail else data.get("items", [])
    articles = []
    for row in rows:
        links = []
        for label, key in [
            ("Website", "website_url"),
            ("Repository", "repository_url"),
            ("Documentation", "docs_url"),
        ]:
            if row.get(key):
                links.append(f'<a href="{escape(row[key], quote=True)}">{label}</a>')
        articles.append(
            f'<article><h2><a href="/tools/{escape(row["id"], quote=True)}">{escape(row["name"])}</a></h2>'
            f"<p>{escape(row['kind'])} · {escape(', '.join(row['disciplines']))} · {escape(row['status'])}</p>"
            f"<p>{' · '.join(links)}</p></article>"
        )
    navigation = '<a href="/tools">All tools</a>'
    if data.get("next_offset") is not None:
        filters = request.model_dump(
            exclude_none=True,
            include={"discipline", "kind", "category", "query", "limit", "tool_status"},
        )
        filters["offset"] = data["next_offset"]
        navigation += f' · <a href="/tools?{escape(urlencode(filters), quote=True)}">Next page</a>'
    from .tool_directory import DISCIPLINES

    navigation += (
        "<p>"
        + " · ".join(
            f'<a href="/tools?discipline={key}">{escape(name)}</a>'
            for key, name in DISCIPLINES.items()
        )
        + "</p>"
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage" if not detail else "WebPage",
        "name": title,
        "url": canonical,
        "publisher": {"@type": "Organization", "name": "Agent Engineering HQ"},
    }
    structured = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")
    source = data["directory"]["source"]
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title><link rel="canonical" href="{escape(canonical, quote=True)}">'
        '<meta name="description" content="Browse agent-engineering tools, models and infrastructure across twelve disciplines with public source links.">'
        f'<script type="application/ld+json">{structured}</script></head><body><main>'
        f"<h1>{escape(title)}</h1><p>{escape(result.answer)}</p>{navigation}"
        + "".join(articles)
        + f"<p>{escape(data['directory']['note'])}</p>"
        + f'<p>Source updated: {escape(source["updated_at"])}. <a href="{escape(source["url"], quote=True)}">SuperRadar source</a></p>'
        + '<nav><a href="/">AgentEng events</a> · <a href="/tools.json">Directory JSON</a> · '
        '<a href="/llms.txt">Agent guide</a> · <a href="/docs">API</a></nav></main></body></html>'
    )
