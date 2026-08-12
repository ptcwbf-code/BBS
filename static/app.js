/**
 * Beast Arena: Roguelike Survival — UI Controller
 */

let run = null;
let selectedBeast = null;
let enemyTargetIndex = 0;
let gameMode = "land";

// ═══════ Beast Selection ═══════
function renderBeastSelect() {
  const grid = $e("beast-select-grid");
  const search = ($e("beast-search")?.value || "").toLowerCase().trim();
  const filter = document.querySelector("#terrain-filter-group .radio-pill.active")?.dataset.filter || "all";
  let pool = ANIMALS;
  if (filter !== "all") pool = ANIMALS.filter(a => a.habitatTag === filter);
  if (search) pool = pool.filter(a => a.name.includes(search) || a.category.includes(search) || a.era.includes(search) || a.features.includes(search));
  grid.innerHTML = pool.map(a => `
    <div class="beast-option ${selectedBeast === a.name ? 'selected' : ''}" onclick="selectBeast('${a.name.replace(/'/g,"\\'")}')">
      <span style="font-size:1.4rem;">${getIconFor(a)}</span>
      <span class="bo-name">${a.name}</span>
      <span class="bo-cat">${a.category}</span>
    </div>
  `).join("");
  const sel = grid.querySelector(".beast-option.selected");
  if (sel) sel.scrollIntoView({ block: "nearest" });
  renderBeastPreview();
}

function getIconFor(animal) {
  const icons = { "恐龙":"🦖","鲨鱼":"🦈","鲸":"🐋","鳄":"🐊","熊":"🐻","虎":"🐅","狮":"🦁","猫科":"🐆","狼":"🐺","章鱼":"🐙","蛇":"🐍","鹰":"🦅","象":"🐘","猿":"🦍","龟":"🐢","灵长":"🦧","狐":"🦊" };
  for (const [k, v] of Object.entries(icons)) if (animal.category.includes(k) || animal.features.includes(k) || animal.name.includes(k)) return v;
  return animal.habitatTag === "海洋" ? "🐟" : animal.habitatTag === "海陆" ? "🦭" : "🦖";
}

function selectBeast(name) { selectedBeast = name; renderBeastSelect(); }

function renderBeastPreview() {
  const preview = $e("beast-preview");
  if (!selectedBeast) { preview.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px;">👆 选择一只巨兽来查看详情</p>'; return; }
  const a = ANIMALS_BY_NAME[selectedBeast];
  const tk = getBestTerrain(a);
  const p = a.terrains[tk] || { attack:"?",defense:"?",mobility:"?",technique:"?",stamina:"?",stability:"?" };
  const abilities = assignAbilities(a);
  const passive = getPassive(a);
  preview.innerHTML = `
    <div class="preview-header">
      <span class="preview-icon">${getIconFor(a)}</span>
      <div><div class="preview-name">${a.name}</div><div class="preview-sub">${a.category} · ${a.era} · ${a.weightDisplay}</div><div class="preview-sub">${a.features}</div></div>
    </div>
    <div class="preview-stats">
      <div class="preview-stat"><div class="ps-label">攻击</div><div class="ps-value">${p.attack}</div></div>
      <div class="preview-stat"><div class="ps-label">防御</div><div class="ps-value">${p.defense}</div></div>
      <div class="preview-stat"><div class="ps-label">机动</div><div class="ps-value">${p.mobility}</div></div>
      <div class="preview-stat"><div class="ps-label">技巧</div><div class="ps-value">${p.technique}</div></div>
      <div class="preview-stat"><div class="ps-label">续航</div><div class="ps-value">${p.stamina}</div></div>
      <div class="preview-stat"><div class="ps-label">智商</div><div class="ps-value">${a.intelligence}</div></div>
    </div>
    <div class="passive-preview"><span>${passive.icon}</span> <b>${passive.name}</b> — ${passive.desc}</div>
    <div class="ability-preview">${abilities.map(ab => `<span class="ability-tag">${ab.icon} <b>${ab.name}</b></span>`).join("")}</div>
    <button class="select-start-btn" onclick="startGame()">⚔️ 开始生存挑战！</button>
  `;
}

function getBestTerrain(a) {
  if (gameMode === "land" && a.terrains.land) return "land";
  if (gameMode === "near" && a.terrains.near) return "near";
  if (gameMode === "far" && a.terrains.far) return "far";
  for (const tk of ["land","near","far"]) if (a.terrains[tk]) return tk;
  return "land";
}

// ═══════ Start Game ═══════
function startGame() {
  if (!selectedBeast) return;
  $e("select-overlay").classList.add("hidden");
  $e("game-ui").classList.remove("hidden");
  $e("action-bar").classList.remove("hidden");
  const bf = gameMode === "land" ? "陆地" : gameMode === "near" ? "近海" : "远海";
  run = createRun(selectedBeast, bf);
  advanceToNextWave();
  renderGameUI();
}

function advanceToNextWave() {
  run.waveNum++;
  run.waveEnemiesDefeated = 0;
  run.enemies = generateEnemyWave(run.waveNum, run.battlefield);
  run.abilityUsedThisTurn = false;
  run.player.exhaustNext = false;
  run.player.hasActedThisRound = false;
  run.phase = "player_turn";
  enemyTargetIndex = 0;
  addLog(`⚡ === 第 ${run.waveNum} 波 === ⚡`, "event");
  run.enemies.forEach(e => addLog(`👹 ${e.name} LV.${e.level} 出现！（HP ${e.hp}/${e.maxHp}）`, "enemy-action"));
  renderGameUI();
}

// ═══════ Player Actions ═══════
function playerBasicAttack() {
  if (run.phase !== "player_turn") return;
  const target = getTargetEnemy(); if (!target) return;
  const result = run.player.basicAttack(target);
  run.comboCount++;
  const comboBonus = run.itemsBought.includes("combo_charm") ? 0.20 : 0.10;
  run.comboMultiplier = Math.min(3.0, 1 + run.comboCount * comboBonus);
  result.log.forEach(l => addLog(l, "player-action"));
  if (!target.alive) onEnemyKilled(target);
  run.player.hasActedThisRound = true;
  run.abilityUsedThisTurn = false;
  endPlayerTurn();
}

function playerUseAbility(abilityId) {
  if (run.phase !== "player_turn") return;
  const ab = run.player.abilities.find(a => a.id === abilityId);
  if (!ab) return;
  if (run.player.activeCooldowns[abilityId] > 0) return;
  const isAll = ab.target === "all_enemies";
  const targets = isAll ? run.enemies.filter(e => e.alive) : [getTargetEnemy()].filter(Boolean);
  if (!isAll && !targets[0]) return;
  const result = run.player.useAbility(abilityId, targets);
  if (!result) return;
  result.log.forEach(l => addLog(l, "player-action"));
  run.abilityUsedThisTurn = true;
  const checkTargets = isAll ? targets : [targets[0]];
  let killed = false;
  checkTargets.forEach(t => { if (t && !t.alive) { onEnemyKilled(t); killed = true; } });
  if (ab.resetOnKill && killed) { run.player.activeCooldowns[abilityId] = 0; addLog(`🔄 ${ab.name} 冷却已重置！`, "event"); }
  run.player.hasActedThisRound = true;
  endPlayerTurn();
}

function endTurnSkip() {
  if (run.phase !== "player_turn") return;
  addLog("⏭️ 跳过行动，结束回合", "player-action");
  endPlayerTurn();
}

// ═══════ Turn Flow ═══════
function endPlayerTurn() {
  // Tick DOTs on enemies
  for (const enemy of run.enemies) {
    if (!enemy.alive) continue;
    enemy.applyDotDmg();
    for (const l of enemy.combatLog) addLog(l, "enemy-action");
    enemy.combatLog = [];
    if (!enemy.alive) onEnemyKilled(enemy);
  }
  // Player DOTs
  run.player.applyDotDmg();
  for (const l of run.player.combatLog) addLog(l, "player-action");
  run.player.combatLog = [];
  if (!run.player.alive) { handlePlayerDeath(); return; }
  run.player.tickBuffs();
  if (run.enemies.every(e => !e.alive)) { run.phase = "shop"; addLog(`🎉 第 ${run.waveNum} 波清除！`, "event"); renderGameUI(); showShopModal(); return; }
  run.phase = "enemy_turn";
  renderGameUI();
  setTimeout(doEnemyTurn, 600);
}

function doEnemyTurn() {
  if (run.phase !== "enemy_turn") return;
  for (const enemy of run.enemies) {
    if (!enemy.alive) continue;
    if (enemy.stunned > 0) { addLog(`🌀 ${enemy.name} 眩晕无法行动`, "enemy-action"); continue; }
    const avail = enemy.abilities.filter(a => (enemy.activeCooldowns[a.id] || 0) <= 0);
    if (Math.random() < 0.35 && avail.length) {
      const ab = avail[Math.floor(Math.random() * avail.length)];
      const tgt = ab.target === "self" ? [enemy] : [run.player];
      const result = enemy.useAbility(ab.id, tgt);
      if (result) { result.log.forEach(l => addLog(l, "enemy-action")); if (!run.player.alive) { handlePlayerDeath(); return; } }
    } else {
      const result = enemy.basicAttack(run.player);
      if (result) { result.log.forEach(l => addLog(l, "enemy-action")); if (!run.player.alive) { handlePlayerDeath(); return; } }
    }
  }
  // End enemy turn cleanup
  for (const enemy of run.enemies) {
    if (!enemy.alive) continue;
    enemy.tickBuffs();
    enemy.applyDotDmg();
    for (const l of enemy.combatLog) addLog(l, "enemy-action");
    enemy.combatLog = [];
    if (!enemy.alive) onEnemyKilled(enemy);
  }
  run.player.tickBuffs();
  run.player.applyDotDmg();
  for (const l of run.player.combatLog) addLog(l, "player-action");
  run.player.combatLog = [];
  if (!run.player.alive) { handlePlayerDeath(); return; }
  if (run.player.passive.type === "regen") { const regen = Math.round(run.player.maxHp * run.player.passive.value); run.player.heal(regen); }
  // New turn
  run.phase = "player_turn";
  run.comboCount = 0;
  run.comboMultiplier = 1.0;
  run.abilityUsedThisTurn = false;
  run.player.hasActedThisRound = false;
  if (run.player.exhaustNext) {
    addLog(`😴 ${run.player.name} 反噬，本回合无法行动`, "event");
    run.player.exhaustNext = false;
    endPlayerTurn();
    return;
  }
  if (run.enemies.every(e => !e.alive)) { run.phase = "shop"; addLog(`🎉 第 ${run.waveNum} 波清除！`, "event"); renderGameUI(); showShopModal(); return; }
  renderGameUI();
}

function handlePlayerDeath() {
  if (run.itemsBought.includes("revive_charm") && !run.reviveUsed) {
    run.reviveUsed = true;
    run.player.hp = Math.round(run.player.maxHp * 0.5);
    run.player.alive = true;
    addLog("💫 复活护符发动！以50%HP复活！", "event");
    run.phase = "player_turn";
    renderGameUI();
    return;
  }
  run.phase = "defeat"; run.isDead = true; run.isFinished = true;
  addLog(`💀 ${run.player.name} 倒下了……`, "event");
  renderGameUI();
  showResultOverlay();
}

function onEnemyKilled(enemy) {
  run.souls += enemy.soulReward;
  run.totalXP += enemy.xpReward;
  run.totalKills++;
  run.waveEnemiesDefeated++;
  addLog(`🏆 击杀 ${enemy.name}！+${enemy.soulReward}💀 +${enemy.xpReward}⭐`, "kill");
}

function getTargetEnemy() {
  const alive = run.enemies.filter(e => e.alive);
  if (!alive.length) return null;
  if (enemyTargetIndex >= alive.length) enemyTargetIndex = 0;
  return alive[enemyTargetIndex];
}

function selectEnemyTarget(idx) {
  if (run.phase !== "player_turn") return;
  const alive = run.enemies.filter(e => e.alive);
  if (idx >= alive.length) return;
  enemyTargetIndex = idx;
  renderGameUI();
}

// ═══════ Shop ═══════
function showShopModal() {
  const overlay = $e("modal-overlay");
  overlay.classList.remove("hidden");
  overlay.innerHTML = `<div class="modal-card modal-wide"><h2>🛒 灵魂商店</h2>
    <p style="text-align:center;color:var(--text-secondary);">第 ${run.waveNum} 波完成！灵魂：<b style="color:var(--accent);">${run.souls}💀</b></p>
    <div class="shop-items">${SHOP_ITEMS.map(item => {
      const bought = run.itemsBought.includes(item.id);
      return `<div class="shop-item ${bought?'bought':''}" onclick="buyItem('${item.id}')">
        <span class="si-icon">${item.icon}</span><div class="si-info"><div class="si-name">${item.name}</div><div class="si-desc">${item.desc}</div></div>
        <span class="si-cost">${bought?'✓':item.cost+'💀'}</span></div>`;
    }).join("")}</div>
    <button class="btn btn-primary btn-block btn-lg" onclick="closeShopAndContinue()">▶️ 继续下一波</button></div>`;
}

function buyItem(itemId) {
  const item = SHOP_ITEMS.find(i => i.id === itemId);
  if (!item || run.itemsBought.includes(itemId)) return;
  if (run.souls < item.cost) { addLog("💀 灵魂不足！", "event"); return; }
  run.souls -= item.cost; run.itemsBought.push(itemId);
  switch (item.effect) {
    case "heal": run.player.heal(run.player.maxHp * item.value); addLog(`💚 ${item.name}：恢复HP！`, "event"); break;
    case "atkUp": run.player.atk += 1; addLog(`💪 ${item.name}：攻击力+1！`, "event"); break;
    case "defUp": run.player.def += 1; addLog(`🛡️ ${item.name}：防御力+1！`, "event"); break;
    case "mobUp": run.player.mob += 1; addLog(`💨 ${item.name}：机动+1！`, "event"); break;
    case "maxHpUp": const g = Math.round(run.player.maxHp * item.value); run.player.maxHp += g; run.player.hp += g; addLog(`❤️ ${item.name}：最大HP+${g}！`, "event"); break;
    case "critUp": addLog(`👁️ ${item.name}：暴击率提升！`, "event"); break;
    case "comboX2": addLog(`⚡ ${item.name}：连击加成翻倍！`, "event"); break;
    case "revive": addLog(`💫 ${item.name}：获得复活机会！`, "event"); break;
    case "xpBoost": addLog(`📚 ${item.name}：经验+50%！`, "event"); break;
    case "newAbility":
      const pool = Object.values(ABILITY_POOL).filter(a => !run.player.abilities.some(pa => pa.id === a.id));
      if (pool.length) { const na = {...pool[Math.floor(Math.random()*pool.length)]}; run.player.abilities.push(na); addLog(`📜 ${item.name}：学会【${na.name}】！`, "event"); }
      break;
  }
  showShopModal();
}

function closeShopAndContinue() {
  $e("modal-overlay").classList.add("hidden");
  if (Math.random() < 0.30) showRandomEvent();
  else advanceToNextWave();
}

// ═══════ Random Events ═══════
function showRandomEvent() {
  const event = CITADEL_EVENTS[Math.floor(Math.random() * CITADEL_EVENTS.length)];
  run.phase = "event"; renderGameUI();
  const overlay = $e("modal-overlay");
  overlay.classList.remove("hidden");
  overlay.innerHTML = `<div class="modal-card"><h2>${event.icon} ${event.name}</h2>
    <p style="color:var(--text-secondary);margin-bottom:12px;">${event.desc}</p>
    <div class="event-choices">${event.choices.map((c,i) => `<div class="event-choice" onclick="handleEventChoice('${event.id}',${i})"><div>${c.text}</div><div class="ec-result">${c.effect}</div></div>`).join("")}</div></div>`;
}

function handleEventChoice(eventId, choiceIdx) {
  const event = CITADEL_EVENTS.find(e => e.id === eventId); if (!event) return;
  const choice = event.choices[choiceIdx];
  // Check costs
  if (eventId === "ancient_shrine" && choiceIdx === 0 && run.souls < 30) { addLog("💀 灵魂不足30！", "event"); return; }
  if (eventId === "mysterious_merchant" && choiceIdx === 0 && run.souls < 25) { addLog("💀 灵魂不足25！", "event"); return; }
  if (eventId === "mysterious_merchant" && choiceIdx === 1 && run.souls < 10) { addLog("💀 灵魂不足10！", "event"); return; }
  // Apply
  const result = choice.apply(run.player);
  if (eventId === "ancient_shrine" && choiceIdx === 0) run.souls -= 30;
  if (eventId === "mysterious_merchant" && choiceIdx === 0) run.souls -= 25;
  if (eventId === "mysterious_merchant" && choiceIdx === 1) { run.souls -= 10; run.souls += 20; run.totalXP += 50; }
  addLog(`❓ ${result}`, "event");
  run.eventsTriggered++;
  $e("modal-overlay").classList.add("hidden");
  if (choice.result === "fight") { const extras = generateEnemyWave(run.waveNum, run.battlefield); run.enemies.push(...extras); addLog(`⚔️ 护卫出现！+${extras.length}敌人！`, "event"); }
  advanceToNextWave();
}

// ═══════ Result ═══════
function showResultOverlay() {
  const overlay = $e("result-overlay");
  overlay.classList.remove("hidden");
  const won = run.phase === "victory";
  overlay.innerHTML = `<div class="result-card">
    <div class="result-icon">${won?'🏆':'💀'}</div><h1>${won?'胜利！':'阵亡'}</h1>
    <p style="color:var(--text-secondary);">抵达第 ${run.waveNum} 波</p>
    <div class="result-stats">
      <div class="result-stat"><div class="rs-val">${run.waveNum}</div><div class="rs-lbl">通关波数</div></div>
      <div class="result-stat"><div class="rs-val">${run.totalKills}</div><div class="rs-lbl">击杀数</div></div>
      <div class="result-stat"><div class="rs-val">${run.souls}</div><div class="rs-lbl">灵魂</div></div>
    </div>
    <div class="result-stats">
      <div class="result-stat"><div class="rs-val">⭐${run.totalXP}</div><div class="rs-lbl">经验</div></div>
      <div class="result-stat"><div class="rs-val">🛒${run.itemsBought.length}</div><div class="rs-lbl">道具</div></div>
      <div class="result-stat"><div class="rs-val">❓${run.eventsTriggered}</div><div class="rs-lbl">事件</div></div>
    </div>
    <div class="result-buttons">
      <button class="btn btn-primary btn-lg" onclick="restartGame()">🔁 再来一局</button>
      <button class="btn btn-lg" onclick="backToSelect()">🦖 换巨兽</button>
    </div></div>`;
}

function restartGame() { $e("result-overlay").classList.add("hidden"); run = createRun(selectedBeast, run.battlefield); advanceToNextWave(); renderGameUI(); }
function backToSelect() { $e("result-overlay").classList.add("hidden"); $e("game-ui").classList.add("hidden"); $e("action-bar").classList.add("hidden"); $e("select-overlay").classList.remove("hidden"); run = null; renderBeastSelect(); }

// ═══════ Render ═══════
function renderGameUI() {
  if (!run) return;
  const p = run.player;
  $e("player-icon").textContent = getIconFor(p.animal);
  $e("player-name").textContent = p.name;
  $e("player-level").textContent = `LV.${p.level}`;
  const hpPct = Math.max(0, (p.hp / p.maxHp) * 100);
  $e("player-hp-bar").style.width = hpPct + "%";
  if (hpPct < 30) $e("player-hp-bar").style.background = "linear-gradient(90deg,#f87171,#ef4444)";
  else if (hpPct < 60) $e("player-hp-bar").style.background = "linear-gradient(90deg,#fbbf24,#f59e0b)";
  else $e("player-hp-bar").style.background = "linear-gradient(90deg,#4ade80,#22c55e)";
  $e("player-hp-text").textContent = `${p.hp}/${p.maxHp}`;
  $e("player-shield-bar").style.width = (p.shield / Math.max(1, p.maxHp) * 100) + "%";

  $e("player-stats").innerHTML = `
    <div class="stat-chip"><div class="sc-val">${p.atk.toFixed(1)}</div><div class="sc-lbl">攻击</div></div>
    <div class="stat-chip"><div class="sc-val">${p.def.toFixed(1)}</div><div class="sc-lbl">防御</div></div>
    <div class="stat-chip"><div class="sc-val">${p.mob.toFixed(1)}</div><div class="sc-lbl">机动</div></div>
    <div class="stat-chip"><div class="sc-val">${p.tec.toFixed(1)}</div><div class="sc-lbl">技巧</div></div>`;

  $e("combo-fill").style.width = (run.comboMultiplier / 3 * 100) + "%";
  $e("combo-count").textContent = run.comboMultiplier.toFixed(1) + "x";

  const buffs = p.statusEffects.map(e => `<span class="buff-tag ${e.delta<0?'debuff':''}">${e.delta<0?'⬇':'⬆'}${e.label}(${e.rounds})</span>`).join("");
  $e("player-buffs").innerHTML = buffs || `<span class="buff-tag">${p.passive.icon} ${p.passive.name}</span>`;

  $e("phase-label").textContent = runPhaseLabel(run.phase);
  $e("phase-icon").textContent = run.phase === "player_turn" ? "⚔️" : run.phase === "enemy_turn" ? "👹" : run.phase === "shop" ? "🛒" : "🔮";
  $e("soul-display").textContent = `💀 ${run.souls}`;
  $e("xp-display").textContent = `⭐ ${run.totalXP}`;

  $e("enemy-cards").innerHTML = run.enemies.map((e, i) => `
    <div class="enemy-card ${i === enemyTargetIndex && run.phase==='player_turn' ? 'targeted' : ''} ${!e.alive?'dead':''}" onclick="selectEnemyTarget(${i})">
      <div class="ec-header"><span class="ec-icon">${getIconFor(e.animal)}</span><div><div class="ec-name">${e.name}</div><div class="ec-level">LV.${e.level}</div></div></div>
      <div class="ec-hp-bar"><div class="ec-hp-fill" style="width:${Math.max(0,(e.hp/e.maxHp)*100)}%"></div></div>
      <div style="font-size:0.7rem;color:var(--text-muted);">${e.hp}/${e.maxHp} ${e.stunned>0?'🌀眩晕':''}</div>
    </div>`).join("");

  renderActionBar();
}

function renderActionBar() {
  const isPT = run.phase === "player_turn";
  const p = run.player;
  $e("actions-inner").innerHTML = `
    <div class="action-btn primary" onclick="${isPT?'playerBasicAttack()':''}" style="${!isPT?'pointer-events:none;opacity:0.5':''}">
      <span class="ab-icon">⚔️</span><span class="ab-name">攻击</span><span class="ab-cd">基础</span>
    </div>
    ${p.abilities.map(ab => {
      const cd = p.activeCooldowns[ab.id] || 0;
      const disabled = !isPT || cd > 0;
      return `<div class="action-btn ${disabled?'on-cooldown':''}" onclick="${disabled?'':`playerUseAbility('${ab.id}')`}">
        <span class="ab-icon">${ab.icon}</span><span class="ab-name">${ab.name}</span>
        <span class="ab-cd">${cd>0?`冷却${cd}回合`:`${ab.cooldown}回合CD`}</span></div>`;
    }).join("")}
    <div class="action-btn" onclick="${isPT?'endTurnSkip()':''}" style="${!isPT?'pointer-events:none;opacity:0.5':''}">
      <span class="ab-icon">⏭️</span><span class="ab-name">跳过</span>
    </div>`;
}

// ═══════ Log ═══════
function addLog(msg, cls) {
  if (!run) return;
  run.combatLog.push({msg,cls});
  const inner = $e("battle-log-inner");
  if (!inner) return;
  const d = document.createElement("div");
  d.className = `log-entry ${cls||""}`;
  d.textContent = msg;
  inner.appendChild(d);
  inner.scrollTop = inner.scrollHeight;
}

// ═══════ Init ═══════
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#terrain-filter-group .radio-pill").forEach(b => {
    b.addEventListener("click", () => {
      document.querySelectorAll("#terrain-filter-group .radio-pill").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      renderBeastSelect();
    });
  });
  $e("beast-search")?.addEventListener("input", () => renderBeastSelect());
  try { initParticlesSimple(); } catch(e) {}
  renderBeastSelect();
});

function initParticlesSimple() {
  const c = document.getElementById("particles-canvas");
  if (!c || typeof c.getContext !== "function") return;
  c.width = window.innerWidth; c.height = window.innerHeight;
  const ctx = c.getContext("2d");
  const ps = [];
  for (let i = 0; i < 50; i++) ps.push({x:Math.random()*c.width,y:Math.random()*c.height,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3,size:Math.random()*2+0.5,opacity:Math.random()*0.4+0.1});
  (function A(){ctx.clearRect(0,0,c.width,c.height);ps.forEach(p=>{p.x+=p.vx;p.y+=p.vy;if(p.x<0)p.x=c.width;if(p.x>c.width)p.x=0;if(p.y<0)p.y=c.height;if(p.y>c.height)p.y=0;ctx.beginPath();ctx.arc(p.x,p.y,p.size,0,Math.PI*2);ctx.fillStyle=`rgba(242,193,78,${p.opacity})`;ctx.fill();});
    for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){const dx=ps[i].x-ps[j].x,dy=ps[i].y-ps[j].y,dist=Math.sqrt(dx*dx+dy*dy);if(dist<100){ctx.beginPath();ctx.moveTo(ps[i].x,ps[i].y);ctx.lineTo(ps[j].x,ps[j].y);ctx.strokeStyle=`rgba(242,193,78,${0.05*(1-dist/100)})`;ctx.lineWidth=0.5;ctx.stroke();}}requestAnimationFrame(A);})();
}

function $e(id) { return document.getElementById(id); }
