#!/usr/bin/env python3
"""A command-line personal assistant powered by a local Ollama model."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import webbrowser

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


def resolve_vosk_model_path() -> Path:
    configured_path = os.getenv("VOSK_MODEL_PATH")
    if configured_path:
        return Path(configured_path)
    if F_DRIVE_VOSK_MODEL.is_dir():
        return F_DRIVE_VOSK_MODEL
    return DEFAULT_VOSK_MODEL


def setup_voice() -> tuple[AudioInput, SpeechRecognizer, SpeechSpeaker]:
    """Load offline speech recognition and speech synthesis components."""
    model_path = resolve_vosk_model_path()

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


def ollama_response_chunks(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    history: list[dict[str, str]] | None = None,
    timeout: float = 120.0,
) -> Iterable[str]:
    """Yield assistant text as Ollama generates it."""
    parsed_host = urlsplit(host)
    if parsed_host.scheme not in {"http", "https"} or not parsed_host.netloc:
        raise OllamaError(f"Invalid Ollama server URL: {host}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": True}
    ).encode("utf-8")
    request = Request(
        f"{host.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            received_text = False
            for line in response:
                if not line.strip():
                    continue
                try:
                    result = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise OllamaError(
                        "Ollama returned an invalid streaming response."
                    ) from exc
                if not isinstance(result, dict):
                    raise OllamaError(
                        "Ollama returned an invalid streaming response."
                    )
                error = result.get("error")
                if isinstance(error, str):
                    raise OllamaError(f"Ollama error: {error}")
                message = result.get("message")
                content = (
                    message.get("content") if isinstance(message, dict) else None
                )
                if isinstance(content, str) and content:
                    received_text = True
                    yield content
                if result.get("done") is True:
                    break
            if not received_text:
                raise OllamaError("Ollama returned no assistant message.")
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


def serve_web_app(*, model: str, host: str, port: int) -> int:
    """Serve the dependency-free browser chat interface."""
    page_path = Path(__file__).with_name("web.html")
    page = page_path.read_bytes()
    voice_model: Any | None = None
    voice_model_lock = threading.Lock()

    class JarvisRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict[str, str]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_chat_request(
            self,
        ) -> tuple[str, list[dict[str, str]]] | None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid request length."})
                return None
            if content_length <= 0 or content_length > 1_000_000:
                self._send_json(400, {"error": "Invalid request size."})
                return None

            try:
                request_data = json.loads(self.rfile.read(content_length))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "Request body must be valid JSON."})
                return None
            if not isinstance(request_data, dict):
                self._send_json(400, {"error": "Request body must be an object."})
                return None

            prompt = request_data.get("prompt")
            history = request_data.get("history", [])
            if not isinstance(prompt, str) or not normalize_prompt(prompt):
                self._send_json(400, {"error": "Enter a message for Jarvis."})
                return None
            if not isinstance(history, list) or any(
                not isinstance(message, dict)
                or message.get("role") not in {"user", "assistant"}
                or not isinstance(message.get("content"), str)
                for message in history
            ):
                self._send_json(400, {"error": "Conversation history is invalid."})
                return None
            return normalize_prompt(prompt), history

        def _get_voice_model(self) -> Any:
            nonlocal voice_model
            if voice_model is not None:
                return voice_model

            model_path = resolve_vosk_model_path()
            if not model_path.is_dir():
                raise VoiceError(
                    f"Offline speech model not found at {model_path}. "
                    "See the voice setup instructions in README.md."
                )
            try:
                from vosk import Model
            except ImportError as exc:
                raise VoiceError(
                    "Voice recognition is unavailable. Install the optional "
                    "voice dependencies with `python -m pip install -r "
                    "requirements.txt`."
                ) from exc

            with voice_model_lock:
                if voice_model is None:
                    try:
                        voice_model = Model(str(model_path))
                    except (OSError, RuntimeError) as exc:
                        raise VoiceError(
                            f"Could not initialize voice recognition: {exc}"
                        ) from exc
            return voice_model

        def do_GET(self) -> None:
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self) -> None:
            if self.path == "/api/transcribe":
                self._transcribe_audio()
                return
            if self.path not in {"/api/chat", "/api/chat/stream"}:
                self.send_error(404)
                return
            chat_request = self._read_chat_request()
            if chat_request is None:
                return
            prompt, history = chat_request

            if self.path == "/api/chat/stream":
                self._stream_chat_response(prompt, history)
                return

            try:
                answer = ollama_response(
                    prompt,
                    model=model,
                    host=host,
                    history=history,
                )
            except OllamaError as exc:
                self._send_json(502, {"error": str(exc)})
                return
            self._send_json(200, {"response": answer})

        def _stream_chat_response(
            self, prompt: str, history: list[dict[str, str]]
        ) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for chunk in ollama_response_chunks(
                    prompt, model=model, host=host, history=history
                ):
                    event = json.dumps({"token": chunk}, ensure_ascii=False)
                    self.wfile.write(f"data: {event}\n\n".encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b'data: {"done":true}\n\n')
                self.wfile.flush()
            except OllamaError as exc:
                event = json.dumps({"error": str(exc)}, ensure_ascii=False)
                self.wfile.write(f"data: {event}\n\n".encode("utf-8"))
                self.wfile.flush()
            self.close_connection = True

        def _transcribe_audio(self) -> None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                sample_rate = int(self.headers.get("X-Audio-Sample-Rate", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid audio metadata."})
                return
            if content_length <= 0 or content_length > 15_000_000:
                self._send_json(400, {"error": "Audio recording size is invalid."})
                return
            if sample_rate != VOICE_SAMPLE_RATE or content_length % 2:
                self._send_json(
                    400,
                    {"error": f"Audio must be mono 16-bit PCM at {VOICE_SAMPLE_RATE} Hz."},
                )
                return
            audio = self.rfile.read(content_length)
            if len(audio) != content_length:
                self._send_json(400, {"error": "Audio recording was incomplete."})
                return

            try:
                speech_model = self._get_voice_model()
                from vosk import KaldiRecognizer

                recognizer = KaldiRecognizer(speech_model, VOICE_SAMPLE_RATE)
                recognizer.AcceptWaveform(audio)
                result = json.loads(recognizer.FinalResult())
            except VoiceError as exc:
                self._send_json(503, {"error": str(exc)})
                return
            except (ImportError, OSError, RuntimeError, json.JSONDecodeError) as exc:
                self._send_json(
                    500, {"error": f"Could not transcribe microphone audio: {exc}"}
                )
                return

            if not isinstance(result, dict) or not isinstance(
                result.get("text"), str
            ):
                self._send_json(500, {"error": "Speech recognition returned an invalid result."})
                return
            self._send_json(200, {"text": normalize_prompt(result["text"])})

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), JarvisRequestHandler)
    except OSError as exc:
        print(f"Could not start Jarvis web server: {exc}", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{port}"
    print(f"Jarvis is ready using {model}. Open {url} in your browser.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJarvis web server stopped.")
    finally:
        server.server_close()
    return 0


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
    parser.add_argument(
        "--web",
        action="store_true",
        help="Open the interactive browser chat interface",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local web interface port (default: 8765)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.web and (args.prompt or args.voice or args.json):
        parser.error("--web cannot be combined with a prompt, --voice, or --json")
    if args.web:
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        return serve_web_app(model=args.model, host=args.host, port=args.port)
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
