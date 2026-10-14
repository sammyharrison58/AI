import io
import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from types import ModuleType
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import ai


def make_sounddevice_stub() -> tuple[ModuleType, type[Exception]]:
    module = ModuleType("sounddevice")
    port_audio_error = type("PortAudioError", (Exception,), {})
    setattr(module, "PortAudioError", port_audio_error)
    return module, port_audio_error


class OllamaResponseTests(unittest.TestCase):
    @patch("ai.urlopen")
    def test_sends_prompt_and_returns_model_reply(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"message": {"role": "assistant", "content": "Hello from the model"}}
        ).encode()
        mock_urlopen.return_value = response

        result = ai.ollama_response(
            "hello",
            model="test-model",
            host="http://localhost:11434/",
            history=[{"role": "user", "content": "previous turn"}],
        )

        self.assertEqual(result, "Hello from the model")
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][-2]["content"], "previous turn")
        self.assertEqual(payload["messages"][-1]["content"], "hello")

    @patch("ai.urlopen")
    def test_streaming_response_yields_generated_chunks(
        self, mock_urlopen: MagicMock
    ) -> None:
        response = MagicMock()
        response.__enter__.return_value.__iter__.return_value = iter(
            [
                b'{"message":{"content":"Hello "},"done":false}\n',
                b'{"message":{"content":"there"},"done":false}\n',
                b'{"message":{"content":""},"done":true}\n',
            ]
        )
        mock_urlopen.return_value = response

        result = list(
            ai.ollama_response_chunks(
                "hello", model="test-model", history=[]
            )
        )

        self.assertEqual(result, ["Hello ", "there"])
        payload = json.loads(mock_urlopen.call_args.args[0].data)
        self.assertTrue(payload["stream"])

    @patch("ai.urlopen", side_effect=URLError("connection refused"))
    def test_connection_failure_is_reported(self, mock_urlopen: MagicMock) -> None:
        with self.assertRaisesRegex(ai.OllamaError, "Could not reach Ollama"):
            ai.ollama_response("hello")
        mock_urlopen.assert_called_once()

    @patch("ai.urlopen")
    def test_empty_model_reply_is_rejected(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"message": {"content": ""}}'
        )
        mock_urlopen.return_value = response

        with self.assertRaisesRegex(ai.OllamaError, "no assistant message"):
            ai.ollama_response("hello")


class CommandLineTests(unittest.TestCase):
    @patch("ai.ollama_response", return_value="42")
    def test_json_output(self, mock_response: MagicMock) -> None:
        output = io.StringIO()
        with patch("sys.stdout", output):
            result = ai.main(["--json", "what", "is", "the", "answer"])

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"prompt": "what is the answer", "response": "42"},
        )
        mock_response.assert_called_once_with(
            "what is the answer", model=ai.DEFAULT_MODEL, host=ai.DEFAULT_HOST
        )

    def test_normalizes_prompt(self) -> None:
        self.assertEqual(ai.normalize_prompt("  hello \n   there  "), "hello there")

    @patch("ai.serve_web_app", return_value=0)
    def test_web_flag_starts_browser_interface(self, mock_web: MagicMock) -> None:
        result = ai.main(["--web", "--model", "llama3.2", "--port", "9000"])

        self.assertEqual(result, 0)
        mock_web.assert_called_once_with(
            model="llama3.2", host=ai.DEFAULT_HOST, port=9000
        )

    def test_web_flag_rejects_prompt(self) -> None:
        with self.assertRaises(SystemExit) as exit_info:
            ai.main(["--web", "hello"])

        self.assertEqual(exit_info.exception.code, 2)

    @patch("ai.interactive_chat", return_value=0)
    def test_voice_flag_starts_voice_chat(self, mock_interactive: MagicMock) -> None:
        result = ai.main(["--voice", "--model", "llama3.2"])

        self.assertEqual(result, 0)
        mock_interactive.assert_called_once_with(
            model="llama3.2", host=ai.DEFAULT_HOST, voice=True
        )


class WebInterfaceTests(unittest.TestCase):
    @patch(
        "ai.ollama_response_chunks",
        return_value=iter(["Hello ", "streaming"]),
    )
    @patch("ai.ollama_response", return_value="Hello from Jarvis")
    @patch("ai.webbrowser.open", return_value=True)
    def test_web_page_and_chat_endpoint(
        self,
        mock_browser: MagicMock,
        mock_response: MagicMock,
        mock_response_chunks: MagicMock,
    ) -> None:
        original_server = ThreadingHTTPServer
        servers: list[ThreadingHTTPServer] = []
        server_ready = threading.Event()

        def capture_server(
            address: tuple[str, int], handler: type
        ) -> ThreadingHTTPServer:
            server = original_server(address, handler)
            servers.append(server)
            server_ready.set()
            return server

        with patch("ai.ThreadingHTTPServer", side_effect=capture_server):
            worker = threading.Thread(
                target=ai.serve_web_app,
                kwargs={"model": "test-model", "host": ai.DEFAULT_HOST, "port": 0},
            )
            worker.start()
            try:
                self.assertTrue(server_ready.wait(timeout=5))
                server = servers[0]
                connection = HTTPConnection(*server.server_address, timeout=5)

                connection.request("GET", "/")
                page_response = connection.getresponse()
                self.assertEqual(page_response.status, 200)
                self.assertIn(b"JARVIS", page_response.read())

                connection.request("GET", "/favicon.ico")
                favicon_response = connection.getresponse()
                self.assertEqual(favicon_response.status, 204)
                self.assertEqual(favicon_response.read(), b"")

                request_body = json.dumps(
                    {"prompt": "hello", "history": []}
                )
                connection.request(
                    "POST",
                    "/api/chat",
                    body=request_body,
                    headers={"Content-Type": "application/json"},
                )
                chat_response = connection.getresponse()
                self.assertEqual(chat_response.status, 200)
                self.assertEqual(
                    json.loads(chat_response.read()),
                    {"response": "Hello from Jarvis"},
                )
                mock_response.assert_called_once_with(
                    "hello",
                    model="test-model",
                    host=ai.DEFAULT_HOST,
                    history=[],
                )

                connection.request(
                    "POST",
                    "/api/chat/stream",
                    body=request_body,
                    headers={"Content-Type": "application/json"},
                )
                stream_response = connection.getresponse()
                stream_data = stream_response.read()
                self.assertEqual(stream_response.status, 200)
                self.assertIn(b'"token": "Hello "', stream_data)
                self.assertIn(b'"token": "streaming"', stream_data)
                self.assertIn(b'"done":true', stream_data)
                mock_response_chunks.assert_called_once_with(
                    "hello",
                    model="test-model",
                    host=ai.DEFAULT_HOST,
                    history=[],
                )

                class FakeRecognizer:
                    def __init__(self, model: object, sample_rate: int) -> None:
                        assert model is not None
                        assert sample_rate == ai.VOICE_SAMPLE_RATE

                    def AcceptWaveform(self, audio: bytes) -> bool:
                        assert audio
                        return True

                    def FinalResult(self) -> str:
                        return json.dumps({"text": "recognized words"})

                vosk_stub = ModuleType("vosk")
                setattr(vosk_stub, "Model", lambda path: path)
                setattr(vosk_stub, "KaldiRecognizer", FakeRecognizer)
                with (
                    tempfile.TemporaryDirectory() as model_directory,
                    patch.dict(os.environ, {"VOSK_MODEL_PATH": model_directory}),
                    patch.dict("sys.modules", {"vosk": vosk_stub}),
                ):
                    audio = b"\x00\x00" * 1600
                    connection.request(
                        "POST",
                        "/api/transcribe",
                        body=audio,
                        headers={
                            "Content-Type": "application/octet-stream",
                            "X-Audio-Sample-Rate": "16000",
                        },
                    )
                    transcription_response = connection.getresponse()
                    self.assertEqual(transcription_response.status, 200)
                    self.assertEqual(
                        json.loads(transcription_response.read()),
                        {"text": "recognized words"},
                    )
                connection.close()
            finally:
                if servers:
                    servers[0].shutdown()
                    servers[0].server_close()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                mock_browser.assert_called_once()


class VoiceTests(unittest.TestCase):
    def test_capture_voice_prompt_uses_local_recognizer(self) -> None:
        recording = MagicMock()
        recording.tobytes.return_value = b"audio data"
        sounddevice_stub = MagicMock()
        sounddevice_stub.rec.return_value = recording
        recognizer = MagicMock()
        recognizer.FinalResult.return_value = json.dumps(
            {"text": "  turn on the lights  "}
        )
        audio_module, _ = make_sounddevice_stub()
        sounddevice_stub = MagicMock()
        sounddevice_stub.rec.return_value = recording

        with patch.dict("sys.modules", {"sounddevice": audio_module}):
            result = ai.capture_voice_prompt(sounddevice_stub, recognizer)

        self.assertEqual(result, "turn on the lights")
        sounddevice_stub.rec.assert_called_once_with(
            ai.VOICE_RECORD_SECONDS * ai.VOICE_SAMPLE_RATE,
            samplerate=ai.VOICE_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sounddevice_stub.wait.assert_called_once_with()
        recognizer.AcceptWaveform.assert_called_once_with(b"audio data")
        recognizer.Reset.assert_called_once_with()

    def test_capture_reports_audio_device_errors(
        self,
    ) -> None:
        audio_module, port_audio_error = make_sounddevice_stub()
        sounddevice_stub = MagicMock()
        sounddevice_stub.rec.side_effect = port_audio_error("no input device")

        with (
            patch.dict("sys.modules", {"sounddevice": audio_module}),
            self.assertRaisesRegex(ai.VoiceError, "Could not record"),
        ):
            ai.capture_voice_prompt(sounddevice_stub, MagicMock())
        sounddevice_stub.rec.assert_called_once()

    def test_setup_voice_reports_missing_model_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_model = os.path.join(directory, "not-a-vosk-model")
            with patch.dict(os.environ, {"VOSK_MODEL_PATH": missing_model}):
                with self.assertRaisesRegex(
                    ai.VoiceError, "Offline speech model not found"
                ):
                    ai.setup_voice()

    @patch("ai.capture_voice_prompt", return_value="tell me a joke")
    @patch("ai.setup_voice")
    @patch("ai.ollama_response", return_value="Why did the chicken cross the road?")
    @patch("builtins.input", side_effect=["", "/exit"])
    def test_push_to_talk_transcribes_and_speaks_reply(
        self,
        _mock_input: MagicMock,
        mock_response: MagicMock,
        mock_setup: MagicMock,
        mock_capture: MagicMock,
    ) -> None:
        sounddevice, recognizer, speaker = MagicMock(), MagicMock(), MagicMock()
        mock_setup.return_value = (sounddevice, recognizer, speaker)

        result = ai.interactive_chat(
            model=ai.DEFAULT_MODEL, host=ai.DEFAULT_HOST, voice=True
        )

        self.assertEqual(result, 0)
        mock_capture.assert_called_once_with(sounddevice, recognizer)
        self.assertEqual(mock_response.call_count, 1)
        self.assertEqual(mock_response.call_args.args, ("tell me a joke",))
        self.assertEqual(
            mock_response.call_args.kwargs["model"], ai.DEFAULT_MODEL
        )
        self.assertEqual(
            mock_response.call_args.kwargs["host"], ai.DEFAULT_HOST
        )
        self.assertEqual(
            mock_response.call_args.kwargs["history"],
            [
                {"role": "user", "content": "tell me a joke"},
                {
                    "role": "assistant",
                    "content": "Why did the chicken cross the road?",
                },
            ],
        )
        speaker.say.assert_called_once_with("Why did the chicken cross the road?")
        speaker.runAndWait.assert_called_once()
        self.assertEqual(_mock_input.call_count, 2)


if __name__ == "__main__":
    unittest.main()
