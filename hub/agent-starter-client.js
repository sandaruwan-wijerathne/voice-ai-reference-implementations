(async () => {
  const statusEl = document.getElementById("status");
  const metaEl = document.getElementById("meta");
  const agentsEl = document.getElementById("agents");
  const errorEl = document.getElementById("error");
  const audioHost = document.getElementById("audioHost");
  const connectBtn = document.getElementById("connectBtn");
  const disconnectBtn = document.getElementById("disconnectBtn");
  const unlockBtn = document.getElementById("unlockBtn");
  const LK = window.LivekitClient;

  let config = null;
  let room = null;
  const audioElements = new Map();

  function setStatus(text) {
    statusEl.textContent = text;
  }

  function setError(text) {
    errorEl.textContent = text || "";
  }

  function renderAgentState() {
    if (!room) {
      agentsEl.textContent = "Agent: not connected";
      return;
    }
    const agents = Array.from(room.remoteParticipants.values()).filter((p) =>
      (p.identity || "").startsWith("agent-")
    );
    if (agents.length === 0) {
      agentsEl.textContent = "Agent: waiting for dispatch";
      return;
    }
    agentsEl.textContent = `Agent: connected (${agents.map((a) => a.identity).join(", ")})`;
  }

  function detachAllAudio() {
    for (const el of audioElements.values()) {
      try {
        el.remove();
      } catch (_e) {}
    }
    audioElements.clear();
  }

  function attachTrack(track, publication, participant) {
    if (track.kind !== "audio") return;
    const key = `${participant.sid}:${publication.trackSid}`;
    if (audioElements.has(key)) return;
    const el = track.attach();
    el.autoplay = true;
    el.controls = false;
    audioHost.appendChild(el);
    audioElements.set(key, el);
  }

  function detachTrack(track, publication, participant) {
    if (track.kind !== "audio") return;
    const key = `${participant.sid}:${publication.trackSid}`;
    const el = audioElements.get(key);
    if (el) {
      try {
        track.detach(el);
      } catch (_e) {}
      el.remove();
      audioElements.delete(key);
    }
  }

  async function loadConfig() {
    const res = await fetch("./agent-starter-config.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load config: ${res.status}`);
    return res.json();
  }

  async function connect() {
    if (!config) return;
    if (room) return;
    if (!LK) {
      setStatus("SDK not loaded");
      setError("LiveKit client SDK failed to load. Check internet access and reload.");
      return;
    }
    setError("");
    room = new LK.Room();
    setStatus("Connecting...");
    metaEl.textContent = `Room: ${config.room} | Identity: ${config.identity}`;

    room.on(LK.RoomEvent.TrackSubscribed, attachTrack);
    room.on(LK.RoomEvent.TrackUnsubscribed, detachTrack);
    room.on(LK.RoomEvent.ParticipantConnected, renderAgentState);
    room.on(LK.RoomEvent.ParticipantDisconnected, renderAgentState);
    room.on(LK.RoomEvent.Disconnected, () => {
      setStatus("Disconnected");
      renderAgentState();
      detachAllAudio();
      room = null;
    });

    try {
      await room.connect(config.serverUrl, config.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      await room.startAudio();
      setStatus("Connected (mic on)");
      renderAgentState();
    } catch (err) {
      setStatus("Connection failed");
      setError(String(err));
      try {
        room.disconnect();
      } catch (_e) {}
      room = null;
    }
  }

  function disconnect() {
    if (!room) return;
    room.disconnect();
    detachAllAudio();
    room = null;
    setStatus("Disconnected");
    renderAgentState();
  }

  async function unlockAudio() {
    if (!room) return;
    try {
      await room.startAudio();
      setStatus("Audio output enabled");
      setError("");
    } catch (err) {
      setError(`Audio unlock failed: ${String(err)}`);
    }
  }

  connectBtn.addEventListener("click", connect);
  disconnectBtn.addEventListener("click", disconnect);
  unlockBtn.addEventListener("click", unlockAudio);

  try {
    config = await loadConfig();
    setStatus(LK ? "Ready to connect" : "SDK not loaded");
    metaEl.textContent = `Server: ${config.serverUrl} | Room: ${config.room}`;
    if (!LK) {
      setError("LiveKit client SDK failed to load. Check internet access and reload.");
    }
  } catch (err) {
    setStatus("Failed to load config");
    setError(String(err));
  }
})();
