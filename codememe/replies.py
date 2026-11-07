"""Pull the one JSON block out of an LLM reply (fenced or bare)."""

from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict:
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for candidate in (*fenced, text):
        candidate = candidate.strip()
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as e:
                last = e
                continue
            if isinstance(data, dict):
                return data
    raise SystemExit(f"No valid JSON object in the reply ({locals().get('last', 'none found')}).")
