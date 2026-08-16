"""Who the company says it is, supplied once by a human and never invented.

A model filling in a contact form will happily produce a plausible contact name,
a phone number and a company address. Every one of those would be a fabrication
sent to a real business under a real company's name, and the first person who
called the number would find out.

So identity is loaded from a file a person wrote, or outreach does not happen.
There is deliberately no code path that generates one, and the file sits behind
the same protection as the grant: nothing the system can edit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IDENTITY_FILENAME = "sender_identity.json"

#: Contact forms in Japan almost always require these. A blank one is not
#: something to fill in creatively.
REQUIRED_FIELDS = ("company_name", "sender_name", "email")


class IdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SenderIdentity:
    company_name: str
    sender_name: str
    email: str
    phone: str = ""
    website: str = ""
    address: str = ""

    def as_form_values(self) -> dict[str, str]:
        return {
            "company": self.company_name,
            "name": self.sender_name,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "address": self.address,
        }

    def missing(self, required: set[str]) -> set[str]:
        """Which of the fields a form demands this identity cannot supply."""
        available = {k for k, v in self.as_form_values().items() if v.strip()}
        return required - available


def load(directory: Path) -> SenderIdentity | None:
    """Read the identity a human wrote, or None if there is not one."""
    path = Path(directory) / IDENTITY_FILENAME
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise IdentityError(f"送信者情報を読めません: {exc}") from None

    blank = [f for f in REQUIRED_FIELDS if not str(raw.get(f, "")).strip()]
    if blank:
        raise IdentityError(
            f"送信者情報に必須項目がありません: {blank}。"
            "推測で補完はしません。"
        )
    return SenderIdentity(
        company_name=str(raw["company_name"]).strip(),
        sender_name=str(raw["sender_name"]).strip(),
        email=str(raw["email"]).strip(),
        phone=str(raw.get("phone", "")).strip(),
        website=str(raw.get("website", "")).strip(),
        address=str(raw.get("address", "")).strip(),
    )


def template() -> dict[str, Any]:
    return {
        "company_name": "",
        "sender_name": "",
        "email": "",
        "phone": "",
        "website": "",
        "address": "",
        "_note": (
            "問い合わせフォームに実際に記入される情報です。"
            "Guildlessはこの内容を生成も変更もしません。"
            "実在する連絡先を記入してください。"
        ),
    }
