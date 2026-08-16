"""What the company has, which is never only its cash.

Zero cash is not zero capability. There is a machine, a GPU, an internet
connection, existing accounts, code, and a model that will work indefinitely.
Treating an empty wallet as "nothing can be done" is the mistake that stops a
company before it starts, so the wallet decides which strategies are available,
never whether the run continues.

Owned resources are deliberately not valued in yen. Counting a GPU as several
hundred thousand yen of capital would let the company believe it can afford
things it cannot pay for, and the books exist to prevent exactly that. What
matters about a resource is its marginal cost: the GPU is free to use again,
and the paid API is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Mode = Literal["bootstrap", "funded"]

#: Actions that require money before any revenue exists. All forbidden at ¥0,
#: not because they are bad but because they cannot be paid for.
UPFRONT_PAID_ACTIONS: frozenset[str] = frozenset({
    "paid_ads",
    "buy_api_credits",
    "subscribe_saas",
    "register_domain",
    "buy_inventory",
    "cloud_gpu",
    "buy_lead_list",
    "paid_directory_listing",
})

#: Work that costs nothing beyond electricity and time already available.
ZERO_COST_ACTIONS: frozenset[str] = frozenset({
    "local_inference",
    "web_research",
    "github_search",
    "oss_usage",
    "existing_account_usage",
    "contact_form_outreach",
    "public_data_collection",
    "code_generation",
    "site_generation",
    "analysis",
    "artifact_production",
    "free_listing",
    # Marketplaces and payment processors take their cut out of money that has
    # already arrived, so they cost nothing to a company holding none.
    "revenue_share_channel",
})


@dataclass
class ResourceInventory:
    """Cash, owned resources, and what each additional use actually costs."""

    cash_yen: int = 0
    local_compute: bool = True
    gpu: str = ""
    internet: bool = True
    github: bool = True
    browser: bool = True
    owned_domains: list[str] = field(default_factory=list)
    email_accounts: list[str] = field(default_factory=list)
    existing_products: list[str] = field(default_factory=list)
    existing_codebases: list[str] = field(default_factory=list)
    #: Credits already paid for. Spendable without new outlay.
    api_credits: dict[str, int] = field(default_factory=dict)
    #: Things the company can do, grown by discovery rather than assumed.
    capabilities: set[str] = field(default_factory=set)

    @property
    def mode(self) -> Mode:
        return "bootstrap" if self.cash_yen <= 0 else "funded"

    @property
    def bootstrap(self) -> bool:
        return self.mode == "bootstrap"

    def can_afford(self, action: str, cost_yen: int = 0) -> tuple[bool, str]:
        """Whether an action is available given the money actually on hand."""
        if action in ZERO_COST_ACTIONS:
            return True, "追加費用なしで実行できます"
        if self.bootstrap:
            if action in UPFRONT_PAID_ACTIONS:
                return False, f"{action}は前払いが必要で、現金¥0では実行できません"
            if cost_yen > 0:
                return False, f"{action}には¥{cost_yen:,}が必要ですが現金がありません"
            return True, "費用が発生しないため実行できます"
        if cost_yen > self.cash_yen:
            return False, f"{action}の¥{cost_yen:,}に対し現金は¥{self.cash_yen:,}しかありません"
        return True, "支払可能です"

    def available_actions(self) -> set[str]:
        if self.bootstrap:
            return set(ZERO_COST_ACTIONS)
        return set(ZERO_COST_ACTIONS) | set(UPFRONT_PAID_ACTIONS)

    def derive_capabilities(self) -> set[str]:
        """Capabilities implied by what is already owned.

        This is what turns an inventory into strategies: a company with an
        authenticated domain can send email, one without can still use contact
        forms, and neither fact needs a person to point it out.
        """
        derived: set[str] = set(self.capabilities)
        if self.browser and self.internet:
            derived |= {"form_submission", "web_research", "sender_identity"}
        if self.github:
            derived.add("oss_discovery")
        if self.local_compute:
            derived.add("local_inference")
        if self.gpu:
            derived.add("local_media_generation")
        if self.email_accounts:
            derived.add("public_company_addresses")
        if self.owned_domains:
            derived.add("owned_domain")
        if self.existing_codebases:
            derived.add("code_reuse")
        return derived

    def record_revenue(self, amount_yen: int) -> None:
        """First money in is what lifts the company out of bootstrap."""
        if amount_yen > 0:
            self.cash_yen += amount_yen


def bootstrap_reason(inventory: ResourceInventory) -> str:
    if not inventory.bootstrap:
        return f"現金¥{inventory.cash_yen:,}があるため通常モードです"
    have = []
    if inventory.local_compute:
        have.append("ローカル計算")
    if inventory.gpu:
        have.append(f"GPU({inventory.gpu})")
    if inventory.internet:
        have.append("ネット接続")
    if inventory.github:
        have.append("GitHub")
    if inventory.email_accounts:
        have.append("既存メールアカウント")
    return (
        f"現金¥0のため無料でできる手段のみ探索します。使えるもの: {'、'.join(have) or 'なし'}"
    )
