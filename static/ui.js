// beast-arena/static/ui.js
// ── UI rendering functions ──

const API = "http://localhost:8767/api";
const MODE_CONFIG = { "1v1": { draw: 3, teamSize: 1 }, "3v3": { draw: 5, nStarters: 3, nBench: 1, teamSize: 3 }, "5v5": { draw: 8, nStarters: 5, nBench: 2, teamSize: 5 } };

// ── Helpers ──
function byName(n) { return ANIMALS_BY_NAME[n]; }
function el(tag, cls = "", html = "") { const e = document.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; return e; }
function $e(id) { return document.getElementById(id); }
function qs(sel, parent = document) { return parent.querySelector(sel); }
function qsa(sel, parent = document) { return parent.querySelectorAll(sel); }

function modeLabel(m) { return m === "1v1" ? "1v1单挑" : m === "3v3" ? "3v3小队战" : "5v5大乱斗"; }
function habitatClass(animal) { const t = animal.habitatTag; return t === "陆地" ? "habitat-land" : t === "海洋" ? "habitat-sea" : "habitat-amphib"; }
function miniLine(a) { return `<b>${a.name}</b> ${a.category} · ${a.weightDisplay}`; }

// ── Radar SVG ──
function buildRadarSVG(animal, terrainKey) {
  const profile = animal.terrains[terrainKey];
  if (!profile) return `<div class="radar-empty">无法在【${TERRAIN_LABELS[terrainKey]}】环境下作战</div>`;
  const values = [gradeValue(profile.attack), gradeValue(profile.defense), gradeValue(profile.mobility), gradeValue(profile.technique), gradeValue(profile.stamina), gradeValue(animal.intelligence)];
  const labels = ["攻击", "防御", "机动", "技巧", "续航", "智商"];
  const n = 6, cx = 160, cy = 160, R = 120;
  const angleFor = (i) => (Math.PI / 2) - (i * 2 * Math.PI / n);
  const pt = (value, i) => { const r = (value / 10) * R; const a = angleFor(i); return [cx + r * Math.cos(a), cy - r * Math.sin(a)]; };
  let svg = `<svg viewBox="0 0 320 340" class="radar-svg">`;
  for (const gv of [2, 4, 6, 8, 10]) { const pts = []; for (let i = 0; i < n; i++) pts.push(pt(gv, i).join(",")); svg += `<polygon points="${pts.join(" ")}" class="radar-grid" />`; }
  for (let i = 0; i < n; i++) { const [x, y] = pt(10, i); svg += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" class="radar-axis" />`; const [lx, ly] = pt(12.6, i); svg += `<text x="${lx}" y="${ly}" class="radar-label" text-anchor="middle" dominant-baseline="middle">${labels[i]}</text>`; }
  const dataPts = []; for (let i = 0; i < n; i++) dataPts.push(pt(values[i], i).join(","));
  svg += `<polygon points="${dataPts.join(" ")}" class="radar-data" />`;
  for (let i = 0; i < n; i++) { const [x, y] = pt(values[i], i); svg += `<circle cx="${x}" cy="${y}" r="4" class="radar-dot" />`; }
  svg += `</svg>`;
  return svg;
}

// ── Arena state ──
const arena = {
  mode: "3v3", teamMode: "draft",
  draft: freshDraftState(), custom: freshCustomState(),
  battleFlow: null, battleResult: null,
};

function freshDraftState() {
  return { phase: "idle", playerPool: [], enemyPool: [], playerPriority: [], enemyPriority: [],
    playerRoles: {}, playerStarters: [], playerBench: [], playerDiscard: [],
    enemyStarters: [], enemyBench: [], enemyDiscard: [],
    firstBanner: null, firstBannerNotes: [], firstBan: null, secondBan: null,
    finalBattlefield: null, finalPlayerRoster: [], finalEnemyRoster: [],
    subNotesPlayer: [], subNotesEnemy: [] };
}
function freshCustomState() {
  return { phase: "setup", playerTeam: [], opponentMode: "random", opponentTeam: [], battlefield: "陆地", eventPct: 100, filterText: "" };
}
function resetArena() { arena.draft = freshDraftState(); arena.custom = freshCustomState(); arena.battleFlow = null; arena.battleResult = null; }

// ── Render Arena ──
function renderArena() {
  const root = $e("arena-container");
  if (arena.battleFlow && arena.battleFlow.active) { renderBattleFlow(root); return; }
  const cfg = MODE_CONFIG[arena.mode];
  const heavyLimit = arena.mode === "1v1" ? null : Math.floor(cfg.teamSize / 2);
  root.innerHTML = `
    <div class="card gold-border">
      <div class="card-title">⚙️ 对战设置</div>
      <div class="field-label">战斗规模</div>
      <div class="radio-group" id="arena-mode-radio">
        ${["1v1", "3v3", "5v5"].map(m => `<label class="radio-pill ${arena.mode === m ? "active" : ""}"><input type="radio" name="arena-mode" value="${m}" ${arena.mode === m ? "checked" : ""}>${modeLabel(m)}</label>`).join("")}
      </div>
      <div class="field-label">组队方式</div>
      <div class="radio-group" id="arena-teammode-radio">
        ${[["draft","🎲 抽卡Ban场"], ["custom","🛠️ 自定义组队"]].map(([v,l]) => `<label class="radio-pill ${arena.teamMode === v ? "active" : ""}"><input type="radio" name="arena-teammode" value="${v}" ${arena.teamMode === v ? "checked" : ""}>${l}</label>`).join("")}
      </div>
      <p style="color:var(--text-secondary);font-size:0.82rem;margin-top:4px;">
        ${arena.teamMode === "draft" ? `系统抽取 ${cfg.draw} 只候选（含栖息标签限定）。${heavyLimit ? `每队最多 ${heavyLimit} 只超1吨。` : ""}` : `自由从全部 ${ANIMALS.length} 只动物中挑选 ${cfg.teamSize} 只阵容。`}
      </p>
      <button class="btn btn-block" onclick="resetArena(); renderArena();" style="margin-top:8px;">🔄 重置</button>
    </div>
    <div id="arena-flow">${arena.teamMode === "draft" ? renderDraftFlow() : renderCustomFlow()}</div>
  `;
  // Wire mode changes
  qsa('input[name="arena-mode"]').forEach(r => r.addEventListener("change", e => { resetArena(); arena.mode = e.target.value; renderArena(); }));
  qsa('input[name="arena-teammode"]').forEach(r => r.addEventListener("change", e => { resetArena(); arena.teamMode = e.target.value; renderArena(); }));
}

// ── Draft Flow ──
function renderDraftFlow() {
  const d = arena.draft, cfg = MODE_CONFIG[arena.mode];
  const steps = ["抽卡", "编队", "Ban场", "开战"];
  const stepIdx = d.phase === "idle" ? 0 : d.phase === "drafted" ? 1 : d.phase === "ready_to_ban" ? 2 : d.phase === "battlefield_resolved" ? 3 : d.phase === "battle_done" ? 4 : 0;
  let stepHTML = '<div class="step-track">';
  steps.forEach((s, i) => {
    const cls = i < stepIdx ? "done" : (i === stepIdx ? "active" : "");
    stepHTML += `<span class="step-dot ${cls}">${i+1}</span>`;
    if (i < steps.length - 1) stepHTML += `<span class="step-sep ${i < stepIdx ? 'done' : ''}"></span>`;
  });
  stepHTML += '</div>';

  let body = "";
  if (d.phase === "idle") {
    body = `<p style="color:var(--text-secondary);margin-bottom:14px;">点击按钮为双方抽取 ${cfg.draw} 只候选。</p>
      <button class="btn btn-primary btn-lg btn-block" onclick="doDraftDraw()">🎲 开始抽卡</button>`;
  } else if (d.phase === "drafted" && arena.mode === "1v1") {
    const pPool = d.playerPool.map(byName), ePool = d.enemyPool.map(byName);
    body = `<div class="two-col">
      <div class="card"><div class="card-title">🟦 我方候选</div>${pPool.map(a => `<div class="roster-item">${miniLine(a)} <span class="${habitatClass(a)}" style="font-size:0.7rem;padding:2px 8px;border-radius:999px;margin-left:auto;">${a.habitatTag}</span></div>`).join("")}</div>
      <div class="card"><div class="card-title">🟥 对方候选</div>${ePool.map(a => `<div class="roster-item">${miniLine(a)} <span class="${habitatClass(a)}" style="font-size:0.7rem;padding:2px 8px;border-radius:999px;margin-left:auto;">${a.habitatTag}</span></div>`).join("")}</div>
    </div>
    <div class="field-label">排定出战优先级</div>
    <select id="draft-rank1" class="select-box">${pPool.map(a => `<option value="${a.name}">🥇 ${a.name}</option>`).join("")}</select>
    <select id="draft-rank2" class="select-box"></select>
    <p style="color:var(--text-muted);font-size:0.82rem;" id="draft-rank3-caption"></p>
    <button class="btn btn-primary btn-block" onclick="doDraftConfirmPriority()">✅ 确认位次</button>`;
  } else if (d.phase === "drafted") { // 3v3 / 5v5
    const pPool = d.playerPool.map(byName);
    const nS = cfg.nStarters, nB = cfg.nBench;
    const starters = Object.entries(d.playerRoles).filter(([,r]) => r === "首发").map(([n]) => n);
    const bench = Object.entries(d.playerRoles).filter(([,r]) => r === "替补").map(([n]) => n);
    const valid = starters.length === nS && bench.length === nB;
    body = `<p style="color:var(--text-secondary);margin-bottom:8px;">为每只动物指定角色：首发 <b>${nS}</b> 只，替补 <b>${nB}</b> 只，其余弃置。</p>
      <div id="draft-role-list">${pPool.map(a => `<div class="role-row"><div class="role-label">${miniLine(a)} ${isHeavy(a) ? '<span style="color:var(--warning);font-size:0.72rem;">⚠️超1吨</span>' : ""}</div>
        <div class="radio-group compact" data-name="${a.name}">${["首发","替补","弃置"].map(r => `<label class="radio-pill ${(d.playerRoles[a.name]||'弃置') === r ? 'active' : ''}" onclick="draftSetRole('${a.name}','${r}')">${r}</label>`).join("")}</div></div>`).join("")}</div>
      <p style="color:var(--text-secondary);font-size:0.85rem;" id="draft-role-summary">首发 ${starters.length}/${nS} · 替补 ${bench.length}/${nB}</p>
      <button class="btn btn-primary btn-block" ${valid ? "" : "disabled"} onclick="doDraftConfirmRoster()">✅ 确认编队</button>`;
  } else if (d.phase === "ready_to_ban") {
    body = renderDraftBanPhase(d, cfg);
  } else if (d.phase === "battlefield_resolved") {
    body = `<div class="alert alert-success">🏟️ 最终战场：【${d.finalBattlefield}】（禁用了【${d.firstBan}】和【${d.secondBan}】）</div>
      <div class="two-col">
        <div class="card"><div class="card-title">🟦 我方出战</div>${d.subNotesPlayer.map(n => `<p style="font-size:0.82rem;color:var(--text-secondary);">${n}</p>`).join("")}${d.finalPlayerRoster.map(([n,s]) => `<div class="roster-item">${miniLine(byName(n))} ${s ? '<span style="color:var(--warning);">（替补-2级）</span>' : ''}</div>`).join("") || '<p style="color:var(--text-muted);">无可出战单位</p>'}</div>
        <div class="card"><div class="card-title">🟥 对方出战</div>${d.subNotesEnemy.map(n => `<p style="font-size:0.82rem;color:var(--text-secondary);">${n}</p>`).join("")}${d.finalEnemyRoster.map(([n,s]) => `<div class="roster-item">${miniLine(byName(n))} ${s ? '<span style="color:var(--warning);">（替补-2级）</span>' : ''}</div>`).join("") || '<p style="color:var(--text-muted);">无可出战单位</p>'}</div>
      </div>
      <button class="btn btn-primary btn-lg btn-block" onclick="doDraftStartBattle()">⚔️ 开始对战！</button>`;
  } else if (d.phase === "battle_done") {
    body = `<div class="alert alert-success">对战已结束！查看下方战报。</div><button class="btn btn-block" onclick="resetArena();renderArena();">🔁 再来一局</button>`;
  }
  return `<div class="card gold-border">${stepHTML}${body}</div>`;
}

function draftSetRole(name, role) { arena.draft.playerRoles[name] = role; renderArena(); }

function doDraftDraw() {
  const d = arena.draft;
  const pPool = drawTeam(Math.random, arena.mode); const ePool = drawTeam(Math.random, arena.mode);
  d.playerPool = pPool.map(a => a.name); d.enemyPool = ePool.map(a => a.name);
  if (arena.mode === "1v1") { d.enemyPriority = aiChooseRoster(ePool, 3, 0).starters; }
  else { const ai = aiChooseRoster(ePool, MODE_CONFIG[arena.mode].nStarters, MODE_CONFIG[arena.mode].nBench); d.enemyStarters = ai.starters; d.enemyBench = ai.bench; d.enemyDiscard = ai.discarded; }
  d.phase = "drafted"; renderArena();
  if (arena.mode === "1v1") draftWireRankSelects();
}

function draftWireRankSelects() {
  const pPool = arena.draft.playerPool;
  const r1 = $e("draft-rank1"), r2 = $e("draft-rank2");
  if (!r1 || !r2) return;
  const update = () => {
    const first = r1.value;
    const remaining = pPool.filter(n => n !== first);
    r2.innerHTML = remaining.map(n => `<option value="${n}">🥈 ${n}</option>`).join("");
    const second = r2.value || remaining[0];
    const third = remaining.find(n => n !== second);
    $e("draft-rank3-caption").textContent = `第三优先（自动）：${third}`;
  };
  r1.addEventListener("change", update); r2.addEventListener("change", update);
  update();
}

function doDraftConfirmPriority() {
  const d = arena.draft;
  const first = $e("draft-rank1").value, second = $e("draft-rank2").value;
  const third = d.playerPool.filter(n => n !== first && n !== second)[0];
  d.playerPriority = [first, second, third];
  const pPri = d.playerPriority.map(byName), ePri = d.enemyPriority.map(byName);
  const { first: fb, notes } = decideFirstBanner(pPri, ePri, Math.random);
  d.firstBanner = fb; d.firstBannerNotes = notes; d.phase = "ready_to_ban";
  renderArena();
}

function doDraftConfirmRoster() {
  const d = arena.draft, cfg = MODE_CONFIG[arena.mode];
  d.playerStarters = Object.entries(d.playerRoles).filter(([,r]) => r === "首发").map(([n]) => n);
  d.playerBench = Object.entries(d.playerRoles).filter(([,r]) => r === "替补").map(([n]) => n);
  d.playerDiscard = d.playerPool.filter(n => !d.playerStarters.includes(n) && !d.playerBench.includes(n));
  const pS = d.playerStarters.map(byName), eS = d.enemyStarters.map(byName);
  const { first, notes } = decideFirstBanner(pS, eS, Math.random);
  d.firstBanner = first; d.firstBannerNotes = notes; d.phase = "ready_to_ban";
  renderArena();
}

function renderDraftBanPhase(d, cfg) {
  let banHTML = `<h4 style="color:var(--accent);margin-bottom:8px;">🎯 先手判定</h4>${d.firstBannerNotes.map(n => `<p style="font-size:0.82rem;color:var(--text-secondary);">${n}</p>`).join("")}<div class="alert alert-info">${d.firstBanner === "player" ? "我方" : "对方"} 先手禁用一个战场。</div>`;
  if (d.firstBan === null) {
    if (d.firstBanner === "enemy") {
      const eu = arena.mode === "1v1" ? d.enemyPriority.map(byName) : d.enemyStarters.map(byName);
      d.firstBan = aiChooseBan(BATTLEFIELDS, eu, Math.random);
      return renderDraftFlow(); // re-render
    }
    banHTML += `<p style="color:var(--text-primary);">请选择要禁用的战场：</p><div class="btn-row">${BATTLEFIELDS.map(bf => `<button class="btn" onclick="draftBanFirst('${bf}')">🚫 禁用【${bf}】</button>`).join("")}</div>`;
  } else if (d.secondBan === null) {
    const remaining = BATTLEFIELDS.filter(b => b !== d.firstBan);
    if (d.firstBanner === "player") {
      const eu = arena.mode === "1v1" ? d.enemyPriority.map(byName) : d.enemyStarters.map(byName);
      d.secondBan = aiChooseBan(remaining, eu, Math.random);
      draftResolveRosters();
      return renderDraftFlow();
    }
    banHTML += `<div class="alert alert-warning">对方已禁用【${d.firstBan}】，请我方禁用剩余战场之一：</div><div class="btn-row">${remaining.map(bf => `<button class="btn btn-danger" onclick="draftBanSecond('${bf}')">🚫 禁用【${bf}】</button>`).join("")}</div>`;
  }
  // Show rosters in 3v3/5v5
  if (arena.mode !== "1v1" && d.playerStarters.length) {
    banHTML += `<hr style="border-color:var(--border-subtle);margin:14px 0;"><div class="two-col"><div><b>我方首发</b>：${d.playerStarters.join("、")}<br><b>替补</b>：${d.playerBench.join("、")}</div><div><b>对方首发</b>：${d.enemyStarters.join("、")}<br><b>替补</b>：${d.enemyBench.join("、")}</div></div>`;
  }
  return banHTML;
}

function draftBanFirst(bf) { arena.draft.firstBan = bf; renderArena(); }
function draftBanSecond(bf) { arena.draft.secondBan = bf; draftResolveRosters(); renderArena(); }

function draftResolveRosters() {
  const d = arena.draft;
  d.finalBattlefield = remainingAfterBans(d.firstBan, d.secondBan);
  if (arena.mode === "1v1") {
    const pP = d.playerPriority.map(byName), eP = d.enemyPriority.map(byName);
    const pC = resolve1v1Combatant(pP, d.finalBattlefield), eC = resolve1v1Combatant(eP, d.finalBattlefield);
    d.finalPlayerRoster = pC ? [[pC.name, 0]] : []; d.finalEnemyRoster = eC ? [[eC.name, 0]] : [];
    d.subNotesPlayer = pC ? [] : ["⚠️ 3只候选均无法适应该战场！"];
    d.subNotesEnemy = eC ? [] : ["⚠️ 对方3只候选均无法适应该战场！"];
  } else {
    const pS = d.playerStarters.map(byName), pB = d.playerBench.map(byName);
    const eS = d.enemyStarters.map(byName), eB = d.enemyBench.map(byName);
    const pR = resolveRosterWithSubs(pS, pB, d.finalBattlefield);
    const eR = resolveRosterWithSubs(eS, eB, d.finalBattlefield);
    d.finalPlayerRoster = pR.finalRoster.map(([a, s]) => [a.name, s]);
    d.finalEnemyRoster = eR.finalRoster.map(([a, s]) => [a.name, s]);
    d.subNotesPlayer = pR.notes; d.subNotesEnemy = eR.notes;
  }
  d.phase = "battlefield_resolved";
}

function doDraftStartBattle() {
  const d = arena.draft;
  const pR = d.finalPlayerRoster.map(([n, s]) => [byName(n), s]);
  const eR = d.finalEnemyRoster.map(([n, s]) => [byName(n), s]);
  const extraNotes = [...d.subNotesPlayer, ...d.subNotesEnemy];
  startBattleFlow(pR, eR, d.finalBattlefield, {}, (result) => {
    if (extraNotes.length) result.log = [...extraNotes, "", ...result.log];
    arena.battleResult = result;
    arena.battleFlow = null;
    d.phase = "battle_done";
    saveBattleRecord(result);
    renderArena();
    renderReportView();
    showBattleResultModal(result);
  });
  renderArena();
}

// ── Custom Flow ──
function renderCustomFlow() {
  const c = arena.custom, cfg = MODE_CONFIG[arena.mode];
  const teamSize = cfg.teamSize;
  if (c.phase === "battle_done") {
    return `<div class="card gold-border"><div class="alert alert-success">对战已结束！查看下方战报。</div><button class="btn btn-block" onclick="resetArena();renderArena();">🔁 再来一局</button></div>`;
  }
  const playerOk = c.playerTeam.length === teamSize;
  const oppOk = c.opponentMode === "random" || c.opponentTeam.length === teamSize;
  const valid = playerOk && oppOk;
  const prePct = Math.min(100, Math.round(30 * c.eventPct / 100));
  const perPct = Math.min(100, Math.round(16 * c.eventPct / 100));

  return `<div class="card gold-border">
    <div class="card-title">🛠️ 自定义组队</div>
    <h4 style="color:var(--accent);margin:12px 0 6px;">我方阵容（${c.playerTeam.length}/${teamSize}）</h4>
    ${pickerHTML("player", c.playerTeam, teamSize, "player")}

    <h4 style="color:var(--accent);margin:12px 0 6px;">对手设置</h4>
    <div class="radio-group" id="custom-opp-mode">
      ${[["random","🎲 随机生成"], ["custom","🛠️ 自定义对手"]].map(([v,l]) => `<label class="radio-pill ${c.opponentMode === v ? 'active' : ''}"><input type="radio" name="opp-mode" value="${v}" ${c.opponentMode === v ? 'checked' : ''}>${l}</label>`).join("")}
    </div>
    ${c.opponentMode === "custom" ? `<h4 style="color:var(--accent);margin:12px 0 6px;">对方阵容（${c.opponentTeam.length}/${teamSize}）</h4>${pickerHTML("opponent", c.opponentTeam, teamSize, "opponent")}` : '<p style="color:var(--text-secondary);font-size:0.85rem;">开战时随机生成。</p>'}

    <div class="field-label">战场选择</div>
    <div class="radio-group" id="custom-bf-radio">
      ${BATTLEFIELDS.map(bf => `<label class="radio-pill ${c.battlefield === bf ? 'active' : ''}" onclick="arena.custom.battlefield='${bf}';renderArena();">${bf}</label>`).join("")}
    </div>

    <div class="field-label">突发事件概率 (${c.eventPct}%) —— 默认100%=战前30%/每回合16%</div>
    <div style="display:flex;align-items:center;gap:10px;">
      <input type="range" min="0" max="300" step="10" value="${c.eventPct}" style="flex:1;accent-color:var(--accent);" oninput="arena.custom.eventPct=parseInt(this.value);document.getElementById('event-pct-label').textContent=this.value+'% (战前~'+Math.min(100,Math.round(30*this.value/100))+'% / 每回合~'+Math.min(100,Math.round(16*this.value/100))+'%)';">
      <span id="event-pct-label" style="color:var(--text-secondary);font-size:0.82rem;min-width:120px;">${c.eventPct}% (战前~${prePct}% / 每回合~${perPct}%)</span>
    </div>
    <button class="btn btn-primary btn-lg btn-block" style="margin-top:16px;" ${valid ? "" : "disabled"} onclick="doCustomBattle()">⚔️ 开始对战！</button>
  </div>`;
}

function pickerHTML(idPrefix, selectedNames, teamSize, label) {
  const heavyCount = selectedNames.filter(n => isHeavy(byName(n))).length;
  return `<input type="text" class="picker-search" id="${idPrefix}-search" placeholder="搜索动物名称或类别…" oninput="filterPicker('${idPrefix}')">
    <div class="picker-grid" id="${idPrefix}-list">${ANIMALS.map(a => `<label class="picker-row ${selectedNames.includes(a.name) ? 'checked' : ''}" data-name="${a.name}" data-category="${a.category}">
      <input type="checkbox" data-name="${a.name}" ${selectedNames.includes(a.name) ? 'checked' : ''} ${!selectedNames.includes(a.name) && selectedNames.length >= teamSize ? 'disabled' : ''} onchange="togglePicker('${idPrefix}','${a.name}',this.checked,${teamSize})">
      <span style="flex:1;">${miniLine(a)}</span>${isHeavy(a) ? '<span class="heavy-tag">⚠️超1吨</span>' : ''}
    </label>`).join("")}</div>
    <p class="picker-summary">已选 <b id="${idPrefix}-count">${selectedNames.length}</b>/${teamSize} · 其中超1吨 <b>${heavyCount}</b>/不限</p>`;
}

function togglePicker(prefix, name, checked, teamSize) {
  const c = arena.custom;
  const arr = prefix === "player" ? c.playerTeam : c.opponentTeam;
  if (checked && arr.length >= teamSize) return;
  if (checked) arr.push(name); else arr.splice(arr.indexOf(name), 1);
  renderArena();
}
function filterPicker(prefix) {
  const ft = $e(`${prefix}-search`).value.trim();
  qsa(`#${prefix}-list .picker-row`).forEach(row => {
    row.style.display = (!ft || row.dataset.name.includes(ft) || row.dataset.category.includes(ft)) ? "" : "none";
  });
}

function doCustomBattle() {
  const c = arena.custom, cfg = MODE_CONFIG[arena.mode];
  const pR = c.playerTeam.map(n => byName(n));
  let oppR;
  if (c.opponentMode === "custom") { oppR = c.opponentTeam.map(n => byName(n)); }
  else { const excl = new Set(c.playerTeam); const pool = ANIMALS.filter(a => !excl.has(a.name)); oppR = sampleN(Math.random, pool, cfg.teamSize); }
  const eventOpts = { preBattleChance: Math.min(1, 0.30 * c.eventPct / 100), perRoundChance: Math.min(1, 0.16 * c.eventPct / 100) };
  startBattleFlow(pR, oppR, c.battlefield, eventOpts, (result) => {
    arena.battleResult = result;
    arena.battleFlow = null;
    c.phase = "battle_done";
    saveBattleRecord(result);
    renderArena();
    renderReportView();
    showBattleResultModal(result);
  });
  renderArena();
}

// ── Battle Flow ──
function freshBattleFlowState() { return { active: false, phase: "setup", battle: null, playerRoster: null, enemyRoster: null, battlefield: null, eventOptions: null, onComplete: null, playerFormation: {}, playerStance: "normal" }; }

function startBattleFlow(pR, eR, bf, eo, complete) {
  const fb = freshBattleFlowState();
  fb.active = true; fb.playerRoster = pR; fb.enemyRoster = eR; fb.battlefield = bf; fb.eventOptions = eo || {}; fb.onComplete = complete;
  const names = pR.map(e => (Array.isArray(e) ? e[0] : e).name);
  fb.playerFormation = Object.fromEntries(names.map(n => [n, "front"]));
  fb.playerStance = "normal";
  arena.battleFlow = fb;
}

function renderBattleFlow(root) {
  const bf = arena.battleFlow;
  if (bf.phase === "setup") renderBattleSetup(root, bf);
  else renderBattleProgress(root, bf);
}

function stanceDesc(k) {
  const d = { normal: "无特殊加成，稳扎稳打。", berserk: "🔥 造成伤害 +25%，防御 -15%", hold: "🛡️ 受到伤害 -25%，造成伤害 -15%，机动 -10%", guerrilla: "🌀 机动 +40%，造成伤害 +10%，防御 -5%" };
  return d[k] || "";
}

function renderBattleSetup(root, bf) {
  const names = bf.playerRoster.map(e => (Array.isArray(e) ? e[0] : e).name);
  root.innerHTML = `<div class="card gold-border">
    <h3 style="color:var(--accent);">🎮 战斗前设置</h3>
    <p style="color:var(--text-secondary);">战场：${bf.battlefield}</p>
    <div class="battle-setup-grid">
      <div class="setup-section">
        <h4>阵型设置（前排优先承受伤害）</h4>
        ${formationHTML(names, bf.playerFormation, "setup")}
      </div>
      <div class="setup-section">
        <h4>战术策略</h4>
        <div class="stance-cards">${STANCE_KEYS.map(k => `<div class="stance-card ${bf.playerStance === k ? 'active' : ''}" onclick="arena.battleFlow.playerStance='${k}';renderArena();">
          <div class="sc-icon">${k === 'normal' ? '⚔️' : k === 'berserk' ? '🔥' : k === 'hold' ? '🛡️' : '🌀'}</div>
          <div class="sc-name">${STANCES[k].label}</div>
          <div class="sc-desc">${stanceDesc(k)}</div>
        </div>`).join("")}</div>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-block" onclick="battleSkip()">⏭️ 跳过战斗，直接看结果</button>
      <button class="btn btn-primary btn-block" onclick="battleStartControl()">🎮 逐回合操纵</button>
    </div>
  </div>`;
  wireFormation("setup", bf.playerFormation);
}

function formationHTML(units, formationState, prefix) {
  return `<div>${units.map(u => { const name = typeof u === "string" ? u : u.name; const animal = typeof u === "string" ? byName(u) : u.animal;
    return `<div class="role-row"><div class="role-label"><b>${name}</b> (${animal.category})</div>
    <div class="radio-group compact" data-name="${name}">${["front","back"].map(r => `<label class="radio-pill ${(formationState[name]||'front') === r ? 'active' : ''}"><input type="radio" name="${prefix}-${name}" value="${r}" ${(formationState[name]||'front') === r ? 'checked' : ''}>${r === 'front' ? '前排' : '后排'}</label>`).join("")}</div></div>`;
  }).join("")}</div>`;
}

function wireFormation(prefix, formationState) {
  qsa(`.radio-group[data-name]`).forEach(g => {
    const name = g.dataset.name;
    g.querySelectorAll("input").forEach(inp => inp.addEventListener("change", e => { formationState[name] = e.target.value; }));
  });
}

function battleSkip() {
  const bf = arena.battleFlow;
  bf.battle = createBattle(bf.playerRoster, bf.enemyRoster, bf.battlefield, bf.eventOptions, Math.random);
  runBattleToCompletion(bf.battle, { stance: bf.playerStance, formation: { ...bf.playerFormation } });
  finishBattleFlow(bf);
}

function battleStartControl() {
  const bf = arena.battleFlow;
  bf.battle = createBattle(bf.playerRoster, bf.enemyRoster, bf.battlefield, bf.eventOptions, Math.random);
  if (bf.battle.finished) { finishBattleFlow(bf); return; }
  bf.phase = "in_progress";
  renderArena();
}

function renderBattleProgress(root, bf) {
  const battle = bf.battle;
  root.innerHTML = `<div class="card gold-border">
    <h3 style="color:var(--accent);">🎮 战斗进行中 — 第 ${battle.roundNo + 1} 回合</h3>
    <div class="log-box" id="live-log-box">${renderLogHTML(battle.log)}</div>
    <h4>本回合阵型</h4>${formationHTML(battle.playerUnits, bf.playerFormation, "live")}
    <h4>战术策略</h4>
    <div class="stance-cards">${STANCE_KEYS.map(k => `<div class="stance-card ${bf.playerStance === k ? 'active' : ''}" onclick="arena.battleFlow.playerStance='${k}';renderArena();">
      <div class="sc-icon">${k==='normal'?'⚔️':k==='berserk'?'🔥':k==='hold'?'🛡️':'🌀'}</div><div class="sc-name">${STANCES[k].label}</div></div>`).join("")}</div>
    <div class="btn-row">
      <button class="btn btn-primary btn-block" onclick="battleNextRound()">▶️ 执行本回合</button>
      <button class="btn btn-block" onclick="battleSkipRemaining()">⏭️ 跳过剩余</button>
    </div>
  </div>`;
  wireFormation("live", bf.playerFormation);
  const logBox = $e("live-log-box"); if (logBox) logBox.scrollTop = logBox.scrollHeight;
}

function battleNextRound() {
  const bf = arena.battleFlow, battle = bf.battle;
  const pDec = { stance: bf.playerStance, formation: { ...bf.playerFormation } };
  const eDec = aiChooseDecision(battle.enemyUnits, Math.random);
  const roundJustDone = battle.roundNo + 1;
  const prevLen = battle.log.length;
  advanceOneRound(battle, pDec, eDec);
  const newLines = battle.log.slice(prevLen);
  showRoundModal(roundJustDone, newLines, battle.finished ? () => finishBattleFlow(bf) : () => renderArena(), battle.finished);
}

function battleSkipRemaining() {
  const bf = arena.battleFlow;
  runBattleToCompletion(bf.battle, { stance: bf.playerStance, formation: { ...bf.playerFormation } });
  finishBattleFlow(bf);
}

function finishBattleFlow(bf) {
  const result = bf.battle;
  const onComplete = bf.onComplete;
  arena.battleFlow = null;
  arena.battleResult = result;
  if (onComplete) onComplete(result);
  saveBattleRecord(result);
  renderArena();
  renderReportView();
  showBattleResultModal(result);
}

function showRoundModal(roundNo, lines, onContinue, isFinished) {
  let overlay = $e("battle-modal-overlay");
  if (!overlay) { overlay = document.createElement("div"); overlay.id = "battle-modal-overlay"; overlay.className = "modal-overlay hidden"; $e("app").appendChild(overlay); }
  overlay.innerHTML = `<div class="modal-card"><h3 style="color:var(--accent);">📢 ${isFinished ? '🏁 战斗结束！' : `第 ${roundNo} 回合战报`}</h3>
    <div class="modal-log" style="flex:1;overflow-y:auto;margin:8px 0 16px;font-size:0.85rem;line-height:1.6;">${renderLogHTML(lines)}</div>
    <button class="btn btn-primary btn-block" id="modal-continue-btn">${isFinished ? '查看最终战报' : '▶️ 继续下一回合'}</button></div>`;
  overlay.classList.remove("hidden");
  $e("modal-continue-btn").addEventListener("click", () => { overlay.classList.add("hidden"); onContinue(); });
}

function showBattleResultModal(result) {
  let overlay = $e("battle-modal-overlay");
  if (!overlay) { overlay = document.createElement("div"); overlay.id = "battle-modal-overlay"; overlay.className = "modal-overlay hidden"; $e("app").appendChild(overlay); }
  const emoji = result.winner === "player" ? "🏆" : result.winner === "enemy" ? "💥" : "🤝";
  const text = result.winner === "player" ? "我方获胜！" : result.winner === "enemy" ? "对方获胜" : "平局！";
  const hpHTML = [...result.playerUnits, ...result.enemyUnits].map(u => {
    const pct = Math.max(0, Math.round(u.hpRatio() * 100));
    return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0;"><span style="flex:0 0 100px;text-align:right;font-size:0.82rem;">${u.name}</span><div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:14px;overflow:hidden;"><div style="width:${pct}%;height:100%;background:${u.side==='player'?'#3498db':'#e74c3c'};border-radius:4px;"></div></div><span style="flex:0 0 80px;font-size:0.75rem;color:var(--text-muted);">${u.hp}/${u.maxHp}</span></div>`;
  }).join("");
  overlay.innerHTML = `<div class="modal-card victory-card"><h2 style="color:var(--accent);text-align:center;">${emoji} ${text}</h2>
    <p style="color:var(--text-secondary);text-align:center;">战场：${result.battlefield} · ${result.rounds} 回合</p>
    <div style="margin:12px 0;">${hpHTML}</div>
    <button class="btn btn-primary btn-block" id="modal-result-btn">✅ 查看详细战报</button></div>`;
  overlay.classList.remove("hidden");
  $e("modal-result-btn").addEventListener("click", () => { overlay.classList.add("hidden"); switchTab("history"); });
}

// ── Report View ──
function renderReportView() {
  const result = arena.battleResult;
  if (!result) return;
  const cont = $e("history-container");
  if (!$e("current-report")) return;
  const bc = result.winner === "player" ? "alert-success" : (result.winner === "enemy" ? "alert-error" : "alert-warning");
  const bt = result.winner === "player" ? `🏆 我方获胜！` : result.winner === "enemy" ? `💥 对方获胜！` : `🤝 平局！`;
  // Append to top of history
  const hpHTML = [...result.playerUnits, ...result.enemyUnits].map(u => {
    const pct = Math.max(0, Math.round(u.hpRatio() * 100));
    return `<div class="hp-row"><div class="hp-name">${u.name}</div><div class="hp-bar-wrap"><div class="hp-bar-fill" style="width:${pct}%;background:${u.side==='player'?'#3498db':'#e74c3c'}"></div></div><div class="hp-num">${u.hp}/${u.maxHp}</div></div>`;
  }).join("");
  const block = document.createElement("div");
  block.className = "card gold-border slide-in";
  block.innerHTML = `<div class="alert ${bc}">${bt}（${result.rounds}回合 · 战场：${result.battlefield}）</div>
    ${hpHTML ? '<div class="hp-chart">'+hpHTML+'</div>' : ''}
    <details><summary style="cursor:pointer;color:var(--accent);font-weight:700;margin:8px 0;">📜 完整战斗日志</summary>
    <div class="log-box">${renderLogHTML(result.log)}</div></details>`;
  cont.insertBefore(block, cont.firstChild);
}

function renderLogHTML(lines) {
  let html = ""; let inEvent = false; let buf = [];
  for (const line of lines) {
    if (line.includes("🌟🌟🌟 突发情况：")) { inEvent = true; buf = [line.trim()]; continue; }
    if (inEvent) { buf.push(line.trim()); if (line.includes("结算完毕")) { html += `<div class="event-card">${buf.filter(Boolean).join("<br>")}</div>`; inEvent = false; buf = []; } continue; }
    if (line.trim()) html += `<div class="log-line">${line}</div>`;
  }
  return html;
}

// ── Guide Tab ──
let guideState = { terrainFilter: "全部", selectedAnimal: null, terrainView: null };

function renderGuide() {
  const root = $e("guide-container");
  const g = guideState;
  const pool = g.terrainFilter === "全部" ? ANIMALS : ANIMALS.filter(a => animalCanFightHere(a, g.terrainFilter));
  if (!g.selectedAnimal || !pool.some(a => a.name === g.selectedAnimal)) g.selectedAnimal = pool[0]?.name || null;
  const animal = g.selectedAnimal ? byName(g.selectedAnimal) : null;
  const myTerrains = animal ? availableTerrains(animal) : [];
  if (animal && (!g.terrainView || !myTerrains.includes(g.terrainView))) g.terrainView = myTerrains[0];
  const tv = animal ? g.terrainView : null;
  const profile = animal && tv ? animal.terrains[tv] : null;

  root.innerHTML = `<div class="card gold-border">
    <div class="card-title">📖 猛兽图鉴（共 ${ANIMALS.length} 只）</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div>
        <div class="field-label">按战场筛选</div>
        <select class="select-box" id="guide-terrain-filter" onchange="guideState.terrainFilter=this.value;renderGuide();">${["全部",...BATTLEFIELDS].map(t => `<option value="${t}" ${t===g.terrainFilter?'selected':''}>${t}</option>`).join("")}</select>
        <div class="field-label">选择猛兽（${pool.length}只）</div>
        <select class="select-box" id="guide-animal-select" onchange="guideState.selectedAnimal=this.value;renderGuide();">${pool.map(a => `<option value="${a.name}" ${a.name===g.selectedAnimal?'selected':''}>${a.name}</option>`).join("")}</select>
        ${animal ? `<div class="card" style="margin-top:12px;">
          <h3>${animal.name} <span style="color:var(--text-muted);font-size:0.85rem;">${animal.category}</span></h3>
          <p style="font-size:0.85rem;color:var(--text-secondary);"><b>定位</b>：${animal.role}<br><b>体重</b>：${animal.weightDisplay}<br><b>时代</b>：${animal.era}<br><b>范围</b>：${animal.range}<br><b>特征</b>：${animal.features}<br><b>栖息标签</b>：${animal.habitatTag} · <b>智商</b>：${animal.intelligence}</p>
          <div class="field-label">战场评级</div>
          <div class="radio-group" id="guide-terrain-view">${myTerrains.map(t => `<label class="radio-pill ${tv===t?'active':''}" onclick="guideState.terrainView='${t}';renderGuide();">${TERRAIN_LABELS[t]}</label>`).join("")}</div>
          ${tv && profile ? `<p style="font-size:0.82rem;color:var(--text-secondary);margin-top:8px;">稳定系数：<b>${profile.stability.toFixed(2)}</b></p>` : ''}
        </div>` : ''}
      </div>
      <div>${animal && tv ? `<div class="radar-title">${animal.name} · ${TERRAIN_LABELS[tv]}</div>${buildRadarSVG(animal, tv)}` : '<p style="color:var(--text-muted);text-align:center;padding:40px;">请选择一只动物</p>'}</div>
    </div>
  </div>`;
}

// ── History Tab ──
async function renderHistory() {
  const root = $e("history-container");
  if (!currentPlayer) { root.innerHTML = `<div class="alert alert-info">请先登录。</div>`; return; }

  // Show local result if available
  let html = '';
  if (arena.battleResult) {
    const result = arena.battleResult;
    const bc = result.winner === "player" ? "alert-success" : (result.winner === "enemy" ? "alert-error" : "alert-warning");
    const hpHTML = [...result.playerUnits, ...result.enemyUnits].map(u => {
      const pct = Math.max(0, Math.round(u.hpRatio() * 100));
      return `<div class="hp-row"><div class="hp-name">${u.name}</div><div class="hp-bar-wrap"><div class="hp-bar-fill" style="width:${pct}%;background:${u.side==='player'?'#3498db':'#e74c3c'}"></div></div><div class="hp-num">${u.hp}/${u.maxHp}</div></div>`;
    }).join("");
    html += `<div class="card gold-border" id="current-report"><div class="alert ${bc}">🏟️ 当前战报（${result.winner === "player" ? "🏆 我方获胜" : result.winner === "enemy" ? "💥 对方获胜" : "🤝 平局"} · ${result.rounds}回合 · 战场：${result.battlefield}）</div>${hpHTML ? '<div class="hp-chart">'+hpHTML+'</div>' : ''}<details><summary style="cursor:pointer;color:var(--accent);font-weight:700;">📜 完整战斗日志</summary><div class="log-box">${renderLogHTML(result.log)}</div></details></div>`;
  }

  try {
    const resp = await fetch(`${API}/players/${currentPlayer.id}/battles?limit=20`);
    const data = await resp.json();
    if (data.battles.length) {
      html += `<div class="card"><div class="card-title">📜 历史战斗记录（${data.total} 场）</div>`;
      for (const b of data.battles) {
        const emoji = b.winner === "player" ? "🏆" : b.winner === "enemy" ? "💔" : "🤝";
        html += `<div class="roster-item" style="justify-content:space-between;">
          <span>${emoji} <b>${b.battlefield}</b> · ${modeLabel(b.mode)} · ${b.rounds}回合 · ${new Date(b.created_at).toLocaleDateString('zh-CN')}</span>
          <button class="btn btn-sm" onclick="loadRemoteBattle('${b.id}')">📋 查看</button>
        </div>`;
      }
      html += `</div>`;
    }
  } catch (e) { html += `<div class="alert alert-warning">无法连接服务器获取历史记录。请确保后端正在运行。</div>`; }

  root.innerHTML = html || '<div class="alert alert-info">暂无战斗记录。去竞技场打一场吧！</div>';
}

async function loadRemoteBattle(id) {
  try {
    const resp = await fetch(`${API}/battles/${id}`);
    const b = await resp.json();
    const hpHTML = [...(b.player_team || [])].map(n => `<div class="roster-item">🟦 ${n}</div>`).join("") + [...(b.enemy_team || [])].map(n => `<div class="roster-item">🟥 ${n}</div>`).join("");
    const logArr = b.battle_log || [];
    showModal(`📋 战斗详情 · ${b.battlefield} · ${b.rounds}回合 · ${new Date(b.created_at).toLocaleString('zh-CN')}`,
      `<div style="margin-bottom:12px;">${hpHTML}</div><div class="log-box" style="max-height:400px;">${renderLogHTML(logArr)}</div>`, true);
  } catch (e) { alert('加载失败：' + e.message); }
}

// ── Leaderboard Tab ──
async function renderLeaderboard() {
  const root = $e("leaderboard-container");
  try {
    const resp = await fetch(`${API}/leaderboard?limit=30`);
    const data = await resp.json();
    if (!data.length) { root.innerHTML = `<div class="alert alert-info">暂无排行数据，去战斗吧！</div>`; return; }
    root.innerHTML = `<div class="card gold-border"><div class="card-title">🏆 排行榜</div>
      <table class="lb-table"><thead><tr><th>#</th><th>玩家</th><th>等级</th><th>场次</th><th>胜</th><th>负</th><th>平</th><th>胜率</th></tr></thead><tbody>
      ${data.map((p, i) => {
        const rc = i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
        return `<tr><td class="lb-rank ${rc}">${i+1}</td><td>${p.avatar_emoji} ${p.display_name || p.username} ${p.id === currentPlayer?.id ? '(你)' : ''}</td><td>LV.${p.level}</td><td>${p.total_games}</td><td style="color:var(--success);">${p.wins}</td><td style="color:var(--danger);">${p.losses}</td><td>${p.draws}</td><td>${p.win_rate}%</td></tr>`;
      }).join("")}
      </tbody></table></div>`;
  } catch (e) { root.innerHTML = `<div class="alert alert-warning">无法连接服务器获取排行榜。</div>`; }
}

// ── My Teams Tab ──
async function renderMyTeams() {
  const root = $e("teams-container");
  if (!currentPlayer) { root.innerHTML = `<div class="alert alert-info">请先登录。</div>`; return; }
  try {
    const resp = await fetch(`${API}/players/${currentPlayer.id}/teams`);
    const data = await resp.json();
    root.innerHTML = `<div class="card gold-border"><div class="card-title">💾 我的编队</div>
      <button class="btn btn-primary" onclick="saveCurrentTeam()" style="margin-bottom:12px;">💾 保存当前阵容</button>
      ${data.length ? data.map(t => `<div class="roster-item" style="justify-content:space-between;">
        <span><b>${t.name}</b> · ${modeLabel(t.mode)} · ${(t.animal_names||[]).length}只</span>
        <span><button class="btn btn-sm btn-danger" onclick="deleteSavedTeam('${t.id}')">🗑</button></span>
      </div>`).join("") : '<p style="color:var(--text-secondary);">暂无保存的编队。在自定义组队中选好阵容后保存。</p>'}</div>`;
  } catch (e) { root.innerHTML = `<div class="alert alert-warning">无法连接服务器。</div>`; }
}

async function saveCurrentTeam() {
  const c = arena.custom;
  if (!c.playerTeam.length) { alert('请先在自定义组队中选择阵容。'); return; }
  const name = prompt('为这个编队起个名字：', `我的${modeLabel(arena.mode)}编队`);
  if (!name) return;
  try {
    await fetch(`${API}/players/${currentPlayer.id}/teams`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: currentPlayer.id, name, mode: arena.mode, team_mode: "custom", animal_names: c.playerTeam }),
    });
    renderMyTeams();
  } catch (e) { alert('保存失败：' + e.message); }
}

async function deleteSavedTeam(id) {
  if (!confirm('确认删除？')) return;
  try { await fetch(`${API}/teams/${id}`, { method: "DELETE" }); renderMyTeams(); }
  catch (e) { alert('删除失败：' + e.message); }
}

// ── Save battle record ──
async function saveBattleRecord(result) {
  if (!currentPlayer) return;
  try {
    const pTeam = result.playerUnits.map(u => u.name);
    const eTeam = result.enemyUnits.map(u => u.name);
    const totalDmg = result.log.filter(l => l.includes("造成") && l.includes("点伤害") && !l.includes("[对方]")).length * 50; // rough estimate
    await fetch(`${API}/battles`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: currentPlayer.id, mode: arena.mode, team_mode: arena.teamMode,
        battlefield: result.battlefield, player_team: pTeam, enemy_team: eTeam,
        winner: result.winner, rounds: result.rounds, battle_log: result.log,
        event_count: result.log.filter(l => l.includes("突发情况：")).length,
        total_damage_dealt: totalDmg, total_damage_taken: Math.round(totalDmg * 0.7),
      }),
    });
  } catch (e) { /* silent fail */ }
}

// ── Modal helper ──
function showModal(title, body, okOnly) {
  let overlay = $e("battle-modal-overlay");
  if (!overlay) { overlay = document.createElement("div"); overlay.id = "battle-modal-overlay"; overlay.className = "modal-overlay hidden"; $e("app").appendChild(overlay); }
  overlay.innerHTML = `<div class="modal-card"><h3 style="color:var(--accent);">${title}</h3><div style="flex:1;overflow-y:auto;margin:8px 0 16px;">${body}</div><button class="btn btn-primary btn-block" onclick="document.getElementById('battle-modal-overlay').classList.add('hidden')">${okOnly ? '关闭' : '确定'}</button></div>`;
  overlay.classList.remove("hidden");
}
