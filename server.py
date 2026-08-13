"""
BBALL CAREER SIMULATOR v3.0
===========================
Deep Strategy Basketball Career RPG
- Point-buy creation with position/build synergy
- Full NBA Draft simulation
- Narrative uncertainty in media/development
- Realistic NBA stat engine
- SQLite persistence, FastAPI backend

Run: python server.py
"""

import random
import math
import json
import sqlite3
import os
import uuid
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager, asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bball_career.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Serialize game simulation to avoid concurrent read-modify-write races
_SIM_LOCK = threading.Lock()

# ============================================================
# DATABASE
# ============================================================
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, position TEXT NOT NULL,
            height REAL NOT NULL, weight REAL NOT NULL, age INTEGER DEFAULT 19,
            experience INTEGER DEFAULT 0, team_id INTEGER DEFAULT 0,
            jersey_number INTEGER DEFAULT 0, role TEXT DEFAULT 'Two-Way Wing',
            draft_pick INTEGER DEFAULT 0, draft_year INTEGER DEFAULT 0,
            wingspan REAL NOT NULL, standing_reach REAL NOT NULL,
            hand_size REAL NOT NULL, frame_build REAL NOT NULL,
            body_fat_pct REAL DEFAULT 8.0,
            vertical_jump INTEGER DEFAULT 45, speed INTEGER DEFAULT 45,
            lateral_quickness INTEGER DEFAULT 45, strength INTEGER DEFAULT 45,
            core_stability INTEGER DEFAULT 45, stamina INTEGER DEFAULT 55,
            durability INTEGER DEFAULT 55,
            perimeter_defense INTEGER DEFAULT 40, help_defense INTEGER DEFAULT 40,
            steal INTEGER DEFAULT 35, rim_protection INTEGER DEFAULT 40,
            box_out INTEGER DEFAULT 40,
            first_step INTEGER DEFAULT 40, finishing INTEGER DEFAULT 40,
            mid_range INTEGER DEFAULT 40, catch_shoot_3pt INTEGER DEFAULT 35,
            pull_up_3pt INTEGER DEFAULT 30, off_ball INTEGER DEFAULT 40,
            drawing_fouls INTEGER DEFAULT 35, free_throw INTEGER DEFAULT 65,
            ball_security INTEGER DEFAULT 45, pnr_vision INTEGER DEFAULT 40,
            passing_accuracy INTEGER DEFAULT 40,
            bbiq INTEGER DEFAULT 50, clutch_factor INTEGER DEFAULT 50,
            work_ethic INTEGER DEFAULT 50, leadership INTEGER DEFAULT 40,
            composure INTEGER DEFAULT 50,
            fatigue REAL DEFAULT 0, injury_risk REAL DEFAULT 0,
            morale INTEGER DEFAULT 75, injury_status TEXT,
            injury_games_remaining INTEGER DEFAULT 0,
            hot_streak INTEGER DEFAULT 0, cold_streak INTEGER DEFAULT 0,
            load_management BOOLEAN DEFAULT 0,
            clout REAL DEFAULT 2, fan_base REAL DEFAULT 5,
            wealth REAL DEFAULT 0.1, chemistry INTEGER DEFAULT 50,
            mvp_votes REAL DEFAULT 0, trained_season INTEGER DEFAULT 0,
            s_pts REAL DEFAULT 0, s_reb REAL DEFAULT 0, s_ast REAL DEFAULT 0,
            s_stl REAL DEFAULT 0, s_blk REAL DEFAULT 0, s_tov REAL DEFAULT 0,
            s_fga REAL DEFAULT 0, s_fgm REAL DEFAULT 0, s_3pa REAL DEFAULT 0,
            s_3pm REAL DEFAULT 0, s_fta REAL DEFAULT 0, s_ftm REAL DEFAULT 0,
            s_games INTEGER DEFAULT 0, s_min REAL DEFAULT 0, s_pf INTEGER DEFAULT 0,
            s_wins INTEGER DEFAULT 0, s_losses INTEGER DEFAULT 0,
            potential INTEGER DEFAULT 50,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER, game_number INTEGER,
            opponent_team_id INTEGER, is_playoff BOOLEAN DEFAULT 0,
            is_home BOOLEAN DEFAULT 1, result TEXT DEFAULT 'L',
            team_score INTEGER DEFAULT 0, opponent_score INTEGER DEFAULT 0,
            minutes REAL DEFAULT 0, pts INTEGER DEFAULT 0, reb INTEGER DEFAULT 0,
            oreb INTEGER DEFAULT 0, dreb INTEGER DEFAULT 0, ast INTEGER DEFAULT 0,
            stl INTEGER DEFAULT 0, blk INTEGER DEFAULT 0, tov INTEGER DEFAULT 0,
            pf INTEGER DEFAULT 0, fga INTEGER DEFAULT 0, fgm INTEGER DEFAULT 0,
            tpa INTEGER DEFAULT 0, tpm INTEGER DEFAULT 0, fta INTEGER DEFAULT 0,
            ftm INTEGER DEFAULT 0, plus_minus INTEGER DEFAULT 0,
            per REAL DEFAULT 0, ts_pct REAL DEFAULT 0, usg_pct REAL DEFAULT 0,
            game_score REAL DEFAULT 0, eff INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS season_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER, team_id INTEGER,
            age INTEGER, games_played INTEGER DEFAULT 0,
            mpg REAL DEFAULT 0, ppg REAL DEFAULT 0, rpg REAL DEFAULT 0,
            apg REAL DEFAULT 0, spg REAL DEFAULT 0, bpg REAL DEFAULT 0,
            topg REAL DEFAULT 0, fg_pct REAL DEFAULT 0, tp_pct REAL DEFAULT 0,
            ft_pct REAL DEFAULT 0, per REAL DEFAULT 0, ts_pct REAL DEFAULT 0,
            usg_pct REAL DEFAULT 0, ws REAL DEFAULT 0, bpm REAL DEFAULT 0,
            vorp REAL DEFAULT 0, team_wins INTEGER DEFAULT 0,
            team_losses INTEGER DEFAULT 0, playoff_result TEXT,
            role TEXT, awards TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER,
            award_type TEXT, award_name TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER, team_id INTEGER,
            years INTEGER, total_value REAL, annual_salary REAL,
            contract_type TEXT DEFAULT 'Standard',
            signed_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS endorsements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, brand_name TEXT, annual_value REAL,
            years_remaining INTEGER, prestige INTEGER DEFAULT 50,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, name TEXT, amount_invested REAL,
            current_value REAL, annual_return REAL DEFAULT 0,
            risk_level TEXT DEFAULT 'Medium',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS media_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER,
            event_type TEXT, description TEXT, choice_made TEXT,
            narrative_result TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS career_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER,
            event_type TEXT, description TEXT, milestone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS save_files (
            id TEXT PRIMARY KEY, player_id TEXT NOT NULL,
            save_name TEXT NOT NULL, season_number INTEGER,
            description TEXT DEFAULT '', snapshot TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS endorsement_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL, season_number INTEGER,
            brand_name TEXT, annual_value REAL, years INTEGER, prestige INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS league_state (
            id INTEGER PRIMARY KEY CHECK (id=1),
            current_season INTEGER DEFAULT 1,
            current_phase TEXT DEFAULT 'regular_season',
            games_played_in_season INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO league_state (id,current_season,current_phase,games_played_in_season)
        VALUES (1,1,'regular_season',0);
        """)
        db.executescript("""
        CREATE INDEX IF NOT EXISTS idx_game_logs_player ON game_logs(player_id, season_number);
        CREATE INDEX IF NOT EXISTS idx_season_summaries_player ON season_summaries(player_id, season_number);
        CREATE INDEX IF NOT EXISTS idx_awards_player ON awards(player_id);
        CREATE INDEX IF NOT EXISTS idx_media_player ON media_events(player_id);
        CREATE INDEX IF NOT EXISTS idx_endorse_player ON endorsements(player_id);
        """)
        # Migrations for pre-existing databases
        for table, col, ddl in [
            ("players", "trained_season", "INTEGER DEFAULT 0"),
            ("save_files", "snapshot", "TEXT"),
        ]:
            cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

# ============================================================
# TEAM DATA
# ============================================================
TEAMS = {
    1:{"name":"Atlanta Hawks","abbr":"ATL","conf":"East","div":"Southeast","off":112,"def":114,"ovr":78},
    2:{"name":"Boston Celtics","abbr":"BOS","conf":"East","div":"Atlantic","off":120,"def":108,"ovr":95},
    3:{"name":"Brooklyn Nets","abbr":"BKN","conf":"East","div":"Atlantic","off":108,"def":113,"ovr":72},
    4:{"name":"Charlotte Hornets","abbr":"CHA","conf":"East","div":"Southeast","off":106,"def":115,"ovr":65},
    5:{"name":"Chicago Bulls","abbr":"CHI","conf":"East","div":"Central","off":110,"def":112,"ovr":74},
    6:{"name":"Cleveland Cavaliers","abbr":"CLE","conf":"East","div":"Central","off":115,"def":110,"ovr":85},
    7:{"name":"Detroit Pistons","abbr":"DET","conf":"East","div":"Central","off":105,"def":113,"ovr":62},
    8:{"name":"Indiana Pacers","abbr":"IND","conf":"East","div":"Central","off":116,"def":113,"ovr":80},
    9:{"name":"Miami Heat","abbr":"MIA","conf":"East","div":"Southeast","off":111,"def":109,"ovr":82},
    10:{"name":"Milwaukee Bucks","abbr":"MIL","conf":"East","div":"Central","off":117,"def":109,"ovr":88},
    11:{"name":"New York Knicks","abbr":"NYK","conf":"East","div":"Atlantic","off":114,"def":108,"ovr":86},
    12:{"name":"Orlando Magic","abbr":"ORL","conf":"East","div":"Southeast","off":110,"def":110,"ovr":79},
    13:{"name":"Philadelphia 76ers","abbr":"PHI","conf":"East","div":"Atlantic","off":116,"def":110,"ovr":84},
    14:{"name":"Toronto Raptors","abbr":"TOR","conf":"East","div":"Atlantic","off":109,"def":112,"ovr":70},
    15:{"name":"Washington Wizards","abbr":"WAS","conf":"East","div":"Southeast","off":107,"def":116,"ovr":60},
    16:{"name":"Dallas Mavericks","abbr":"DAL","conf":"West","div":"Southwest","off":118,"def":111,"ovr":87},
    17:{"name":"Denver Nuggets","abbr":"DEN","conf":"West","div":"Northwest","off":119,"def":110,"ovr":92},
    18:{"name":"Golden State Warriors","abbr":"GSW","conf":"West","div":"Pacific","off":115,"def":111,"ovr":83},
    19:{"name":"Houston Rockets","abbr":"HOU","conf":"West","div":"Southwest","off":111,"def":112,"ovr":76},
    20:{"name":"LA Clippers","abbr":"LAC","conf":"West","div":"Pacific","off":115,"def":109,"ovr":84},
    21:{"name":"Los Angeles Lakers","abbr":"LAL","conf":"West","div":"Pacific","off":114,"def":111,"ovr":83},
    22:{"name":"Memphis Grizzlies","abbr":"MEM","conf":"West","div":"Southwest","off":113,"def":109,"ovr":83},
    23:{"name":"Minnesota Timberwolves","abbr":"MIN","conf":"West","div":"Northwest","off":114,"def":107,"ovr":88},
    24:{"name":"New Orleans Pelicans","abbr":"NOP","conf":"West","div":"Southwest","off":113,"def":111,"ovr":80},
    25:{"name":"Oklahoma City Thunder","abbr":"OKC","conf":"West","div":"Northwest","off":119,"def":106,"ovr":96},
    26:{"name":"Phoenix Suns","abbr":"PHX","conf":"West","div":"Pacific","off":115,"def":112,"ovr":81},
    27:{"name":"Portland Trail Blazers","abbr":"POR","conf":"West","div":"Northwest","off":107,"def":115,"ovr":64},
    28:{"name":"Sacramento Kings","abbr":"SAC","conf":"West","div":"Pacific","off":114,"def":113,"ovr":78},
    29:{"name":"San Antonio Spurs","abbr":"SAS","conf":"West","div":"Southwest","off":110,"def":112,"ovr":73},
    30:{"name":"Utah Jazz","abbr":"UTA","conf":"West","div":"Northwest","off":108,"def":114,"ovr":66},
}

# ============================================================
# HELPERS
# ============================================================
def clamp(v, lo, hi): return max(lo, min(hi, v))
def roll(mean, std=15): return clamp(round(random.gauss(mean, std)), 1, 99)
def weighted_choice(w):
    total = sum(w.values())
    if total == 0: return random.choice(list(w.keys()))
    r = random.random() * total
    a = 0
    for k, wt in w.items():
        a += wt
        if r <= a: return k
    return list(w.keys())[-1]

# ============================================================
# POSITION / BUILD SYSTEM
# ============================================================
POSITION_PROFILES = {
    "PG": {"label":"Point Guard","icon":"🎯","height_range":(1.83,1.96),"weight_range":(77,93),"base_points":260,
           "aptitudes":{"athleticism":45,"defense":40,"scoring":55,"playmaking":65,"mental":55}},
    "SG": {"label":"Shooting Guard","icon":"🔥","height_range":(1.91,2.03),"weight_range":(84,102),"base_points":250,
           "aptitudes":{"athleticism":45,"defense":40,"scoring":65,"playmaking":45,"mental":55}},
    "SF": {"label":"Small Forward","icon":"⚡","height_range":(1.98,2.08),"weight_range":(93,112),"base_points":245,
           "aptitudes":{"athleticism":50,"defense":50,"scoring":55,"playmaking":35,"mental":55}},
    "PF": {"label":"Power Forward","icon":"💪","height_range":(2.03,2.13),"weight_range":(102,122),"base_points":240,
           "aptitudes":{"athleticism":55,"defense":60,"scoring":45,"playmaking":25,"mental":55}},
    "C":  {"label":"Center","icon":"🏔️","height_range":(2.08,2.21),"weight_range":(109,136),"base_points":235,
           "aptitudes":{"athleticism":55,"defense":70,"scoring":35,"playmaking":20,"mental":55}},
}

ATTRIBUTE_CATEGORIES = {
    "athleticism": {"label":"Athleticism","icon":"⚡","desc":"Speed, jumping, stamina — the physical foundation.",
                    "attrs":["vertical_jump","speed","lateral_quickness","strength","core_stability","stamina","durability"]},
    "scoring": {"label":"Scoring","icon":"🎯","desc":"Putting the ball in the basket at all three levels.",
                "attrs":["first_step","finishing","mid_range","catch_shoot_3pt","pull_up_3pt","off_ball","drawing_fouls","free_throw"]},
    "playmaking": {"label":"Playmaking","icon":"👁️","desc":"Creating for others and protecting the ball.",
                   "attrs":["ball_security","pnr_vision","passing_accuracy"]},
    "defense": {"label":"Defense","icon":"🛡️","desc":"Stopping the opposition and forcing turnovers.",
                "attrs":["perimeter_defense","help_defense","steal","rim_protection","box_out"]},
    "mental": {"label":"Basketball IQ","icon":"🧠","desc":"Decision-making, composure, and leadership.",
               "attrs":["bbiq","clutch_factor","work_ethic","leadership","composure"]},
}

# ============================================================
# PLAYER CREATION (Point-Buy)
# ============================================================

def calculate_point_pool(position: str, height: float, weight: float, luck_bonus: Optional[int] = None) -> Dict:
    """Calculate available attribute points based on position, height, weight.

    `luck_bonus` lets callers pass a previously-rolled luck value so the pool
    shown during character creation matches the one actually used to create.
    """
    profile = POSITION_PROFILES[position]
    base = profile["base_points"]
    h_mid = (profile["height_range"][0] + profile["height_range"][1]) / 2
    h_dev = (height - h_mid) / (profile["height_range"][1] - profile["height_range"][0])
    height_bonus = round(h_dev * 15)
    w_mid = (profile["weight_range"][0] + profile["weight_range"][1]) / 2
    w_dev = (weight - w_mid) / (profile["weight_range"][1] - profile["weight_range"][0])
    weight_bonus = round(w_dev * 8)
    luck = luck_bonus if luck_bonus is not None else random.randint(-12, 12)
    total_points = base + height_bonus + weight_bonus + luck

    aptitudes = dict(profile["aptitudes"])
    if h_dev > 0.3:
        aptitudes["defense"] += 3; aptitudes["athleticism"] += 2; aptitudes["scoring"] -= 2
    elif h_dev < -0.3:
        aptitudes["scoring"] += 3; aptitudes["playmaking"] += 2; aptitudes["defense"] -= 2

    return {"total_points":total_points,"base":base,"height_bonus":height_bonus,
            "weight_bonus":weight_bonus,"luck_bonus":luck,"aptitudes":aptitudes,
            "height_deviation":round(h_dev,2),"weight_deviation":round(w_dev,2)}

def generate_static_physicals(position: str, height: float, weight: float) -> Dict:
    pos_cfg = {"PG":(1.00,1.06),"SG":(1.01,1.08),"SF":(1.02,1.10),"PF":(1.03,1.12),"C":(1.04,1.15)}
    ws_lo, ws_hi = pos_cfg.get(position, (1.01,1.10))
    wingspan = round(height * random.uniform(ws_lo, ws_hi), 2)
    standing_reach = round(height * 1.28 + (wingspan - height) * 0.45, 2)
    hand_size = round(random.uniform(20.0, 28.5), 1)
    frame = roll(50, 18)
    body_fat = round(random.uniform(5.5, 14.0), 1)
    return {"wingspan":wingspan,"standing_reach":standing_reach,"hand_size":hand_size,"frame_build":frame,"body_fat_pct":body_fat}

def create_player_with_points(name: str, position: str, age: int, height: float, weight: float, allocations: Dict[str, int], luck_bonus: Optional[int] = None) -> str:
    pid = str(uuid.uuid4())[:8]
    pool_info = calculate_point_pool(position, height, weight, luck_bonus)
    attrs = {}
    for cat, cat_info in ATTRIBUTE_CATEGORIES.items():
        cat_points = allocations.get(cat, pool_info["aptitudes"].get(cat, 30))
        attr_list = cat_info["attrs"]
        # Each category point translates to ~1.5 attribute points spread across its attributes
        pts_per_attr = round(cat_points * 1.5 / len(attr_list))
        for attr in attr_list:
            attrs[attr] = clamp(40 + pts_per_attr + random.randint(-3, 3), 25, 90)
    phys = generate_static_physicals(position, height, weight)
    potential = clamp(roll(50, 18), 20, 95)
    team_id = random.choice(list(TEAMS.keys()))
    jersey = random.randint(0, 55)
    with get_db() as db:
        cols = ["id","name","position","height","weight","age","team_id","jersey_number",
                "wingspan","standing_reach","hand_size","frame_build","body_fat_pct","potential",
                "vertical_jump","speed","lateral_quickness","strength","core_stability","stamina","durability",
                "perimeter_defense","help_defense","steal","rim_protection","box_out",
                "first_step","finishing","mid_range","catch_shoot_3pt","pull_up_3pt","off_ball","drawing_fouls",
                "ball_security","pnr_vision","passing_accuracy","free_throw",
                "bbiq","clutch_factor","work_ethic","leadership","composure"]
        vals = [pid,name,position,height,weight,age,team_id,jersey,
                phys["wingspan"],phys["standing_reach"],phys["hand_size"],phys["frame_build"],phys["body_fat_pct"],potential,
                attrs.get("vertical_jump",45),attrs.get("speed",45),attrs.get("lateral_quickness",45),attrs.get("strength",45),
                attrs.get("core_stability",45),attrs.get("stamina",55),attrs.get("durability",55),
                attrs.get("perimeter_defense",40),attrs.get("help_defense",40),attrs.get("steal",35),
                attrs.get("rim_protection",40),attrs.get("box_out",40),attrs.get("first_step",40),
                attrs.get("finishing",40),attrs.get("mid_range",40),attrs.get("catch_shoot_3pt",35),
                attrs.get("pull_up_3pt",30),attrs.get("off_ball",40),attrs.get("drawing_fouls",35),
                attrs.get("ball_security",45),attrs.get("pnr_vision",40),attrs.get("passing_accuracy",40),
                attrs.get("free_throw",65),attrs.get("bbiq",50),attrs.get("clutch_factor",50),
                attrs.get("work_ethic",50),attrs.get("leadership",40),attrs.get("composure",50)]
        assert len(cols) == len(vals), f"Column/value mismatch: {len(cols)} cols vs {len(vals)} vals"
        placeholders = ",".join(["?"] * len(cols))
        db.execute(f"INSERT INTO players ({','.join(cols)}) VALUES ({placeholders})", vals)
        sal = round(random.uniform(1.0, 8.0), 1)
        db.execute("INSERT INTO contracts (player_id,season_number,team_id,years,total_value,annual_salary,contract_type) VALUES (?,0,?,3,?,?,'Rookie')",
                   (pid, team_id, sal*3, sal))
    return pid

# ============================================================
# DRAFT SYSTEM
# ============================================================
FIRST_NAMES = ["Jalen","Marcus","DeAndre","Malik","Isaiah","Cameron","Jordan","Donte","Terrence","Amari","Kai","Zion","Elijah","Bryce","Xavier","Jayden","Tariq","Desmond","Roman","Andre","Kobe","Tyler","Jamal","Brandon","Darius","Shawn","Trey","Malcolm","Derek","Quinn"]
LAST_NAMES = ["Williams","Johnson","Thompson","Carter","Henderson","Mitchell","Robinson","Washington","Griffin","Bridges","Walker","Reeves","Anderson","Parker","Martinez","Okafor","Murphy","Chen","Santos","Bell","Pierce","Hughes","Monroe","Fox","Stone","Cross","Bennett","Knight","Reid","Blake"]

def generate_draft_class() -> List[Dict]:
    prospects = []
    for i in range(60):
        pos = weighted_choice({"PG":16,"SG":18,"SF":20,"PF":22,"C":14})
        profile = POSITION_PROFILES[pos]
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        height = round(random.uniform(*profile["height_range"]), 2)
        weight = round(random.uniform(*profile["weight_range"]), 1)
        age = random.randint(19, 22)
        tr = random.random()
        if tr < 0.03: overall = roll(88, 5)
        elif tr < 0.10: overall = roll(80, 6)
        elif tr < 0.25: overall = roll(72, 8)
        elif tr < 0.55: overall = roll(62, 10)
        else: overall = roll(50, 12)
        overall = clamp(overall, 28, 97)
        potential = clamp(overall + random.randint(-10, 20), 30, 99)
        prospects.append({"id":i+1,"name":name,"position":pos,"height":height,"weight":weight,"age":age,"overall":overall,"potential":potential})
    random.shuffle(prospects)
    for i, p in enumerate(prospects): p["id"] = i + 1
    return prospects

def simulate_draft_lottery() -> List[int]:
    weights = [140,140,140,125,105,90,75,60,45,30,20,15,10,5]
    lottery_order = []
    available = list(range(1, 15))
    for i in range(4):
        w = [weights[j-1] for j in available]
        pick = random.choices(available, weights=w, k=1)[0]
        lottery_order.append(pick)
        available.remove(pick)
    lottery_order.extend(available)
    return lottery_order

def calculate_overall_rating(player: Dict) -> int:
    scoring = (player.get("first_step",40)+player.get("finishing",40)+player.get("mid_range",40)+player.get("catch_shoot_3pt",35)+player.get("pull_up_3pt",30))/5
    playmaking = (player.get("ball_security",45)+player.get("pnr_vision",40)+player.get("passing_accuracy",40))/3
    defense = (player.get("perimeter_defense",40)+player.get("help_defense",40)+player.get("steal",35)+player.get("rim_protection",40)+player.get("box_out",40))/5
    athleticism = (player.get("vertical_jump",45)+player.get("speed",45)+player.get("lateral_quickness",45)+player.get("strength",45)+player.get("stamina",55))/5
    mental = (player.get("bbiq",50)+player.get("clutch_factor",50)+player.get("composure",50))/3
    return clamp(round(scoring*0.35+playmaking*0.15+defense*0.2+athleticism*0.2+mental*0.1), 25, 95)

def simulate_draft(player_id: str) -> Dict:
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not player: raise HTTPException(status_code=404, detail="Player not found")
    overall = calculate_overall_rating(player)
    draft_class = generate_draft_class()
    lottery = simulate_draft_lottery()
    draft_order = lottery + list(range(15, 31))
    combine_swing = random.randint(-8, 8)
    draft_stock = clamp(overall + combine_swing, 25, 95)
    all_prospects = draft_class + [{"id":0,"name":player["name"],"position":player["position"],"height":player["height"],"weight":player["weight"],"age":player["age"],"overall":draft_stock,"potential":player.get("potential",50),"is_player":True}]
    all_prospects.sort(key=lambda x: x["overall"], reverse=True)
    player_rank = next(i for i,p in enumerate(all_prospects) if p.get("is_player"))
    draft_position = player_rank + 1
    team_pick_idx = min(draft_position - 1, 29)
    drafted_team_id = draft_order[team_pick_idx] if team_pick_idx < 30 else random.choice(list(TEAMS.keys()))
    drafted_team = TEAMS.get(drafted_team_id, TEAMS[1])
    draft_round = 1 if draft_position <= 30 else 2
    salary_scale = {1:10.0,2:8.5,3:7.5,4:6.5,5:5.8,10:4.0,15:3.0,20:2.2,30:1.8,45:1.0}
    salary = 1.0
    for thresh, sal in sorted(salary_scale.items(), reverse=True):
        if draft_position <= thresh: salary = sal
    with get_db() as db:
        db.execute("UPDATE players SET team_id=?,draft_pick=?,draft_year=(SELECT current_season FROM league_state WHERE id=1),clout=?,fan_base=?,updated_at=datetime('now') WHERE id=?",
                   (drafted_team_id, draft_position, 2+draft_position*0.3, 3+draft_position*0.5, player_id))
        db.execute("UPDATE contracts SET team_id=?,annual_salary=?,total_value=? WHERE player_id=? AND season_number=0",
                   (drafted_team_id, salary, salary*3, player_id))
    return {"draft_position":draft_position,"draft_round":draft_round,"team":drafted_team["name"],"team_abbr":drafted_team["abbr"],"combine_swing":combine_swing,"draft_stock":draft_stock,"rookie_salary":salary,"top_prospects":all_prospects[:10]}

# ============================================================
# GAME SIMULATION ENGINE
# ============================================================

def simulate_game(player_id: str, opponent_team_id: int = None, is_playoff: bool = False) -> Dict:
    """Serialize game simulation to prevent concurrent read-modify-write races."""
    with _SIM_LOCK:
        return _simulate_game_inner(player_id, opponent_team_id, is_playoff)

def _simulate_game_inner(player_id: str, opponent_team_id: int = None, is_playoff: bool = False) -> Dict:
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not player: raise HTTPException(status_code=404, detail="Player not found")
    state = get_league_state()
    # Server-side guard: games can only be played during the season, and not past 82
    if state["current_phase"] == "offseason":
        raise HTTPException(status_code=400, detail="It's the offseason. Advance to the next season to play games.")
    if not is_playoff and state["games_played_in_season"] >= 82:
        raise HTTPException(status_code=400, detail="Season is complete (82 games played). Finalize the season first.")
    if opponent_team_id is None:
        schedule = generate_season_schedule(player["team_id"])
        idx = min(state["games_played_in_season"], 81)
        opponent_team_id = schedule[idx]
    opp = TEAMS.get(opponent_team_id, TEAMS[1])
    team = TEAMS.get(player["team_id"], TEAMS[1])

    fatigue_penalty = player["fatigue"]/100.0
    if player["load_management"]: fatigue_penalty = max(fatigue_penalty-0.15, 0)

    base_mpg = 24 + (player["stamina"]-40)*0.25 + (calculate_overall_rating(player)-60)*0.15
    base_mpg = clamp(base_mpg, 8, 42)
    if player["load_management"]: base_mpg -= 8
    if is_playoff: base_mpg += 5
    minutes = clamp(round(base_mpg - fatigue_penalty*12 + random.uniform(-4,4), 1), 2, 44)
    if player["injury_games_remaining"] > 0: minutes = 0

    streak_mod = 0
    if player["hot_streak"] > 0: streak_mod = min(player["hot_streak"]*2.5, 15)
    elif player["cold_streak"] < 0: streak_mod = max(player["cold_streak"]*2.5, -15)

    role_usage = {"Ball-Dominant Creator":0.33,"Off-Ball Finisher":0.21,"Rim Protector":0.14,"Two-Way Wing":0.25,"3-and-D Specialist":0.17,"Point Forward":0.28,"Stretch Big":0.19,"Defensive Anchor":0.12}
    usage_rate = role_usage.get(player["role"], 0.24)

    total_poss = random.randint(195, 210)
    court_pct = minutes/48.0
    box = {"pts":0,"oreb":0,"dreb":0,"reb":0,"ast":0,"stl":0,"blk":0,"tov":0,"pf":0,"fga":0,"fgm":0,"tpa":0,"tpm":0,"fta":0,"ftm":0}
    team_off = team["off"]; opp_def = opp["def"]; opp_off = opp["off"]; team_def = team["def"]
    team_score = 0; opp_score = 0

    for pos_num in range(total_poss):
        is_clutch = (pos_num > total_poss-15) and abs(team_score-opp_score) <= 8
        my_possession = random.random() < 0.50
        if my_possession:
            def_factor = opp_def/110.0
            base_prob = team_off/155.0 * def_factor * 0.68
            player_on = random.random() < court_pct
            player_involved = player_on and random.random() < usage_rate*1.25
            if player_involved:
                action = determine_action(player, is_clutch, streak_mod)
                result = resolve_action(player, action, opp, is_clutch, streak_mod)
                box = update_box(box, result)
                if result.get("points",0) > 0: team_score += result["points"]
                if result.get("assist",0) > 0: team_score += result.get("assist_points",2)
            else:
                if random.random() < base_prob:
                    team_score += weighted_choice({2:56,3:32,0:12})
        else:
            def_factor = team_def/110.0
            opp_prob = opp_off/155.0 * def_factor * 0.68
            if random.random() < opp_prob:
                opp_score += weighted_choice({2:54,3:30,0:16})
            if random.random() < court_pct:
                dr = resolve_defense(player, is_clutch)
                box = update_def_box(box, dr)

    box["reb"] = box["oreb"] + box["dreb"]
    if minutes > 6 and box["fga"] < 1:
        box["fga"] = max(1, int(minutes*usage_rate*0.35))
        box["fgm"] = max(0, int(box["fga"]*0.3))

    adv = calc_advanced(box, minutes, total_poss)
    plus_minus = team_score-opp_score if minutes > 0 else 0
    result = "W" if team_score > opp_score else "L"

    new_fatigue = clamp(player["fatigue"] + (minutes/40.0)*random.uniform(3,7), 0, 100)
    new_hot = player["hot_streak"]; new_cold = player["cold_streak"]
    if box["pts"] >= 28: new_hot = min(new_hot+2,5); new_cold = 0
    elif box["pts"] >= 20: new_hot = min(new_hot+1,5); new_cold = 0
    elif box["pts"] <= 6 and box["fga"] >= 7: new_cold = max(new_cold-1,-5); new_hot = 0
    else:
        if new_hot > 0 and random.random() < 0.25: new_hot -= 1
        if new_cold < 0 and random.random() < 0.25: new_cold += 1

    inj_risk = player["injury_risk"] + (minutes/36.0)*random.uniform(0,1.5)*(1.2-player["durability"]/100.0)
    if player["fatigue"] > 65: inj_risk += 1.5
    injury = None
    if minutes > 0 and random.random() < inj_risk/100.0:
        sev = random.random()
        if sev < 0.35: injury = ("Minor sprain", random.randint(1,4))
        elif sev < 0.60: injury = ("Moderate strain", random.randint(5,14))
        elif sev < 0.85: injury = ("Serious tear", random.randint(15,30))
        else: injury = ("Major rupture", random.randint(31,70))
        inj_risk = 0

    morale_delta = (1 if result=="W" else -1)*random.randint(1,3)
    if box["pts"] >= 25: morale_delta += random.randint(2,4)
    new_morale = clamp(player["morale"]+morale_delta, 10, 100)

    # Resolve injury state: a new injury overrides; otherwise decrement recovery timer.
    new_inj_status = None
    new_inj_games = 0
    if injury:
        new_inj_status = injury[0]
        new_inj_games = injury[1]
    elif player["injury_games_remaining"] > 0:
        remaining = player["injury_games_remaining"] - 1
        if remaining > 0:
            new_inj_status = player["injury_status"]
            new_inj_games = remaining
        # else recovered: stays None/0

    # Games played only count if the player actually appeared (not injured out).
    played = 1 if minutes > 0 else 0

    with get_db() as db:
        gcols = ["player_id","season_number","game_number","opponent_team_id","is_playoff","is_home","result","team_score","opponent_score","minutes","pts","reb","oreb","dreb","ast","stl","blk","tov","pf","fga","fgm","tpa","tpm","fta","ftm","plus_minus","per","ts_pct","usg_pct","game_score","eff"]
        gvals = [player_id,state["current_season"],state["games_played_in_season"]+1,opponent_team_id,int(is_playoff),int(random.random()<0.5),result,team_score,opp_score,
                 minutes,box["pts"],box["reb"],box["oreb"],box["dreb"],box["ast"],box["stl"],box["blk"],box["tov"],box["pf"],
                 box["fga"],box["fgm"],box["tpa"],box["tpm"],box["fta"],box["ftm"],plus_minus,adv["per"],adv["ts_pct"],adv["usg_pct"],adv["game_score"],adv["eff"]]
        assert len(gcols) == len(gvals), f"game_logs mismatch: {len(gcols)} vs {len(gvals)}"
        db.execute(f"INSERT INTO game_logs ({','.join(gcols)}) VALUES ({','.join(['?']*len(gcols))})", gvals)
        db.execute("""UPDATE players SET s_pts=s_pts+?,s_reb=s_reb+?,s_ast=s_ast+?,s_stl=s_stl+?,s_blk=s_blk+?,s_tov=s_tov+?,s_fga=s_fga+?,s_fgm=s_fgm+?,s_3pa=s_3pa+?,s_3pm=s_3pm+?,s_fta=s_fta+?,s_ftm=s_ftm+?,s_games=s_games+?,s_min=s_min+?,s_pf=s_pf+?,fatigue=?,injury_risk=?,morale=?,hot_streak=?,cold_streak=?,s_wins=s_wins+?,s_losses=s_losses+?,injury_status=?,injury_games_remaining=? WHERE id=?""",
            (box["pts"],box["reb"],box["ast"],box["stl"],box["blk"],box["tov"],box["fga"],box["fgm"],box["tpa"],box["tpm"],box["fta"],box["ftm"],
             played,minutes,box["pf"],new_fatigue,inj_risk,new_morale,new_hot,new_cold,1 if result=="W" else 0,1 if result=="L" else 0,
             new_inj_status,new_inj_games,player_id))
        db.execute("UPDATE league_state SET games_played_in_season=games_played_in_season+1 WHERE id=1")

    return {"game_number":state["games_played_in_season"]+1,"opponent":opp["name"],"opponent_abbr":opp["abbr"],"result":result,"team_score":team_score,"opponent_score":opp_score,"minutes":minutes,"box_score":box,"advanced":adv,"plus_minus":plus_minus,"fatigue":round(new_fatigue,1),"injury":{"type":new_inj_status,"games":new_inj_games} if new_inj_status else None,"morale":new_morale,"hot_streak":new_hot,"cold_streak":new_cold}

def determine_action(player, is_clutch, streak_mod):
    role_actions = {
        "Ball-Dominant Creator":{"iso_score":28,"pnr":25,"pull_up":22,"drive_and_kick":13,"catch_shoot":7},
        "Off-Ball Finisher":{"catch_shoot":28,"cut":28,"iso_score":14,"drive_and_kick":14,"pnr":14},
        "Rim Protector":{"post_up":28,"putback":22,"catch_shoot":20,"cut":20,"iso_score":8},
        "Two-Way Wing":{"iso_score":22,"catch_shoot":22,"drive_and_kick":20,"pull_up":16,"cut":18},
        "3-and-D Specialist":{"catch_shoot":45,"cut":25,"iso_score":14,"drive_and_kick":9,"pull_up":5},
        "Point Forward":{"pnr":28,"drive_and_kick":25,"iso_score":20,"catch_shoot":13,"pull_up":12},
        "Stretch Big":{"catch_shoot":35,"post_up":22,"cut":18,"putback":14,"iso_score":9},
        "Defensive Anchor":{"putback":32,"post_up":22,"catch_shoot":20,"cut":18,"iso_score":6},
    }
    weights = dict(role_actions.get(player["role"], role_actions["Two-Way Wing"]))
    if is_clutch and player["clutch_factor"] > 55:
        weights["iso_score"] = weights.get("iso_score",20)+14
        if "pull_up" in weights: weights["pull_up"] += 8
    return weighted_choice(weights)

def resolve_action(player, action, opp, is_clutch, streak_mod):
    r = {"points":0,"fgm":0,"fga":0,"tpa":0,"tpm":0,"fta":0,"ftm":0,"tov":0,"assist":0,"assist_points":0}
    def_factor = opp["def"]/110.0
    stk = 1 + streak_mod/100.0
    cl = 1 + (player["clutch_factor"]-50)/180.0 if is_clutch else 1.0

    if action == "iso_score":
        r["fga"]=1
        p = (player["first_step"]+player["finishing"]+player["mid_range"]*0.6)/290.0*def_factor*0.88*stk*cl
        if random.random() < p:
            if random.random() < player["pull_up_3pt"]/145.0:
                r["tpa"]=1; r["tpm"]=1; r["points"]=3
            else:
                r["fgm"]=1; r["points"]=2
            if random.random() < player["drawing_fouls"]/320.0:
                r["fta"]=1; r["ftm"]=1 if random.random()<player["free_throw"]/100.0 else 0; r["points"]+=r["ftm"]
        else:
            if random.random() < player["pull_up_3pt"]/145.0: r["tpa"]=1
            if random.random() < player["drawing_fouls"]/380.0:
                r["fta"]=2; r["ftm"]=sum(1 for _ in range(2) if random.random()<player["free_throw"]/100.0); r["points"]=r["ftm"]

    elif action == "catch_shoot":
        r["fga"]=1
        p = (player["catch_shoot_3pt"]*1.3+player["off_ball"]*0.5)/175.0*def_factor*0.85*stk
        is_three = random.random() < 0.62
        if is_three:
            r["tpa"]=1
            if random.random() < p: r["tpm"]=1; r["points"]=3
        else:
            if random.random() < p*1.12: r["fgm"]=1; r["points"]=2

    elif action == "pnr":
        d = weighted_choice({"score":28+player["finishing"]/5,"pass_to_roller":26+player["pnr_vision"]/4,"kick_out":22+player["passing_accuracy"]/5,"pull_up":24})
        if d == "score":
            r["fga"]=1
            if random.random() < (player["finishing"]+player["first_step"])/240.0*def_factor: r["fgm"]=1; r["points"]=2
        elif d in ("pass_to_roller","kick_out"):
            if random.random() < player["passing_accuracy"]/125.0: r["assist"]=1; r["assist_points"]=weighted_choice({2:58,3:28,0:14})
        elif d == "pull_up":
            r["fga"]=1; r["tpa"]=1
            if random.random() < player["mid_range"]/210.0*stk*cl: r["tpm"]=1; r["points"]=3

    elif action == "pull_up":
        r["fga"]=1; r["tpa"]=1
        p = (player["pull_up_3pt"]+player["mid_range"]*0.5)/195.0*def_factor*stk*cl
        if random.random() < p: r["tpm"]=1; r["points"]=3

    elif action == "drive_and_kick":
        if random.random() < player["first_step"]/135.0*def_factor:
            if random.random() < player["passing_accuracy"]/125.0:
                r["assist"]=1; r["assist_points"]=weighted_choice({2:56,3:32,0:12})
            else:
                r["fga"]=1
                if random.random() < player["finishing"]/185.0*def_factor: r["fgm"]=1; r["points"]=2
        else: r["tov"]=1

    elif action == "cut":
        r["fga"]=1
        if random.random() < (player["off_ball"]+player["finishing"])/235.0*def_factor: r["fgm"]=1; r["points"]=2

    elif action in ("post_up","putback"):
        r["fga"]=1
        if random.random() < (player["strength"]+player["core_stability"]+player["finishing"])/340.0*def_factor: r["fgm"]=1; r["points"]=2
    return r

def resolve_defense(player, is_clutch):
    r = {"stl":0,"blk":0,"dreb":0,"oreb":0,"pf":0}
    if random.random() < (player["steal"]+player["perimeter_defense"]*0.3+player["bbiq"]*0.2)/3300.0*(0.6 if is_clutch else 1.0): r["stl"]=1
    if not r["stl"] and random.random() < (player["rim_protection"]+player["vertical_jump"]*0.4)/5200.0: r["blk"]=1
    if random.random() < (player["box_out"]+player["strength"]*0.35+player["vertical_jump"]*0.15)/1400.0: r["dreb"]=1
    if random.random() < (player["box_out"]+player["vertical_jump"]*0.4+player["core_stability"]*0.2)/3000.0: r["oreb"]=1
    fc = 0.018+(1-player["bbiq"]/100.0)*0.04+(1-player["composure"]/100.0)*0.015
    if random.random() < fc: r["pf"]=1; r["blk"]=0
    return r

def update_box(box, r):
    for k in ["fgm","fga","tpa","tpm","fta","ftm","tov"]:
        box[k] = box.get(k,0) + r.get(k,0)
    box["pts"] = box.get("pts",0) + r.get("points",0)  # result uses "points" key
    box["fgm"] += r.get("tpm",0)  # made 3PM also count as FGM
    return box

def update_def_box(box, r):
    for k in ["stl","blk","dreb","oreb","pf"]:
        box[k] = box.get(k,0) + r.get(k,0)
    return box

def calc_advanced(box, minutes, possessions):
    if minutes < 1: return {"per":0,"ts_pct":0,"usg_pct":0,"game_score":0,"eff":0}
    fga,fgm = box["fga"],box["fgm"]; tpa,tpm = box["tpa"],box["tpm"]
    fta,ftm = box["fta"],box["ftm"]; pts,reb,ast = box["pts"],box["reb"],box["ast"]
    stl,blk,tov,pf = box["stl"],box["blk"],box["tov"],box["pf"]
    ts_denom = 2*(fga+0.44*fta)
    ts_pct = round(pts/ts_denom,3) if ts_denom>0 else 0
    team_poss = possessions*0.5
    usg = 100*(fga+0.44*fta+tov)*(48/max(1,minutes))/max(1,team_poss*5)
    usg_pct = round(clamp(usg,3,55),1)
    gs = round(pts+0.4*fgm-0.7*fga-0.4*(fta-ftm)+0.7*box["oreb"]+0.3*box["dreb"]+stl+0.7*ast+0.7*blk-0.4*pf-tov,1)
    eff = pts+reb+ast+stl+blk-(fga-fgm)-(fta-ftm)-tov
    uPER = (1/max(1,minutes))*(pts+0.85*fgm+0.5*tpm+0.7*box["oreb"]+0.3*box["dreb"]+0.9*ast+1.1*stl+1.2*blk-0.9*fga-0.5*fta-0.8*tov-0.3*pf)*15
    per = round(clamp(uPER,0,55),1)
    return {"per":per,"ts_pct":ts_pct,"usg_pct":usg_pct,"game_score":gs,"eff":eff}

def generate_season_schedule(team_id):
    rng = random.Random(team_id*777 + get_league_state().get("current_season",1)*131)
    all_teams = list(TEAMS.keys())
    schedule = []
    div_teams = [t for t in TEAMS if TEAMS[t]["div"]==TEAMS[team_id]["div"] and t != team_id]
    conf_teams = [t for t in TEAMS if TEAMS[t]["conf"]==TEAMS[team_id]["conf"] and t != team_id and t not in div_teams]
    opp_conf = [t for t in TEAMS if t not in conf_teams and t != team_id and t not in div_teams]
    for t in div_teams: schedule.extend([t]*4)
    for t in conf_teams: schedule.extend([t]*rng.choice([3,4]))
    for t in opp_conf: schedule.extend([t]*2)
    rng.shuffle(schedule)
    return schedule[:82]

# ============================================================
# SEASON MANAGEMENT
# ============================================================
def init_league_state():
    with get_db() as db:
        db.execute("INSERT OR IGNORE INTO league_state (id,current_season,current_phase,games_played_in_season) VALUES (1,1,'regular_season',0)")

def get_league_state() -> Dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM league_state WHERE id=1").fetchone()
        return dict(row) if row else {"current_season":1,"current_phase":"regular_season","games_played_in_season":0}

def advance_league_phase():
    with get_db() as db:
        s = dict(db.execute("SELECT * FROM league_state WHERE id=1").fetchone())
        if s["current_phase"] == "regular_season":
            db.execute("UPDATE league_state SET current_phase='playoffs',games_played_in_season=0 WHERE id=1")
        elif s["current_phase"] == "playoffs":
            db.execute("UPDATE league_state SET current_phase='offseason',games_played_in_season=0 WHERE id=1")
        elif s["current_phase"] == "offseason":
            db.execute("UPDATE league_state SET current_season=current_season+1,current_phase='regular_season',games_played_in_season=0 WHERE id=1")

def finalize_season(player_id: str) -> Dict:
    state = get_league_state()
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not p: raise HTTPException(status_code=404, detail="Player not found")
        # Guard: must have played a full regular season
        if state["games_played_in_season"] < 82:
            raise HTTPException(status_code=400, detail=f"Season not complete ({state['games_played_in_season']}/82 games). Keep playing.")
        # Idempotency guard: don't finalize the same season twice
        existing = db.execute("SELECT id FROM season_summaries WHERE player_id=? AND season_number=?", (player_id, state["current_season"])).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="This season has already been finalized.")
    g = max(1, p["s_games"]); m = max(1, p["s_min"])
    mpg = round(m/g,1); ppg = round(p["s_pts"]/g,1); rpg = round(p["s_reb"]/g,1)
    apg = round(p["s_ast"]/g,1); spg = round(p["s_stl"]/g,1); bpg = round(p["s_blk"]/g,1)
    topg = round(p["s_tov"]/g,1)
    fg_pct = round(p["s_fgm"]/max(1,p["s_fga"]),3); tp_pct = round(p["s_3pm"]/max(1,p["s_3pa"]),3)
    ft_pct = round(p["s_ftm"]/max(1,p["s_fta"]),3)
    ws = round(p["s_wins"]*(ppg+rpg*0.5+apg*0.5)/160.0,1)
    bpm = round((ppg*0.4+rpg*0.3+apg*0.5+spg*1.5+bpg*1.5-topg*1.0)/(max(1,mpg)/36.0)-2.0,1)
    vorp = round(max(0,bpm+2)*g/82.0*1.5,1)
    per = clamp(round(15+(ppg-14)*0.8+(rpg-5)*0.3+(apg-3)*0.4+(spg-1)*2+(bpg-0.5)*2,1),0,45)
    ts_denom = 2*(p["s_fga"]+0.44*p["s_fta"])
    ts_pct = round(p["s_pts"]/max(1,ts_denom),3)
    usg_pct = clamp(round(100*(p["s_fga"]+0.44*p["s_fta"]+p["s_tov"])*(48/max(1,mpg))/500,1),3,50)

    awards = []
    mvp_score = ppg*0.8+rpg*0.5+apg*0.8+spg*3+bpg*3+p["s_wins"]*0.6+p["mvp_votes"]*0.3
    if mvp_score > 68 and p["s_wins"] > 40: awards.append("MVP")
    if mvp_score > 52: awards.append("All-NBA First Team")
    elif mvp_score > 40: awards.append("All-NBA Second Team")
    elif mvp_score > 30: awards.append("All-NBA Third Team")
    def_score = spg*4+bpg*5+p["perimeter_defense"]*0.1+p["help_defense"]*0.1+p["rim_protection"]*0.1
    if def_score > 32: awards.append("DPOY")
    if def_score > 26: awards.append("All-Defensive First Team")
    elif def_score > 20: awards.append("All-Defensive Second Team")
    if p["experience"] == 0:
        if ppg > 14: awards.append("ROTY")
        awards.append("All-Rookie First Team")
    if 11 < ppg < 23 and g > 55: awards.append("Sixth Man of the Year")
    playoff_result = None
    if p["s_wins"] >= 40:
        rounds = ["First Round","Conf Semis","Conf Finals","Finals Loss","NBA CHAMPION"]
        idx = clamp((p["s_wins"]-38)//8 + random.randint(-1,1), 0, 4)
        playoff_result = rounds[idx]
        if playoff_result == "NBA CHAMPION": awards.append("NBA Champion")

    with get_db() as db:
        scols = ["player_id","season_number","team_id","age","games_played","mpg","ppg","rpg","apg","spg","bpg","topg","fg_pct","tp_pct","ft_pct","per","ts_pct","usg_pct","ws","bpm","vorp","team_wins","team_losses","playoff_result","role","awards"]
        svals = [player_id,state["current_season"],p["team_id"],p["age"],g,mpg,ppg,rpg,apg,spg,bpg,topg,fg_pct,tp_pct,ft_pct,per,ts_pct,usg_pct,ws,bpm,vorp,p["s_wins"],p["s_losses"],playoff_result,p["role"],json.dumps(awards)]
        assert len(scols) == len(svals), f"season_summaries mismatch: {len(scols)} vs {len(svals)}"
        db.execute(f"INSERT INTO season_summaries ({','.join(scols)}) VALUES ({','.join(['?']*len(scols))})", svals)
        for a in awards:
            db.execute("INSERT INTO awards (player_id,season_number,award_type,award_name) VALUES (?,?,'season',?)",(player_id,state["current_season"],a))
        db.execute("""UPDATE players SET s_pts=0,s_reb=0,s_ast=0,s_stl=0,s_blk=0,s_tov=0,s_fga=0,s_fgm=0,s_3pa=0,s_3pm=0,s_fta=0,s_ftm=0,s_games=0,s_min=0,s_pf=0,s_wins=0,s_losses=0,hot_streak=0,cold_streak=0,injury_status=NULL,injury_games_remaining=0,fatigue=MAX(0,fatigue-45),injury_risk=MAX(0,injury_risk-25),experience=experience+1,mvp_votes=0 WHERE id=?""",(player_id,))
        # Move league into offseason so training unlocks (and cannot double-finalize)
        db.execute("UPDATE league_state SET current_phase='offseason', games_played_in_season=0 WHERE id=1")
    age_changes = apply_aging(player_id)
    return {"season":state["current_season"],"stats":{"ppg":ppg,"rpg":rpg,"apg":apg,"spg":spg,"bpg":bpg,"topg":topg,"fg_pct":fg_pct,"tp_pct":tp_pct,"ft_pct":ft_pct,"mpg":mpg},"advanced":{"per":per,"ts_pct":ts_pct,"usg_pct":usg_pct,"ws":ws,"bpm":bpm,"vorp":vorp},"team_record":f"{p['s_wins']}-{p['s_losses']}","playoff_result":playoff_result,"awards":awards,"age_changes":age_changes}

def apply_aging(player_id: str) -> Dict:
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
    new_age = p["age"] + 1
    changes = {}
    if new_age >= 30:
        rate = (new_age-29)*0.7
        for attr in ["vertical_jump","speed","lateral_quickness","strength","core_stability","stamina","durability","first_step","finishing"]:
            decline = round(rate*random.uniform(0.4,1.4))
            if decline > 0: changes[attr] = clamp(p[attr]-decline,8,99)
    if new_age <= 35:
        for attr in ["bbiq","composure","leadership"]:
            gain = random.randint(0,2)
            if gain > 0: changes[attr] = clamp(p[attr]+gain,20,99)
    if new_age < 27:
        dev_chance = p.get("potential",50)/100.0 * p.get("work_ethic",50)/100.0
        if random.random() < dev_chance:
            dev_attrs = ["mid_range","catch_shoot_3pt","perimeter_defense","help_defense","pnr_vision","ball_security"]
            for attr in random.sample(dev_attrs, min(3, len(dev_attrs))):
                gain = random.randint(1,3)
                changes[attr] = clamp(p[attr]+gain,15,95)
    with get_db() as db:
        parts = ["age=?","updated_at=datetime('now')"]; vals = [new_age]
        for attr, val in changes.items():
            parts.append(f"{attr}=?"); vals.append(val)
        vals.append(player_id)
        db.execute(f"UPDATE players SET {', '.join(parts)} WHERE id=?", vals)
    return {"new_age":new_age,"attribute_changes":changes}

# ============================================================
# TRAINING
# ============================================================
TRAINING_PROGRAMS = {
    "Explosive Athlete": {"desc":"Plyometrics and sprint work to boost vertical, first step, and speed.","primary":["vertical_jump","speed","first_step"],"secondary":["lateral_quickness","stamina"],"intensity":0.82,"inj_risk":5},
    "Strength & Power": {"desc":"Heavy weight training for strength, core stability, and contact finishing.","primary":["strength","core_stability","finishing"],"secondary":["box_out","vertical_jump"],"intensity":0.78,"inj_risk":4},
    "Shooting Lab": {"desc":"10,000 reps: catch-and-shoot, pull-up, mid-range, free throws.","primary":["catch_shoot_3pt","mid_range","pull_up_3pt","free_throw"],"secondary":["off_ball"],"intensity":0.62,"inj_risk":1},
    "Ball Handling": {"desc":"Tight handles, PnR reads, passing under pressure.","primary":["ball_security","pnr_vision","passing_accuracy"],"secondary":["first_step","composure"],"intensity":0.68,"inj_risk":2},
    "Defensive Specialist": {"desc":"Lateral slides, closeouts, film study for defensive IQ.","primary":["perimeter_defense","help_defense","lateral_quickness","steal"],"secondary":["rim_protection","bbiq"],"intensity":0.72,"inj_risk":3},
    "Conditioning": {"desc":"Marathon training — stamina, durability, body maintenance.","primary":["stamina","durability"],"secondary":["speed","strength"],"intensity":0.58,"inj_risk":0},
    "Post Game": {"desc":"Footwork, hook shots, rebounding positioning.","primary":["finishing","box_out","core_stability"],"secondary":["strength","mid_range"],"intensity":0.68,"inj_risk":2},
    "Mental Toughness": {"desc":"Pressure simulation, meditation, late-game scenario work.","primary":["clutch_factor","composure","bbiq"],"secondary":["leadership","mid_range"],"intensity":0.48,"inj_risk":0},
}

def apply_training(player_id: str, program_name: str) -> Dict:
    if program_name not in TRAINING_PROGRAMS:
        raise HTTPException(status_code=400, detail=f"Unknown program: {program_name}")
    prog = TRAINING_PROGRAMS[program_name]
    state = get_league_state()
    if state["current_phase"] != "offseason":
        raise HTTPException(status_code=400, detail="Training is only available during the offseason.")
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not p: raise HTTPException(status_code=404, detail="Player not found")
        if p["trained_season"] == state["current_season"]:
            raise HTTPException(status_code=400, detail="You've already trained this offseason. One program per offseason.")
    age = p["age"]
    if age < 22: tmult = 1.35
    elif age < 26: tmult = 1.12
    elif age < 30: tmult = 0.88
    elif age < 33: tmult = 0.60
    else: tmult = 0.30
    wmult = 0.65 + (p["work_ethic"]/100.0)*0.7
    uncertainty = random.uniform(0.7, 1.3)
    results = {"program":program_name,"gains":{},"injuries":[],"fatigue_cleared":0}
    for attr in prog["primary"]:
        cur = p.get(attr,50)
        base_gain = 3 if attr in ("stamina","durability") else 2
        gain = max(0, round(base_gain*tmult*wmult*prog["intensity"]*uncertainty))
        if cur > 80: gain = max(0, gain-1)
        if cur > 90: gain = max(0, gain-2)
        new_val = clamp(cur+gain,10,99)
        results["gains"][attr] = {"before":cur,"after":new_val,"gain":gain}
    for attr in prog["secondary"]:
        cur = p.get(attr,50)
        gain = max(0, round(1.5*tmult*wmult*prog["intensity"]*uncertainty))
        if cur > 85: gain = max(0, gain-1)
        new_val = clamp(cur+gain,10,99)
        results["gains"][attr] = {"before":cur,"after":new_val,"gain":gain}
    inj_chance = prog["inj_risk"]*(1.2-p["durability"]/100.0)/100.0
    injury_occurred = random.random() < inj_chance
    if injury_occurred:
        itype = random.choice(["Minor training strain","Moderate muscle pull","Stress reaction"])
        igames = random.randint(1,12) if "Minor" in itype else random.randint(8,28)
        results["injuries"] = [{"type":itype,"games":igames}]
    fatigue_cleared = random.uniform(55,90)
    results["fatigue_cleared"] = round(fatigue_cleared,1)
    with get_db() as db:
        parts = ["fatigue=MAX(0,fatigue-?)","updated_at=datetime('now')"]; vals = [fatigue_cleared]
        for attr, data in results["gains"].items():
            parts.append(f"{attr}=?"); vals.append(data["after"])
        if injury_occurred:
            parts.append("injury_status=?"); vals.append(results["injuries"][0]["type"])
            parts.append("injury_games_remaining=?"); vals.append(results["injuries"][0]["games"])
        parts.append("trained_season=?"); vals.append(state["current_season"])
        vals.append(player_id)
        db.execute(f"UPDATE players SET {', '.join(parts)} WHERE id=?", vals)
    results["injury_occurred"] = injury_occurred
    return results

# ============================================================
# ECONOMY & MEDIA (Narrative, uncertain)
# ============================================================
def get_endorsement_offers(player_id: str) -> List[Dict]:
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not p: raise HTTPException(status_code=404, detail="Player not found")
        state = dict(db.execute("SELECT * FROM league_state WHERE id=1").fetchone())
        # Clear stale offers and generate a fresh, persisted set so signing can reference them server-side
        db.execute("DELETE FROM endorsement_offers WHERE player_id=?", (player_id,))
    fan = p["fan_base"]; clout = p["clout"]
    perf = (p["s_pts"]/max(1,p["s_games"]))/22.0
    brands = [("Nike",95,8.0),("Adidas",90,6.0),("Jordan Brand",98,10.0),("Under Armour",75,4.0),("Puma",70,3.5),("New Balance",65,2.5),("Anta",60,3.0),("Gatorade",80,2.0),("Beats",70,1.0),("State Farm",60,1.5),("Mercedes",70,1.5)]
    offers = []
    for brand, prestige, base in random.sample(brands, min(5, len(brands))):
        if fan > prestige-35:
            multi = perf*(fan/80.0)*(clout/50.0)
            annual = round(base*max(0.25,multi)*random.uniform(0.7,1.3),2)
            if annual > 0.2:
                years = random.choice([2,3,4,5])
                offers.append({"brand":brand,"prestige":prestige,"annual_value":annual,"years":years})
    with get_db() as db:
        for o in offers:
            cur = db.execute("INSERT INTO endorsement_offers (player_id,season_number,brand_name,annual_value,years,prestige) VALUES (?,?,?,?,?,?)",
                             (player_id, state["current_season"], o["brand"], o["annual_value"], o["years"], o["prestige"]))
            o["id"] = cur.lastrowid
    return sorted(offers, key=lambda o: o["annual_value"], reverse=True)

def sign_endorsement(player_id: str, offer_id: int) -> Dict:
    with get_db() as db:
        offer = db.execute("SELECT * FROM endorsement_offers WHERE id=? AND player_id=?", (offer_id, player_id)).fetchone()
        if not offer: raise HTTPException(status_code=404, detail="Offer not found or no longer available")
        brand = offer["brand_name"]; annual = offer["annual_value"]; years = offer["years"]
        db.execute("INSERT INTO endorsements (player_id,brand_name,annual_value,years_remaining,prestige) VALUES (?,?,?,?,?)",
                   (player_id, brand, annual, years, offer["prestige"]))
        db.execute("UPDATE players SET wealth=wealth+?,fan_base=MIN(100,fan_base+?) WHERE id=?",(annual,random.uniform(0.3,1.8),player_id))
        db.execute("DELETE FROM endorsement_offers WHERE id=?", (offer_id,))
    return {"brand":brand,"annual_value":annual,"years":years,"status":"signed"}

def make_investment(player_id: str, name: str, amount: float, risk: str) -> Dict:
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
    if amount > p["wealth"]: raise HTTPException(status_code=400, detail="Insufficient funds")
    returns = {"Low":(0.02,0.09),"Medium":(-0.06,0.22),"High":(-0.35,0.55)}
    lo, hi = returns.get(risk,(0.0,0.18))
    annual_return = round(random.uniform(lo,hi),3)
    with get_db() as db:
        db.execute("INSERT INTO investments (player_id,name,amount_invested,current_value,annual_return,risk_level) VALUES (?,?,?,?,?,?)",(player_id,name,amount,amount,annual_return,risk))
        db.execute("UPDATE players SET wealth=wealth-? WHERE id=?",(amount,player_id))
    return {"name":name,"amount":amount,"annual_return":annual_return,"risk":risk}

MEDIA_SCENARIOS = [
    {"id":"postgame_loss","trigger":"after_loss","question":"Tough loss tonight. The fans want to hear from you.",
     "choices":[
        {"text":"\"This one's on me. I need to step up.\"","tone":"accountable","fan_base":(1,6),"clout":(-1,3),"chemistry":(1,5),"mvp":(0,2)},
        {"text":"\"We didn't execute as a group. We'll fix it.\"","tone":"diplomatic","fan_base":(-3,2),"clout":(-2,1),"chemistry":(-6,-1),"mvp":(-4,0)},
        {"text":"\"Next question. We're on to the next one.\"","tone":"dismissive","fan_base":(-4,0),"clout":(0,3),"chemistry":(-3,1),"mvp":(-2,1)}]},
    {"id":"mvp_campaign","trigger":"mid_season","question":"You're in the MVP conversation. How do you feel about that?",
     "choices":[
        {"text":"\"It's an honor just to be mentioned alongside those names.\"","tone":"humble","fan_base":(1,4),"clout":(1,5),"chemistry":(1,4),"mvp":(3,8)},
        {"text":"\"My numbers speak for themselves.\"","tone":"confident","fan_base":(0,5),"clout":(3,8),"chemistry":(-5,0),"mvp":(5,12)},
        {"text":"\"We're winning games. That's all I care about.\"","tone":"team-first","fan_base":(2,6),"clout":(0,4),"chemistry":(3,7),"mvp":(1,5)}]},
    {"id":"trade_rumors","trigger":"random","question":"Rumors are swirling that you want out. Any truth to that?",
     "choices":[
        {"text":"\"I'm committed to this city and this team.\"","tone":"loyal","fan_base":(3,8),"clout":(-4,0),"chemistry":(3,8),"mvp":(0,0)},
        {"text":"\"I'm focused on basketball, not rumors.\"","tone":"neutral","fan_base":(-2,2),"clout":(0,2),"chemistry":(-1,1),"mvp":(0,0)},
        {"text":"\"I want to win championships — wherever that takes me.\"","tone":"ambitious","fan_base":(-10,-2),"clout":(2,7),"chemistry":(-12,-3),"mvp":(-3,1)}]},
    {"id":"social_media","trigger":"random","question":"Old posts of yours have resurfaced online. How do you respond?",
     "choices":[
        {"text":"\"I was young. I've grown a lot since then.\"","tone":"sincere","fan_base":(-1,3),"clout":(0,3),"chemistry":(0,2),"mvp":(0,2)},
        {"text":"\"People are digging for drama. I'm not engaging.\"","tone":"defensive","fan_base":(-5,0),"clout":(-3,1),"chemistry":(-2,1),"mvp":(-5,0)},
        {"text":"Stay silent. Let it blow over.","tone":"silent","fan_base":(-3,1),"clout":(-1,1),"chemistry":(0,0),"mvp":(-4,0)}]},
]

NARRATIVES = {
    "accountable":"You earned respect by owning the loss. The locker room notices your leadership.",
    "diplomatic":"Your words came across as deflecting blame. Some teammates seemed frustrated.",
    "dismissive":"Fans and media felt brushed off. Your image took a minor hit.",
    "humble":"Your humility played well with voters and fans alike. Respect grows quietly.",
    "confident":"The bold statement raised eyebrows — some admire the swagger, others see arrogance.",
    "team-first":"Putting the team first resonated deeply. The coaching staff took note.",
    "loyal":"Your commitment shut down the trade rumors. The city loves you for it.",
    "neutral":"A safe answer that neither hurt nor helped. The story will likely die down.",
    "ambitious":"Your honesty about chasing rings stirred controversy. Management is on edge.",
    "sincere":"A sincere apology went over well. Most people respect growth.",
    "defensive":"Your combative response amplified the controversy. Not the best look.",
    "silent":"Silence left a vacuum. Speculation continues, but it'll fade with time.",
}

def handle_media_event(player_id: str, scenario_id: str, choice_index: int) -> Dict:
    scenario = next((s for s in MEDIA_SCENARIOS if s["id"]==scenario_id), None)
    if not scenario or choice_index < 0 or choice_index >= len(scenario["choices"]):
        raise HTTPException(status_code=400, detail="Invalid scenario or choice")
    choice = scenario["choices"][choice_index]
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
    effects = {}
    for key in ["fan_base","clout","chemistry"]:
        if key in choice:
            effects[key] = clamp(p.get(key,50) + random.randint(choice[key][0],choice[key][1]), 0, 100)
    if "mvp" in choice:
        effects["mvp_votes"] = clamp(p.get("mvp_votes",0) + random.randint(choice["mvp"][0],choice["mvp"][1]), 0, 100)
    narrative = NARRATIVES.get(choice["tone"], "Your words had a subtle impact on those around you.")
    with get_db() as db:
        parts = []; vals = []
        for key, val in effects.items():
            col = "mvp_votes" if key == "mvp_votes" else key
            parts.append(f"{col}=?"); vals.append(val)
        parts.append("morale=?"); vals.append(clamp(p["morale"]+random.randint(-3,5),10,100))
        parts.append("updated_at=datetime('now')")
        vals.append(player_id)
        db.execute(f"UPDATE players SET {', '.join(parts)} WHERE id=?", vals)
        db.execute("INSERT INTO media_events (player_id,season_number,event_type,description,choice_made,narrative_result) VALUES (?,(SELECT current_season FROM league_state WHERE id=1),'interview',?,?,?)",
                   (player_id, scenario["question"], choice["text"], narrative))
    return {"scenario":scenario["question"],"choice":choice["text"],"narrative":narrative,"tone":choice["tone"]}

def get_random_media_scenario(player_id: str) -> Dict:
    state = get_league_state()
    phase = state["current_phase"]
    if phase == "playoffs": candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("playoffs","random")]
    elif phase == "regular_season" and state["games_played_in_season"] > 40: candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("mid_season","random","after_loss")]
    else: candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("random","after_loss")]
    return {"scenario":random.choice(candidates)}

# ============================================================
# CLOUT ACTIONS
# ============================================================
def request_trade(player_id: str, desired_team_id: int) -> Dict:
    if desired_team_id not in TEAMS:
        raise HTTPException(status_code=400, detail=f"Unknown team id: {desired_team_id}")
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not p: raise HTTPException(status_code=404, detail="Player not found")
    if p["clout"] < 25: return {"success":False,"message":"You don't have enough influence yet. Build your reputation first."}
    success = random.random() < min(0.85, p["clout"]/120.0)
    with get_db() as db:
        if success:
            db.execute("UPDATE players SET team_id=?,clout=MAX(0,clout-12),chemistry=50 WHERE id=?",(desired_team_id,player_id))
            db.execute("INSERT INTO career_progress (player_id,season_number,event_type,description) VALUES (?,(SELECT current_season FROM league_state WHERE id=1),'trade',?)",
                       (player_id, f"Forced trade to {TEAMS[desired_team_id]['name']}"))
            return {"success":True,"new_team":TEAMS[desired_team_id]["name"],"message":"The trade demand worked. You've been moved — a fresh start awaits."}
        else:
            db.execute("UPDATE players SET clout=MAX(0,clout-6),chemistry=MAX(10,chemistry-12),morale=MAX(10,morale-8) WHERE id=?",(player_id,))
            return {"success":False,"message":"Management refused your request. The fallout has hurt team chemistry."}

# ============================================================
# CAREER OVERVIEW
# ============================================================
def get_career_overview(player_id: str) -> Dict:
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
        if not p: raise HTTPException(status_code=404, detail="Player not found")
        seasons = [dict(s) for s in db.execute("SELECT * FROM season_summaries WHERE player_id=? ORDER BY season_number",(player_id,)).fetchall()]
        awards = [dict(a) for a in db.execute("SELECT * FROM awards WHERE player_id=? ORDER BY season_number DESC",(player_id,)).fetchall()]
    cg = sum(s["games_played"] for s in seasons); cp = sum(s["ppg"]*s["games_played"] for s in seasons)
    cr = sum(s["rpg"]*s["games_played"] for s in seasons); ca = sum(s["apg"]*s["games_played"] for s in seasons)
    chips = sum(1 for a in awards if a["award_name"]=="NBA Champion")
    mvps = sum(1 for a in awards if a["award_name"]=="MVP")
    all_nba = sum(1 for a in awards if "All-NBA" in a["award_name"])
    goat = chips*25+mvps*20+all_nba*8+(cp/1000)*3+(cr/500)*1+(ca/500)*2
    goat_pct = min(100, goat/6.5)
    return {"player":{"name":p["name"],"position":p["position"],"age":p["age"],"height":p["height"],"weight":p["weight"],"team":TEAMS.get(p["team_id"],{}).get("name","FA"),"experience":p["experience"],"clout":p["clout"],"fan_base":p["fan_base"],"wealth":round(p["wealth"],2),"morale":p["morale"]},"career_totals":{"games":cg,"pts":round(cp),"reb":round(cr),"ast":round(ca)},"goat_score":round(goat_pct,1),"championships":chips,"mvps":mvps,"all_nba":all_nba,"seasons":seasons,"awards":awards}

# ============================================================
# SAVE/LOAD
# ============================================================
def save_game(player_id: str, save_name: str, description: str = "") -> Dict:
    state = get_league_state(); sid = str(uuid.uuid4())[:8]
    with get_db() as db:
        p = db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone()
        if not p: raise HTTPException(status_code=404, detail="Player not found")
        snapshot = json.dumps({"player": dict(p), "league": state})
        ex = db.execute("SELECT id FROM save_files WHERE player_id=? AND save_name=?",(player_id,save_name)).fetchone()
        if ex:
            db.execute("UPDATE save_files SET season_number=?,description=?,snapshot=?,created_at=datetime('now') WHERE id=?",(state["current_season"],description,snapshot,ex["id"]))
            sid = ex["id"]
        else:
            db.execute("INSERT INTO save_files (id,player_id,save_name,season_number,description,snapshot) VALUES (?,?,?,?,?,?)",(sid,player_id,save_name,state["current_season"],description,snapshot))
    return {"save_id":sid,"save_name":save_name,"season":state["current_season"]}

def load_game(player_id: str, save_id: str) -> Dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM save_files WHERE id=? AND player_id=?",(save_id,player_id)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="Save not found")
        snap = json.loads(row["snapshot"])
        p = snap["player"]; lg = snap["league"]
        # Restore player row (all columns except id)
        cols = [c for c in p.keys() if c != "id"]
        set_clause = ", ".join(f"{c}=?" for c in cols) + ", updated_at=datetime('now')"
        vals = [p[c] for c in cols] + [player_id]
        db.execute(f"UPDATE players SET {set_clause} WHERE id=?", vals)
        # Restore league state
        db.execute("UPDATE league_state SET current_season=?, current_phase=?, games_played_in_season=? WHERE id=1",
                   (lg["current_season"], lg["current_phase"], lg["games_played_in_season"]))
    return {"loaded": True, "save_id": save_id, "season": lg["current_season"], "phase": lg["current_phase"]}

def list_saves(player_id: str) -> List[Dict]:
    with get_db() as db:
        return [{"id":s["id"],"save_name":s["save_name"],"season_number":s["season_number"],"description":s["description"],"created_at":s["created_at"]}
                for s in db.execute("SELECT id,save_name,season_number,description,created_at FROM save_files WHERE player_id=? ORDER BY created_at DESC",(player_id,)).fetchall()]

def export_career_json(player_id: str) -> Dict:
    career = get_career_overview(player_id)
    with get_db() as db:
        games = [dict(g) for g in db.execute("SELECT * FROM game_logs WHERE player_id=? ORDER BY season_number,game_number",(player_id,)).fetchall()]
        media = [dict(m) for m in db.execute("SELECT * FROM media_events WHERE player_id=? ORDER BY created_at DESC LIMIT 50",(player_id,)).fetchall()]
    career["game_logs"] = games; career["media_events"] = media
    return career

# ============================================================
# FASTAPI APP
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); yield

app = FastAPI(title="BBall Career Simulator v3", version="3.0.0", lifespan=lifespan)

class CreatePlayerRequest(BaseModel):
    name: str
    position: str
    age: int = 19
    height: float
    weight: float
    allocations: Dict[str, int]
    luck_bonus: Optional[int] = None

@app.post("/api/player/create")
def api_create(req: CreatePlayerRequest):
    if req.position not in POSITION_PROFILES: raise HTTPException(400,"Invalid position")
    if not (19 <= req.age <= 23): raise HTTPException(400, f"Age must be 19-23, got {req.age}")
    profile = POSITION_PROFILES[req.position]
    if not (profile["height_range"][0]-0.03 <= req.height <= profile["height_range"][1]+0.03):
        raise HTTPException(400,f"Height {req.height}m outside range for {req.position}")
    if not (profile["weight_range"][0]-5 <= req.weight <= profile["weight_range"][1]+5):
        raise HTTPException(400,f"Weight {req.weight}kg outside range for {req.position}")
    # Recompute pool deterministically (reusing the frontend's rolled luck) and validate the budget
    pool_info = calculate_point_pool(req.position, req.height, req.weight, req.luck_bonus)
    total_allocated = sum(req.allocations.values())
    if total_allocated != pool_info["total_points"]:
        raise HTTPException(400, f"Allocation total {total_allocated} does not match point pool {pool_info['total_points']}")
    pid = create_player_with_points(req.name, req.position, req.age, req.height, req.weight, req.allocations, req.luck_bonus)
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone())
    return {"player_id":pid,"player":sanitize_player(player),"pool_info":pool_info}

@app.get("/api/player/{player_id}")
async def api_get(player_id: str):
    with get_db() as db:
        p = db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone()
        if not p: raise HTTPException(404,"Not found")
    return {"player":sanitize_player(dict(p))}

@app.get("/api/player/{player_id}/attributes")
async def api_attrs(player_id: str):
    with get_db() as db:
        p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
    return {"static":{"height":p["height"],"weight":p["weight"],"wingspan":p["wingspan"],"standing_reach":p["standing_reach"],"hand_size":p["hand_size"],"frame_build":p["frame_build"],"body_fat_pct":p["body_fat_pct"]},
            "athleticism":{"vertical_jump":p["vertical_jump"],"speed":p["speed"],"lateral_quickness":p["lateral_quickness"],"strength":p["strength"],"core_stability":p["core_stability"],"stamina":p["stamina"],"durability":p["durability"]},
            "defense":{"perimeter_defense":p["perimeter_defense"],"help_defense":p["help_defense"],"steal":p["steal"],"rim_protection":p["rim_protection"],"box_out":p["box_out"]},
            "scoring":{"first_step":p["first_step"],"finishing":p["finishing"],"mid_range":p["mid_range"],"catch_shoot_3pt":p["catch_shoot_3pt"],"pull_up_3pt":p["pull_up_3pt"],"off_ball":p["off_ball"],"drawing_fouls":p["drawing_fouls"],"free_throw":p["free_throw"]},
            "playmaking":{"ball_security":p["ball_security"],"pnr_vision":p["pnr_vision"],"passing_accuracy":p["passing_accuracy"]},
            "mental":{"bbiq":p["bbiq"],"clutch_factor":p["clutch_factor"],"work_ethic":p["work_ethic"],"leadership":p["leadership"],"composure":p["composure"]}}

@app.get("/api/player/{player_id}/season-stats")
async def api_season_stats(player_id: str):
    with get_db() as db: p = dict(db.execute("SELECT * FROM players WHERE id=?",(player_id,)).fetchone())
    g = max(1,p["s_games"]); m = max(1,p["s_min"])
    return {"games":g,"mpg":round(m/g,1),"ppg":round(p["s_pts"]/g,1),"rpg":round(p["s_reb"]/g,1),"apg":round(p["s_ast"]/g,1),"spg":round(p["s_stl"]/g,1),"bpg":round(p["s_blk"]/g,1),"topg":round(p["s_tov"]/g,1),"fg_pct":round(p["s_fgm"]/max(1,p["s_fga"]),3),"tp_pct":round(p["s_3pm"]/max(1,p["s_3pa"]),3),"ft_pct":round(p["s_ftm"]/max(1,p["s_fta"]),3),"team_wins":p["s_wins"],"team_losses":p["s_losses"]}

@app.put("/api/player/{player_id}/role")
async def api_set_role(player_id: str, role: str = Query(...)):
    valid = ["Ball-Dominant Creator","Off-Ball Finisher","Rim Protector","Two-Way Wing","3-and-D Specialist","Point Forward","Stretch Big","Defensive Anchor"]
    if role not in valid: raise HTTPException(400,f"Invalid role. Options: {valid}")
    with get_db() as db: db.execute("UPDATE players SET role=?,updated_at=datetime('now') WHERE id=?",(role,player_id))
    return {"role":role}

@app.put("/api/player/{player_id}/load-management")
async def api_load_mgmt(player_id: str, enabled: bool = Query(...)):
    with get_db() as db: db.execute("UPDATE players SET load_management=?,updated_at=datetime('now') WHERE id=?",(int(enabled),player_id))
    return {"load_management":enabled}

@app.get("/api/draft/point-pool")
async def api_point_pool(position: str, height: float, weight: float):
    if position not in POSITION_PROFILES: raise HTTPException(400,"Invalid position")
    return calculate_point_pool(position, height, weight)

@app.post("/api/draft/simulate/{player_id}")
def api_draft(player_id: str): return simulate_draft(player_id)

@app.get("/api/draft/class")
def api_draft_class(): return {"prospects": generate_draft_class()[:30]}

@app.post("/api/game/simulate/{player_id}")
def api_sim_game(player_id: str, opponent_id: int = None, is_playoff: bool = False): return simulate_game(player_id, opponent_id, is_playoff)

@app.post("/api/game/simulate-batch/{player_id}")
def api_sim_batch(player_id: str, count: int = Query(5, le=20)):
    return {"games":[simulate_game(player_id) for _ in range(count)],"count":count}

@app.get("/api/game/logs/{player_id}")
async def api_logs(player_id: str, season: int = None, limit: int = 20):
    with get_db() as db:
        if season: rows = db.execute("SELECT * FROM game_logs WHERE player_id=? AND season_number=? ORDER BY game_number DESC LIMIT ?",(player_id,season,limit)).fetchall()
        else: rows = db.execute("SELECT * FROM game_logs WHERE player_id=? ORDER BY season_number DESC,game_number DESC LIMIT ?",(player_id,limit)).fetchall()
    return {"games":[dict(r) for r in rows]}

@app.get("/api/season/state")
async def api_state(): return get_league_state()

@app.post("/api/season/advance-phase")
async def api_advance():
    advance_league_phase(); return get_league_state()

@app.post("/api/season/finalize/{player_id}")
def api_finalize(player_id: str): return finalize_season(player_id)

@app.get("/api/season/schedule/{team_id}")
async def api_schedule(team_id: int):
    sched = generate_season_schedule(team_id)
    return {"team_id":team_id,"team":TEAMS.get(team_id,{}).get("name"),"schedule":[{"opponent_id":o,"opponent_name":TEAMS[o]["name"],"opponent_abbr":TEAMS[o]["abbr"],"opponent_ovr":TEAMS[o]["ovr"]} for o in sched]}

@app.get("/api/season/summaries/{player_id}")
async def api_summaries(player_id: str):
    with get_db() as db: rows = [dict(r) for r in db.execute("SELECT * FROM season_summaries WHERE player_id=? ORDER BY season_number",(player_id,)).fetchall()]
    return {"seasons":rows}

@app.get("/api/training/programs")
async def api_programs(): return {"programs":{k:{"desc":v["desc"],"primary":v["primary"],"secondary":v["secondary"],"intensity":v["intensity"],"injury_risk":v["inj_risk"]} for k,v in TRAINING_PROGRAMS.items()}}

@app.post("/api/training/apply/{player_id}")
def api_apply_training(player_id: str, program: str = Query(...)): return apply_training(player_id, program)

@app.get("/api/economy/endorsements/{player_id}")
async def api_endorsements(player_id: str): return {"offers":get_endorsement_offers(player_id)}

@app.post("/api/economy/sign-endorsement/{player_id}")
def api_sign_endorse(player_id: str, offer_id: int = Query(...)): return sign_endorsement(player_id, offer_id)

@app.get("/api/economy/endorsements-active/{player_id}")
async def api_active_endorse(player_id: str):
    with get_db() as db: return {"endorsements":[dict(r) for r in db.execute("SELECT * FROM endorsements WHERE player_id=? AND years_remaining>0",(player_id,)).fetchall()]}

@app.post("/api/economy/invest/{player_id}")
async def api_invest(player_id: str, name: str = Query(...), amount: float = Query(...), risk: str = Query("Medium")): return make_investment(player_id, name, amount, risk)

@app.get("/api/economy/investments/{player_id}")
async def api_investments(player_id: str):
    with get_db() as db: return {"investments":[dict(r) for r in db.execute("SELECT * FROM investments WHERE player_id=?",(player_id,)).fetchall()]}

@app.get("/api/media/scenario/{player_id}")
async def api_media_scenario(player_id: str): return get_random_media_scenario(player_id)

@app.post("/api/media/respond/{player_id}")
async def api_media_respond(player_id: str, scenario_id: str = Query(...), choice_index: int = Query(...)): return handle_media_event(player_id, scenario_id, choice_index)

@app.get("/api/media/history/{player_id}")
async def api_media_history(player_id: str, limit: int = 20):
    with get_db() as db: return {"events":[dict(r) for r in db.execute("SELECT * FROM media_events WHERE player_id=? ORDER BY created_at DESC LIMIT ?",(player_id,limit)).fetchall()]}

@app.post("/api/clout/request-trade/{player_id}")
async def api_trade(player_id: str, desired_team_id: int = Query(...)): return request_trade(player_id, desired_team_id)

@app.get("/api/career/{player_id}")
async def api_career(player_id: str): return get_career_overview(player_id)

@app.get("/api/career/export/{player_id}")
async def api_export(player_id: str): return export_career_json(player_id)

@app.post("/api/save/{player_id}")
async def api_save(player_id: str, save_name: str = Query(...), description: str = Query("")): return save_game(player_id, save_name, description)

@app.get("/api/saves/{player_id}")
async def api_saves(player_id: str): return {"saves":list_saves(player_id)}

@app.post("/api/load/{player_id}")
def api_load(player_id: str, save_id: str = Query(...)): return load_game(player_id, save_id)

@app.get("/api/teams")
async def api_teams(): return {"teams":{str(k):v for k,v in TEAMS.items()}}

@app.get("/api/league/standings")
def api_standings(player_id: str = None):
    state = get_league_state(); standings = []
    # Player's actual simulated team record (if known), used to keep standings consistent
    actual_record = None
    if player_id:
        with get_db() as db:
            p = db.execute("SELECT team_id,s_wins,s_losses FROM players WHERE id=?",(player_id,)).fetchone()
            if p: actual_record = (p["team_id"], p["s_wins"], p["s_losses"])
    for tid, t in TEAMS.items():
        rng = random.Random(tid*777+state["current_season"]*131)
        w = clamp(round(t["ovr"]/1.6+rng.randint(-10,10)),15,67)
        if actual_record and tid == actual_record[0]:
            w = actual_record[1]
        standings.append({"team_id":tid,"name":t["name"],"abbr":t["abbr"],"conference":t["conf"],"division":t["div"],"wins":w,"losses":82-w,"overall":t["ovr"]})
    east = sorted([t for t in standings if t["conference"]=="East"],key=lambda x:x["wins"],reverse=True)
    west = sorted([t for t in standings if t["conference"]=="West"],key=lambda x:x["wins"],reverse=True)
    return {"east":east,"west":west,"estimated":True}

@app.get("/api/health")
async def health(): return {"status":"ok","teams":len(TEAMS)}

def sanitize_player(p: Dict) -> Dict:
    skip = {"s_pts","s_reb","s_ast","s_stl","s_blk","s_tov","s_fga","s_fgm","s_3pa","s_3pm","s_fta","s_ftm","s_games","s_min","s_pf","s_wins","s_losses"}
    r = {k:(round(v,2) if isinstance(v,float) else v) for k,v in p.items() if k not in skip}
    r["team_name"] = TEAMS.get(p.get("team_id",0),{}).get("name","Free Agent")
    r["team_abbr"] = TEAMS.get(p.get("team_id",0),{}).get("abbr","FA")
    r["overall"] = calculate_overall_rating(p)
    return r

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.get("/")
async def root():
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message":"BBall Career Simulator API","docs":"/docs"}

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n    [BBALL CAREER SIMULATOR v3.0]")
    print("    http://localhost:8765\n")
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
