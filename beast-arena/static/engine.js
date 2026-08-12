// beast-arena/static/engine.js
// ── Numerical system & battle engine (ported from original Python battle_engine.py) ──

const GRADE_MAP = {
  "S+": 10.0, "S": 9.5, "S-": 9.0,
  "A+": 8.5, "A": 8.0, "A-": 7.5,
  "B+": 7.0, "B": 6.5, "B-": 6.0,
  "C+": 5.5, "C": 5.0, "C-": 4.5,
  "D+": 4.0, "D": 3.5, "D-": 3.0,
  "E": 2.0,
};
const GRADE_SEQUENCE = ["S+","S","S-","A+","A","A-","B+","B","B-","C+","C","C-","D+","D","D-","E"];

function gradeValue(letter) { return GRADE_MAP.hasOwnProperty(letter) ? GRADE_MAP[letter] : 5.0; }

function downgradeGrade(letter, steps = 1) {
  const idx = GRADE_SEQUENCE.indexOf(letter);
  if (idx === -1) return letter;
  return GRADE_SEQUENCE[Math.min(idx + steps, GRADE_SEQUENCE.length - 1)];
}

const STAT_KEYS = ["attack", "defense", "mobility", "technique", "stamina", "intelligence"];
const STAT_LABELS = { attack: "攻击", defense: "防御", mobility: "机动", technique: "技巧", stamina: "续航", intelligence: "智商" };
const TERRAIN_LABELS = { land: "陆地", near: "近海", far: "远海" };

const BATTLEFIELD_LAND = "陆地", BATTLEFIELD_NEAR = "近海", BATTLEFIELD_FAR = "远海";
const BATTLEFIELDS = [BATTLEFIELD_LAND, BATTLEFIELD_NEAR, BATTLEFIELD_FAR];
const TERRAIN_BY_BATTLEFIELD = { [BATTLEFIELD_LAND]: "land", [BATTLEFIELD_NEAR]: "near", [BATTLEFIELD_FAR]: "far" };

const MAX_ROUNDS = 30;

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function terrainProfile(animal, terrainKey) { return animal.terrains[terrainKey]; }
function availableTerrains(animal) { return ["land", "near", "far"].filter(t => animal.terrains[t] !== null); }
function animalCanFightHere(animal, battlefield) { return terrainProfile(animal, TERRAIN_BY_BATTLEFIELD[battlefield]) !== null; }

function avgWeightKg(animal) { return (animal.weightMinKg + animal.weightMaxKg) / 2.0; }
function isHeavy(animal) { return avgWeightKg(animal) > 1000.0; }
function maxHeavyAllowed(teamSize, modeKey) { return modeKey === "1v1" ? teamSize : Math.floor(teamSize / 2); }

function animalAvgStability(animal) {
  const vals = ["land", "near", "far"].map(t => animal.terrains[t]).filter(p => p !== null).map(p => p.stability);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0.0;
}
function teamStabilitySum(starters) { return starters.reduce((s, a) => s + animalAvgStability(a), 0); }
function teamTotalWeight(starters) { return starters.reduce((s, a) => s + avgWeightKg(a), 0); }

const ENDOTHERM_CATEGORIES = new Set([
  "兽脚类恐龙", "翼手龙类", "哺乳动物", "有袋形类/近缘", "剑齿虎类",
  "大型猫科", "有袋类捕食者", "熊科", "灵长类", "食肉目", "猛禽",
  "齿鲸", "原始鲸类", "现代鲸类", "鳍脚类", "海狮",
]);
function isEctotherm(animal) { return !ENDOTHERM_CATEGORIES.has(animal.category); }

const STANCES = {
  normal:    { label: "常规", outDmgMult: 1.00, inDmgMult: 1.00, defMult: 1.00, mobMult: 1.00 },
  berserk:   { label: "狂暴", outDmgMult: 1.25, inDmgMult: 1.00, defMult: 0.85, mobMult: 1.00 },
  hold:      { label: "坚守", outDmgMult: 0.85, inDmgMult: 0.75, defMult: 1.00, mobMult: 0.90 },
  guerrilla: { label: "游击", outDmgMult: 1.10, inDmgMult: 1.00, defMult: 0.95, mobMult: 1.40 },
};
const STANCE_KEYS = ["normal", "berserk", "hold", "guerrilla"];

function unitTag(unit) {
  const side = unit.side === "player" ? "[我方]" : "[对方]";
  const stance = (unit.stance && unit.stance !== "normal") ? `［${STANCES[unit.stance].label}］` : "";
  return `${side}${unit.name}${stance}`;
}

// ── BattleUnit ──
class BattleUnit {
  constructor(animal, side, battlefield, downgradeSteps = 0) {
    this.animal = animal;
    this.side = side;
    this.name = animal.name;
    this.isSubstitute = downgradeSteps > 0;

    const terrainKey = TERRAIN_BY_BATTLEFIELD[battlefield];
    let profile = terrainProfile(animal, terrainKey);

    this.deadByEnvironment = profile === null;
    this.environmentNote = "";
    if (this.deadByEnvironment) {
      this.environmentNote = `${animal.name} 无法适应【${battlefield}】环境，开局即被判定环境淘汰。`;
      profile = { attack: "E", defense: "E", mobility: "E", technique: "E", stamina: "E", stability: 0.5 };
    }

    const g = (letter) => gradeValue(downgradeSteps ? downgradeGrade(letter, downgradeSteps) : letter);

    this.baseStats = {
      attack: g(profile.attack), defense: g(profile.defense), mobility: g(profile.mobility),
      technique: g(profile.technique), stamina: g(profile.stamina),
      intelligence: gradeValue(animal.intelligence),
    };
    this.stability = profile.stability;

    const weightKg = avgWeightKg(animal);
    const baseHp = 65 + Math.sqrt(weightKg) * 2.6;
    const extraHp = baseHp * (this.baseStats.defense - 3) * 0.12;
    this.maxHp = Math.round(clamp(baseHp + extraHp, 100, 15000));
    this.hp = this.maxHp;

    this.roundMods = Object.fromEntries(STAT_KEYS.map(k => [k, 0.0]));
    this.stunnedRounds = 0;
    this.statusEffects = [];
    this.dots = [];
    this.hitPenaltyEffects = [];

    this.observedNextAttackCrit = false;
    this.observedNextDefenseCrit = false;

    this.stance = "normal";
    this.row = "front";

    this.alive = !this.deadByEnvironment;
    if (this.deadByEnvironment) this.hp = 0;
  }

  clearRoundMods() { this.roundMods = Object.fromEntries(STAT_KEYS.map(k => [k, 0.0])); }

  effStat(key) {
    let v = this.baseStats[key] + this.roundMods[key];
    for (const e of this.statusEffects) if (e.stat === key) v += e.delta;
    const stance = STANCES[this.stance] || STANCES.normal;
    if (key === "defense") v *= stance.defMult;
    if (key === "mobility") v *= stance.mobMult;
    return clamp(v, 0.5, 14.0);
  }

  effStability() { return clamp(this.stability, 0.2, 1.3); }

  addStatusEffect(stat, delta, rounds, label = "") { this.statusEffects.push({ stat, delta, rounds, label }); }
  addHitPenalty(amount, rounds, label = "") { this.hitPenaltyEffects.push({ delta: amount, rounds, label }); }

  hitPenalty() { return clamp(this.hitPenaltyEffects.reduce((s, e) => s + e.delta, 0), 0.0, 0.9); }

  tickStatus() {
    this.statusEffects.forEach(e => e.rounds -= 1);
    this.statusEffects = this.statusEffects.filter(e => e.rounds > 0);
    this.hitPenaltyEffects.forEach(e => e.rounds -= 1);
    this.hitPenaltyEffects = this.hitPenaltyEffects.filter(e => e.rounds > 0);
    if (this.stunnedRounds > 0) this.stunnedRounds -= 1;
  }

  passiveReduction() {
    const d = this.effStat("defense");
    if (d >= 9.0) return 0.80;
    if (d >= 7.5) return 0.88;
    return 1.0;
  }

  takeDamage(dmg) {
    this.hp = Math.max(0, this.hp - Math.max(0, Math.round(dmg)));
    if (this.hp <= 0) this.alive = false;
  }

  hpRatio() { return this.maxHp ? this.hp / this.maxHp : 0.0; }

  snapshot() {
    return { hp: this.hp, alive: this.alive, statusEffects: this.statusEffects.map(e => ({...e})), dots: this.dots.map(e => ({...e})), hitPenaltyEffects: this.hitPenaltyEffects.map(e => ({...e})), stunnedRounds: this.stunnedRounds };
  }
  restore(snap) {
    this.hp = snap.hp; this.alive = snap.alive;
    this.statusEffects = snap.statusEffects.map(e => ({...e}));
    this.dots = snap.dots.map(e => ({...e}));
    this.hitPenaltyEffects = snap.hitPenaltyEffects.map(e => ({...e}));
    this.stunnedRounds = snap.stunnedRounds;
  }
}

function applyEnvironmentalDamage(unit, amount, ignorePassive = false) {
  const dmg = ignorePassive ? amount : amount * unit.passiveReduction();
  const rounded = Math.max(0, Math.round(dmg));
  unit.takeDamage(rounded);
  return rounded;
}

// ── Attack resolution ──
function resolveAttack(attacker, defender, rng, log) {
  const atk = attacker.effStat("attack");
  const df = defender.effStat("defense");
  const mobA = attacker.effStat("mobility");
  const mobD = defender.effStat("mobility");
  const tecA = attacker.effStat("technique");
  const tecD = defender.effStat("technique");
  const intA = attacker.effStat("intelligence");
  const intD = defender.effStat("intelligence");

  let mobilityMultiplier, dodgeRate;
  if (mobA > mobD) { mobilityMultiplier = 1 + (mobA - mobD) * 0.05; dodgeRate = 0.0; }
  else { mobilityMultiplier = 1.0; dodgeRate = Math.min((mobD - mobA) * 0.02, 0.3); }

  const extraMiss = attacker.hitPenalty();
  const combinedMiss = 1 - (1 - dodgeRate) * (1 - extraMiss);
  if (rng() < combinedMiss) {
    log.push(`💨 ${unitTag(attacker)} 发起攻击，但被 ${unitTag(defender)} 躲开了！`);
    return 0;
  }

  const vitalRate = clamp(Math.max(0.0, intA - intD) * 0.02, 0.0, 0.9);
  const isVital = rng() < vitalRate;
  const effectiveDef = isVital ? df * 0.7 : df;

  let dmg = atk ** 2 - (effectiveDef ** 2) * 0.5;
  if (dmg < 0) dmg = atk * 0.8;

  dmg *= mobilityMultiplier;

  const critRate = clamp(Math.max(0.0, tecA - tecD) * 0.05, 0.0, 0.9);
  const blockRate = clamp(Math.max(0.0, tecD - tecA) * 0.05, 0.0, 0.9);
  let isCrit = rng() < critRate;
  if (attacker.observedNextAttackCrit) { isCrit = true; attacker.observedNextAttackCrit = false; }
  if (defender.observedNextDefenseCrit) { isCrit = true; defender.observedNextDefenseCrit = false; }
  const isBlock = !isCrit && rng() < blockRate;

  if (isCrit) dmg *= 1.5;
  if (isBlock) dmg *= 0.5;
  if (isVital) dmg *= 2.0;

  const stab = attacker.effStability();
  const lo = 0.85 + stab * 0.3, hi = 1.15 - stab * 0.3;
  dmg *= (lo + rng() * (hi - lo));

  dmg *= defender.passiveReduction();
  dmg *= (STANCES[attacker.stance] || STANCES.normal).outDmgMult;
  dmg *= (STANCES[defender.stance] || STANCES.normal).inDmgMult;

  dmg = Math.max(1, Math.round(dmg));
  defender.takeDamage(dmg);

  const tags = (isVital ? "🎯要害" : "") + (isCrit ? "💥暴击" : "") + (isBlock ? "🛡格挡" : "");
  log.push(`⚔️${tags} ${unitTag(attacker)} 攻击 ${unitTag(defender)}，造成 ${dmg} 点伤害（${defender.name} 剩余HP ${defender.hp}/${defender.maxHp}）`);
  if (!defender.alive) log.push(`☠️ ${unitTag(defender)} 倒下，退出战斗！`);
  return dmg;
}

// ── Utility ──
function pickOne(rng, arr) { return arr[Math.floor(rng() * arr.length)]; }
function sampleN(rng, arr, k) {
  const pool = arr.slice(); const out = []; k = Math.min(k, pool.length);
  for (let i = 0; i < k; i++) { const idx = Math.floor(rng() * pool.length); out.push(pool.splice(idx, 1)[0]); }
  return out;
}
function weightedChoice(rng, items, weightFn) {
  const weights = items.map(weightFn); const total = weights.reduce((a, b) => a + b, 0);
  let r = rng() * total; for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r <= 0) return items[i]; }
  return items[items.length - 1];
}

// ── Events ──
function eventMeteor(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("☄️【陨石撞击】长空骤然裂开一道炽白的伤口，燃烧的天外碎屑拖着火尾坠落——仿佛六千六百万年前那场终结了一个时代的天火，正不由分说地重演。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const dmg = 160 + avgWeightKg(u.animal) * 0.004;
    const applied = applyEnvironmentalDamage(u, dmg);
    log.push(`    - ${unitTag(u)} 受到 ${applied} 点撞击伤害（剩余HP ${u.hp}/${u.maxHp}）`);
    if (!u.alive) log.push(`    - ☠️ ${unitTag(u)} 未能撑过这次撞击。`);
  }
  for (const u of [...playerUnits, ...enemyUnits]) if (u.alive) u.addHitPenalty(0.30, 1, "尘埃蔽日");
  return { skipCombat: false };
}

function eventFlood(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🌊【暴洪/海啸】远方传来低沉的轰鸣，一堵墙般的巨浪毫无预兆地扑向战场，仿佛大海终于想起了自己远比陆地古老。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const tag = u.animal.habitatTag;
    if (tag === "海陆") {
      if (u.effStability() < 0.9) { u.hp = 0; u.alive = false; log.push(`    - 💀 ${unitTag(u)}（水陆两栖，稳定性不足）被巨浪卷走，直接淘汰！`); }
      else { log.push(`    - ${unitTag(u)}（水陆两栖）稳住了身形，安然无恙。`); }
    } else if (tag === "海洋") {
      u.addStatusEffect("mobility", -0.5, 2, "海啸冲击");
      log.push(`    - ${unitTag(u)}（纯水生）机动性下降1级，持续2回合。`);
    }
  }
  return { skipCombat: false };
}

function eventIceAge(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🥶【冰期骤降】气温毫无征兆地骤然滑落，呼出的气息瞬间凝成白雾——寒潮如同一位耐心的猎手，专挑那些依赖阳光续命的躯体下手。");
  let anyHit = false;
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    if (isEctotherm(u.animal)) {
      u.addStatusEffect("attack", -0.5, 3, "冰期骤降");
      u.addStatusEffect("mobility", -0.5, 3, "冰期骤降");
      log.push(`    - ${unitTag(u)}（变温动物）攻击/机动下降1级，持续3回合。`);
      anyHit = true;
    }
  }
  if (!anyHit) log.push("    场上皆为恒温动物，未受影响。");
  return { skipCombat: false };
}

function eventVolcano(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🌋【海底火山喷发】海床深处轰然裂开，滚烫的岩浆混着蒸汽狂涌而出，将幽暗的深海短暂地照亮成地狱般的橙红色。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const applied = applyEnvironmentalDamage(u, 120);
    log.push(`    - ${unitTag(u)} 受到 ${applied} 点熔岩灼伤（剩余HP ${u.hp}/${u.maxHp}）`);
    if (u.alive) { const dotAmount = u.effStat("defense") * 4; u.dots.push({ amount: dotAmount, rounds: 2, label: "沸腾" }); }
  }
  return { skipCombat: false };
}

function eventFallingTree(playerUnits, enemyUnits, battlefield, rng, log) {
  const alive = [...playerUnits, ...enemyUnits].filter(u => u.alive);
  if (!alive.length) return { skipCombat: false };
  const victim = pickOne(rng, alive);
  const dmg = Math.max(80, Math.round(victim.maxHp * 0.15));
  const applied = applyEnvironmentalDamage(victim, dmg);
  if (victim.alive) victim.stunnedRounds = Math.max(victim.stunnedRounds, 1);
  log.push(`🌳【巨树倾倒】没有一丝风声预警，一棵见证过无数季节轮回的参天巨树轰然倒下，不偏不倚地压中了 ${unitTag(victim)}——命运有时就是这样，毫无道理可言。受到 ${applied} 点伤害（剩余HP ${victim.hp}/${victim.maxHp}），并陷入昏迷（下回合无法行动）。`);
  return { skipCombat: false };
}

function eventWhale(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🐋【蓝鲸巡游】一道庞大的青灰色身影自远方悠然游来，低沉悠远的歌声穿透水层，尾流所过之处，连杀意都被抚平成了粼粼波光。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const heal = Math.round(u.maxHp * 0.05);
    u.hp = Math.min(u.maxHp, u.hp + heal);
    log.push(`    - ${unitTag(u)} 恢复 ${heal} 点HP（当前 ${u.hp}/${u.maxHp}）`);
  }
  log.push("    双方本回合心神宁静，无法发起攻击。");
  return { skipCombat: true };
}

function eventArgentinosaurus(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🦕【阿根廷龙迁徙】地平线上扬起漫天尘土，一列如山峦移动般的巨大身影正踏过战场边缘，每一步都让大地发出沉闷的呻吟。");
  const alive = [...playerUnits, ...enemyUnits].filter(u => u.alive);
  if (!alive.length) return { skipCombat: false };
  const k = Math.min(alive.length, Math.floor(rng() * Math.max(1, Math.floor(alive.length / 2))) + 1);
  const targets = sampleN(rng, alive, k);
  for (const u of targets) {
    const hasPassive = u.effStat("defense") >= 7.5;
    const dmg = hasPassive ? 80 : 160;
    u.takeDamage(dmg);
    const tag = hasPassive ? "（坚韧/重甲减半）" : "";
    log.push(`    - ${unitTag(u)} 被踏中，受到 ${dmg} 点践踏伤害${tag}（剩余HP ${u.hp}/${u.maxHp}）`);
    if (u.alive) u.addStatusEffect("mobility", -0.5, 1, "震地");
    else log.push(`    - ☠️ ${unitTag(u)} 被巨兽踏平，当场死亡！`);
  }
  return { skipCombat: false };
}

function eventHumans(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🏹【早期智人偶遇】几个手持木棍的身影，误入这片属于巨兽的战场。此刻的他们，渺小得不值一提。数百万年后，他们的后裔却将统治这颗星球。可现在——木棍无法伤及大多数巨兽分毫。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const d = u.effStat("defense");
    if (d <= 4.5) {
      const dmg = Math.max(0, Math.round((5 - d) * 16));
      const applied = applyEnvironmentalDamage(u, dmg);
      log.push(`    - 唯独 ${unitTag(u)} 身形单薄……被戳中了要害，受到 ${applied} 点伤害（剩余HP ${u.hp}/${u.maxHp}）`);
    }
  }
  log.push("他们倒下。战斗继续。关于未来的事，它们不会知道。他们也不会知道。");
  return { skipCombat: false };
}

function eventBomb(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("💣【现代兵器误射】一声突兀的爆响撕裂了亘古的宁静，一枚不属于这个时代的重型航弹轰然引爆，仿佛未来的某个错误，不小心投影回了过去。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const applied = applyEnvironmentalDamage(u, 200);
    log.push(`    - ${unitTag(u)} 受到 ${applied} 点爆炸冲击（剩余HP ${u.hp}/${u.maxHp}）`);
    if (u.alive) u.addStatusEffect("mobility", -0.5, 2, "冲击波");
    else log.push(`    - ☠️ ${unitTag(u)} 未能幸免。`);
  }
  return { skipCombat: false };
}

function eventNuke(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("☢️【真正的毁灭武器】一颗小型太阳，在战场中心升起。它来自未来。它迟到了数千万年。也早到了数千万年。一群智人的后裔终于掌握了恒星的力量。然后，他们发现——最危险的敌人，从来不是别的生命。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    u.takeDamage(1600);
    if (!u.alive) log.push(`    - ☠️ ${unitTag(u)} 在爆炸中化为灰烬。`);
    else log.push(`    - ${unitTag(u)} 奇迹般地扛住了这一击！（剩余HP ${u.hp}/${u.maxHp}）`);
  }
  return { skipCombat: false };
}

function eventFossilResonance(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🦴【化石共鸣】地底深处，某些沉睡了亿万年的骨骼突然轻轻震颤，仿佛远古的血脉隔着时间长河，向后代低声传递了一丝力量。");
  for (const units of [playerUnits, enemyUnits]) {
    const alive = units.filter(u => u.alive); if (!alive.length) continue;
    const chosen = pickOne(rng, alive);
    chosen.addStatusEffect("attack", 0.5, 2, "先祖之力");
    chosen.addStatusEffect("defense", 0.5, 2, "先祖之力");
    log.push(`    - ${unitTag(chosen)} 获得【先祖之力】：攻击/防御提升1级，持续2回合！`);
  }
  return { skipCombat: false };
}

function eventMuseum(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🏛️【博物馆之夜】战场景象忽然定格又扭曲，所有生物眨眼间变成了展柜里的骨架模型，滑稽地互相推搡起来，像是谁不小心按错了时间的开关。");
  for (const u of [...playerUnits, ...enemyUnits]) {
    if (!u.alive) continue;
    const heal = Math.round(u.maxHp * 0.10);
    u.hp = Math.min(u.maxHp, u.hp + heal);
    log.push(`    - ${unitTag(u)} 恢复 ${heal} 点HP（当前 ${u.hp}/${u.maxHp}）`);
  }
  log.push("    本回合双方都放下了杀意，没有发生真正的战斗。");
  return { skipCombat: true };
}

function eventTimeFold(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("🌀【时间褶皱】战场边缘泛起水波般的涟漪，时间本身仿佛被悄悄揉皱——一切正朝着某个已经发生过的瞬间，缓缓坍缩回流。所有单位的状态被拨回到第3回合开始时。");
  return { skipCombat: true, timeFoldToRound: 3 };
}

function eventObserver(playerUnits, enemyUnits, battlefield, rng, log) {
  log.push("👁️【观测者之眼】亿万年的演化，让它们抵达此处。亿万年的时间，让你站在彼端。巨影回首。你看见了它。它也看见了你。在它眼中，你来自未来。在你眼中，它来自远古。可在时间面前，皆不过一瞬。");
  for (const u of [...playerUnits, ...enemyUnits]) { if (!u.alive) continue; u.observedNextAttackCrit = true; u.observedNextDefenseCrit = true; }
  log.push("    全场单位都进入了【被观测】状态。");
  return { skipCombat: false };
}

const EVENT_CATEGORIES = [
  { name: "环境剧变", weight: 40, events: [
    { name: "陨石撞击", weight: 4, battlefields: null, fn: eventMeteor },
    { name: "暴洪/海啸", weight: 10, battlefields: ["near", "far"], fn: eventFlood },
    { name: "冰期骤降", weight: 8, battlefields: null, fn: eventIceAge },
    { name: "海底火山喷发", weight: 14, battlefields: ["far"], fn: eventVolcano },
    { name: "巨树倾倒", weight: 14, battlefields: ["land"], fn: eventFallingTree },
  ]},
  { name: "生物介入", weight: 30, events: [
    { name: "蓝鲸巡游", weight: 4, battlefields: ["near", "far"], fn: eventWhale },
    { name: "阿根廷龙迁徙", weight: 12, battlefields: ["land"], fn: eventArgentinosaurus },
    { name: "早期智人偶遇", weight: 9, battlefields: ["land", "near"], fn: eventHumans },
  ]},
  { name: "神秘力量与未来残片", weight: 20, events: [
    { name: "现代兵器误射", weight: 20, battlefields: ["land"], fn: eventBomb },
    { name: "真正的毁灭武器", weight: 1, battlefields: null, fn: eventNuke },
    { name: "化石共鸣", weight: 5, battlefields: null, fn: eventFossilResonance },
  ]},
  { name: "哲思彩蛋", weight: 10, events: [
    { name: "博物馆之夜", weight: 5, battlefields: null, fn: eventMuseum },
    { name: "时间褶皱", weight: 3, battlefields: null, fn: eventTimeFold },
    { name: "观测者之眼", weight: 2, battlefields: null, fn: eventObserver },
  ]},
];

function eventsAvailableHere(events, terrainKey, disableTimeFold) {
  return events.filter(e => { if (e.battlefields !== null && !e.battlefields.includes(terrainKey)) return false; if (disableTimeFold && e.fn === eventTimeFold) return false; return true; });
}

function pickEvent(battlefield, rng, ctx) {
  const terrainKey = TERRAIN_BY_BATTLEFIELD[battlefield];
  const cat = weightedChoice(rng, EVENT_CATEGORIES, c => c.weight);
  let available = eventsAvailableHere(cat.events, terrainKey, ctx && ctx.disableTimeFold);
  if (!available.length) { const allEvents = EVENT_CATEGORIES.flatMap(c => c.events); available = eventsAvailableHere(allEvents, terrainKey, ctx && ctx.disableTimeFold); }
  return weightedChoice(rng, available, e => e.weight);
}

function maybeTriggerEvent(playerUnits, enemyUnits, battlefield, rng, log, ctx, triggerChance) {
  if (rng() >= triggerChance) return null;
  const event = pickEvent(battlefield, rng, ctx);
  log.push(`\n🌟🌟🌟 突发情况：${event.name} 🌟🌟🌟`);
  const result = event.fn(playerUnits, enemyUnits, battlefield, rng, log);
  log.push("🌟🌟🌟 突发情况结算完毕 🌟🌟🌟");
  result.eventName = event.name;
  return result;
}

// ── Round resolution ──
function pickTarget(attacker, enemyUnits, rng) {
  const aliveEnemies = enemyUnits.filter(e => e.alive);
  if (!aliveEnemies.length) return null;
  const frontAlive = aliveEnemies.filter(e => e.row !== "back");
  const pool = frontAlive.length ? frontAlive : aliveEnemies;
  const intel = attacker.effStat("intelligence");
  if (intel >= 7.5 && rng() < 0.6) { return pool.reduce((best, e) => (e.hpRatio() < best.hpRatio() ? e : best)); }
  return pickOne(rng, pool);
}

function applyDots(units, log) {
  for (const u of units) {
    if (!u.alive || !u.dots.length) continue;
    for (const dot of [...u.dots]) {
      const applied = applyEnvironmentalDamage(u, dot.amount);
      log.push(`🔥 ${u.name} 受到【${dot.label}】持续伤害 ${applied} 点（剩余HP ${u.hp}/${u.maxHp}）`);
      if (!u.alive) { log.push(`    - ☠️ ${u.name} 因【${dot.label}】伤重不治。`); break; }
    }
  }
}

function runRound(roundNo, playerUnits, enemyUnits, battlefield, rng, log, ctx, eventChance) {
  const allUnits = [...playerUnits, ...enemyUnits];
  for (const u of allUnits) u.clearRoundMods();
  log.push(`\n───────── 第 ${roundNo} 回合 ─────────`);

  let timeFoldTarget = null;
  const eventResult = maybeTriggerEvent(playerUnits, enemyUnits, battlefield, rng, log, ctx, eventChance);
  const skipCombat = !!(eventResult && eventResult.skipCombat);
  if (eventResult && eventResult.timeFoldToRound !== undefined) timeFoldTarget = eventResult.timeFoldToRound;

  if (!skipCombat) {
    for (const u of allUnits) if (u.alive && u.stunnedRounds > 0) log.push(`🌀 ${u.name} 仍处于昏迷中，本回合无法行动。`);
    const actors = allUnits.filter(u => u.alive && u.stunnedRounds <= 0);
    actors.sort((a, b) => (b.effStat("mobility") + rng() * 2 - 1) - (a.effStat("mobility") + rng() * 2 - 1));
    for (const u of actors) {
      if (!u.alive) continue;
      const enemies = u.side === "player" ? enemyUnits : playerUnits;
      const target = pickTarget(u, enemies, rng);
      if (target === null) continue;
      resolveAttack(u, target, rng, log);
    }
  }

  applyDots(allUnits, log);
  for (const u of allUnits) u.tickStatus();
  const playerAlive = playerUnits.some(u => u.alive);
  const enemyAlive = enemyUnits.some(u => u.alive);
  return { playerAlive, enemyAlive, timeFoldTarget };
}

function snapshotAll(units) { const m = new Map(); for (const u of units) m.set(u, u.snapshot()); return m; }

function fastForwardSkipRounds(startRound, targetRound, playerUnits, enemyUnits, battlefield, rng, log, ctx, eventChance) {
  ctx.disableTimeFold = true;
  let r = startRound;
  while (r < targetRound - 1) {
    r += 1;
    log.push(`\n⏩（时间快进：第 ${r} 回合被跳过战斗，仅判定是否有突发事件）`);
    maybeTriggerEvent(playerUnits, enemyUnits, battlefield, rng, log, ctx, eventChance);
    for (const u of [...playerUnits, ...enemyUnits]) u.tickStatus();
  }
  ctx.disableTimeFold = false;
  return targetRound - 1;
}

function applyDecision(units, decision) {
  const stanceKey = (decision && STANCES[decision.stance]) ? decision.stance : "normal";
  const formation = (decision && decision.formation) || {};
  for (const u of units) { u.stance = stanceKey; u.row = formation[u.name] === "back" ? "back" : "front"; }
}

function finishBattle(battle, playerAlive, enemyAlive) {
  const { playerUnits, enemyUnits, log } = battle;
  let winner;
  if (playerAlive && !enemyAlive) winner = "player";
  else if (enemyAlive && !playerAlive) winner = "enemy";
  else if (!playerAlive && !enemyAlive) winner = "draw";
  else { const pHp = playerUnits.reduce((s, u) => s + u.hp, 0); const eHp = enemyUnits.reduce((s, u) => s + u.hp, 0); winner = pHp > eHp ? "player" : (eHp > pHp ? "enemy" : "draw"); log.push(`\n⏱️ 战斗已达到 ${MAX_ROUNDS} 回合上限，按双方剩余生命值总量判定胜负。`); }
  log.push("\n🏁 战斗结束！");
  if (winner === "player") log.push("🏆 我方阵营获胜！");
  else if (winner === "enemy") log.push("🏆 对方阵营获胜！");
  else log.push("🤝 双方同归于尽，本场战斗判定为平局。");
  battle.finished = true; battle.winner = winner; battle.rounds = battle.roundNo;
}

function createBattle(playerRoster, enemyRoster, battlefield, eventOptions, rngFn) {
  const rng = rngFn || Math.random;
  const preBattleChance = (eventOptions && eventOptions.preBattleChance !== undefined) ? eventOptions.preBattleChance : 0.30;
  const perRoundChance = (eventOptions && eventOptions.perRoundChance !== undefined) ? eventOptions.perRoundChance : 0.16;
  const log = []; const ctx = { disableTimeFold: false };

  const buildUnits = (roster, side) => roster.map(entry => {
    const [animal, steps] = Array.isArray(entry) ? entry : [entry, 0];
    return new BattleUnit(animal, side, battlefield, steps);
  });

  const playerUnits = buildUnits(playerRoster, "player");
  const enemyUnits = buildUnits(enemyRoster, "enemy");
  const allUnits = [...playerUnits, ...enemyUnits];

  log.push(`🏟️ 战场：${battlefield}`);
  let anyEnvDeath = false;
  for (const u of allUnits) { if (u.deadByEnvironment) { anyEnvDeath = true; log.push(`💀 [环境判定] ${u.environmentNote}`); } }
  if (!anyEnvDeath) log.push("双方均可适应当前战场环境，战斗正式开始！");

  let playerAlive = playerUnits.some(u => u.alive);
  let enemyAlive = enemyUnits.some(u => u.alive);
  let roundNo = 0;
  const roundSnapshots = new Map();

  if (playerAlive && enemyAlive) {
    log.push("\n═══════ 战前突发事件判定 ═══════");
    const preResult = maybeTriggerEvent(playerUnits, enemyUnits, battlefield, rng, log, ctx, preBattleChance);
    if (preResult === null) { log.push("（本场战斗风平浪静，未触发战前突发事件）"); }
    else if (preResult.timeFoldToRound !== undefined) { roundNo = fastForwardSkipRounds(0, preResult.timeFoldToRound, playerUnits, enemyUnits, battlefield, rng, log, ctx, perRoundChance); }
    playerAlive = playerUnits.some(u => u.alive);
    enemyAlive = enemyUnits.some(u => u.alive);
  }

  const battle = { playerUnits, enemyUnits, log, ctx, roundNo, roundSnapshots, battlefield, perRoundChance, rng, finished: false, winner: null, rounds: 0 };
  if (!playerAlive || !enemyAlive) finishBattle(battle, playerAlive, enemyAlive);
  return battle;
}

function advanceOneRound(battle, playerDecision, enemyDecision) {
  if (battle.finished) return battle;
  const { playerUnits, enemyUnits, battlefield, log, ctx, perRoundChance, rng } = battle;
  applyDecision(playerUnits, playerDecision);
  applyDecision(enemyUnits, enemyDecision);
  battle.roundNo += 1;
  battle.roundSnapshots.set(battle.roundNo, snapshotAll([...playerUnits, ...enemyUnits]));
  const res = runRound(battle.roundNo, playerUnits, enemyUnits, battlefield, rng, log, ctx, perRoundChance);
  let playerAlive = res.playerAlive, enemyAlive = res.enemyAlive;
  if (res.timeFoldTarget !== null) {
    if (battle.roundNo >= res.timeFoldTarget && battle.roundSnapshots.has(res.timeFoldTarget)) {
      const snap = battle.roundSnapshots.get(res.timeFoldTarget);
      for (const u of [...playerUnits, ...enemyUnits]) if (snap.has(u)) u.restore(snap.get(u));
      log.push(`⏪ 时间已拨回至第 ${res.timeFoldTarget} 回合开始时的状态。`);
      for (const k of [...battle.roundSnapshots.keys()]) if (k > res.timeFoldTarget) battle.roundSnapshots.delete(k);
      battle.roundNo = res.timeFoldTarget - 1;
    } else { battle.roundNo = fastForwardSkipRounds(battle.roundNo, res.timeFoldTarget, playerUnits, enemyUnits, battlefield, rng, log, ctx, perRoundChance); }
    playerAlive = playerUnits.some(u => u.alive); enemyAlive = enemyUnits.some(u => u.alive);
  }
  if (!playerAlive || !enemyAlive || battle.roundNo >= MAX_ROUNDS) finishBattle(battle, playerAlive, enemyAlive);
  return battle;
}

function aiChooseDecision(units, rng) {
  const roll = rng || Math.random;
  const alive = units.filter(u => u.alive);
  if (!alive.length) return { stance: "normal", formation: {} };
  const avgHpRatio = alive.reduce((s, u) => s + u.hpRatio(), 0) / alive.length;
  let stance;
  if (avgHpRatio < 0.35) stance = "hold";
  else if (avgHpRatio > 0.7) stance = "berserk";
  else stance = roll() < 0.5 ? "guerrilla" : "normal";
  const sorted = [...alive].sort((a, b) => b.baseStats.defense - a.baseStats.defense);
  const frontCount = Math.max(1, Math.ceil(alive.length / 2));
  const formation = {};
  sorted.forEach((u, i) => { formation[u.name] = i < frontCount ? "front" : "back"; });
  return { stance, formation };
}

function runBattleToCompletion(battle, fixedPlayerDecision) {
  while (!battle.finished) { const enemyDecision = aiChooseDecision(battle.enemyUnits, battle.rng); advanceOneRound(battle, fixedPlayerDecision, enemyDecision); }
  return battle;
}

function simulateBattle(playerRoster, enemyRoster, battlefield, rngFn, eventOptions) {
  const battle = createBattle(playerRoster, enemyRoster, battlefield, eventOptions, rngFn);
  runBattleToCompletion(battle, { stance: "normal", formation: {} });
  return battle;
}

// ── Draft Engine ──
function drawByTag(rng, tag, excludeNames) {
  const pool = ANIMALS.filter(a => a.habitatTag === tag && !excludeNames.has(a.name));
  return pickOne(rng, pool);
}
function drawRandom(rng, excludeNames) {
  const pool = ANIMALS.filter(a => !excludeNames.has(a.name));
  return pickOne(rng, pool);
}

function drawTeam(rng, modeKey) {
  const used = new Set(); const picks = [];
  const takeTag = (tag) => { const a = drawByTag(rng, tag, used); used.add(a.name); picks.push(a); };
  const takeRandom = () => { const a = drawRandom(rng, used); used.add(a.name); picks.push(a); };
  if (modeKey === "1v1") { takeTag("陆地"); takeTag("海洋"); takeTag("海陆"); }
  else if (modeKey === "3v3") { takeTag("陆地"); takeTag("海洋"); takeTag("海陆"); takeRandom(); takeRandom(); }
  else if (modeKey === "5v5") { takeTag("陆地"); takeTag("陆地"); takeTag("海洋"); takeTag("海洋"); takeTag("海陆"); takeRandom(); takeRandom(); takeRandom(); }
  return picks;
}

function decideFirstBanner(playerStarters, enemyStarters, rng) {
  const notes = [];
  const pStab = teamStabilitySum(playerStarters);
  const eStab = teamStabilitySum(enemyStarters);
  notes.push(`我方首发稳定系数总和：${pStab.toFixed(3)}　|　对方首发稳定系数总和：${eStab.toFixed(3)}`);
  if (pStab !== eStab) { const first = pStab < eStab ? "player" : "enemy"; notes.push(`稳定系数总和更低的一方先手ban场：${first === "player" ? "我方" : "对方"}`); return { first, notes }; }
  const pW = teamTotalWeight(playerStarters); const eW = teamTotalWeight(enemyStarters);
  notes.push(`稳定系数总和打平，比较首发总吨位：我方 ${pW.toFixed(0)}kg　|　对方 ${eW.toFixed(0)}kg`);
  if (pW !== eW) { const first = pW < eW ? "player" : "enemy"; notes.push(`总吨位更低的一方先手ban场：${first === "player" ? "我方" : "对方"}`); return { first, notes }; }
  const first = rng() < 0.5 ? "player" : "enemy"; notes.push(`总吨位也打平，随机决定先手：${first === "player" ? "我方" : "对方"}`);
  return { first, notes };
}

function powerScore(animal) {
  const vals = [];
  for (const tk of ["land", "near", "far"]) { const profile = animal.terrains[tk]; if (!profile) continue; for (const k of ["attack", "defense", "mobility", "technique", "stamina"]) vals.push(gradeValue(profile[k])); }
  vals.push(gradeValue(animal.intelligence));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
}

function aiChooseRoster(pool, nStarters, nBench) {
  const ranked = [...pool].sort((a, b) => powerScore(b) - powerScore(a));
  return { starters: ranked.slice(0, nStarters).map(a => a.name), bench: ranked.slice(nStarters, nStarters + nBench).map(a => a.name), discarded: ranked.slice(nStarters + nBench).map(a => a.name) };
}

function aiChooseBan(candidateBattlefields, ownStarters, rng) {
  const eligibleCount = (bf) => ownStarters.filter(a => animalCanFightHere(a, bf)).length;
  const scored = candidateBattlefields.map(bf => [bf, eligibleCount(bf)]);
  const minCount = Math.min(...scored.map(s => s[1]));
  const worst = scored.filter(s => s[1] === minCount).map(s => s[0]);
  return pickOne(rng, worst);
}

function remainingAfterBans(ban1, ban2) {
  const remaining = BATTLEFIELDS.filter(b => b !== ban1 && b !== ban2);
  return remaining.length ? remaining[0] : null;
}

function resolve1v1Combatant(rankedAnimals, battlefield) {
  for (const a of rankedAnimals) if (animalCanFightHere(a, battlefield)) return a;
  return null;
}

function resolveRosterWithSubs(starters, bench, battlefield) {
  const finalRoster = []; const notes = []; let availableBench = [...bench];
  for (const s of starters) {
    if (animalCanFightHere(s, battlefield)) { finalRoster.push([s, 0]); }
    else {
      notes.push(`首发 ${s.name} 无法适应【${battlefield}】，被环境淘汰。`);
      const eligibleBench = availableBench.filter(b => animalCanFightHere(b, battlefield));
      if (eligibleBench.length) {
        const sub = eligibleBench.reduce((best, b) => (avgWeightKg(b) > avgWeightKg(best) ? b : best));
        availableBench = availableBench.filter(b => b !== sub);
        finalRoster.push([sub, 2]);
        notes.push(`　→ 替补 ${sub.name}（吨位最大且适应该战场）顶替登场，五维评级降两级。`);
      } else { notes.push("　→ 替补中无适应该战场者，该位置空缺，本场少一人出战。"); }
    }
  }
  return { finalRoster, notes };
}
