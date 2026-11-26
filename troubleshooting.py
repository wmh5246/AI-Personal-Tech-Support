"""Quick-start topics and scripted replies for the interface preview."""

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


def placeholder_reply(category: str | None, first_message: bool) -> str:
    """Return a fixed example without analyzing the user's message."""
    if not first_message:
        return "Your update is in the conversation. This preview stops at recording details."
    if category is not None:
        return QUICK_STARTS[category]["question"]
    return "When did the problem start, and what were you doing when you first noticed it?"
