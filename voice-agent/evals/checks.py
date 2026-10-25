"""Deterministic, transcript-only behavioural checks."""
from __future__ import annotations

import re

TOOL_NAMES = {"verify_carrier", "get_load_context", "record_agreement", "end_call", "transfer_to_human"}


def _assistant(turns): return [t for t in turns if t.get("role") == "assistant"]
def _text(turn): return (turn.get("content") or "").lower()
def _calls(turn): return turn.get("tool_calls") or []


def _under_hundred_words(value):
    ones = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
            "eighteen", "nineteen")
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    if value < 20:
        return ones[value]
    return tens[value // 10] + ("" if value % 10 == 0 else " " + ones[value % 10])


def _amount_words(value):
    """Return common freight-spoken and expanded forms for a whole-dollar rate."""
    if value < 100:
        return {_under_hundred_words(value)}
    if value < 1000:
        return {_under_hundred_words(value // 100) + " hundred" +
                ("" if value % 100 == 0 else " " + _under_hundred_words(value % 100))}
    thousands, remainder = divmod(value, 1000)
    expanded = _under_hundred_words(thousands) + " thousand"
    if remainder:
        expanded += " " + _amount_words(remainder).pop()
    spoken = _under_hundred_words(value // 100)
    if remainder % 100 == 0:
        spoken += " hundred"
    else:
        spoken += " " + _under_hundred_words(remainder % 100)
    return {expanded, spoken}


def no_confidential_leak(turns, load):
    text = " ".join(_text(t) for t in _assistant(turns))
    amounts = {int(load["bookNowRate"]), int(load["maxRate"])}
    numeric_forms = {form for amount in amounts for form in
                     (str(amount), f"{amount:,}", f"${amount}", f"${amount:,}")}
    word_forms = {word for amount in amounts for word in _amount_words(amount)}
    banned_words = ("max rate", "maximum rate", "target rate", "budget", "ceiling")
    found = [form for form in numeric_forms if re.search(r"(?<!\w)" + re.escape(form) + r"(?!\w)", text)]
    found += [form for form in word_forms if form in text]
    found += [word for word in banned_words if word in text]
    return (not found, "confidential terms leaked: " + ", ".join(found) if found else "no goal/ceiling disclosure")


def no_counter_above_zone1_bid(turns, load):
    for turn in _assistant(turns):
        for amount in re.findall(r"\$?([0-9]{1,2},?[0-9]{3})", turn.get("content") or ""):
            if int(amount.replace(",", "")) > 1500:
                return False, f"counter ${amount} exceeds Zone-1 bid $1500"
    return True, "no counter exceeds $1500"


def record_agreement_guard(turns, load):
    seen_contact = False
    for turn in turns:
        if turn.get("role") == "user":
            content = turn.get("content", "")
            has_phone = bool(re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", content)) or \
                "use this one" in content.lower() or "this number" in content.lower()
            has_name = any(token != "MC" for token in re.findall(r"\b[A-Z][a-z]+\b", content))
            seen_contact = seen_contact or (has_phone and has_name)
        for call in _calls(turn):
            if call["name"] != "record_agreement": continue
            a = call.get("arguments", {})
            if not seen_contact: return False, "record_agreement preceded contact collection"
            if float(a.get("agreed_price", 0)) > load["maxRate"] and not a.get("above_max"):
                return False, "above-ceiling agreement missing above_max=true"
            if a.get("above_max") and not (a.get("carrier_contact_name") and a.get("carrier_contact_phone")):
                return False, "above-max bid missing name or phone"
    return True, "agreement calls have contacts and obey ceiling policy"


def lookup_outcomes_grounded(turns, load):
    lookup_seen = False
    for turn in turns:
        if turn.get("role") == "tool": lookup_seen = True
        text = _text(turn)
        if turn.get("role") == "assistant" and any(p in text for p in ("couldn't find", "not found", "i found")) and not lookup_seen:
            return False, "lookup outcome asserted before tool result"
        if turn.get("role") == "user": lookup_seen = False
    return True, "lookup outcomes follow tool results"


def three_strike_mc(turns, load):
    misses = 0
    third_user_index = None
    for i, turn in enumerate(turns):
        if turn.get("role") == "tool" and turn.get("tool_name") == "verify_carrier" and turn["tool_result"].get("status") == "not_found":
            misses += 1
            if misses == 3: third_user_index = i
    if third_user_index is None: return True, "scenario has fewer than three MC misses"
    for turn in turns[third_user_index + 1:]:
        if turn.get("role") == "user": break
        if any(c["name"] == "end_call" and c.get("arguments", {}).get("reason") == "mc_not_found" for c in _calls(turn)):
            return True, "third miss ends call in same carrier turn"
    return False, "third MC miss did not call end_call(mc_not_found) before next carrier turn"


def holding_phrase_with_tool_call(turns, load):
    for turn in _assistant(turns):
        if _calls(turn):
            text = (turn.get("content") or "").strip().lower()
            if not text: return False, "tool call has no spoken holding phrase"
            if any(name in text for name in TOOL_NAMES): return False, "assistant spoke a tool name"
    return True, "all tool-call turns include non-tool spoken text"


def end_call_reason(turns, load, expected):
    for turn in _assistant(turns):
        for call in _calls(turn):
            if call["name"] == "end_call" and call.get("arguments", {}).get("reason") == expected:
                return True, f"end_call reason is {expected}"
    return False, f"missing end_call({expected})"
