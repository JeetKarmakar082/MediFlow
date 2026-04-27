"""
AI Triage Engine — uses Google Gemini (new google-genai SDK) with rule-based fallback.
Set GEMINI_API_KEY in .env to enable AI scoring.
"""
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def rule_based_score(vitals: dict) -> dict:
    """Deterministic fallback when no API key is set or Gemini fails."""
    score = 5
    reasons = []

    oxygen = float(vitals.get('oxygen', 99))
    pulse   = int(vitals.get('pulse', 80))
    pain    = int(vitals.get('pain', 0))
    temp    = float(vitals.get('temperature', 37.0))
    bp_sys  = int(vitals.get('bp_systolic', 120))

    if oxygen < 90:
        score = min(score, 1); reasons.append(f"Critical SpO2: {oxygen}%")
    elif oxygen < 94:
        score = min(score, 2); reasons.append(f"Low SpO2: {oxygen}%")

    if pulse > 150 or pulse < 40:
        score = min(score, 1); reasons.append(f"Dangerous pulse: {pulse} bpm")
    elif pulse > 120 or pulse < 50:
        score = min(score, 2); reasons.append(f"Abnormal pulse: {pulse} bpm")

    if bp_sys > 180 or bp_sys < 70:
        score = min(score, 1); reasons.append(f"Critical BP: {bp_sys} mmHg")
    elif bp_sys > 160 or bp_sys < 90:
        score = min(score, 2); reasons.append(f"Abnormal BP: {bp_sys} mmHg")

    if temp > 40.0 or temp < 35.0:
        score = min(score, 2); reasons.append(f"Dangerous temp: {temp}°C")
    elif temp > 38.5:
        score = min(score, 3); reasons.append(f"High fever: {temp}°C")

    if pain >= 9:
        score = min(score, 2); reasons.append(f"Severe pain: {pain}/10")
    elif pain >= 7:
        score = min(score, 3); reasons.append(f"High pain: {pain}/10")

    action_map = {
        1: 'Immediate resuscitation — alert senior doctor NOW',
        2: 'Emergency treatment within 15 minutes',
        3: 'Seen within 30 minutes',
        4: 'Seen within 1 hour',
        5: 'Routine queue — seen within 2 hours',
    }
    return {
        'score': score,
        'reason': '; '.join(reasons) if reasons else 'Vitals within normal range',
        'action': action_map[score],
        'source': 'rule_based',
    }


def build_prompt(vitals: dict, symptoms: str) -> str:
    return f"""You are a medical triage assistant in a government hospital in India.

Patient vitals:
- Blood Pressure: {vitals.get('bp_systolic')}/{vitals.get('bp_diastolic')} mmHg
- Pulse: {vitals.get('pulse')} bpm
- Temperature: {vitals.get('temperature')}°C
- SpO2: {vitals.get('oxygen')}%
- Pain Scale: {vitals.get('pain')}/10
- Symptoms: {symptoms}

Score this patient 1 to 5:
1 = Immediate (life threatening)
2 = Emergency (urgent, within 15 min)
3 = Urgent (within 30 min)
4 = Semi-Urgent (within 1 hour)
5 = Non-Urgent (routine)

Respond ONLY with valid JSON, no extra text:
{{"score": <integer 1-5>, "reason": "<brief clinical reason>", "action": "<recommended action>"}}"""


def calculate_triage_score(vitals: dict, symptoms: str) -> dict:
    """
    Main entry point.
    Uses Google Gemini (new google-genai SDK) → falls back to rule-based.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')

    if not api_key:
        logger.info("No GEMINI_API_KEY — using rule-based scorer")
        return rule_based_score(vitals)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=build_prompt(vitals, symptoms),
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=500,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        # Extract text safely
        try:
            text = response.text.strip()
        except Exception:
            text = response.candidates[0].content.parts[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        score = int(result['score'])
        assert 1 <= score <= 5

        logger.info(f"Gemini triage score: {score}")
        return {
            'score': score,
            'reason': result.get('reason', ''),
            'action': result.get('action', ''),
            'source': 'gemini',
        }

    except Exception as exc:
        logger.warning(f"Gemini triage failed ({exc}) — falling back to rule-based scorer")
        return rule_based_score(vitals)
