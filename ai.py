#!/usr/bin/env python3
"""A command-line personal assistant powered by a local Ollama model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_MODEL = "llama3.2"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_VOSK_MODEL = Path("models/vosk-model-small-en-us-0.15")
F_DRIVE_VOSK_MODEL = Path("F:/Ollama/speech/vosk-model-small-en-us-0.15")
VOICE_SAMPLE_RATE = 16_000
VOICE_RECORD_SECONDS = 7
SYSTEM_PROMPT = (
    "You are Jarvis, a helpful, capable personal AI assistant. "
    "Be clear, practical, and honest about uncertainty."
)


class OllamaError(RuntimeError):
    """Raised when Ollama cannot provide a valid assistant response."""


class VoiceError(RuntimeError):
    """Raised when offline voice input or output is unavailable."""


class AudioRecording(Protocol):
    def tobytes(self) -> bytes: ...


class AudioInput(Protocol):
    def rec(
        self, frames: int, *, samplerate: int, channels: int, dtype: str
    ) -> AudioRecording: ...

    def wait(self) -> None: ...


class SpeechRecognizer(Protocol):
    def AcceptWaveform(self, data: bytes) -> bool: ...

    def FinalResult(self) -> str: ...

    def Reset(self) -> None: ...


class SpeechSpeaker(Protocol):
    def say(self, text: str) -> None: ...

    def runAndWait(self) -> None: ...


def normalize_prompt(text: str) -> str:
    return " ".join(text.strip().split())


def setup_voice() -> tuple[AudioInput, SpeechRecognizer, SpeechSpeaker]:
    """Load offline speech recognition and speech synthesis components."""
    configured_path = os.getenv("VOSK_MODEL_PATH")
    if configured_path:
        model_path = Path(configured_path)
    elif F_DRIVE_VOSK_MODEL.is_dir():
        model_path = F_DRIVE_VOSK_MODEL
    else:
        model_path = DEFAULT_VOSK_MODEL

    if not model_path.is_dir():
        raise VoiceError(
            f"Offline speech model not found at {model_path}. "
            "See the voice setup instructions in README.md."
        )

    try:
        import pyttsx3
        import sounddevice
        from vosk import KaldiRecognizer, Model
    except ImportError as exc:
        raise VoiceError(
            "Voice dependencies are missing. Install them with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    try:
        speech_model = Model(str(model_path))
        recognizer = KaldiRecognizer(speech_model, VOICE_SAMPLE_RATE)
        speaker = pyttsx3.init()
    except (OSError, RuntimeError) as exc:
        raise VoiceError(f"Could not initialize voice support: {exc}") from exc
    return sounddevice, recognizer, speaker


def capture_voice_prompt(
    sounddevice: AudioInput, recognizer: SpeechRecognizer
) -> str:
    """Record a short push-to-talk utterance and transcribe it locally."""
    try:
        from sounddevice import PortAudioError
    except ImportError as exc:
        raise VoiceError(
            "Voice dependencies are missing. Install them with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    try:
        try:
            recording = sounddevice.rec(
                int(VOICE_RECORD_SECONDS * VOICE_SAMPLE_RATE),
                samplerate=VOICE_SAMPLE_RATE,
                channels=1,
                dtype="int16",
            )
            sounddevice.wait()
            recognizer.AcceptWaveform(recording.tobytes())
            result = json.loads(recognizer.FinalResult())
        finally:
            recognizer.Reset()
    except (OSError, RuntimeError, PortAudioError, json.JSONDecodeError) as exc:
        raise VoiceError(f"Could not record or transcribe audio: {exc}") from exc

    if not isinstance(result, dict):
        raise VoiceError("Speech recognition returned an invalid result.")
    prompt = result.get("text")
    if not isinstance(prompt, str):
        raise VoiceError("Speech recognition returned an invalid result.")
    return normalize_prompt(prompt)


def ollama_response(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    history: list[dict[str, str]] | None = None,
    timeout: float = 120.0,
) -> str:
    """Send a conversation to Ollama and return its assistant message."""
    parsed_host = urlsplit(host)
    if parsed_host.scheme not in {"http", "https"} or not parsed_host.netloc:
        raise OllamaError(f"Invalid Ollama server URL: {host}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": False}
    ).encode("utf-8")
    request = Request(
        f"{host.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if exc.code == 404:
            raise OllamaError(
                f"Ollama returned 404. Check that it is running and that the "
                f"'{model}' model is installed (run `ollama pull {model}`)."
            ) from exc
        raise OllamaError(
            f"Ollama returned HTTP {exc.code}"
            + (f": {detail}" if detail else ".")
        ) from exc
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise OllamaError(
            f"Could not reach Ollama at {host}. Start Ollama and try again. "
            f"Details: {reason}"
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OllamaError("Ollama returned an invalid JSON response.") from exc

    if not isinstance(result, dict):
        raise OllamaError("Ollama returned an invalid response object.")
    message = result.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("Ollama returned no assistant message.")
    return content.strip()


def chat(
    prompt: str,
    output_json: bool = False,
    *,
    model: str | None = None,
    host: str | None = None,
) -> str:
    model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    host = host or os.getenv("OLLAMA_HOST", DEFAULT_HOST)
    answer = ollama_response(prompt, model=model, host=host)
    if output_json:
        return json.dumps({"prompt": prompt, "response": answer}, ensure_ascii=False)
    return answer


def interactive_chat(*, model: str, host: str, voice: bool = False) -> int:
    """Run a multi-turn terminal conversation until the user exits."""
    history: list[dict[str, str]] = []
    if voice:
        sounddevice, recognizer, speaker = setup_voice()
        print(
            f"Jarvis is ready using {model}. Press Enter to record "
            f"for up to {VOICE_RECORD_SECONDS} seconds; type /exit to quit."
        )
    else:
        print(f"Jarvis is ready using {model}. Type /exit to quit.")

    while True:
        try:
            if voice:
                action = input("Press Enter to talk (or /exit): ").strip()
                if action.lower() in {"/exit", "/quit"}:
                    return 0
                print("Listening...")
                prompt = capture_voice_prompt(sounddevice, recognizer)
                if not prompt:
                    print("Jarvis: I didn't catch that. Please try again.")
                    continue
                print(f"You: {prompt}")
            else:
                prompt = normalize_prompt(input("You: "))
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        except VoiceError as exc:
            print(f"Jarvis voice error: {exc}", file=sys.stderr)
            continue
        if not voice and prompt.lower() in {"/exit", "/quit"}:
            return 0
        if not prompt:
            continue

        try:
            answer = ollama_response(
                prompt, model=model, host=host, history=history
            )
        except OllamaError as exc:
            print(f"Jarvis error: {exc}", file=sys.stderr)
            continue

        print(f"Jarvis: {answer}")
        if voice:
            try:
                speaker.say(answer)
                speaker.runAndWait()
            except RuntimeError as exc:
                print(f"Jarvis voice error: {exc}", file=sys.stderr)
        history.extend(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ]
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chat with a local Ollama-powered personal assistant."
    )
    parser.add_argument("prompt", nargs="*", help="Prompt to send")
    parser.add_argument(
        "--json", action="store_true", help="Print the prompt and response as JSON"
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
        help=f"Ollama model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("OLLAMA_HOST", DEFAULT_HOST),
        help=f"Ollama server URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Use offline push-to-talk input and spoken replies",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.voice and args.prompt:
        parser.error(
            "--voice starts an interactive microphone session; do not pass a prompt"
        )
    if args.voice:
        try:
            return interactive_chat(model=args.model, host=args.host, voice=True)
        except VoiceError as exc:
            print(f"Jarvis voice error: {exc}", file=sys.stderr)
            return 1
    if args.prompt:
        prompt = normalize_prompt(" ".join(args.prompt))
    elif sys.stdin.isatty():
        if args.json:
            parser.error("--json requires a prompt or piped input")
        return interactive_chat(model=args.model, host=args.host)
    else:
        prompt = normalize_prompt(sys.stdin.read())

    if not prompt:
        parser.error("provide a prompt or pipe text through stdin")

    try:
        print(
            chat(
                prompt,
                output_json=args.json,
                model=args.model,
                host=args.host,
            )
        )
    except OllamaError as exc:
        print(f"Jarvis error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
