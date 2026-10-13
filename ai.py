#!/usr/bin/env python3
"""Simple AI-style command-line assistant.

This script can answer a prompt locally without any external dependency. If an
OpenAI-compatible API key is configured, it will try to use it; otherwise it
falls back to a lightweight rule-based assistant.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable


def normalize_prompt(text: str) -> str:
    return " ".join(text.strip().split())


def extract_keywords(prompt: str) -> list[str]:
    words = [word.lower() for word in prompt.replace("?", " ").split() if word.isalpha()]
    seen: set[str] = set()
    keywords: list[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            keywords.append(word)
    return keywords


def rule_based_response(prompt: str) -> str:
    clean = normalize_prompt(prompt)
    if not clean:
        return "I can help with ideas, planning, summarizing, debugging, or writing. Ask me anything."

    lowered = clean.lower()
    keywords = extract_keywords(clean)

    if any(word in lowered for word in ("hello", "hi", "hey")):
        return "Hello! I'm your local AI assistant. Ask me to summarize, plan, explain, or generate ideas."

    if any(word in lowered for word in ("summar", "overview", "brief")):
        return (
            "Summary: "
            f"You asked about '{clean}'. The key points are: "
            + ", ".join(keywords[:5])
            + ". If you want, I can turn this into a fuller outline or actionable plan."
        )

    if any(word in lowered for word in ("plan", "roadmap", "strategy")):
        return (
            "Here is a simple plan: 1) define your goal, 2) identify constraints, 3) break the work into phases, "
            "4) validate each phase with tests or checkpoints, and 5) iterate based on results."
        )

    if any(word in lowered for word in ("debug", "error", "bug")):
        return (
            "For a debugging task, start by reproducing the issue, isolating the failing code path, "
            "checking the inputs and assumptions, then testing the smallest fix before expanding scope."
        )

    if any(word in lowered for word in ("write", "create", "generate", "code")):
        return (
            "I can help with drafting code and project structure. Start by specifying the language, target behavior, "
            "and constraints, and I will propose a clean implementation plan or example."
        )

    if any(word in lowered for word in ("explain", "what is", "how does")):
        return (
            f"In simple terms, '{clean}' is a request to understand a concept or workflow. "
            "The best way to approach it is to break it into the problem, the goal, the inputs, and the expected outcome."
        )

    return (
        f"I can help with: {', '.join(keywords[:6]) or 'your prompt'} . "
        "Try asking for a summary, code example, debugging help, or a step-by-step plan."
    )


def openai_style_response(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return rule_based_response(prompt)

    try:
        # This import is intentionally lazy so the script runs in lightweight local setups.
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=250,
        )
        content = response.choices[0].message.content
        if content:
            return content.strip()
    except Exception:
        pass

    return rule_based_response(prompt)


def chat(prompt: str, output_json: bool = False) -> str:
    answer = openai_style_response(prompt)
    if output_json:
        return json.dumps({"prompt": prompt, "response": answer}, ensure_ascii=False)
    return answer


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a simple local AI assistant.")
    parser.add_argument("prompt", nargs="*", help="Prompt to answer")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    prompt = normalize_prompt(" ".join(args.prompt))
    if not prompt:
        try:
            prompt = normalize_prompt(sys.stdin.read())
        except KeyboardInterrupt:
            prompt = ""

    if not prompt:
        parser.print_help()
        return 1

    print(chat(prompt, output_json=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
