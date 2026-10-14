"""Python source for Jarvis's browser interface."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#090d18">
  <title>Jarvis | Personal AI</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #090d18;
      color: #eef3ff;
      font-synthesis: none;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(ellipse at 50% 16%, #18264a 0, transparent 42%),
        #090d18;
    }
    button, textarea { font: inherit; }
    .app { display: flex; min-height: 100vh; flex-direction: column; }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 22px clamp(20px, 5vw, 72px);
      border-bottom: 1px solid #ffffff12;
    }
    .brand { display: flex; align-items: center; gap: 12px; font-size: 15px; font-weight: 650; letter-spacing: .12em; }
    .brand-mark {
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      border: 1px solid #65d7ff77;
      border-radius: 50%;
      color: #7ee3ff;
      box-shadow: 0 0 22px #41caff22;
    }
    .online { color: #9baac6; font-size: 12px; }
    .online::before { display: inline-block; width: 7px; height: 7px; margin-right: 8px; border-radius: 50%; background: #64e6bd; content: ""; }
    main { display: flex; width: min(100% - 32px, 820px); flex: 1; flex-direction: column; align-items: center; margin: 0 auto; }
    .hero { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; min-height: 310px; padding: 34px 0 20px; text-align: center; }
    .orb {
      position: relative;
      display: grid;
      width: 126px;
      height: 126px;
      place-items: center;
      border: 1px solid #67ceff66;
      border-radius: 50%;
      background: radial-gradient(circle at 36% 30%, #4f8fc466, #182f5c 43%, #111a30 72%);
      box-shadow: 0 0 32px #36b9ff33, inset 0 0 30px #67d9ff22;
    }
    .orb::before, .orb::after { position: absolute; border: 1px solid #64d4ff35; border-radius: 50%; content: ""; }
    .orb::before { inset: -12px; }
    .orb::after { inset: -23px; border-color: #64d4ff20; }
    .orb.listening { animation: pulse 1.25s ease-in-out infinite alternate; }
    @keyframes pulse { to { box-shadow: 0 0 52px #36b9ff99, inset 0 0 35px #67d9ff55; transform: scale(1.045); } }
    .orb svg { width: 43px; color: #a7edff; }
    h1 { margin: 30px 0 8px; font-size: clamp(28px, 5vw, 38px); font-weight: 550; letter-spacing: -.035em; }
    .subtitle { margin: 0; color: #9aa8c2; font-size: 14px; }
    .conversation { display: flex; width: 100%; flex-direction: column; gap: 15px; padding: 4px 0 24px; }
    .message { max-width: min(88%, 650px); padding: 13px 16px; border: 1px solid #ffffff12; border-radius: 17px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
    .message.user { align-self: flex-end; border-color: #56caff35; background: #18304a; }
    .message.assistant { align-self: flex-start; background: #121a2a; }
    .message.action-card { width: min(100%, 650px); border-color: #69d7ff55; }
    .action-summary { margin: 0 0 10px; color: #dff7ff; }
    .action-preview { max-height: 180px; overflow: auto; margin: 0 0 12px; padding: 10px; border-radius: 9px; background: #080d18; white-space: pre-wrap; overflow-wrap: anywhere; }
    .action-buttons { display: flex; gap: 8px; }
    .action-buttons button { padding: 8px 12px; border: 1px solid #ffffff25; border-radius: 9px; background: #ffffff0d; color: #eef3ff; cursor: pointer; }
    .action-buttons button:first-child { border-color: #56caff66; background: #177aaa; }
    .action-buttons button:disabled { cursor: wait; opacity: .55; }
    .message.error { align-self: center; border-color: #ff718055; color: #ffb5bc; font-size: 13px; }
    .composer { width: 100%; padding: 0 0 28px; }
    .input-wrap { display: flex; align-items: flex-end; gap: 10px; padding: 10px; border: 1px solid #ffffff20; border-radius: 21px; background: #111827e8; box-shadow: 0 14px 45px #0005; }
    textarea { width: 100%; min-height: 46px; max-height: 150px; resize: vertical; padding: 13px 10px; border: 0; outline: 0; background: transparent; color: #eef3ff; line-height: 1.4; }
    textarea::placeholder { color: #77839b; }
    .icon-button { display: grid; width: 46px; height: 46px; flex: 0 0 auto; place-items: center; border: 1px solid #ffffff1c; border-radius: 15px; background: #ffffff08; color: #b9c9e5; cursor: pointer; transition: .18s ease; }
    .icon-button:hover { border-color: #5ecfff80; background: #2f9bc526; color: #a6edff; }
    .icon-button:disabled { cursor: wait; opacity: .48; }
    .icon-button svg { width: 20px; height: 20px; }
    #mic.call-active { border-color: #ff718088; background: #c8364528; color: #ff9ba4; }
    #send { border-color: #4abef755; background: #177aaa; color: white; }
    #send:hover { background: #2197c9; }
    .footnote { margin: 12px 0 0; color: #71809b; font-size: 11px; text-align: center; }
    .status { min-height: 18px; margin: 11px 4px 0; color: #8bdcf5; font-size: 12px; text-align: center; }
    @media (max-height: 700px) { .hero { min-height: 250px; } .orb { width: 96px; height: 96px; } h1 { margin-top: 24px; } }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand"><span class="brand-mark" aria-hidden="true">J</span><span>JARVIS</span></div>
      <div class="online">Local assistant</div>
    </header>
    <main>
      <section class="hero" aria-label="Jarvis assistant">
        <div class="orb" id="orb" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3">
            <path d="M12 3v18M3 12h18M5.64 5.64l12.72 12.72m0-12.72L5.64 18.36" />
            <circle cx="12" cy="12" r="5.2" />
          </svg>
        </div>
        <h1>Good to see you.</h1>
        <p class="subtitle">I’m listening. What can I help you with?</p>
      </section>
      <section class="conversation" id="conversation" aria-live="polite" aria-label="Conversation"></section>
      <form class="composer" id="composer">
        <div class="input-wrap">
          <textarea id="prompt" rows="1" aria-label="Message Jarvis" placeholder="Ask Jarvis anything…"></textarea>
          <button class="icon-button" id="mic" type="button" aria-label="Speak to Jarvis" title="Speak to Jarvis">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="2.5" width="6" height="12" rx="3" /><path d="M5 11.5a7 7 0 0 0 14 0M12 18.5v3m-4 0h8" />
            </svg>
          </button>
          <button class="icon-button" id="send" type="submit" aria-label="Send message" title="Send message">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m21 3-7.2 18-3.9-7.9L2 9.2 21 3Z" /><path d="M21 3 9.9 13.1" />
            </svg>
          </button>
        </div>
        <div class="status" id="status" role="status">Type a message or start a voice call.</div>
        <p class="footnote">Voice replies speak while text streams. Can open approved apps, folders and URLs, manage text files in Documents\Jarvis, and adjust volume or brightness. Every action needs approval; shell, admin, delete, install and shutdown actions are blocked.</p>
      </form>
    </main>
  </div>
  <script>
    const form = document.querySelector("#composer");
    const input = document.querySelector("#prompt");
    const conversationEl = document.querySelector("#conversation");
    const statusEl = document.querySelector("#status");
    const micButton = document.querySelector("#mic");
    const sendButton = document.querySelector("#send");
    const orb = document.querySelector("#orb");
    const history = [];
    let busy = false;
    let callActive = false;
    let audioStream;
    let audioContext;
    let audioSource;
    let audioProcessor;
    let muteGain;
    let preRollChunks = [];
    let utteranceChunks = [];
    let utteranceActive = false;
    let lastVoiceAt = 0;
    let utteranceStartedAt = 0;
    let noiseLevel = 0;
    let callStartedAt = 0;
    let resumeListeningAt = 0;
    let activeChatController;
    let speechQueue = Promise.resolve();
    let pendingSpeech = "";
    let pendingActionResolver;

    const silenceDuration = 650;
    const maxUtteranceDuration = 15000;
    const callWarmupDuration = 500;
    const maxPreRollSamples = 9600;

    function addMessage(role, text, extraClass = "") {
      const message = document.createElement("div");
      message.className = `message ${role} ${extraClass}`.trim();
      message.textContent = text;
      conversationEl.append(message);
      message.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return message;
    }

    function setBusy(value) {
      busy = value;
      input.disabled = value;
      sendButton.disabled = value;
      micButton.disabled = value && !callActive;
      orb.classList.toggle("listening", callActive && !busy);
    }

    function queueSpeech(text) {
      if (!text.trim()) return;
      speechQueue = speechQueue.then(() => new Promise((resolve) => {
        if (!callActive || !("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
          resolve();
          return;
        }
        const utterance = new SpeechSynthesisUtterance(text.trim());
        utterance.rate = 0.96;
        const voices = window.speechSynthesis.getVoices();
        utterance.voice = voices.find((voice) => /^en[-_]/i.test(voice.lang) && /natural|neural|online/i.test(voice.name))
          || voices.find((voice) => /^en[-_]/i.test(voice.lang))
          || null;
        utterance.onend = resolve;
        utterance.onerror = resolve;
        window.speechSynthesis.speak(utterance);
      }));
    }

    function queueCompletedSentences(final = false) {
      const complete = /[.!?](?:["')\]]*)\s+/;
      let match;
      while ((match = complete.exec(pendingSpeech))) {
        const end = match.index + match[0].length;
        queueSpeech(pendingSpeech.slice(0, end));
        pendingSpeech = pendingSpeech.slice(end);
      }
      if (final && pendingSpeech.trim()) {
        queueSpeech(pendingSpeech);
        pendingSpeech = "";
      }
    }

    function requestActionApproval(action, summary, bubble) {
      return new Promise((resolve) => {
        bubble.classList.add("action-card");
        const description = document.createElement("p");
        description.className = "action-summary";
        description.textContent = `Approval required: ${summary}`;
        bubble.append(description);
        if (action.kind === "write_file") {
          const preview = document.createElement("pre");
          preview.className = "action-preview";
          preview.textContent = action.content || "(empty file)";
          bubble.append(preview);
        }
        const buttons = document.createElement("div");
        buttons.className = "action-buttons";
        const approve = document.createElement("button");
        approve.type = "button";
        approve.textContent = "Approve action";
        const reject = document.createElement("button");
        reject.type = "button";
        reject.textContent = "Cancel";
        let settled = false;
        const finish = (approved) => {
          if (settled) return;
          settled = true;
          approve.disabled = true;
          reject.disabled = true;
          pendingActionResolver = undefined;
          const outcome = document.createElement("p");
          outcome.textContent = approved ? "Approved. Applying…" : "Cancelled; nothing was changed.";
          bubble.append(outcome);
          resolve(approved);
        };
        approve.addEventListener("click", () => finish(true));
        reject.addEventListener("click", () => finish(false));
        buttons.append(approve, reject);
        bubble.append(buttons);
        pendingActionResolver = () => finish(false);
      });
    }

    async function requestJson(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
      return result;
    }

    async function sendMessage(text, voiceMode = false, alreadyBusy = false) {
      const prompt = text.trim();
      if (!prompt || (busy && !alreadyBusy)) return;
      addMessage("user", prompt);
      input.value = "";
      setBusy(true);
      statusEl.textContent = voiceMode ? "Jarvis is listening…" : "Jarvis is responding…";
      const answerBubble = addMessage("assistant", "");
      let answer = "";
      const controller = new AbortController();
      if (voiceMode) activeChatController = controller;
      try {
        const prepared = await requestJson("/api/action/prepare", { prompt });
        if (prepared.action) {
          statusEl.textContent = "Waiting for your approval…";
          const approved = await requestActionApproval(prepared.action, prepared.summary, answerBubble);
          if (!approved) {
            statusEl.textContent = "Action cancelled; nothing was changed.";
            return;
          }
          const result = await requestJson("/api/action/execute", { action: prepared.action });
          answerBubble.textContent = result.message;
          history.push({ role: "user", content: prompt }, { role: "assistant", content: result.message });
          if (voiceMode) {
            queueSpeech(result.message);
            await speechQueue;
          }
          statusEl.textContent = "Action complete.";
          return;
        }
        const response = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, history, voice_mode: voiceMode }),
          signal: controller.signal
        });
        if (!response.ok || !response.body) {
          const data = await response.json();
          throw new Error(data.error || `Request failed (${response.status}).`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffered = "";
        let finished = false;
        while (!finished) {
          const { value, done } = await reader.read();
          buffered += decoder.decode(value, { stream: !done });
          let boundary = buffered.indexOf("\n\n");
          while (boundary !== -1) {
            const event = buffered.slice(0, boundary);
            buffered = buffered.slice(boundary + 2);
            const dataLine = event.split("\n").find((line) => line.startsWith("data:"));
            if (dataLine) {
              const data = JSON.parse(dataLine.slice(5).trim());
              if (data.error) throw new Error(data.error);
              if (typeof data.token === "string") {
                answer += data.token;
                answerBubble.textContent = answer;
                answerBubble.scrollIntoView({ behavior: "smooth", block: "nearest" });
                if (voiceMode) {
                  pendingSpeech += data.token;
                  queueCompletedSentences();
                  if (pendingSpeech.trim()) statusEl.textContent = "Jarvis is speaking…";
                }
              }
              if (data.done) finished = true;
            }
            boundary = buffered.indexOf("\n\n");
          }
          if (done) break;
        }
        if (!answer) throw new Error("Jarvis returned an empty response.");
        history.push({ role: "user", content: prompt }, { role: "assistant", content: answer });
        if (voiceMode) {
          queueCompletedSentences(true);
          await speechQueue;
          resumeListeningAt = performance.now() + silenceDuration;
        }
        statusEl.textContent = callActive ? "Call active · listening for you…" : "Ready when you are.";
      } catch (error) {
        if (error.name !== "AbortError") {
          answerBubble.classList.add("error");
          answerBubble.textContent = error instanceof Error ? error.message : String(error);
          statusEl.textContent = error instanceof Error ? error.message : String(error);
        }
      } finally {
        if (activeChatController === controller) activeChatController = undefined;
        pendingSpeech = "";
        setBusy(false);
        if (!callActive) input.focus();
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage(input.value);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    async function transcribeAudio(pcm) {
      try {
        statusEl.textContent = "I heard you · transcribing…";
        const response = await fetch("/api/transcribe", {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream", "X-Audio-Sample-Rate": "16000" },
          body: pcm
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Transcription failed (${response.status}).`);
        if (!callActive) return;
        if (!result.text) {
          setBusy(false);
          statusEl.textContent = callActive ? "Call active · listening for you…" : "I didn’t catch that.";
          return;
        }
        setBusy(false);
        await sendMessage(result.text, true);
      } catch (error) {
        setBusy(false);
        if (callActive) {
          statusEl.textContent = error instanceof Error ? error.message : String(error);
        }
      } finally {
        if (!busy) micButton.disabled = false;
      }
    }

    async function finishUtterance() {
      if (!utteranceActive || busy) return;
      utteranceActive = false;
      const chunks = utteranceChunks;
      utteranceChunks = [];
      const context = audioContext;
      try {
        const totalSamples = chunks.reduce((total, chunk) => total + chunk.length, 0);
        if (!totalSamples || !context) return;
        const samples = new Float32Array(totalSamples);
        let offset = 0;
        for (const chunk of chunks) {
          samples.set(chunk, offset);
          offset += chunk.length;
        }
        let mean = 0;
        let peak = 0;
        for (const sample of samples) mean += sample;
        mean /= samples.length;
        for (const sample of samples) peak = Math.max(peak, Math.abs(sample - mean));
        const gain = peak > 0.01 ? Math.min(4, 0.7 / peak) : 1;
        const ratio = context.sampleRate / 16000;
        const sampleCount = Math.floor(samples.length / ratio);
        if (!sampleCount) throw new Error("The recording was too short. Please try again.");
        const pcm = new Int16Array(sampleCount);
        for (let i = 0; i < sampleCount; i++) {
          const sourceIndex = i * ratio;
          const low = Math.floor(sourceIndex);
          const fraction = sourceIndex - low;
          const sample = samples[low] * (1 - fraction) + samples[Math.min(low + 1, samples.length - 1)] * fraction;
          const normalized = (sample - mean) * gain;
          pcm[i] = Math.max(-1, Math.min(1, normalized)) * 32767;
        }
        setBusy(true);
        await transcribeAudio(pcm);
      } catch (error) {
        setBusy(false);
        statusEl.textContent = error instanceof Error ? error.message : String(error);
      }
    }

    async function startCall() {
      if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === "undefined") {
        statusEl.textContent = "This browser cannot capture microphone audio. Try a recent version of Chrome or Edge.";
        return;
      }
      try {
        micButton.disabled = true;
        statusEl.textContent = "Allow microphone access to start recording…";
        audioStream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
        });
        audioContext = new AudioContext();
        if (audioContext.state === "suspended") await audioContext.resume();
        audioSource = audioContext.createMediaStreamSource(audioStream);
        audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        muteGain = audioContext.createGain();
        muteGain.gain.value = 0;
        audioProcessor.onaudioprocess = (event) => {
          if (!callActive || busy) return;
          if (performance.now() < resumeListeningAt) {
            preRollChunks = [];
            return;
          }
          const frame = event.inputBuffer.getChannelData(0).slice();
          let energy = 0;
          for (let i = 0; i < frame.length; i++) energy += frame[i] * frame[i];
          const level = Math.sqrt(energy / frame.length);
          if (!utteranceActive) {
            preRollChunks.push(frame);
            let preRollSamples = preRollChunks.reduce((total, chunk) => total + chunk.length, 0);
            while (preRollSamples > maxPreRollSamples && preRollChunks.length) {
              preRollSamples -= preRollChunks.shift().length;
            }
            if (performance.now() - callStartedAt < callWarmupDuration) {
              noiseLevel = noiseLevel * 0.8 + level * 0.2;
              return;
            }
            const speechThreshold = Math.max(0.012, noiseLevel * 2.2);
            if (level >= speechThreshold) {
              utteranceActive = true;
              utteranceChunks = [...preRollChunks];
              preRollChunks = [];
              lastVoiceAt = performance.now();
              utteranceStartedAt = lastVoiceAt;
              statusEl.textContent = "I hear you…";
            } else {
              noiseLevel = noiseLevel * 0.95 + level * 0.05;
            }
            return;
          }

          utteranceChunks.push(frame);
          const silenceThreshold = Math.max(0.008, noiseLevel * 1.5);
          if (level >= silenceThreshold) {
            lastVoiceAt = performance.now();
          } else if (
            performance.now() - lastVoiceAt >= silenceDuration
            || performance.now() - utteranceStartedAt >= maxUtteranceDuration
          ) {
            void finishUtterance();
          }
        };
        audioSource.connect(audioProcessor);
        audioProcessor.connect(muteGain);
        muteGain.connect(audioContext.destination);
        preRollChunks = [];
        utteranceChunks = [];
        utteranceActive = false;
        noiseLevel = 0;
        callStartedAt = performance.now();
        resumeListeningAt = 0;
        callActive = true;
        micButton.disabled = false;
        micButton.classList.add("call-active");
        micButton.setAttribute("aria-label", "End voice call");
        micButton.title = "End voice call";
        orb.classList.add("listening");
        statusEl.textContent = "Call active · listening for you…";
      } catch (error) {
        audioStream?.getTracks().forEach((track) => track.stop());
        audioStream = undefined;
        if (audioContext && audioContext.state !== "closed") await audioContext.close();
        audioContext = undefined;
        micButton.disabled = false;
        const message = error instanceof Error ? error.message : String(error);
        statusEl.textContent = error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone access was denied. Allow microphone access for this page in your browser settings."
          : error instanceof DOMException && error.name === "NotFoundError"
            ? "No microphone was found. Connect or enable a microphone and try again."
            : `Could not start microphone recording: ${message}`;
        orb.classList.remove("listening");
        micButton.classList.remove("call-active");
        micButton.setAttribute("aria-label", "Speak to Jarvis");
        micButton.title = "Speak to Jarvis";
      }
    }

    async function endCall() {
      callActive = false;
      pendingActionResolver?.();
      utteranceActive = false;
      preRollChunks = [];
      utteranceChunks = [];
      activeChatController?.abort();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      audioProcessor?.disconnect();
      audioSource?.disconnect();
      muteGain?.disconnect();
      audioStream?.getTracks().forEach((track) => track.stop());
      audioStream = undefined;
      audioProcessor = undefined;
      audioSource = undefined;
      muteGain = undefined;
      const context = audioContext;
      audioContext = undefined;
      if (context && context.state !== "closed") await context.close();
      micButton.classList.remove("call-active");
      micButton.setAttribute("aria-label", "Start voice call");
      micButton.title = "Start voice call";
      orb.classList.remove("listening");
      statusEl.textContent = "Call ended · type a message or start another call.";
    }

    micButton.addEventListener("click", () => {
      if (callActive) {
        void endCall();
      } else if (!busy) {
        void startCall();
      }
    });
  </script>
</body>
</html>
"""