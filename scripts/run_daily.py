
from src.ingest_feeds import pull_company_posts
from src.ingest_arxiv import pull_arxiv
from src.ingest_semanticscholar import pull_s2
from src.ingest_crossref import pull_crossref
from src.ingest_pwc import pull_paperswithcode
from src.deliver_telegram import send_digest_telegram
from src.utils import boost_score_by_keywords, safe_get

TOP_SOURCES = {"Google AI Blog","DeepMind","OpenAI News","Microsoft Research","Meta Engineering"}

KEYWORDS = [
    "sdk","api","library","tool","agent","workflow","rag",
    "web dev","web development","app dev","application","developer","data engineering"
]

def score(item):
    s = 0
    if item.get("source") in TOP_SOURCES: s += 3
    s += boost_score_by_keywords(item, KEYWORDS)
    if item.get("code_url"): s += 2
    return s

def main():
    items = []
    items += pull_company_posts()
    items += pull_arxiv()
    items += pull_s2()
    items += pull_crossref()
    items += pull_paperswithcode()

    uniq = {}
    for i in items:
        k = i.get("url") or i.get("arxiv_id") or i.get("DOI")
        if k and (k not in uniq or score(i) > score(uniq[k])):
            uniq[k] = i

    ranked = sorted(uniq.values(), key=score, reverse=True)

    for i in ranked[:10]:
        i["key_findings"] = "- New/updated tool or concept\n- Practical relevance\n- See link for details"

    send_digest_telegram(ranked, bullets=7)

if __name__ == "__main__":
    main()
