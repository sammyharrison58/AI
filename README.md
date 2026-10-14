# Jarvis local AI assistant

Jarvis is a local personal assistant powered by [Ollama](https://ollama.com/).
Text chat needs no Python packages or paid API key. Optional offline voice
commands use Vosk for speech recognition and the Windows speech engine for
spoken replies. Prompts, audio transcription, and model replies stay on your
computer.

## Windows setup

Install Ollama and its model storage under `F:\Ollama`. Ollama needs internet
access for the initial software and model downloads. Run these commands in
PowerShell from the project folder:

```powershell
$env:OLLAMA_INSTALL_DIR = 'F:\Ollama\app'
$env:OLLAMA_MODELS = 'F:\Ollama\models'
[Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $env:OLLAMA_MODELS, 'User')
irm https://ollama.com/install.ps1 | iex
Start-Process -FilePath 'F:\Ollama\app\ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden
ollama pull llama3.2
```

If using the virtual environment in this repository, install the optional voice
dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Download and unpack the small English Vosk speech model onto F:, then configure
its path for the current PowerShell session:

```powershell
New-Item -ItemType Directory -Force F:\Ollama\speech | Out-Null
Invoke-WebRequest `
  -Uri https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip `
  -OutFile F:\Ollama\vosk-model.zip
Expand-Archive F:\Ollama\vosk-model.zip -DestinationPath F:\Ollama\speech -Force
$env:VOSK_MODEL_PATH = 'F:\Ollama\speech\vosk-model-small-en-us-0.15'
[Environment]::SetEnvironmentVariable('VOSK_MODEL_PATH', $env:VOSK_MODEL_PATH, 'User')
Remove-Item F:\Ollama\vosk-model.zip
```

Start text chat:

```powershell
.\.venv\Scripts\python.exe ai.py
```

Start push-to-talk voice chat:

```powershell
.\.venv\Scripts\python.exe ai.py --voice
```

Press Enter to record up to seven seconds, then Jarvis transcribes locally and
speaks the answer. Type `/exit` to quit. Single-prompt text chat is also
available:

```powershell
.\.venv\Scripts\python.exe ai.py "Help me plan my week"
```

For JSON output, add `--json` to a one-shot prompt. To use another model that
you have already pulled, pass `--model model-name`. The Ollama server URL can
be changed with `--host URL` or the `OLLAMA_HOST` environment variable.

Ollama runs a local server on `http://localhost:11434`. Start the server before
using Jarvis if it is not already running:

```powershell
Start-Process -FilePath 'F:\Ollama\app\ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden
```

If the server or model is unavailable, Jarvis prints an actionable error
rather than substituting a canned answer.

## Tests

Run the tests from the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
