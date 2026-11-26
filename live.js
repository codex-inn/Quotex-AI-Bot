(() => {
  const base = (window.QUOTEX_API_BASE || "").replace(/\/$/, "");
  const source = document.createElement("div");
  source.className = "field";
  source.innerHTML = '<label>Market source</label><select id="marketSource"><option value="spot">Live spot Forex</option><option value="otc">Quotex OTC</option></select>';
  const cadence = document.createElement("div");
  cadence.className = "field";
  cadence.innerHTML = '<label>Target refresh</label><select id="liveCadence"><option value="1000">1 second (if feed permits)</option><option value="5000">5 seconds</option><option value="10000">10 seconds</option></select>';
  const controls = document.querySelector(".controls");
  controls.insertBefore(source, controls.firstChild);
  controls.insertBefore(cadence, controls.children[2]);
  const liveStatus = document.createElement("span");
  liveStatus.className = "pill";
  liveStatus.id = "liveStatus";
  liveStatus.textContent = "LIVE: NOT CONNECTED";
  document.querySelector("header .status").appendChild(liveStatus);

  let socket = null, lastTick = 0, lastPrice = null, cadenceTimer = null, activeSymbol = "";
  const status = (msg, color) => {
    liveStatus.textContent = msg;
    liveStatus.style.color = color || "#a9bdd5";
  };
  const market = () => document.getElementById("marketSource").value;
  const pair = () => document.getElementById("pair").value;
  const interval = () => ({ "1m": "1min", "5m": "5min", "15m": "15min" })[document.getElementById("tf").value] || "1min";

  function stop() {
    if (socket) { socket.onclose = null; socket.close(); socket = null; }
    if (cadenceTimer) { clearInterval(cadenceTimer); cadenceTimer = null; }
  }
  function setLiveNotice(message) {
    const box = document.querySelector(".notice");
    box.innerHTML = "<b>Live data:</b> " + message +
      " Analysis signals are rule-based indicators, not probabilities or guarantees. No trades are placed.";
  }
  function addTick(price, timestamp) {
    const value = Number(price);
    if (!Number.isFinite(value)) return;
    const date = new Date(Number(timestamp) > 1e12 ? Number(timestamp) : Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) return;
    const minute = new Date(date);
    minute.setSeconds(0, 0);
    const key = minute.toISOString().slice(0, 16);
    let current = candles[candles.length - 1];
    if (!current || String(current.datetime).slice(0, 16).replace(" ", "T") !== key) {
      candles.push({ datetime: minute.toISOString(), open: lastPrice ?? value, high: value, low: value, close: value });
      if (candles.length > 500) candles.shift();
    } else {
      current.high = Math.max(current.high, value);
      current.low = Math.min(current.low, value);
      current.close = value;
    }
    lastPrice = value;
    lastTick = Date.now();
    imported = true;
    analyze();
    document.getElementById("delta").textContent = "LIVE SPOT FX";
    document.getElementById("delta").style.color = "#2bd69b";
    status("LIVE · " + new Date().toLocaleTimeString(), "#2bd69b");
  }
  async function loadCandles(symbol) {
    const url = base + "/api/candles?symbol=" + encodeURIComponent(symbol) +
      "&interval=" + interval() + "&outputsize=160";
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load provider candles");
    candles = data.values;
    imported = true;
    lastPrice = candles[candles.length - 1].close;
    analyze();
    return data;
  }
  async function connect() {
    stop();
    if (market() === "otc") {
      status("OTC FEED UNAVAILABLE", "#f5c66a");
      setLiveNotice("Quotex OTC is not connected. No authorized Quotex OTC API/feed has been configured. The app will not substitute spot-FX prices and label them OTC.");
      return;
    }
    if (!base) {
      status("BACKEND URL REQUIRED", "#f5c66a");
      setLiveNotice("Live mode is not configured yet. Deploy the backend, add your Twelve Data API key to the backend's secret settings, then set the backend URL in config.js. Demo candles remain available until then.");
      return;
    }
    activeSymbol = pair();
    status("CONNECTING…", "#f5c66a");
    try {
      const boot = await loadCandles(activeSymbol);
      setLiveNotice("Connected to Twelve Data spot Forex. Initial " + boot.values.length +
        " candles loaded. Live tick streaming depends on your Twelve Data plan and symbol permissions; refresh target is a preference, not a guaranteed feed rate.");
      const wsUrl = base.replace(/^http/, "ws") + "/ws?symbol=" + encodeURIComponent(activeSymbol);
      socket = new WebSocket(wsUrl);
      socket.onopen = () => status("STREAM CONNECTING…", "#f5c66a");
      socket.onmessage = event => {
        let msg;
        try { msg = JSON.parse(event.data); } catch { return; }
        if (msg.event === "connected") status("STREAM CONNECTED", "#2bd69b");
        else if (msg.event === "price") addTick(msg.price, msg.timestamp);
        else if (msg.event === "error") {
          status("PROVIDER ERROR", "#ff637d");
          setLiveNotice("Provider stream error: " + (msg.message || "unknown error") +
            ". Check your plan, symbol access, and backend logs. No demo data is being presented as live.");
        }
      };
      socket.onerror = () => status("STREAM ERROR", "#ff637d");
      socket.onclose = () => {
        if (market() === "spot" && base) status("STREAM DISCONNECTED", "#ff637d");
      };
      const desired = Number(document.getElementById("liveCadence").value);
      cadenceTimer = setInterval(() => {
        if (lastTick && Date.now() - lastTick > Math.max(15000, desired * 5)) {
          status("STALE · WAITING FOR TICK", "#f5c66a");
        }
      }, 1000);
    } catch (error) {
      status("DATA LOAD FAILED", "#ff637d");
      setLiveNotice("Could not load live spot-FX candles: " + error.message +
        ". Check backend deployment, API key, provider permissions, and CORS.");
    }
  }
  document.getElementById("marketSource").addEventListener("change", connect);
  document.getElementById("liveCadence").addEventListener("change", () => {
    if (lastTick) status("LIVE · TARGET " + (Number(document.getElementById("liveCadence").value) / 1000) + "s", "#2bd69b");
  });
  document.getElementById("pair").addEventListener("change", () => { if (base) connect(); });
  document.getElementById("tf").addEventListener("change", () => { if (base) connect(); });
  document.getElementById("refresh").addEventListener("click", () => { if (base && market() === "spot") connect(); });
  if (!base) {
    status("DEMO · LIVE NOT CONFIGURED", "#f5c66a");
    setLiveNotice("Demo mode is active. Deploy the backend and configure a Twelve Data API key to enable live spot-FX prices. Quotex OTC remains unavailable unless an authorized OTC feed is supplied.");
  } else {
    connect();
  }
})();