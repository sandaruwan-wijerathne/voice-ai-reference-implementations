const integrationApps = [
  { id: "livekit", name: "Realtime LiveKit Nova2", url: "http://localhost:3002" },
  { id: "bedrock", name: "Realtime Bedrock Nova2", url: "http://localhost:3001" },
  { id: "pipecat", name: "Realtime Pipecat Nova2", url: "http://localhost:5173" },
  { id: "poc", name: "Voice AI POC", url: "http://localhost:5174" },
];

const traditionalApps = [
  { id: "agentStarterPython", name: "Traditional LiveKit Agent", url: "http://localhost:8090/hub/agent-starter-client.html" },
  { id: "pipecatQuickstart", name: "Traditional Pipecat Pipeline", url: "http://localhost:7861" },
];

function setStatus(badge, isUp) {
  badge.classList.remove("up", "down");
  if (isUp) {
    badge.classList.add("up");
    badge.textContent = "Reachable";
  } else {
    badge.classList.add("down");
    badge.textContent = "Unreachable";
  }
}

function getById(id, apps) {
  return apps.find((app) => app.id === id) || apps[0];
}

async function checkReachable(url) {
  try {
    const response = await fetch(url, { method: "GET", mode: "no-cors", cache: "no-store" });
    return !!response;
  } catch (_error) {
    return false;
  }
}

function initViewer(prefix, apps) {
  const select = document.getElementById(`${prefix}Select`);
  const status = document.getElementById(`${prefix}Status`);
  const reloadBtn = document.getElementById(`${prefix}ReloadBtn`);
  const openBtn = document.getElementById(`${prefix}OpenBtn`);
  const frame = document.getElementById(`${prefix}Frame`);

  for (const app of apps) {
    const option = document.createElement("option");
    option.value = app.id;
    option.textContent = app.name;
    select.appendChild(option);
  }

  async function refreshStatus() {
    const app = getById(select.value, apps);
    const isUp = await checkReachable(app.url);
    setStatus(status, isUp);
  }

  function loadSelected() {
    const app = getById(select.value, apps);
    frame.src = app.url;
    openBtn.href = app.url;
    refreshStatus();
  }

  select.addEventListener("change", loadSelected);
  reloadBtn.addEventListener("click", loadSelected);
  setInterval(refreshStatus, 5000);
  loadSelected();
}

initViewer("realtime", integrationApps);
initViewer("traditional", traditionalApps);
