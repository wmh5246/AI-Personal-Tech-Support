"""Quick-start topics and local behavior for the simulated preview."""

import re

from diagnostic_state import Category

QUICK_STARTS = {
    "internet": {
        "label": "Internet & Wi-Fi",
        "icon": "wifi",
        "question": "Does the connection problem affect this PC only, or other devices too?",
    },
    "performance": {
        "label": "Slow PC",
        "icon": "speed",
        "question": "When do you notice the slowdown most, such as at startup or in a specific app?",
    },
    "storage": {
        "label": "Storage",
        "icon": "hard_drive",
        "question": "What storage warning appeared, and did it name a drive?",
    },
    "audio": {
        "label": "Audio & Drivers",
        "icon": "headphones",
        "question": "Which device or app is affected, and when did the problem start?",
    },
    "gaming": {
        "label": "Overheating & Gaming",
        "icon": "sports_esports",
        "question": "Does this happen during a particular game or after the PC has been running for a while?",
    },
}


PREVIEW_CATEGORY_HINTS = {
    "internet": r"wi[ -]?fi|wireless network|internet|router|ethernet",
    "performance": r"slow(?:er|down)?|sluggish|freez(?:e|es|ing)|takes a long time",
    "storage": r"storage|disk space|drive (?:is )?full|c: drive",
    "audio": r"audio|no sound|lost sound|microphone|headphones|speakers?",
    "gaming": r"overheat(?:s|ing)?|too hot|gaming|(?:low|drops? in) fps",
}


def detect_preview_category(problem: str) -> Category | None:
    """Give the offline preview a category only when one set of hints matches."""
    matches = [
        category
        for category, hints in PREVIEW_CATEGORY_HINTS.items()
        if re.search(rf"\b(?:{hints})\b", problem, re.IGNORECASE)
    ]
    return matches[0] if len(matches) == 1 else None


def placeholder_reply(category: str | None, first_message: bool) -> str:
    """Return a fixed example without analyzing the user's message."""
    if not first_message:
        return "Your update is in the conversation. This preview stops at recording details."
    if category is not None:
        return QUICK_STARTS[category]["question"]
    return "When did the problem start, and what were you doing when you first noticed it?"
