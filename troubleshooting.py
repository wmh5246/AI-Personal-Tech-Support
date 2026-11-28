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

CATEGORY_LABELS = {key: topic["label"] for key, topic in QUICK_STARTS.items()} | {"general": "General Troubleshooting"}
GENERAL_QUESTION = "What are you trying to do, and what message or behavior do you see instead?"

PREVIEW_CATEGORY_HINTS = {
    "internet": r"wi[ -]?fi|wireless network|internet|router|ethernet",
    "performance": r"slow(?:er|down)?|sluggish|freez(?:e|es|ing)|takes a long time",
    "storage": r"low (?:disk space|storage)|running out of (?:disk space|storage)|(?:drive|storage) (?:is )?(?:almost )?full|needs? more space",
    "audio": r"audio|no sound|lost sound|microphone|headphones|speakers?",
    "gaming": r"overheat(?:s|ing)?|too hot|gaming|(?:low|drops? in) fps",
}

PREVIEW_GENERAL_ISSUES = re.compile(
    r"\b(?:windows updates?.*\b(?:error|fail\w*|stuck|won't install)|"
    r"printer\b.*\b(?:jam\w*|offline|won't print)|blue screen|"
    r"(?:can't|cannot) (?:start windows|sign in to windows))\b",
    re.IGNORECASE,
)


def detect_preview_category(problem: str, previous: Category | None = None) -> Category | None:
    """Give the offline preview a category only when one set of hints matches."""
    matches = [
        category
        for category, hints in PREVIEW_CATEGORY_HINTS.items()
        if re.search(rf"\b(?:{hints})\b", problem, re.IGNORECASE)
    ]
    if matches:
        return matches[0] if len(matches) == 1 else None
    if PREVIEW_GENERAL_ISSUES.search(problem):
        return "general"
    return previous


def placeholder_reply(category: Category | None, first_message: bool) -> str:
    """Return a fixed example without analyzing the user's message."""
    if not first_message:
        return "Your update is in the conversation. This preview stops at recording details."
    if category == "general":
        return GENERAL_QUESTION
    if category is not None:
        return QUICK_STARTS[category]["question"]
    return "When did the problem start, and what were you doing when you first noticed it?"
