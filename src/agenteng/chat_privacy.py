"""Contact/credential checks for public chat, not a complete personal-data detector."""

import re

EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE = re.compile(r"(?<![\w])\+?\d[\d ()-]{7,}\d(?![\w])")
SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|ae_participant_[A-Za-z0-9_-]{20,}|"
    r"(?:AKIA|ASIA)[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"
    r"|\bBearer\s+\S{16,}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
    re.I,
)
SELF_DISCLOSURE = re.compile(
    r"\bmy\s+(?:full\s+)?(?:name\s+is|(?:home\s+)?address\s+is|"
    r"(?:email|phone|mobile|passport|ssn|social security|date of birth|credit card)\b)",
    re.I,
)
PRIVATE_RECORDS = re.compile(
    r"\b(?:private|nonpublic|non-public|unpublished|confidential)\b.{0,80}"
    r"\b(?:records?|contacts?|proposals?|submissions?|attendees?|members?|emails?|phones?|addresses?|database)\b"
    r"|\b(?:attendees?|members?|registrants?|participants?)\b.{0,80}"
    r"\b(?:emails?|phones?|addresses?|contact (?:details|information)|personal (?:details|information)|records?|data)\b"
    r"|\b(?:emails?|phones?|addresses?|contact (?:details|information)|personal (?:details|information))\b.{0,80}"
    r"\b(?:attendees?|members?|registrants?|participants?)\b",
    re.I | re.S,
)

PRIVACY_REPLY = (
    "I can help with published events, speakers, agendas and engineering tools. "
    "Please leave personal contact details, credentials and private records out of chat."
)


def identifiers(text):
    values = {match.group().casefold() for match in EMAIL.finditer(text)}
    for match in PHONE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 9 <= len(digits) <= 15:
            values.add(digits)
    return values


def has_sensitive_input(text, public_identifiers=()):
    return bool(
        SECRET.search(text)
        or SELF_DISCLOSURE.search(text)
        or PRIVATE_RECORDS.search(text)
        or identifiers(text) - set(public_identifiers)
    )
