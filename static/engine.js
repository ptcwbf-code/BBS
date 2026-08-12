/**
 * Beast Arena: Roguelike Survival — Complete Game Engine
 *
 * Core Design:
 * - Player controls ONE beast in real-time-ish interactive combat
 * - Face waves of increasingly difficult enemy beasts
 * - Each beast has unique Active Abilities (up to 3) + Passive traits
 * - Kill enemies → collect Souls → spend at shop between waves
 * - Rogue-lite: permadeath per run, XP carries to next run
 * - Combo system: chaining attacks builds combo meter → bonus damage
 * - Critical moments: timed QTE-style decisions mid-combat
 * - Terrain/environment hazards that affect combat dynamically
 */

// ═══════════════════════════════════════════
// GRADE SYSTEM (ported, preserved)
// ═══════════════════════════════════════════
const GRADE_MAP = {
  "S+":10,"S":9.5,"S-":9,"A+":8.5,"A":8,"A-":7.5,"B+":7,"B":6.5,"B-":6,
  "C+":5.5,"C":5,"C-":4.5,"D+":4,"D":3.5,"D-":3,"E":2
};
const GRADE_SEQ = ["S+","S","S-","A+","A","A-","B+","B","B-","C+","C","C-","D+","D","D-","E"];
function gv(l) { return GRADE_MAP[l] || 5; }

const ANIMALS_BY_NAME = {};
for (const a of ANIMALS) ANIMALS_BY_NAME[a.name] = a;
function avgW(a) { return (a.weightMinKg + a.weightMaxKg) / 2; }
function canFightHere(a, terrainKey) { return a.terrains[terrainKey] !== null; }

// ═══════════════════════════════════════════
// ABILITY SYSTEM — every beast has unique moves
// ═══════════════════════════════════════════
const ABILITY_POOL = {
  // ═══ DAMAGE ═══
  bite_crush: { id:"bite_crush",name:"骨碎咬合",icon:"🦷",type:"damage",desc:"撕咬对手要害，造成攻击力×3.5的伤害",dmgMult:3.5,cooldown:3,target:"enemy" },
  tail_sweep: { id:"tail_sweep",name:"巨尾横扫",icon:"🦕",type:"damage",desc:"甩尾横扫全场，对所有敌人造成攻击力×2的伤害",dmgMult:2.0,cooldown:4,target:"all_enemies" },
  charge_tackle: { id:"charge_tackle",name:"冲锋撞击",icon:"💨",type:"damage",desc:"全速冲击，造成攻击力×4的伤害但自身受到20%反伤",dmgMult:4.0,selfDmg:0.20,cooldown:3,target:"enemy" },
  bleed_strike: { id:"bleed_strike",name:"放血利爪",icon:"🩸",type:"damage",desc:"深度切割，攻击力×2立即伤害+3回合30%流血",dmgMult:2.0,bleed:{pct:0.30,rounds:3},cooldown:4,target:"enemy" },
  venom_bite: { id:"venom_bite",name:"毒液注入",icon:"🧪",type:"damage",desc:"注入毒液，攻击力×1.5伤害+敌方攻击力-30%持续3回合",dmgMult:1.5,debuff:{stat:"attack",pct:-0.30,rounds:3},cooldown:4,target:"enemy" },
  ambush_pounce: { id:"ambush_pounce",name:"伏击猛扑",icon:"🐅",type:"damage",desc:"隐匿后发动致命一击，必定暴击×5伤害",dmgMult:5.0,guaranteed:"crit",cooldown:5,target:"enemy" },
  skull_crush: { id:"skull_crush",name:"头骨粉碎",icon:"💀",type:"damage",desc:"瞄准头部，攻击力×4.5伤害+眩晕1回合",dmgMult:4.5,stun:1,cooldown:5,target:"enemy" },
  // ═══ DEFENSE ═══
  iron_armor: { id:"iron_armor",name:"铁壁装甲",icon:"🛡️",type:"defense",desc:"硬化皮肤，获得防御力×1.5的护盾持续3回合",shieldMult:1.5,duration:3,cooldown:5,target:"self" },
  regeneration: { id:"regeneration",name:"快速再生",icon:"💚",type:"defense",desc:"激活再生能力，恢复最大HP的30%",healPct:0.30,cooldown:6,target:"self" },
  counter_stance: { id:"counter_stance",name:"反击架势",icon:"⚔️",type:"defense",desc:"本回合防御+100%，被攻击时反击×2伤害",defBuff:1.0,counterDmg:2.0,cooldown:4,target:"self" },
  dodge_roll: { id:"dodge_roll",name:"闪避翻滚",icon:"🌀",type:"defense",desc:"闪避率提升至90%，持续2回合",dodgeBuff:0.90,duration:2,cooldown:5,target:"self" },
  // ═══ SPECIAL ═══
  berserk_rage: { id:"berserk_rage",name:"狂暴之怒",icon:"🔥",type:"special",desc:"进入狂暴3回合：攻击+50%，受伤+20%",buffs:[{stat:"attack",pct:0.50,rounds:3},{stat:"dmgTaken",pct:0.20,rounds:3}],cooldown:6,target:"self" },
  primal_roar: { id:"primal_roar",name:"原始咆哮",icon:"📢",type:"special",desc:"咆哮震慑：所有敌人防御-40%机动-30%持续2回合",enemyDebuffs:[{stat:"defense",pct:-0.40,rounds:2},{stat:"mobility",pct:-0.30,rounds:2}],cooldown:6,target:"all_enemies" },
  stalker_mark: { id:"stalker_mark",name:"猎手标记",icon:"🎯",type:"special",desc:"标记敌人3回合，对其伤害+40%，击杀后重置冷却",markDmgBonus:0.40,duration:3,cooldown:5,resetOnKill:true,target:"enemy" },
  sand_storm: { id:"sand_storm",name:"沙暴召唤",icon:"🏜️",type:"special",desc:"沙暴遮蔽战场2回合，所有敌人命中率-50%",enemyHitDebuff:0.50,duration:2,cooldown:6,target:"all_enemies" },
  pack_hunt: { id:"pack_hunt",name:"群猎本能",icon:"🐺",type:"special",desc:"召唤2只幽灵狼，每回合自动攻击随机敌人",summon:{name:"幽灵狼",hp:200,attack:5,count:2},cooldown:8,target:"self" },
  fossil_resonance: { id:"fossil_resonance",name:"化石共鸣",icon:"🦴",type:"special",desc:"召唤先祖之力：本回合所有伤害翻倍，下回合无法行动",dmgDouble:true,exhaustNext:true,cooldown:7,target:"self" },
};

function assignAbilities(animal) {
  const abilities = [];
  // Get best terrain profile for attack rating
  const profiles = [];
  for (const tk of ["land","near","far"]) { const p = animal.terrains[tk]; if (p) profiles.push(p); }
  const bestAtk = Math.max(...profiles.map(p => gv(p.attack)));
  const bestDef = Math.max(...profiles.map(p => gv(p.defense)));
  const bestMob = Math.max(...profiles.map(p => gv(p.mobility)));

  if (bestAtk >= 9) abilities.push("skull_crush");
  else if (bestAtk >= 8 && bestMob >= 7) abilities.push("ambush_pounce");
  else if (bestAtk >= 8) abilities.push("bite_crush");
  else if (bestAtk >= 7 && bestMob >= 8) abilities.push("bleed_strike");
  else if (bestMob >= 8) abilities.push("charge_tackle");
  else abilities.push("tail_sweep");

  if (bestDef >= 8) abilities.push("iron_armor");
  else if (bestMob >= 8) abilities.push("dodge_roll");
  else if (bestDef >= 7) abilities.push("counter_stance");
  else abilities.push("regeneration");

  if (gv(animal.intelligence) >= 8) abilities.push("primal_roar");
  else if (bestAtk >= 8.5) abilities.push("berserk_rage");
  else if (bestMob >= 7.5 && gv(animal.intelligence) >= 7) abilities.push("pack_hunt");
  else if (animal.habitatTag === "陆地" && bestAtk >= 7) abilities.push("sand_storm");
  else abilities.push("stalker_mark");

  return abilities.map(id => ABILITY_POOL[id]);
}

function getPassive(animal) {
  const hp = avgW(animal);
  if (hp > 10000) return {name:"庞然巨物",icon:"🏔️",desc:"每回合恢复最大HP的3%",type:"regen",value:0.03};
  if (hp > 3000) return {name:"厚皮装甲",icon:"🛡️",desc:"受到的物理伤害减少12%",type:"reduce",value:0.12};
  if (animal.intelligence === "S+") return {name:"战术大师",icon:"🧠",desc:"技能冷却时间-1回合",type:"cdr",value:1};
  if (animal.intelligence === "A" || animal.intelligence === "A-") return {name:"猎手直觉",icon:"👁️",desc:"10%几率闪避任何攻击",type:"dodge",value:0.10};
  if (animal.category.includes("猫科") || animal.category.includes("剑齿")) return {name:"伏击本能",icon:"🐾",desc:"先手攻击时伤害+25%",type:"firstStrike",value:0.25};
  const profiles = [];
  for (const tk of ["land","near","far"]) { const p = animal.terrains[tk]; if (p) profiles.push(p); }
  const bestMob = Math.max(...profiles.map(p => gv(p.mobility)));
  if (bestMob >= 9) return {name:"迅捷如风",icon:"💨",desc:"每3回合获得一次额外行动",type:"extraTurn",value:3};
  return {name:"不屈斗志",icon:"💪",desc:"HP低于25%时攻击力+30%",type:"lowHpBuff",value:{threshold:0.25,atkBuff:0.30}};
}

// ═══════════════════════════════════════════
// BATTLE UNIT (for combat logic)
// ═══════════════════════════════════════════
class BattleUnit {
  constructor(animal, level, side, battlefield) {
    this.animal = animal;
    this.name = animal.name;
    this.side = side; // "player" or "enemy"
    this.level = level || 1;
    this.battlefield = battlefield || "陆地";

    const terrainKey = { "陆地":"land","近海":"near","远海":"far" }[battlefield];
    const profile = animal.terrains[terrainKey] || Object.values(animal.terrains).find(p => p !== null) || { attack:"C",defense:"C",mobility:"C",technique:"C",stamina:"C",stability:1.0 };

    this.atk = gv(profile.attack) + (level - 1) * 0.4;
    this.def = gv(profile.defense) + (level - 1) * 0.3;
    this.mob = gv(profile.mobility) + (level - 1) * 0.3;
    this.tec = gv(profile.technique);
    this.sta = gv(profile.stamina);
    this.intel = gv(animal.intelligence);
    this.stability = profile.stability;

    // HP scales with weight and level
    const w = avgW(animal);
    const baseHp = 120 + Math.sqrt(w) * 3.5;
    this.maxHp = Math.round(baseHp + baseHp * (level - 1) * 0.15 + this.def * 10);
    this.hp = this.maxHp;
    this.shield = 0;

    this.alive = true;
    this.abilities = assignAbilities(animal);
    this.passive = getPassive(animal);
    this.activeCooldowns = {}; // ability_id -> remaining rounds

    // Status effects
    this.statusEffects = []; // {stat, delta, rounds, label}
    this.dots = []; // {amount, rounds, label}
    this.stunned = 0;
    this.marked = false;
    this.markedDmgBonus = 0;
    this.combatLog = [];

    // Enemies only
    if (side === "enemy") {
      this.xpReward = Math.round(20 + w * 0.003 + level * 10);
      this.soulReward = Math.round(5 + w * 0.001 + level * 3);
    }
    this.comboCount = 0;
    this.exhaustNext = false;
    this.dmgDoubled = false;
    this.summonedPets = [];
  }

  effStat(stat) {
    let v = this[stat] || 5;
    for (const e of this.statusEffects) if (e.stat === stat) v += v * e.delta;
    if (this.passive.type === "lowHpBuff" && this.hpRatio() < this.passive.value.threshold && stat === "attack") v *= (1 + this.passive.value.atkBuff);
    return Math.max(1, v);
  }

  hpRatio() { return this.maxHp ? this.hp / this.maxHp : 0; }

  takeDamage(dmg, ignoreShield) {
    dmg = Math.round(Math.max(1, dmg));
    if (this.passive.type === "reduce") dmg = Math.round(dmg * (1 - this.passive.value));
    // Shield absorbs damage first
    if (!ignoreShield && this.shield > 0) {
      const absorbed = Math.min(this.shield, dmg);
      this.shield -= absorbed;
      dmg -= absorbed;
    }
    this.hp = Math.max(0, this.hp - dmg);
    if (this.hp <= 0) { this.hp = 0; this.alive = false; }
    return dmg;
  }

  heal(amount) {
    const actual = Math.round(Math.min(amount, this.maxHp - this.hp));
    this.hp = Math.min(this.maxHp, this.hp + actual);
    return actual;
  }

  tickBuffs() {
    this.statusEffects.forEach(e => e.rounds--);
    this.statusEffects = this.statusEffects.filter(e => e.rounds > 0);
    this.dots.forEach(e => e.rounds--);
    this.dots = this.dots.filter(e => e.rounds > 0);
    if (this.stunned > 0) this.stunned--;
    this.dmgDoubled = false;
    Object.keys(this.activeCooldowns).forEach(k => { if (this.activeCooldowns[k] > 0) this.activeCooldowns[k]--; });
  }

  applyDotDmg() {
    let total = 0;
    for (const dot of this.dots) {
      const dmg = Math.round(dot.amount * this.maxHp);
      this.takeDamage(dmg, true);
      total += Math.round(dmg);
      this.combatLog.push(`🔥 ${this.name} 受到【${dot.label}】${Math.round(dmg)}点伤害`);
    }
    return total;
  }

  useAbility(abilityId, targets) {
    const ab = this.abilities.find(a => a.id === abilityId);
    if (!ab) return null;
    if (this.activeCooldowns[abilityId] > 0) return null;

    const result = { ability: ab, damage: 0, healing: 0, shieldGained: 0, log: [], effects: [] };
    const cdMult = this.passive.type === "cdr" ? 1 : 0;
    const cd = Math.max(1, ab.cooldown - cdMult);
    this.activeCooldowns[abilityId] = cd;

    if (ab.dmgMult) {
      let baseDmg = this.effStat("attack") * ab.dmgMult * (this.dmgDoubled ? 2 : 1);
      if (ab.guaranteed === "crit") baseDmg *= 1.5;
      if (this.passive.type === "firstStrike" && !this.hasActedThisRound) baseDmg *= (1 + this.passive.value);

      if (ab.target === "enemy" && targets[0]) {
        const t = targets[0];
        const dmg = t.takeDamage(baseDmg);
        result.damage = dmg;
        result.log.push(`⚔️ ${ab.icon} ${this.name} 使用【${ab.name}】对 ${t.name} 造成 ${dmg} 伤害`);
        if (!t.alive) result.log.push(`☠️ ${t.name} 被击败！`);
        if (ab.stun) { t.stunned = ab.stun; result.log.push(`🌀 ${t.name} 眩晕${ab.stun}回合！`); }
        if (ab.bleed) { t.dots.push({amount:ab.bleed.pct, rounds:ab.bleed.rounds, label:"流血"}); result.log.push(`🩸 ${t.name} 开始流血！`); }
        if (ab.debuff) { t.statusEffects.push({...ab.debuff}); result.log.push(`⬇️ ${t.name} ${ab.debuff.stat==='attack'?'攻击力':'防御力'}下降`); }
        if (ab.markDmgBonus) { t.marked = true; t.markedDmgBonus = ab.markDmgBonus; result.log.push(`🎯 ${t.name} 被标记！对其伤害+${Math.round(ab.markDmgBonus*100)}%`); }
      } else if (ab.target === "all_enemies") {
        for (const t of targets) {
          if (!t.alive) continue;
          const dmg = t.takeDamage(baseDmg);
          result.damage += dmg;
          result.log.push(`⚔️ ${ab.icon} ${this.name} 使用【${ab.name}】对 ${t.name} 造成 ${dmg} 伤害`);
        }
      }
      if (ab.selfDmg) {
        const selfDmg = Math.round(baseDmg * ab.selfDmg);
        this.takeDamage(selfDmg, true);
        result.log.push(`💢 ${this.name} 受到${selfDmg}点反伤`);
      }
    }

    if (ab.shieldMult) {
      result.shieldGained = Math.round(this.effStat("defense") * ab.shieldMult);
      this.shield += result.shieldGained;
      result.log.push(`🛡️ ${this.name} 获得 ${result.shieldGained} 护盾`);
    }

    if (ab.healPct) {
      result.healing = this.heal(this.maxHp * ab.healPct);
      result.log.push(`💚 ${this.name} 恢复 ${result.healing} HP`);
    }

    if (ab.buffs) {
      for (const b of ab.buffs) {
        this.statusEffects.push({stat:b.stat,delta:b.pct,rounds:b.rounds,label:ab.name});
        result.log.push(`⬆️ ${this.name} ${b.stat} ${b.pct>0?'+':''}${Math.round(b.pct*100)}%`);
      }
    }

    if (ab.enemyDebuffs) {
      for (const t of targets) {
        if (!t.alive) continue;
        for (const d of ab.enemyDebuffs) {
          t.statusEffects.push({stat:d.stat,delta:d.pct,rounds:d.rounds,label:ab.name});
          result.log.push(`⬇️ ${t.name} ${d.stat} ${Math.round(d.pct*100)}%`);
        }
      }
    }

    if (ab.enemyHitDebuff) {
      for (const t of targets) {
        if (!t.alive) continue;
        t.statusEffects.push({stat:"hit",delta:-ab.enemyHitDebuff,rounds:ab.duration,label:ab.name});
      }
      result.log.push(`🌫️ 沙暴遮蔽战场，敌人命中率下降！`);
    }

    if (ab.dmgDouble) this.dmgDoubled = true;
    if (ab.exhaustNext) this.exhaustNext = true;

    return result;
  }

  basicAttack(target) {
    let dmg = this.effStat("attack") * 2.5;
    if (this.passive.type === "firstStrike" && !this.hasActedThisRound) dmg *= (1 + this.passive.value);
    if (this.dmgDoubled) dmg *= 2;
    const finalDmg = target.takeDamage(dmg);
    return { damage: finalDmg, log: [`⚔️ ${this.name} 攻击 ${target.name}，造成 ${finalDmg} 伤害`] };
  }
}

// ═══════════════════════════════════════════
// SHOP ITEMS (between waves)
// ═══════════════════════════════════════════
const SHOP_ITEMS = [
  { id:"heal_full",name:"生命之泉",icon:"💚",cost:20,desc:"恢复全部HP",effect:"heal",value:1.0 },
  { id:"heal_half",name:"治疗草药",icon:"🌿",cost:8,desc:"恢复40%HP",effect:"heal",value:0.40 },
  { id:"atk_up",name:"力量果实",icon:"💪",cost:15,desc:"永久攻击力+1级",effect:"atkUp",value:1 },
  { id:"def_up",name:"铁壁蘑菇",icon:"🍄",cost:15,desc:"永久防御力+1级",effect:"defUp",value:1 },
  { id:"mob_up",name:"疾风之羽",icon:"🪶",cost:12,desc:"永久机动+1级",effect:"mobUp",value:1 },
  { id:"maxHp_up",name:"远古巨心",icon:"❤️",cost:18,desc:"最大HP+20%",effect:"maxHpUp",value:0.20 },
  { id:"crit_boost",name:"猎手之眼",icon:"👁️",cost:22,desc:"暴击率+15%",effect:"critUp",value:0.15 },
  { id:"combo_charm",name:"连击护符",icon:"⚡",cost:25,desc:"连击伤害加成翻倍",effect:"comboX2",value:2 },
  { id:"revive_charm",name:"复活护符",icon:"💫",cost:40,desc:"死亡后以50%HP复活一次",effect:"revive",value:1 },
  { id:"xp_boost",name:"远古智慧",icon:"📚",cost:20,desc:"战斗经验+50%",effect:"xpBoost",value:0.50 },
  { id:"new_ability",name:"技能石板",icon:"📜",cost:35,desc:"随机获得一个额外技能",effect:"newAbility",value:1 },
];

// ═══════════════════════════════════════════
// ENEMY WAVE GENERATION
// ═══════════════════════════════════════════
function generateEnemyWave(waveNum, battlefield) {
  const terrainKey = { "陆地":"land","近海":"near","远海":"far" }[battlefield];
  const eligible = ANIMALS.filter(a => a.terrains[terrainKey] !== null);

  const enemyCount = Math.min(1 + Math.floor(waveNum / 2), 5);
  const enemies = [];
  for (let i = 0; i < enemyCount; i++) {
    const idx = Math.floor(Math.random() * eligible.length);
    const animal = eligible[idx];
    const level = Math.max(1, waveNum + Math.floor(Math.random() * 3) - 1);
    const enemy = new BattleUnit(animal, level, "enemy", battlefield);
    enemies.push(enemy);
  }
  return enemies;
}

// ═══════════════════════════════════════════
// CITADEL EVENTS (random encounters)
// ═══════════════════════════════════════════
const CITADEL_EVENTS = [
  { id:"ancient_shrine",name:"远古祭坛",icon:"🏛️",desc:"一座远古祭坛散发着神秘光芒……",
    choices: [
      { text:"🛐 献祭30灵魂", result:"gain", effect:"获得攻击力+2永久提升", apply:(p)=>{p.atk+=2;return"攻击力+2！";} },
      { text:"🙏 默默祈祷", result:"heal", effect:"恢复全部HP", apply:(p)=>{p.heal(p.maxHp);return"HP完全恢复！";} },
      { text:"🚶 绕道而行", result:"nothing", effect:"什么也没发生", apply:(p)=>{return"你谨慎地绕开了。";} },
    ]
  },
  { id:"mysterious_merchant",name:"神秘商人",icon:"🧙",desc:"一位披着斗篷的神秘商人拦住了你……",
    choices: [
      { text:"💰 花25灵魂购买神秘药水", result:"gain", effect:"随机属性+2", apply:(p)=>{const s=["atk","def","mob"];const k=s[Math.floor(Math.random()*3)];p[k]+=2;return`${k}永久+2！`;} },
      { text:"🔄 用10灵魂交换情报", result:"mixed", effect:"获得20灵魂和少量经验", apply:(p)=>{p.souls+=20;p.xp+=50;return"获得20灵魂+50经验！";} },
      { text:"👊 威胁商人", result:"fight", effect:"触发额外战斗(胜利获得50灵魂)", apply:(p)=>{return"商人召唤了护卫！";} },
    ]
  },
  { id:"bone_yard",name:"骸骨荒野",icon:"🦴",desc:"你踏入了一片遍布巨兽骨骸的区域……",
    choices: [
      { text:"🔍 仔细搜寻", result:"gain", effect:"找到远古遗物", apply:(p)=>{p.souls+=15;p.xp+=30;return"找到15灵魂+30经验！";} },
      { text:"⚡ 快速通过", result:"nothing", effect:"安全通过", apply:(p)=>{return"你安全地通过了。";} },
    ]
  },
  { id:"storm_front",name:"风暴前线",icon:"🌩️",desc:"前方乌云密布，雷暴即将来临……",
    choices: [
      { text:"⛺ 原地扎营等待", result:"heal", effect:"恢复30%HP", apply:(p)=>{const h=p.heal(p.maxHp*0.3);return`恢复了${h}HP。`;} },
      { text:"🏃 冒雨冲刺", result:"mixed", effect:"受到100伤害但获得25灵魂", apply:(p)=>{p.takeDamage(100,true);p.souls+=25;return"受到100伤害但获得25灵魂！";} },
      { text:"🛡️ 硬扛暴风雨", result:"lose", effect:"受到150伤害", apply:(p)=>{p.takeDamage(150,true);return"受到了150点伤害！";} },
    ]
  },
  { id:"echo_pool",name:"回响之池",icon:"🌊",desc:"一汪清澈的池水倒映着远古的记忆……",
    choices: [
      { text:"🧪 饮用池水", result:"gain", effect:"随机获得一个被动技能", apply:(p)=>{return"你感到体内涌动着新的力量！";} },
      { text:"🪞 凝视倒影", result:"mixed", effect:"获得经验但失去10灵魂", apply:(p)=>{p.xp+=100;p.souls=Math.max(0,p.souls-10);return"获得100经验，失去10灵魂。";} },
    ]
  },
];

// ═══════════════════════════════════════════
// RUN STATE (the current run)
// ═══════════════════════════════════════════
function createRun(beastName, battlefield) {
  const animal = ANIMALS_BY_NAME[beastName];
  const player = new BattleUnit(animal, 1, "player", battlefield);
  const run = {
    player: player,
    battlefield: battlefield,
    waveNum: 0,
    souls: 0,
    totalXP: 0,
    totalKills: 0,
    comboCount: 0,
    comboMultiplier: 1.0,
    eventsTriggered: 0,
    itemsBought: [],
    isFinished: false,
    isDead: false,
    reviveUsed: false,
    combatLog: [],
    phase: "pre_battle", // pre_battle | player_turn | enemy_turn | shop | event | victory | defeat
    enemies: [],
    turnCount: 0,
    waveEnemiesDefeated: 0,
    abilityUsedThisTurn: false,
  };
  return run;
}

function runPhaseLabel(phase) {
  const map = {
    pre_battle: "🔮 准备战斗",
    player_turn: "⚔️ 你的回合",
    enemy_turn: "👹 敌人回合",
    shop: "🛒 灵魂商店",
    event: "❓ 随机事件",
    victory: "🏆 胜利！",
    defeat: "💀 阵亡",
  };
  return map[phase] || phase;
}
