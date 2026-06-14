import os
import json
import logging
import re
from datetime import datetime, timezone
from anthropic import Anthropic
from db import get_db

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

FALLBACK_FEED = [
    {
        "title": "Health feed temporarily unavailable",
        "summary": "Unable to retrieve the latest AHS/Health Canada updates at this time.",
        "source": "CareFlow AI",
        "date": "",
    }
]

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        _client = Anthropic(api_key=api_key)
    return _client


def fetch_health_feed():
    prompt = (
        "Search for the most recent public health alerts, advisories, or notices relevant to "
        "Calgary, Alberta from Alberta Health Services (AHS) or Health Canada "
        "(e.g. flu activity, outbreaks, recalls, vaccination updates, air quality advisories).\n\n"
        "Return ONLY a JSON array (no preamble, no explanation) of up to 5 items in this exact format:\n"
        '[{"title": "short title", "summary": "1-2 sentence summary", "source": "AHS or Health Canada", "date": "YYYY-MM-DD"}]'
    )

    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = _extract_text(response)
        cleaned_text = _strip_citation_tags(raw_text)
        return _parse_feed_response(cleaned_text)
    except Exception as e:
        logger.error(f"Health feed fetch failed: {e}")
        return list(FALLBACK_FEED)


def _extract_text(response):
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _strip_citation_tags(text):
    text = re.sub(r"<citation[^>]*>.*?</citation>", "", text, flags=re.DOTALL)
    text = re.sub(r"<\/?citation[^>]*>", "", text)
    return text.strip()


def _parse_feed_response(text):
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in response")

        entries = json.loads(match.group(0))
        if not isinstance(entries, list):
            raise ValueError("Parsed result is not a list")

        validated = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            validated.append({
                "title": str(entry.get("title", "")).strip(),
                "summary": str(entry.get("summary", "")).strip(),
                "source": str(entry.get("source", "")).strip(),
                "date": str(entry.get("date", "")).strip(),
            })

        if not validated:
            raise ValueError("No valid entries found")

        return validated
    except Exception as e:
        logger.error(f"Failed to parse health feed response: {e} | raw: {text}")
        return list(FALLBACK_FEED)


def store_health_feed(entries):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO health_feed (entries, fetched_at) VALUES (?, ?)",
        (json.dumps(entries), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def run_health_feed_job():
    entries = fetch_health_feed()
    store_health_feed(entries)
    logger.info(f"Health feed updated with {len(entries)} entries")
