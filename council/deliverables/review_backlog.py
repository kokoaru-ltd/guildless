"""Builds the deliverable for the review-backlog offer.

The product is a prioritised backlog, not a summary of complaints. What makes it
worth paying for is that every ticket carries the evidence it came from, so the
buyer can act without going back to read the reviews themselves — which is the
work they were trying to avoid.

Reviews are public data fetched from the store's own feed. Nothing here needs
credentials from the customer, which is what lets the offer be proven before it
is sold.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from pydantic import Field

from council.schemas import StrictModel


TicketKind = Literal["bug", "request", "praise", "other"]
Severity = Literal["critical", "high", "medium", "low"]


@dataclass
class Review:
    review_id: str
    title: str
    body: str
    rating: int
    version: str = ""

    @property
    def text(self) -> str:
        return f"{self.title} / {self.body}".strip(" /")


def fetch_reviews(app_id: str, *, country: str = "jp", pages: int = 5) -> list[Review]:
    """Pull public customer reviews from the store feed.

    Paging stops on the first empty or failing page rather than retrying: an
    app with few reviews is a fact about the app, not an error to work around.
    """
    reviews: list[Review] = []
    for page in range(1, pages + 1):
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"id={app_id}/sortBy=mostRecent/page={page}/json"
        )
        try:
            response = httpx.get(url, timeout=30)
        except httpx.HTTPError:
            break
        if response.status_code != 200:
            break
        entries = (response.json().get("feed") or {}).get("entry") or []
        # The first entry on page 1 is the app itself, not a review.
        rows = [e for e in entries if "im:rating" in e]
        if not rows:
            break
        for entry in rows:
            reviews.append(
                Review(
                    review_id=(entry.get("id") or {}).get("label", ""),
                    title=(entry.get("title") or {}).get("label", ""),
                    body=(entry.get("content") or {}).get("label", ""),
                    rating=int((entry.get("im:rating") or {}).get("label", 0) or 0),
                    version=(entry.get("im:version") or {}).get("label", ""),
                )
            )
    return reviews


class Ticket(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    kind: TicketKind
    severity: Severity
    #: What the user cannot do, stated so an engineer can act on it.
    problem: str = Field(min_length=1, max_length=500)
    #: Best guess at how to reproduce, marked as a hypothesis because it is one.
    reproduction_hypothesis: str = Field(default="", max_length=400)
    #: Which reviews this rests on, by the number shown in the prompt. The model
    #: cites; it never quotes. Asked for quotes it stitches fragments together
    #: with ellipses and reworks the wording, which reads as verbatim and is not
    #: — fatal for a deliverable whose whole value is that the buyer can trust
    #: the evidence without going back to check it. Code pastes the real text.
    source_review_numbers: list[int] = Field(min_length=1, max_length=8)
    affected_versions: list[str] = Field(default_factory=list, max_length=10)


class Backlog(StrictModel):
    tickets: list[Ticket] = Field(min_length=1, max_length=40)


@dataclass
class DeliveryResult:
    app_id: str
    review_count: int
    tickets: list[dict[str, Any]]
    csv_text: str
    summary: dict[str, Any] = field(default_factory=dict)


ANALYSIS_PROMPT = """
以下は実際のアプリストアのカスタマーレビュー{count}件です。
これを開発チームがそのまま着手できる改善バックログに変換してください。

要件:
- 不具合(bug)と要望(request)を分ける。称賛のみのレビューは無視してよい
- 同じ内容のレビューは1つのチケットにまとめる
- source_review_numbersには、根拠となったレビューの先頭の番号だけを入れる。
  レビュー本文は引用しない。引用文はこちらが番号から自動で挿入する
- severityは、アプリが使えない/データが失われる=critical、主要機能が使えない=high、
  不便だが回避可能=medium、軽微=low
- reproduction_hypothesisは推測であることを前提に、再現手順の仮説を書く
- レビューに書かれていないことをproblemに書かない

レビュー:
{reviews}
""".strip()


def build_prompt(reviews: list[Review], limit: int = 120) -> str:
    selected = reviews[:limit]
    lines = [
        f"#{index} [{r.rating}星 v{r.version or '不明'}] {r.text[:400]}"
        for index, r in enumerate(selected, start=1)
    ]
    return ANALYSIS_PROMPT.format(count=len(selected), reviews="\n".join(lines))


def to_csv(tickets: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["優先度", "種別", "タイトル", "内容", "再現仮説", "根拠レビュー", "影響バージョン"]
    )
    for ticket in tickets:
        writer.writerow([
            ticket.get("severity", ""),
            ticket.get("kind", ""),
            ticket.get("title", ""),
            ticket.get("problem", ""),
            ticket.get("reproduction_hypothesis", ""),
            " | ".join(ticket.get("evidence") or []),
            ", ".join(ticket.get("affected_versions") or []),
        ])
    return buffer.getvalue()


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def assemble(
    app_id: str, reviews: list[Review], backlog: Backlog, *, prompt_limit: int = 120
) -> DeliveryResult:
    """Attach verbatim review text to each ticket from its cited numbers.

    The quotes are pasted here rather than written by the model, so what the
    buyer reads is exactly what a customer wrote.
    """
    cited = reviews[:prompt_limit]
    tickets = []
    for ticket in backlog.tickets:
        row = ticket.model_dump(mode="json")
        quotes, missing = [], []
        for number in row.pop("source_review_numbers", []):
            if 1 <= number <= len(cited):
                quotes.append(cited[number - 1].text)
            else:
                missing.append(number)
        row["evidence"] = quotes
        row["invalid_citations"] = missing
        tickets.append(row)
    tickets.sort(key=lambda t: SEVERITY_RANK.get(t["severity"], 9))
    kinds = Counter(t["kind"] for t in tickets)
    severities = Counter(t["severity"] for t in tickets)
    return DeliveryResult(
        app_id=app_id,
        review_count=len(reviews),
        tickets=tickets,
        csv_text=to_csv(tickets),
        summary={
            "tickets": len(tickets),
            "by_kind": dict(kinds),
            "by_severity": dict(severities),
            "average_rating": round(
                sum(r.rating for r in reviews) / len(reviews), 2
            ) if reviews else 0,
        },
    )


def check_quality(result: DeliveryResult, reviews: list[Review]) -> tuple[bool, list[str]]:
    """Judge the artefact against what was promised, before anyone is charged.

    Evidence is verified against the actual review text rather than trusted,
    because a fabricated quote is the one defect that would destroy the product
    the moment a customer checked it.
    """
    problems: list[str] = []
    corpus = "\n".join(r.text for r in reviews)

    if result.review_count < 20:
        problems.append(f"レビューが{result.review_count}件しかなく、優先度を判断できない")
    if len(result.tickets) < 5:
        problems.append(f"チケットが{len(result.tickets)}件では納品物として薄い")

    # Quotes are pasted from cited reviews, so they cannot be fabricated. What
    # can still go wrong is a citation pointing at a review that was never in
    # the prompt, which would leave a ticket resting on nothing.
    invalid = sum(len(t.get("invalid_citations") or []) for t in result.tickets)
    if invalid:
        problems.append(f"存在しないレビュー番号の引用が{invalid}件ある")

    unsupported = sum(
        1
        for ticket in result.tickets
        for quote in ticket.get("evidence") or []
        if quote.strip()[:18] and quote.strip()[:18] not in corpus
    )
    if unsupported:
        problems.append(f"レビュー本文に存在しない引用が{unsupported}件ある（捏造）")

    if any(not (t.get("evidence") or []) for t in result.tickets):
        problems.append("根拠レビューが1件も紐づいていないチケットがある")

    if not any(t["kind"] == "bug" for t in result.tickets):
        problems.append("不具合チケットが1件もない")
    if not result.csv_text.strip():
        problems.append("CSVが空")

    return (not problems), problems
