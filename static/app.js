// beast-arena/static/app.js
// ── App: Login, Particles, Navigation, and Global State ──

let currentPlayer = null;
const EMOJIS = ["🦖","🦕","🐊","🦈","🐋","🦅","🐻","🐅","🦁","🐺","🦑","🐙","🦞","🐍","🦎","🐘","🦏","🐃","🦬","🦭","🐬","🦦","🦧","🦍","🐾"];

// ── Particles ──
// ═══════ Particles (optional, silently skipped if canvas unavailable) ═══════
function initParticles() {
  var canvas = document.getElementById("particles-canvas");
  if (!canvas || canvas.nodeName !== "CANVAS") return;
  // Check for proper canvas support
  if (typeof canvas.getContext !== "function") return;
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  var ctx = canvas.getContext("2d");
  var particles = [];
  for (var _i = 0; _i < 50; _i++) {
    particles.push({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 0.5, opacity: Math.random() * 0.4 + 0.1
    });
  }
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = canvas.width; if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height; if (p.y > canvas.height) p.y = 0;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(242,193,78,${p.opacity})`; ctx.fill();
    }
    // Connect near particles
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 100) { ctx.beginPath(); ctx.moveTo(particles[i].x, particles[i].y); ctx.lineTo(particles[j].x, particles[j].y); ctx.strokeStyle = `rgba(242,193,78,${0.05 * (1 - dist / 100)})`; ctx.lineWidth = 0.5; ctx.stroke(); }
      }
    }
    requestAnimationFrame(animate);
  }
  animate();
}
window.addEventListener("resize", () => {
  const c = document.getElementById("particles-canvas");
  if (c) { c.width = window.innerWidth; c.height = window.innerHeight; }
});

// ── Login ──
function initLogin() {
  // Emoji picker
  const picker = $e("reg-emoji-picker");
  if (picker) {
    EMOJIS.forEach(e => {
      const d = document.createElement("span"); d.className = "emoji-opt" + (e === "🦖" ? " selected" : ""); d.textContent = e;
      d.onclick = () => { picker.querySelectorAll(".emoji-opt").forEach(o => o.classList.remove("selected")); d.classList.add("selected"); };
      picker.appendChild(d);
    });
  }
  // Tab switch
  qsa(".login-tab").forEach(b => b.addEventListener("click", () => {
    qsa(".login-tab").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    $e("login-panel").classList.toggle("hidden", b.dataset.tab !== "login");
    $e("register-panel").classList.toggle("hidden", b.dataset.tab !== "register");
  }));
  // Login
  $e("login-btn").addEventListener("click", doLogin);
  $e("login-password").addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
  // Register
  $e("register-btn").addEventListener("click", doRegister);
}

async function doLogin() {
  const username = $e("login-username").value.trim();
  const password = $e("login-password").value.trim();
  const errEl = $e("login-error");
  if (!username || !password) { errEl.textContent = "请填写用户名和密码"; return; }
  errEl.textContent = "";
  try {
    const resp = await fetch(`${API}/players/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) { const e = await resp.json(); errEl.textContent = e.detail || "登录失败"; return; }
    currentPlayer = await resp.json();
    onLoginSuccess();
  } catch (e) { errEl.textContent = "无法连接服务器，请确认后端已启动。"; }
}

async function doRegister() {
  const username = $e("reg-username").value.trim();
  const display = $e("reg-display").value.trim();
  const password = $e("reg-password").value.trim();
  const password2 = $e("reg-password2").value.trim();
  const errEl = $e("reg-error");
  if (username.length < 3) { errEl.textContent = "用户名至少3个字符"; return; }
  if (!display) { errEl.textContent = "请填写显示名称"; return; }
  if (password.length < 4) { errEl.textContent = "密码至少4个字符"; return; }
  if (password !== password2) { errEl.textContent = "两次密码不一致"; return; }
  const selEmoji = qs("#reg-emoji-picker .selected");
  const avatar = selEmoji ? selEmoji.textContent : "🦖";
  errEl.textContent = "";
  try {
    const resp = await fetch(`${API}/players/register`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, display_name: display, avatar_emoji: avatar }),
    });
    if (!resp.ok) { const e = await resp.json(); errEl.textContent = e.detail || "注册失败"; return; }
    currentPlayer = await resp.json();
    // Auto-fill login
    $e("login-username").value = username;
    $e("login-password").value = password;
    // Switch to login tab then login
    qsa(".login-tab").forEach(b => { b.classList.remove("active"); if (b.dataset.tab === "login") b.classList.add("active"); });
    $e("login-panel").classList.remove("hidden");
    $e("register-panel").classList.add("hidden");
    doLogin();
  } catch (e) { errEl.textContent = "无法连接服务器，请确认后端已启动。"; }
}

function onLoginSuccess() {
  $e("login-overlay").classList.add("hidden");
  $e("main-ui").classList.remove("hidden");
  updatePlayerHeader();
  switchTab("arena");
}

function updatePlayerHeader() {
  if (!currentPlayer) return;
  $e("header-player").innerHTML = `
    <div class="player-chip" onclick="switchTab('teams')">
      <span class="player-avatar">${currentPlayer.avatar_emoji || "🦖"}</span>
      <span>${currentPlayer.display_name || currentPlayer.username}</span>
      <span class="level-badge">LV.${currentPlayer.level || 1}</span>
    </div>
    <button class="btn btn-sm" onclick="logout()">退出</button>
  `;
}

function logout() {
  currentPlayer = null;
  arena.battleResult = null;
  arena.battleFlow = null;
  resetArena();
  $e("login-overlay").classList.remove("hidden");
  $e("main-ui").classList.add("hidden");
}

// ── Tab Navigation ──
let currentTab = "arena";

function switchTab(tab) {
  currentTab = tab;
  qsa(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  qsa(".tab-panel").forEach(p => p.classList.toggle("hidden", p.id !== `tab-${tab}`));
  if (tab === "arena") renderArena();
  else if (tab === "guide") renderGuide();
  else if (tab === "history") renderHistory();
  else if (tab === "leaderboard") renderLeaderboard();
  else if (tab === "teams") renderMyTeams();
}

// ── Init ──
document.addEventListener("DOMContentLoaded", () => {
  try { initParticles(); } catch(e) { console.warn('Particles init failed (non-fatal):', e.message); }
  initLogin();
  // Nav clicks
  qsa(".nav-btn").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  // Load saved login from localStorage
  const savedPlayer = localStorage.getItem("beast_arena_player");
  if (savedPlayer) {
    try {
      currentPlayer = JSON.parse(savedPlayer);
      // Verify player still exists
      fetch(`${API}/players/${currentPlayer.id}`).then(r => {
        if (r.ok) { onLoginSuccess(); }
        else { localStorage.removeItem("beast_arena_player"); currentPlayer = null; }
      }).catch(() => {});
    } catch (e) { localStorage.removeItem("beast_arena_player"); }
  }
});

// Persist login
const origOnLoginSuccess = onLoginSuccess;
onLoginSuccess = function() {
  localStorage.setItem("beast_arena_player", JSON.stringify(currentPlayer));
  origOnLoginSuccess();
};
