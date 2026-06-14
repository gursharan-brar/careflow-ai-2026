import os
import json
import logging
import re
from anthropic import Anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

VALID_PRIORITIES = ("routine", "moderate", "urgent")

TRIAGE_QUESTIONS = {
    "gp_consult": [
        "What is the main reason for your visit today?",
        "How long have you had this issue?",
        "On a scale of 1-10, how would you rate your discomfort?",
        "Do you have any chronic conditions (diabetes, heart disease, etc.)?",
        "Are you currently taking any medications?",
    ],
    "prescription_renewal": [
        "Which medication(s) do you need renewed?",
        "When did you last fill this prescription?",
        "Have you experienced any side effects from this medication?",
        "Has a doctor changed your dosage recently?",
        "Do you have any new symptoms since your last visit?",
    ],
    "injury": [
        "What part of your body is injured?",
        "How did the injury happen?",
        "When did the injury occur?",
        "On a scale of 1-10, how would you rate your pain?",
        "Are you able to move or put weight on the injured area?",
    ],
    "general": [
        "What is the main reason for your visit today?",
        "How long have you been experiencing this?",
        "On a scale of 1-10, how would you rate your discomfort?",
        "Have you had a fever in the last 24 hours?",
        "Are you currently taking any medications?",
    ],
}

FALLBACK_RESULT = {
    "priority_level": "moderate",
    "summary": "Automated triage unavailable. Manual review required.",
    "flag_reason": "ai_unavailable",
}

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        _client = Anthropic(api_key=api_key)
    return _client


def classify_triage(visit_type, symptom_answers):
    questions = TRIAGE_QUESTIONS.get(visit_type, TRIAGE_QUESTIONS["general"])
    qa_pairs = "\n".join(
        f"{i + 1}. {questions[i]}\n   Answer: {symptom_answers[i]}"
        for i in range(min(len(questions), len(symptom_answers)))
    )

    prompt = (
        "You are a clinical triage assistant for a Calgary walk-in clinic. "
        "Based on the patient's visit type and answers below, classify the urgency.\n\n"
        f"Visit type: {visit_type}\n\n"
        f"Questions and answers:\n{qa_pairs}\n\n"
        "Respond with ONLY a JSON object (no other text) in this exact format:\n"
        '{"priority_level": "routine|moderate|urgent", "summary": "1-2 sentence clinical summary", '
        '"flag_reason": "short reason if urgent/moderate, or empty string if routine"}'
    )

    try:
        client = get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()
        return _parse_triage_response(raw_text)
    except Exception as e:
        logger.error(f"Triage classification failed: {e}")
        return dict(FALLBACK_RESULT)


def _parse_triage_response(raw_text):
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in response")

        data = json.loads(match.group(0))

        priority_level = data.get("priority_level", "").strip().lower()
        summary = data.get("summary", "").strip()
        flag_reason = data.get("flag_reason", "").strip()

        if priority_level not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority_level: {priority_level}")
        if not summary:
            raise ValueError("Empty summary")

        return {
            "priority_level": priority_level,
            "summary": summary,
            "flag_reason": flag_reason,
        }
    except Exception as e:
        logger.error(f"Failed to parse triage response: {e} | raw: {raw_text}")
        return dict(FALLBACK_RESULT)
