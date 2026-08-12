"""
BBALL CAREER SIMULATOR — Deep Strategy Basketball Career RPG
============================================================
FastAPI backend: game simulation engine, attribute systems,
economy, media, SQLite persistence.

Run: python server.py
"""

import random
import math
import json
import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager, asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "bball_career.db"
STATIC_DIR = "static"
random.seed()

# ============================================================
# DATABASE SETUP
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
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            height REAL NOT NULL,
            weight REAL NOT NULL,
            age INTEGER NOT NULL DEFAULT 19,
            experience INTEGER NOT NULL DEFAULT 0,
            team_id INTEGER NOT NULL DEFAULT 0,
            jersey_number INTEGER NOT NULL DEFAULT 0,
            role TEXT NOT NULL DEFAULT 'Two-Way Wing',

            -- Static Physicals (immutable after creation, except age)
            wingspan REAL NOT NULL,
            standing_reach REAL NOT NULL,
            hand_size REAL NOT NULL,
            frame_build REAL NOT NULL,
            height_no_shoes REAL NOT NULL,
            body_fat_pct REAL NOT NULL DEFAULT 8.0,

            -- Dynamic Athleticism (trainable, declines with age/injury)
            vertical_jump INTEGER NOT NULL DEFAULT 50,
            speed INTEGER NOT NULL DEFAULT 50,
            lateral_quickness INTEGER NOT NULL DEFAULT 50,
            strength INTEGER NOT NULL DEFAULT 50,
            core_stability INTEGER NOT NULL DEFAULT 50,
            stamina INTEGER NOT NULL DEFAULT 60,
            durability INTEGER NOT NULL DEFAULT 60,

            -- Defense & Rebounding
            perimeter_defense INTEGER NOT NULL DEFAULT 40,
            help_defense INTEGER NOT NULL DEFAULT 40,
            steal INTEGER NOT NULL DEFAULT 40,
            rim_protection INTEGER NOT NULL DEFAULT 40,
            box_out INTEGER NOT NULL DEFAULT 40,

            -- Scoring Offense
            first_step INTEGER NOT NULL DEFAULT 40,
            finishing INTEGER NOT NULL DEFAULT 40,
            mid_range INTEGER NOT NULL DEFAULT 40,
            catch_shoot_3pt INTEGER NOT NULL DEFAULT 40,
            pull_up_3pt INTEGER NOT NULL DEFAULT 35,
            off_ball INTEGER NOT NULL DEFAULT 40,
            drawing_fouls INTEGER NOT NULL DEFAULT 35,

            -- Playmaking
            ball_security INTEGER NOT NULL DEFAULT 45,
            pnr_vision INTEGER NOT NULL DEFAULT 40,
            passing_accuracy INTEGER NOT NULL DEFAULT 40,
            free_throw INTEGER NOT NULL DEFAULT 65,

            -- Mental
            bbiq INTEGER NOT NULL DEFAULT 50,
            clutch_factor INTEGER NOT NULL DEFAULT 50,
            work_ethic INTEGER NOT NULL DEFAULT 50,
            leadership INTEGER NOT NULL DEFAULT 40,
            composure INTEGER NOT NULL DEFAULT 50,

            -- Current Status
            fatigue REAL NOT NULL DEFAULT 0.0,
            injury_risk REAL NOT NULL DEFAULT 0.0,
            morale INTEGER NOT NULL DEFAULT 75,
            injury_status TEXT DEFAULT NULL,
            injury_games_remaining INTEGER DEFAULT 0,
            hot_streak INTEGER NOT NULL DEFAULT 0,
            cold_streak INTEGER NOT NULL DEFAULT 0,
            load_management BOOLEAN NOT NULL DEFAULT 0,

            -- Career Tracking
            clout REAL NOT NULL DEFAULT 5.0,
            fan_base REAL NOT NULL DEFAULT 10.0,
            wealth REAL NOT NULL DEFAULT 0.5,
            chemistry INTEGER NOT NULL DEFAULT 50,
            mvp_votes REAL NOT NULL DEFAULT 0.0,

            -- Game log cache
            season_pts REAL NOT NULL DEFAULT 0,
            season_reb REAL NOT NULL DEFAULT 0,
            season_ast REAL NOT NULL DEFAULT 0,
            season_stl REAL NOT NULL DEFAULT 0,
            season_blk REAL NOT NULL DEFAULT 0,
            season_tov REAL NOT NULL DEFAULT 0,
            season_fga REAL NOT NULL DEFAULT 0,
            season_fgm REAL NOT NULL DEFAULT 0,
            season_3pa REAL NOT NULL DEFAULT 0,
            season_3pm REAL NOT NULL DEFAULT 0,
            season_fta REAL NOT NULL DEFAULT 0,
            season_ftm REAL NOT NULL DEFAULT 0,
            season_games INTEGER NOT NULL DEFAULT 0,
            season_minutes REAL NOT NULL DEFAULT 0,
            season_fouls INTEGER NOT NULL DEFAULT 0,
            season_team_wins INTEGER NOT NULL DEFAULT 0,
            season_team_losses INTEGER NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            game_number INTEGER NOT NULL,
            opponent_team_id INTEGER NOT NULL,
            is_playoff BOOLEAN NOT NULL DEFAULT 0,
            is_home BOOLEAN NOT NULL DEFAULT 1,
            result TEXT NOT NULL DEFAULT 'L',
            team_score INTEGER NOT NULL DEFAULT 0,
            opponent_score INTEGER NOT NULL DEFAULT 0,

            minutes REAL NOT NULL DEFAULT 0,
            pts INTEGER NOT NULL DEFAULT 0,
            reb INTEGER NOT NULL DEFAULT 0,
            oreb INTEGER NOT NULL DEFAULT 0,
            dreb INTEGER NOT NULL DEFAULT 0,
            ast INTEGER NOT NULL DEFAULT 0,
            stl INTEGER NOT NULL DEFAULT 0,
            blk INTEGER NOT NULL DEFAULT 0,
            tov INTEGER NOT NULL DEFAULT 0,
            pf INTEGER NOT NULL DEFAULT 0,
            fga INTEGER NOT NULL DEFAULT 0,
            fgm INTEGER NOT NULL DEFAULT 0,
            tpa INTEGER NOT NULL DEFAULT 0,
            tpm INTEGER NOT NULL DEFAULT 0,
            fta INTEGER NOT NULL DEFAULT 0,
            ftm INTEGER NOT NULL DEFAULT 0,
            plus_minus INTEGER NOT NULL DEFAULT 0,

            -- Advanced stats
            per REAL NOT NULL DEFAULT 0,
            ts_pct REAL NOT NULL DEFAULT 0,
            usg_pct REAL NOT NULL DEFAULT 0,
            game_score REAL NOT NULL DEFAULT 0,
            eff REAL NOT NULL DEFAULT 0,

            -- Clutch performance
            clutch_pts INTEGER NOT NULL DEFAULT 0,
            clutch_fga INTEGER NOT NULL DEFAULT 0,
            clutch_fgm INTEGER NOT NULL DEFAULT 0,

            -- Notes
            notes TEXT DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS season_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            age INTEGER NOT NULL,
            games_played INTEGER NOT NULL DEFAULT 0,
            games_started INTEGER NOT NULL DEFAULT 0,
            mpg REAL NOT NULL DEFAULT 0,
            ppg REAL NOT NULL DEFAULT 0,
            rpg REAL NOT NULL DEFAULT 0,
            apg REAL NOT NULL DEFAULT 0,
            spg REAL NOT NULL DEFAULT 0,
            bpg REAL NOT NULL DEFAULT 0,
            topg REAL NOT NULL DEFAULT 0,
            fg_pct REAL NOT NULL DEFAULT 0,
            tp_pct REAL NOT NULL DEFAULT 0,
            ft_pct REAL NOT NULL DEFAULT 0,
            per REAL NOT NULL DEFAULT 0,
            ts_pct REAL NOT NULL DEFAULT 0,
            usg_pct REAL NOT NULL DEFAULT 0,
            ws REAL NOT NULL DEFAULT 0,
            bpm REAL NOT NULL DEFAULT 0,
            vorp REAL NOT NULL DEFAULT 0,
            team_wins INTEGER NOT NULL DEFAULT 0,
            team_losses INTEGER NOT NULL DEFAULT 0,
            playoff_result TEXT DEFAULT NULL,
            role TEXT NOT NULL DEFAULT 'Two-Way Wing',
            awards TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            award_type TEXT NOT NULL,
            award_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            years INTEGER NOT NULL,
            total_value REAL NOT NULL,
            annual_salary REAL NOT NULL,
            contract_type TEXT NOT NULL DEFAULT 'Standard',
            signed_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS endorsements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            annual_value REAL NOT NULL,
            years_remaining INTEGER NOT NULL,
            prestige INTEGER NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            name TEXT NOT NULL,
            amount_invested REAL NOT NULL,
            current_value REAL NOT NULL,
            annual_return REAL NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'Medium',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS media_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            choice_made TEXT DEFAULT NULL,
            fan_impact REAL NOT NULL DEFAULT 0,
            clout_impact REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS career_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            milestone TEXT DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS save_files (
            id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            save_name TEXT NOT NULL,
            season_number INTEGER NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS league_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_season INTEGER NOT NULL DEFAULT 1,
            current_phase TEXT NOT NULL DEFAULT 'regular_season',
            games_played_in_season INTEGER NOT NULL DEFAULT 0
        );

        INSERT OR IGNORE INTO league_state (id, current_season, current_phase, games_played_in_season)
        VALUES (1, 1, 'regular_season', 0);

        CREATE TABLE IF NOT EXISTS league_standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_number INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            conference TEXT NOT NULL,
            division TEXT NOT NULL
        );
        """)

# ============================================================
# TEAM DATA (30 NBA Teams with realistic ratings)
# ============================================================

TEAMS = {
    1:  {"name": "Atlanta Hawks", "abbr": "ATL", "conference": "East", "division": "Southeast", "off_rtg": 112, "def_rtg": 114, "overall": 78},
    2:  {"name": "Boston Celtics", "abbr": "BOS", "conference": "East", "division": "Atlantic", "off_rtg": 120, "def_rtg": 108, "overall": 95},
    3:  {"name": "Brooklyn Nets", "abbr": "BKN", "conference": "East", "division": "Atlantic", "off_rtg": 108, "def_rtg": 113, "overall": 72},
    4:  {"name": "Charlotte Hornets", "abbr": "CHA", "conference": "East", "division": "Southeast", "off_rtg": 106, "def_rtg": 115, "overall": 65},
    5:  {"name": "Chicago Bulls", "abbr": "CHI", "conference": "East", "division": "Central", "off_rtg": 110, "def_rtg": 112, "overall": 74},
    6:  {"name": "Cleveland Cavaliers", "abbr": "CLE", "conference": "East", "division": "Central", "off_rtg": 115, "def_rtg": 110, "overall": 85},
    7:  {"name": "Detroit Pistons", "abbr": "DET", "conference": "East", "division": "Central", "off_rtg": 105, "def_rtg": 113, "overall": 62},
    8:  {"name": "Indiana Pacers", "abbr": "IND", "conference": "East", "division": "Central", "off_rtg": 116, "def_rtg": 113, "overall": 80},
    9:  {"name": "Miami Heat", "abbr": "MIA", "conference": "East", "division": "Southeast", "off_rtg": 111, "def_rtg": 109, "overall": 82},
    10: {"name": "Milwaukee Bucks", "abbr": "MIL", "conference": "East", "division": "Central", "off_rtg": 117, "def_rtg": 109, "overall": 88},
    11: {"name": "New York Knicks", "abbr": "NYK", "conference": "East", "division": "Atlantic", "off_rtg": 114, "def_rtg": 108, "overall": 86},
    12: {"name": "Orlando Magic", "abbr": "ORL", "conference": "East", "division": "Southeast", "off_rtg": 110, "def_rtg": 110, "overall": 79},
    13: {"name": "Philadelphia 76ers", "abbr": "PHI", "conference": "East", "division": "Atlantic", "off_rtg": 116, "def_rtg": 110, "overall": 84},
    14: {"name": "Toronto Raptors", "abbr": "TOR", "conference": "East", "division": "Atlantic", "off_rtg": 109, "def_rtg": 112, "overall": 70},
    15: {"name": "Washington Wizards", "abbr": "WAS", "conference": "East", "division": "Southeast", "off_rtg": 107, "def_rtg": 116, "overall": 60},
    16: {"name": "Dallas Mavericks", "abbr": "DAL", "conference": "West", "division": "Southwest", "off_rtg": 118, "def_rtg": 111, "overall": 87},
    17: {"name": "Denver Nuggets", "abbr": "DEN", "conference": "West", "division": "Northwest", "off_rtg": 119, "def_rtg": 110, "overall": 92},
    18: {"name": "Golden State Warriors", "abbr": "GSW", "conference": "West", "division": "Pacific", "off_rtg": 115, "def_rtg": 111, "overall": 83},
    19: {"name": "Houston Rockets", "abbr": "HOU", "conference": "West", "division": "Southwest", "off_rtg": 111, "def_rtg": 112, "overall": 76},
    20: {"name": "LA Clippers", "abbr": "LAC", "conference": "West", "division": "Pacific", "off_rtg": 115, "def_rtg": 109, "overall": 84},
    21: {"name": "Los Angeles Lakers", "abbr": "LAL", "conference": "West", "division": "Pacific", "off_rtg": 114, "def_rtg": 111, "overall": 83},
    22: {"name": "Memphis Grizzlies", "abbr": "MEM", "conference": "West", "division": "Southwest", "off_rtg": 113, "def_rtg": 109, "overall": 83},
    23: {"name": "Minnesota Timberwolves", "abbr": "MIN", "conference": "West", "division": "Northwest", "off_rtg": 114, "def_rtg": 107, "overall": 88},
    24: {"name": "New Orleans Pelicans", "abbr": "NOP", "conference": "West", "division": "Southwest", "off_rtg": 113, "def_rtg": 111, "overall": 80},
    25: {"name": "Oklahoma City Thunder", "abbr": "OKC", "conference": "West", "division": "Northwest", "off_rtg": 119, "def_rtg": 106, "overall": 96},
    26: {"name": "Phoenix Suns", "abbr": "PHX", "conference": "West", "division": "Pacific", "off_rtg": 115, "def_rtg": 112, "overall": 81},
    27: {"name": "Portland Trail Blazers", "abbr": "POR", "conference": "West", "division": "Northwest", "off_rtg": 107, "def_rtg": 115, "overall": 64},
    28: {"name": "Sacramento Kings", "abbr": "SAC", "conference": "West", "division": "Pacific", "off_rtg": 114, "def_rtg": 113, "overall": 78},
    29: {"name": "San Antonio Spurs", "abbr": "SAS", "conference": "West", "division": "Southwest", "off_rtg": 110, "def_rtg": 112, "overall": 73},
    30: {"name": "Utah Jazz", "abbr": "UTA", "conference": "West", "division": "Northwest", "off_rtg": 108, "def_rtg": 114, "overall": 66},
}

# Star players per team (simplified opponent model)
TEAM_STARS = {
    1:  [("Trae Young", "PG", 88), ("Jalen Johnson", "SF", 82)],
    2:  [("Jayson Tatum", "SF", 93), ("Jaylen Brown", "SG", 88), ("Kristaps Porzingis", "C", 83)],
    3:  [("Cam Thomas", "SG", 80), ("Nic Claxton", "C", 78)],
    4:  [("LaMelo Ball", "PG", 86), ("Brandon Miller", "SF", 82)],
    5:  [("Coby White", "PG", 81), ("Nikola Vucevic", "C", 80)],
    6:  [("Donovan Mitchell", "SG", 91), ("Darius Garland", "PG", 85), ("Evan Mobley", "PF", 86)],
    7:  [("Cade Cunningham", "PG", 85), ("Jaden Ivey", "SG", 79)],
    8:  [("Tyrese Haliburton", "PG", 90), ("Pascal Siakam", "PF", 84)],
    9:  [("Bam Adebayo", "C", 86), ("Tyler Herro", "SG", 82)],
    10: [("Giannis Antetokounmpo", "PF", 97), ("Damian Lillard", "PG", 90)],
    11: [("Jalen Brunson", "PG", 89), ("Karl-Anthony Towns", "C", 87)],
    12: [("Paolo Banchero", "PF", 85), ("Franz Wagner", "SF", 83)],
    13: [("Joel Embiid", "C", 93), ("Tyrese Maxey", "PG", 87)],
    14: [("Scottie Barnes", "SF", 84), ("Immanuel Quickley", "PG", 80)],
    15: [("Jordan Poole", "SG", 78), ("Kyle Kuzma", "PF", 79)],
    16: [("Luka Doncic", "PG", 96), ("Kyrie Irving", "SG", 90)],
    17: [("Nikola Jokic", "C", 98), ("Jamal Murray", "PG", 87)],
    18: [("Stephen Curry", "PG", 94), ("Jimmy Butler", "SF", 88)],
    19: [("Jalen Green", "SG", 82), ("Alperen Sengun", "C", 85)],
    20: [("Kawhi Leonard", "SF", 90), ("James Harden", "PG", 86)],
    21: [("LeBron James", "SF", 92), ("Anthony Davis", "PF", 91)],
    22: [("Ja Morant", "PG", 89), ("Jaren Jackson Jr.", "PF", 85)],
    23: [("Anthony Edwards", "SG", 92), ("Rudy Gobert", "C", 83)],
    24: [("Zion Williamson", "PF", 87), ("Dejounte Murray", "PG", 82)],
    25: [("Shai Gilgeous-Alexander", "PG", 96), ("Chet Holmgren", "C", 86)],
    26: [("Devin Booker", "SG", 90), ("Kevin Durant", "SF", 93)],
    27: [("Scoot Henderson", "PG", 79), ("Shaedon Sharpe", "SG", 80)],
    28: [("De'Aaron Fox", "PG", 87), ("Domantas Sabonis", "C", 86)],
    29: [("Victor Wembanyama", "C", 91), ("Devin Vassell", "SG", 81)],
    30: [("Lauri Markkanen", "PF", 84), ("Keyonte George", "PG", 78)],
}

POSITION_TENDENCIES = {
    "PG": {"speed": 15, "passing_accuracy": 15, "pnr_vision": 15, "ball_security": 15, "first_step": 12,
           "lateral_quickness": 10, "perimeter_defense": 8, "catch_shoot_3pt": 8, "steal": 8,
           "vertical_jump": -5, "strength": -8, "rim_protection": -15, "box_out": -10},
    "SG": {"catch_shoot_3pt": 14, "mid_range": 12, "first_step": 10, "off_ball": 12,
           "pull_up_3pt": 10, "speed": 8, "perimeter_defense": 8,
           "rim_protection": -8, "box_out": -5, "strength": -3},
    "SF": {"mid_range": 8, "first_step": 6, "speed": 5, "strength": 5, "perimeter_defense": 5,
           "help_defense": 5, "off_ball": 6, "vertical_jump": 5,
           "pnr_vision": -3, "rim_protection": -3},
    "PF": {"strength": 12, "box_out": 12, "rim_protection": 8, "mid_range": 5, "finishing": 8,
           "core_stability": 10, "vertical_jump": 5, "help_defense": 6,
           "speed": -5, "steal": -5, "ball_security": -5, "catch_shoot_3pt": -5},
    "C":  {"rim_protection": 18, "box_out": 18, "strength": 15, "core_stability": 12,
           "vertical_jump": 5, "finishing": 10, "standing_reach_bonus": 0.15,
           "speed": -10, "steal": -10, "first_step": -12, "ball_security": -8,
           "catch_shoot_3pt": -10, "pull_up_3pt": -15},
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def roll(mean, std=15):
    """Normal-ish distribution roll."""
    return clamp(round(random.gauss(mean, std)), 1, 99)

def attr_roll(base, bonus=0):
    return clamp(roll(base + bonus, 12), 15, 95)

def weighted_choice(weights: Dict[Any, float]) -> Any:
    total = sum(weights.values())
    if total == 0:
        return random.choice(list(weights.keys()))
    r = random.random() * total
    accum = 0
    for k, w in weights.items():
        accum += w
        if r <= accum:
            return k
    return list(weights.keys())[-1]

def pct_to_rating(pct: float) -> str:
    """Convert a percentage to a display rating."""
    if pct >= 0.600: return "S+"
    if pct >= 0.550: return "S"
    if pct >= 0.500: return "A+"
    if pct >= 0.450: return "A"
    if pct >= 0.400: return "B+"
    if pct >= 0.350: return "B"
    if pct >= 0.300: return "C+"
    return "C"

# ============================================================
# PLAYER CREATION
# ============================================================

def generate_static_physicals(position: str) -> Dict:
    """Generate immutable physical attributes based on position."""
    pos_templates = {
        "PG": {"height_range": (1.80, 1.95), "weight_range": (75, 92), "wingspan_factor": (1.00, 1.06)},
        "SG": {"height_range": (1.88, 2.01), "weight_range": (82, 100), "wingspan_factor": (1.01, 1.08)},
        "SF": {"height_range": (1.95, 2.08), "weight_range": (90, 110), "wingspan_factor": (1.02, 1.10)},
        "PF": {"height_range": (2.03, 2.13), "weight_range": (100, 120), "wingspan_factor": (1.03, 1.12)},
        "C":  {"height_range": (2.08, 2.20), "weight_range": (108, 135), "wingspan_factor": (1.04, 1.15)},
    }
    tmpl = pos_templates.get(position, pos_templates["SF"])
    height = round(random.uniform(*tmpl["height_range"]), 2)
    weight = round(random.uniform(*tmpl["weight_range"]), 1)
    wingspan_factor = random.uniform(*tmpl["wingspan_factor"])
    wingspan = round(height * wingspan_factor, 2)
    standing_reach = round(height * 1.28 + (wingspan - height) * 0.45, 2)
    hand_size = round(random.uniform(20.0, 28.0), 1)
    frame = roll(50, 18)
    body_fat = round(random.uniform(5.0, 14.0), 1)

    return {
        "height": height, "weight": weight, "wingspan": wingspan,
        "standing_reach": standing_reach, "hand_size": hand_size,
        "frame_build": frame, "height_no_shoes": round(height - 0.025, 2),
        "body_fat_pct": body_fat
    }

def generate_dynamic_attributes(position: str, potential_bonus: int = 0) -> Dict:
    """Generate trainable attributes."""
    tend = POSITION_TENDENCIES.get(position, {})
    attrs = {}
    attr_names = [
        "vertical_jump", "speed", "lateral_quickness", "strength", "core_stability",
        "stamina", "durability", "perimeter_defense", "help_defense", "steal",
        "rim_protection", "box_out", "first_step", "finishing", "mid_range",
        "catch_shoot_3pt", "pull_up_3pt", "off_ball", "drawing_fouls",
        "ball_security", "pnr_vision", "passing_accuracy", "free_throw"
    ]
    for attr in attr_names:
        bonus = tend.get(attr, 0) + potential_bonus
        base = 45
        if attr in ("stamina", "durability", "free_throw"):
            base = 55
        attrs[attr] = attr_roll(base, bonus)

    # Mental attributes
    attrs["bbiq"] = attr_roll(48, potential_bonus // 2)
    attrs["clutch_factor"] = attr_roll(45, random.randint(-5, 10))
    attrs["work_ethic"] = attr_roll(50, random.randint(-10, 15))
    attrs["leadership"] = attr_roll(42, random.randint(-8, 12))
    attrs["composure"] = attr_roll(48, potential_bonus // 3)
    return attrs

def create_player(name: str, position: str, age: int = 19, team_id: int = 0) -> str:
    """Create a new player and return their ID."""
    pid = str(uuid.uuid4())[:8]
    static = generate_static_physicals(position)
    # Potential bonus simulates draft pedigree
    potential = roll(50, 20)
    dynamic = generate_dynamic_attributes(position, potential - 50)

    # Assign to a random team if not specified
    if team_id == 0:
        team_id = random.choice(list(TEAMS.keys()))

    jersey = random.randint(0, 55)

    with get_db() as db:
        db.execute("""
            INSERT INTO players (id, name, position, height, weight, age, team_id,
            jersey_number, role, wingspan, standing_reach, hand_size, frame_build,
            height_no_shoes, body_fat_pct, vertical_jump, speed, lateral_quickness,
            strength, core_stability, stamina, durability, perimeter_defense,
            help_defense, steal, rim_protection, box_out, first_step, finishing,
            mid_range, catch_shoot_3pt, pull_up_3pt, off_ball, drawing_fouls,
            ball_security, pnr_vision, passing_accuracy, free_throw, bbiq,
            clutch_factor, work_ethic, leadership, composure)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (pid, name, position, static["height"], static["weight"], age, team_id,
              jersey, "Two-Way Wing", static["wingspan"], static["standing_reach"],
              static["hand_size"], static["frame_build"], static["height_no_shoes"],
              static["body_fat_pct"], dynamic["vertical_jump"], dynamic["speed"],
              dynamic["lateral_quickness"], dynamic["strength"], dynamic["core_stability"],
              dynamic["stamina"], dynamic["durability"], dynamic["perimeter_defense"],
              dynamic["help_defense"], dynamic["steal"], dynamic["rim_protection"],
              dynamic["box_out"], dynamic["first_step"], dynamic["finishing"],
              dynamic["mid_range"], dynamic["catch_shoot_3pt"], dynamic["pull_up_3pt"],
              dynamic["off_ball"], dynamic["drawing_fouls"], dynamic["ball_security"],
              dynamic["pnr_vision"], dynamic["passing_accuracy"], dynamic["free_throw"],
              dynamic["bbiq"], dynamic["clutch_factor"], dynamic["work_ethic"],
              dynamic["leadership"], dynamic["composure"]))

        # Initial rookie contract
        salary = round(random.uniform(1.5, 12.0), 1)
        db.execute("""
            INSERT INTO contracts (player_id, season_number, team_id, years, total_value, annual_salary, contract_type)
            VALUES (?, 0, ?, 4, ?, ?, 'Rookie')
        """, (pid, team_id, salary * 4, salary))

    init_league_state()
    return pid

# ============================================================
# LEAGUE STATE
# ============================================================

def init_league_state():
    with get_db() as db:
        db.execute("INSERT OR IGNORE INTO league_state (id, current_season, current_phase, games_played_in_season) VALUES (1,1,'regular_season',0)")

def get_league_state() -> Dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM league_state WHERE id=1").fetchone()
        if not row:
            init_league_state()
            row = db.execute("SELECT * FROM league_state WHERE id=1").fetchone()
        return dict(row)

def advance_league_phase():
    with get_db() as db:
        state = dict(db.execute("SELECT * FROM league_state WHERE id=1").fetchone())
        if state["current_phase"] == "regular_season":
            db.execute("UPDATE league_state SET current_phase='playoffs', games_played_in_season=0 WHERE id=1")
        elif state["current_phase"] == "playoffs":
            db.execute("UPDATE league_state SET current_phase='offseason', games_played_in_season=0 WHERE id=1")
        elif state["current_phase"] == "offseason":
            db.execute("UPDATE league_state SET current_season=current_season+1, current_phase='regular_season', games_played_in_season=0 WHERE id=1")

# ============================================================
# GAME SIMULATION ENGINE
# ============================================================

def simulate_game(player_id: str, opponent_team_id: int = None, is_playoff: bool = False) -> Dict:
    """Simulate a full basketball game. Returns detailed box score + advanced stats."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

    if opponent_team_id is None:
        schedule = generate_season_schedule(player["team_id"])
        state = get_league_state()
        idx = min(state["games_played_in_season"], 81)
        opponent_team_id = schedule[idx]

    opp = TEAMS.get(opponent_team_id, TEAMS[1])
    team = TEAMS.get(player["team_id"], TEAMS[1])

    # ── Fatigue & Load Management ──
    fatigue_penalty = player["fatigue"] / 100.0
    if player["load_management"]:
        fatigue_penalty = max(fatigue_penalty - 0.15, 0)

    # ── Minutes calculation ──
    base_mpg = 28 + (player["stamina"] - 40) * 0.2 + (player["overall_rating"] if "overall_rating" in player else 70 - 70) * 0.1
    base_mpg = clamp(base_mpg, 12, 42)
    if player["load_management"]:
        base_mpg -= 8
    if is_playoff:
        base_mpg += 5
    minutes = clamp(base_mpg - fatigue_penalty * 10, 8, 44)
    minutes = round(minutes + random.uniform(-3, 3), 1)
    minutes = max(minutes, 4)

    # ── Hot / Cold streak ──
    streak_mod = 0
    if player["hot_streak"] > 0:
        streak_mod = min(player["hot_streak"] * 2, 12)
    elif player["cold_streak"] < 0:
        streak_mod = max(player["cold_streak"] * 2, -12)

    # ── Injury check ──
    if player["injury_games_remaining"] > 0:
        minutes = 0

    # ── Possession simulation ──
    total_poss = random.randint(195, 210)  # ~100 possessions per team
    court_time_pct = minutes / 48.0  # fraction of game player is on court

    # Determine usage rate from attributes
    scoring_avg = (player["first_step"] + player["finishing"] + player["mid_range"] +
                   player["catch_shoot_3pt"] + player["pull_up_3pt"]) / 5.0
    playmaking_avg = (player["pnr_vision"] + player["passing_accuracy"] + player["ball_security"]) / 3.0

    # Role-based usage
    role_usage = {
        "Ball-Dominant Creator": 0.35, "Off-Ball Finisher": 0.22,
        "Rim Protector": 0.14, "Two-Way Wing": 0.26, "3-and-D Specialist": 0.18,
        "Point Forward": 0.28, "Stretch Big": 0.20, "Defensive Anchor": 0.12
    }
    usage_rate = role_usage.get(player["role"], 0.24)

    # Initialize box score
    box = {"pts": 0, "oreb": 0, "dreb": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0,
           "tov": 0, "pf": 0, "fga": 0, "fgm": 0, "tpa": 0, "tpm": 0, "fta": 0, "ftm": 0,
           "clutch_pts": 0, "clutch_fga": 0, "clutch_fgm": 0}

    # Team context
    team_off = team["off_rtg"]
    opp_def = opp["def_rtg"]
    opp_off = opp["off_rtg"]
    team_def = team["def_rtg"]

    # Simulate
    team_score = 0
    opp_score = 0
    is_clutch = False  # Will be true in last 5 min with close score

    for pos_num in range(total_poss):
        # Determine if clutch time (last ~12 possessions, score within 8)
        is_clutch = (pos_num > total_poss - 14) and abs(team_score - opp_score) <= 8

        # Opponent possession half the time
        my_possession = random.random() < 0.50

        if my_possession:
            # Our team's possession
            opp_def_factor = max(0.85, opp_def / 115.0)
            base_score_prob = team_off / 160.0 * opp_def_factor * 0.7

            # Is user player on court and involved?
            player_on = random.random() < court_time_pct
            player_involved = player_on and random.random() < usage_rate * 1.2  # boost for more realistic FGA

            if player_involved:
                # Determine action type
                action = determine_player_action(player, is_clutch, streak_mod)
                result = resolve_player_action(player, action, opp, is_clutch, streak_mod)
                box = update_box_score(box, result)
                if result.get("points", 0) > 0:
                    team_score += result["points"]
                    if is_clutch:
                        box["clutch_fga"] += 1
                        box["clutch_fgm"] += 1 if result["points"] >= 2 else 0
                        box["clutch_pts"] += result["points"]
                if result.get("assist", 0) > 0:
                    team_score += result.get("assist_points", 2)
                    box["ast"] += 1
            else:
                # Teammate resolves possession
                if random.random() < base_score_prob:
                    pts = weighted_choice({2: 55, 3: 35, 0: 10})
                    team_score += pts
                else:
                    if random.random() < 0.10:
                        box["dreb"] += 1  # defensive board chance after miss
        else:
            # Opponent possession
            team_def_factor = max(0.85, team_def / 115.0)
            opp_score_prob = opp_off / 160.0 * team_def_factor * 0.7

            if random.random() < opp_score_prob:
                pts = weighted_choice({2: 52, 3: 33, 0: 15})
                opp_score += pts

            # User defensive actions (if on court)
            if random.random() < court_time_pct:
                def_result = resolve_defensive_action(player, is_clutch)
                box = update_defensive_box(box, def_result, True)

    box["reb"] = box["oreb"] + box["dreb"]

    # ── Post-game adjustments ──
    # Ensure minimum stats if minutes > 0
    if minutes > 8 and box["fga"] == 0:
        box["fga"] = max(1, int(minutes * usage_rate * 0.3))
        box["fgm"] = max(0, int(box["fga"] * (scoring_avg / 180)))

    if box["fga"] > 0 and box["fgm"] == 0 and scoring_avg > 40:
        box["fgm"] = max(1, int(box["fga"] * 0.25))

    if box["fgm"] > 0:
        box["pts"] = max(box["pts"], box["fgm"] * 2)

    # Fix: ensure fgm <= fga
    box["fgm"] = min(box["fgm"], box["fga"])
    box["tpm"] = min(box["tpm"], box["tpa"])

    # ── Advanced stats ──
    adv = calculate_advanced_stats_player(box, minutes, team_score, opp_score, total_poss)

    plus_minus = (team_score - opp_score) if minutes > 0 else 0

    # ── Game result ──
    result = "W" if team_score > opp_score else "L"
    is_home = random.random() < 0.5

    # ── Fatigue update ──
    new_fatigue = clamp(player["fatigue"] + (minutes / 48.0) * random.uniform(4, 8), 0, 100)

    # ── Hot/cold streak update ──
    new_hot = player["hot_streak"]
    new_cold = player["cold_streak"]
    if box["pts"] >= 30:
        new_hot = min(player["hot_streak"] + 1, 5)
        new_cold = 0
    elif box["pts"] <= 8 and box["fga"] >= 8:
        new_cold = max(player["cold_streak"] - 1, -5)
        new_hot = 0
    else:
        if new_hot > 0 and random.random() < 0.3:
            new_hot -= 1
        if new_cold < 0 and random.random() < 0.3:
            new_cold += 1

    # ── Injury risk ──
    injury_risk = player["injury_risk"]
    injury_risk += (minutes / 35.0) * random.uniform(0, 2) * (1 - player["durability"] / 100.0)
    if player["fatigue"] > 70:
        injury_risk += 2
    injury_occurred = False
    injury_type = None
    injury_games = 0
    if random.random() < injury_risk / 100.0:
        injury_occurred = True
        severity_roll = random.random()
        if severity_roll < 0.4:
            injury_type = "Mild ankle sprain"
            injury_games = random.randint(1, 5)
        elif severity_roll < 0.7:
            injury_type = "Moderate knee strain"
            injury_games = random.randint(6, 15)
        elif severity_roll < 0.9:
            injury_type = "Severe hamstring tear"
            injury_games = random.randint(16, 35)
        else:
            injury_type = "Major injury (ACL/MCL)"
            injury_games = random.randint(40, 82)
        injury_risk = 0  # reset after injury

    # ── Morale update ──
    morale_change = 0
    if result == "W":
        morale_change += random.randint(1, 4)
    else:
        morale_change -= random.randint(1, 3)
    if box["pts"] >= 25:
        morale_change += random.randint(2, 5)
    new_morale = clamp(player["morale"] + morale_change, 10, 100)

    # ── Save game log ──
    state = get_league_state()
    with get_db() as db:
        db.execute("""
            INSERT INTO game_logs (player_id, season_number, game_number, opponent_team_id,
            is_playoff, is_home, result, team_score, opponent_score, minutes, pts, reb,
            oreb, dreb, ast, stl, blk, tov, pf, fga, fgm, tpa, tpm, fta, ftm,
            plus_minus, per, ts_pct, usg_pct, game_score, eff,
            clutch_pts, clutch_fga, clutch_fgm)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (player_id, state["current_season"], state["games_played_in_season"] + 1,
              opponent_team_id, is_playoff, is_home, result, team_score, opp_score,
              minutes, box["pts"], box["reb"], box["oreb"], box["dreb"],
              box["ast"], box["stl"], box["blk"], box["tov"], box["pf"],
              box["fga"], box["fgm"], box["tpa"], box["tpm"],
              box["fta"], box["ftm"], plus_minus,
              adv["per"], adv["ts_pct"], adv["usg_pct"],
              adv["game_score"], adv["eff"],
              box["clutch_pts"], box["clutch_fga"], box["clutch_fgm"]))

        # Update player season totals
        db.execute("""
            UPDATE players SET
            season_pts = season_pts + ?, season_reb = season_reb + ?,
            season_ast = season_ast + ?, season_stl = season_stl + ?,
            season_blk = season_blk + ?, season_tov = season_tov + ?,
            season_fga = season_fga + ?, season_fgm = season_fgm + ?,
            season_3pa = season_3pa + ?, season_3pm = season_3pm + ?,
            season_fta = season_fta + ?, season_ftm = season_ftm + ?,
            season_games = season_games + 1, season_minutes = season_minutes + ?,
            season_fouls = season_fouls + ?, fatigue = ?, injury_risk = ?,
            morale = ?, hot_streak = ?, cold_streak = ?,
            season_team_wins = season_team_wins + ?,
            season_team_losses = season_team_losses + ?,
            injury_status = ?, injury_games_remaining = ?
            WHERE id = ?
        """, (box["pts"], box["reb"], box["ast"], box["stl"], box["blk"], box["tov"],
              box["fga"], box["fgm"], box["tpa"], box["tpm"], box["fta"], box["ftm"],
              minutes, box["pf"], new_fatigue, injury_risk,
              new_morale, new_hot, new_cold,
              1 if result == "W" else 0, 1 if result == "L" else 0,
              injury_type, injury_games,
              player_id))

        # Advance game counter
        db.execute("UPDATE league_state SET games_played_in_season = games_played_in_season + 1 WHERE id=1")

    return {
        "game_number": state["games_played_in_season"] + 1,
        "opponent": opp["name"],
        "opponent_abbr": opp["abbr"],
        "result": result,
        "team_score": team_score,
        "opponent_score": opp_score,
        "minutes": minutes,
        "box_score": box,
        "advanced": adv,
        "plus_minus": plus_minus,
        "is_home": is_home,
        "fatigue": round(new_fatigue, 1),
        "injury": {"occurred": injury_occurred, "type": injury_type, "games": injury_games} if injury_occurred else None,
        "morale": new_morale,
        "hot_streak": new_hot,
        "cold_streak": new_cold
    }

def determine_player_action(player: Dict, is_clutch: bool, streak_mod: int) -> str:
    """Determine what the player does on a possession."""
    role_actions = {
        "Ball-Dominant Creator": {"iso_score": 30, "pnr": 25, "pull_up": 20, "drive_and_kick": 15, "catch_shoot": 10},
        "Off-Ball Finisher": {"catch_shoot": 30, "cut": 25, "iso_score": 15, "drive_and_kick": 15, "pnr": 15},
        "Rim Protector": {"post_up": 25, "putback": 25, "catch_shoot": 20, "cut": 20, "iso_score": 10},
        "Two-Way Wing": {"iso_score": 22, "catch_shoot": 22, "drive_and_kick": 20, "pull_up": 18, "cut": 18},
        "3-and-D Specialist": {"catch_shoot": 45, "cut": 25, "iso_score": 15, "drive_and_kick": 10, "pull_up": 5},
        "Point Forward": {"pnr": 28, "drive_and_kick": 25, "iso_score": 20, "catch_shoot": 15, "pull_up": 12},
        "Stretch Big": {"catch_shoot": 35, "post_up": 20, "cut": 20, "putback": 15, "iso_score": 10},
        "Defensive Anchor": {"putback": 30, "post_up": 25, "catch_shoot": 20, "cut": 20, "iso_score": 5},
    }
    weights = role_actions.get(player["role"], role_actions["Two-Way Wing"])

    # Clutch modifier: more iso and pull-up
    if is_clutch and player["clutch_factor"] > 60:
        if "iso_score" in weights:
            weights["iso_score"] += 15
        if "pull_up" in weights:
            weights["pull_up"] += 10

    return weighted_choice(weights)

def resolve_player_action(player: Dict, action: str, opponent: Dict, is_clutch: bool, streak_mod: int) -> Dict:
    """Resolve a player's offensive action and return results."""
    result = {"points": 0, "fgm": 0, "fga": 0, "tpa": 0, "tpm": 0,
              "fta": 0, "ftm": 0, "tov": 0, "assist": 0, "assist_points": 0}

    opp_overall = opponent["overall"]
    # Higher def_rtg = worse defense, so we multiply directly (not 1/)
    opp_def_factor = opponent["def_rtg"] / 110.0

    if action == "iso_score":
        result["fga"] = 1
        success_prob = (player["first_step"] + player["finishing"] + player["mid_range"] * 0.6) / 300.0
        success_prob *= opp_def_factor * 0.85
        success_prob *= (1 + streak_mod / 100.0)
        if is_clutch:
            success_prob *= (1 + (player["clutch_factor"] - 50) / 200.0)

        if random.random() < success_prob:
            # Determine if 3pt or 2pt
            if random.random() < player["pull_up_3pt"] / 150.0:
                result["tpa"] = 1
                result["tpm"] = 1
                result["points"] = 3
            else:
                result["fgm"] = 1
                result["points"] = 2
            # Possible and-1
            if random.random() < player["drawing_fouls"] / 300.0:
                result["fta"] = 1
                result["ftm"] = 1 if random.random() < player["free_throw"] / 100.0 else 0
                result["points"] += result["ftm"]
        else:
            # Missed shot
            if random.random() < player["pull_up_3pt"] / 150.0:
                result["tpa"] = 1
            # Possible foul drawn on miss
            if random.random() < player["drawing_fouls"] / 400.0:
                result["fta"] = 2
                result["ftm"] = sum(1 for _ in range(2) if random.random() < player["free_throw"] / 100.0)
                result["points"] = result["ftm"]

    elif action == "catch_shoot":
        result["fga"] = 1
        success_prob = (player["catch_shoot_3pt"] * 1.2 + player["off_ball"] * 0.5) / 180.0
        success_prob *= opp_def_factor * 0.82
        success_prob *= (1 + streak_mod / 100.0)

        is_three = random.random() < 0.65  # catch and shoot tends to be 3pt
        if is_three:
            result["tpa"] = 1
            if random.random() < success_prob:
                result["tpm"] = 1
                result["points"] = 3
        else:
            if random.random() < success_prob * 1.1:
                result["fgm"] = 1
                result["points"] = 2

    elif action == "pnr":
        # Pick and roll: decision tree
        decision = weighted_choice({
            "score": 30 + player["finishing"] / 5,
            "pass_to_roller": 25 + player["pnr_vision"] / 4,
            "kick_out": 20 + player["passing_accuracy"] / 5,
            "pull_up": 25
        })
        if decision == "score":
            result["fga"] = 1
            if random.random() < (player["finishing"] + player["first_step"]) / 250.0:
                result["fgm"] = 1
                result["points"] = 2
        elif decision in ("pass_to_roller", "kick_out"):
            if random.random() < player["passing_accuracy"] / 120.0:
                result["assist"] = 1
                result["assist_points"] = weighted_choice({2: 60, 3: 30, 0: 10})
        elif decision == "pull_up":
            result["fga"] = 1
            result["tpa"] = 1
            if random.random() < player["mid_range"] / 220.0:
                result["tpm"] = 1
                result["points"] = 3

    elif action == "pull_up":
        result["fga"] = 1
        result["tpa"] = 1
        success_prob = (player["pull_up_3pt"] + player["mid_range"] * 0.5) / 200.0
        success_prob *= (1 + streak_mod / 100.0)
        if is_clutch:
            success_prob *= (1 + (player["clutch_factor"] - 50) / 150.0)
        if random.random() < success_prob:
            result["tpm"] = 1
            result["points"] = 3

    elif action == "drive_and_kick":
        drive_success = random.random() < player["first_step"] / 130.0
        if drive_success:
            will_pass = random.random() < player["passing_accuracy"] / 120.0
            if will_pass:
                result["assist"] = 1
                result["assist_points"] = weighted_choice({2: 55, 3: 35, 0: 10})
            else:
                result["fga"] = 1
                if random.random() < player["finishing"] / 190.0:
                    result["fgm"] = 1
                    result["points"] = 2
        else:
            result["tov"] = 1

    elif action == "cut":
        result["fga"] = 1
        success_prob = (player["off_ball"] + player["finishing"]) / 240.0
        if random.random() < success_prob:
            result["fgm"] = 1
            result["points"] = 2

    elif action == "post_up":
        result["fga"] = 1
        success_prob = (player["strength"] + player["core_stability"] + player["mid_range"]) / 350.0
        if random.random() < success_prob:
            result["fgm"] = 1
            result["points"] = 2

    elif action == "putback":
        result["fga"] = 1
        success_prob = (player["vertical_jump"] + player["box_out"] + player["strength"]) / 350.0
        if random.random() < success_prob:
            result["fgm"] = 1
            result["points"] = 2

    # Free throw resolution
    if result["fta"] > 0:
        made = sum(1 for _ in range(result["fta"]) if random.random() < player["free_throw"] / 100.0)
        result["ftm"] = min(made, result["fta"])
        result["points"] = result.get("points", 0) - (result.get("ftm", 0) if result.get("ftm", 0) else 0) + result["ftm"]
        # Recalculate: base points from FG + FT points
        base_pts = (result.get("tpm", 0) * 3) + (result.get("fgm", 0) * 2)
        result["points"] = base_pts + result["ftm"]

    return result

def resolve_defensive_action(player: Dict, is_clutch: bool) -> Dict:
    """Resolve defensive actions during opponent possessions."""
    result = {"stl": 0, "blk": 0, "dreb": 0, "oreb": 0, "pf": 0}

    # Steal chance (~2-3% per defensive possession for elite, ~1% for average)
    steal_chance = (player["steal"] + player["perimeter_defense"] * 0.3 + player["bbiq"] * 0.2) / 3500.0
    if is_clutch:
        steal_chance *= 0.6  # fewer gambles in clutch
    if random.random() < steal_chance:
        result["stl"] = 1

    # Block chance (~2-3% for elite rim protectors, ~1% for average)
    block_chance = (player["rim_protection"] + player["vertical_jump"] * 0.5) / 5500.0
    if not result["stl"] and random.random() < block_chance:
        result["blk"] = 1

    # Defensive rebound chance (~8-12% for good rebounders, ~5% for average)
    dreb_chance = (player["box_out"] + player["strength"] * 0.4 + player["vertical_jump"] * 0.2) / 1400.0
    if random.random() < dreb_chance:
        result["dreb"] = 1

    # Offensive rebound chance (~3-5% for good rebounders, ~1.5% for average)
    oreb_chance = (player["box_out"] + player["vertical_jump"] * 0.5 + player["core_stability"] * 0.2) / 3000.0
    if random.random() < oreb_chance:
        result["oreb"] = 1

    # Foul risk (~3-5% per defensive possession)
    foul_chance = 0.02 + (1 - player["bbiq"] / 100.0) * 0.05 + (1 - player["composure"] / 100.0) * 0.02
    if random.random() < foul_chance:
        result["pf"] = 1
        # Foul can negate a block or steal
        if result["blk"]:
            result["blk"] = 0
        if result["stl"] and random.random() < 0.3:
            result["stl"] = 0

    return result

def update_box_score(box: Dict, result: Dict) -> Dict:
    """Update box score with action result. Made 3PM also count as FGM per NBA rules."""
    for key in ["pts", "fgm", "fga", "tpa", "tpm", "fta", "ftm", "tov"]:
        box[key] = box.get(key, 0) + result.get(key, 0)
    # Made 3-pointers also count as made field goals
    box["fgm"] = box.get("fgm", 0) + result.get("tpm", 0)
    return box

def update_defensive_box(box: Dict, result: Dict, on_court: bool) -> Dict:
    """Update box score with defensive stats."""
    if not on_court:
        return box
    for key in ["stl", "blk", "dreb", "oreb", "pf"]:
        box[key] = box.get(key, 0) + result.get(key, 0)
    return box

def calculate_advanced_stats_player(box: Dict, minutes: float, team_score: int, opp_score: int, possessions: int) -> Dict:
    """Calculate advanced stats for a single game."""
    if minutes < 1:
        return {"per": 0, "ts_pct": 0, "usg_pct": 0, "game_score": 0, "eff": 0}

    fga, fgm = box["fga"], box["fgm"]
    tpa, tpm = box["tpa"], box["tpm"]
    fta, ftm = box["fta"], box["ftm"]
    pts, reb, ast = box["pts"], box["reb"], box["ast"]
    stl, blk, tov, pf = box["stl"], box["blk"], box["tov"], box["pf"]

    # True Shooting %
    ts_denom = 2 * (fga + 0.44 * fta)
    ts_pct = round(pts / ts_denom, 3) if ts_denom > 0 else 0

    # Usage %
    usg_pct = round(100 * (fga + 0.44 * fta + tov) * (48 / minutes) / (possessions * 5 / 48 * 48), 1) if possessions > 0 else 0
    usg_pct = clamp(usg_pct, 5, 55)

    # Game Score
    gs = pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * box["oreb"] + 0.3 * box["dreb"] + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - tov
    gs = round(gs, 1)

    # Efficiency
    eff = pts + reb + ast + stl + blk - (fga - fgm) - (fta - ftm) - tov

    # PER (simplified Hollinger)
    uPER = (1 / minutes) * (
        pts + 0.85 * fgm + 0.5 * tpm + 0.7 * box["oreb"] + 0.3 * box["dreb"] +
        0.9 * ast + 1.1 * stl + 1.2 * blk - 0.9 * fga - 0.5 * fta - 0.8 * tov - 0.3 * pf
    ) * 15
    per = round(clamp(uPER, 0, 55), 1)

    return {"per": per, "ts_pct": ts_pct, "usg_pct": usg_pct, "game_score": gs, "eff": eff}

def generate_season_schedule(team_id: int) -> List[int]:
    """Generate an 82-game schedule for a team."""
    # Deterministic-but-random schedule based on team_id
    rng = random.Random(team_id * 777 + get_league_state().get("current_season", 1) * 131)
    all_teams = list(TEAMS.keys())
    schedule = []

    # 4 games vs division (4 teams × 4 = 16)
    div_teams = [tid for tid, t in TEAMS.items() if t["division"] == TEAMS[team_id]["division"] and tid != team_id]
    for t in div_teams:
        schedule.extend([t] * 4)

    # 3-4 games vs conference (10 teams × ~3.5 = 35)
    conf_teams = [tid for tid, t in TEAMS.items() if t["conference"] == TEAMS[team_id]["conference"] and tid != team_id and tid not in div_teams]
    for t in conf_teams:
        schedule.extend([t] * rng.choice([3, 4]))

    # 2 games vs opposite conference (15 teams × 2 = 30)
    opp_conf = [tid for tid in TEAMS if tid not in conf_teams and tid != team_id and tid not in div_teams]
    for t in opp_conf:
        schedule.extend([t] * 2)

    rng.shuffle(schedule)
    return schedule[:82]

# ============================================================
# SIMULATE FULL SEASON (Quick Sim for non-user games)
# ============================================================

def simulate_team_season(team_id: int, season: int) -> Dict:
    """Simulate a full season for a team (for league standings)."""
    schedule = generate_season_schedule(team_id)
    wins = 0
    losses = 0
    for opp_id in schedule:
        team = TEAMS[team_id]
        opp = TEAMS[opp_id]
        win_prob = team["overall"] / (team["overall"] + opp["overall"])
        if random.random() < win_prob * (1.05 if random.random() < 0.6 else 0.95):  # home/away variance
            wins += 1
        else:
            losses += 1
    return {"team_id": team_id, "wins": wins, "losses": losses}

# ============================================================
# TRAINING SYSTEM
# ============================================================

TRAINING_PROGRAMS = {
    "Explosive Athlete": {
        "description": "Focus on vertical jump, first step, and speed. High intensity.",
        "primary": ["vertical_jump", "speed", "first_step"],
        "secondary": ["lateral_quickness", "stamina"],
        "intensity": 0.85,
        "injury_risk": 5,
        "duration_weeks": 8
    },
    "Strength & Power": {
        "description": "Weight room focus: strength, core stability, finishing through contact.",
        "primary": ["strength", "core_stability", "finishing"],
        "secondary": ["box_out", "vertical_jump"],
        "intensity": 0.80,
        "injury_risk": 4,
        "duration_weeks": 8
    },
    "Shooting Lab": {
        "description": "Thousands of reps: catch-and-shoot, pull-up, mid-range, free throws.",
        "primary": ["catch_shoot_3pt", "mid_range", "pull_up_3pt", "free_throw"],
        "secondary": ["off_ball"],
        "intensity": 0.65,
        "injury_risk": 1,
        "duration_weeks": 8
    },
    "Ball Handling & Playmaking": {
        "description": "Tight handles, PnR reads, passing drills under pressure.",
        "primary": ["ball_security", "pnr_vision", "passing_accuracy"],
        "secondary": ["first_step", "composure"],
        "intensity": 0.70,
        "injury_risk": 2,
        "duration_weeks": 8
    },
    "Defensive Specialist": {
        "description": "Lateral slides, closeouts, film study for defensive IQ.",
        "primary": ["perimeter_defense", "help_defense", "lateral_quickness", "steal"],
        "secondary": ["rim_protection", "bbiq"],
        "intensity": 0.75,
        "injury_risk": 3,
        "duration_weeks": 8
    },
    "Conditioning & Longevity": {
        "description": "Marathon training: stamina, durability, body maintenance.",
        "primary": ["stamina", "durability"],
        "secondary": ["speed", "strength"],
        "intensity": 0.60,
        "injury_risk": 0,
        "duration_weeks": 8
    },
    "Post Game Mastery": {
        "description": "Footwork, hook shots, up-and-under, rebounding positioning.",
        "primary": ["finishing", "box_out", "core_stability"],
        "secondary": ["strength", "mid_range"],
        "intensity": 0.70,
        "injury_risk": 2,
        "duration_weeks": 8
    },
    "Clutch Performer": {
        "description": "Pressure simulation, mental conditioning, late-game scenarios.",
        "primary": ["clutch_factor", "composure", "bbiq"],
        "secondary": ["leadership", "mid_range"],
        "intensity": 0.50,
        "injury_risk": 0,
        "duration_weeks": 6
    },
}

def apply_training(player_id: str, program_name: str) -> Dict:
    """Apply an offseason training program to a player."""
    if program_name not in TRAINING_PROGRAMS:
        raise HTTPException(status_code=400, detail=f"Unknown training program: {program_name}")

    program = TRAINING_PROGRAMS[program_name]

    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

    results = {"program": program_name, "gains": {}, "injuries": [], "fatigue_cleared": 0}

    # Age-based training effectiveness
    age = player["age"]
    if age < 22:
        training_mult = 1.3  # Young players develop faster
    elif age < 26:
        training_mult = 1.1
    elif age < 30:
        training_mult = 0.9
    elif age < 33:
        training_mult = 0.65
    else:
        training_mult = 0.35  # Veterans decline

    # Work ethic bonus
    work_mult = 0.7 + (player["work_ethic"] / 100.0) * 0.6

    # Apply training to primary attributes
    for attr in program["primary"]:
        current = player.get(attr, 50)
        if attr in ["stamina", "durability"]:
            gain = roll(3, 2)
        else:
            gain = roll(2, 1.5)
        gain = max(0, round(gain * training_mult * work_mult * program["intensity"]))
        # Diminishing returns at high levels
        if current > 80:
            gain = max(0, gain - 1)
        if current > 90:
            gain = max(0, gain - 2)
        new_val = clamp(current + gain, 15, 99)
        results["gains"][attr] = {"before": current, "after": new_val, "gain": gain}

    # Apply to secondary attributes
    for attr in program["secondary"]:
        current = player.get(attr, 50)
        gain = max(0, round(roll(1, 1.5) * training_mult * work_mult * program["intensity"]))
        if current > 85:
            gain = max(0, gain - 1)
        new_val = clamp(current + gain, 15, 99)
        results["gains"][attr] = {"before": current, "after": new_val, "gain": gain}

    # Injury risk from training
    injury_risk = program["injury_risk"] * (1 - player["durability"] / 100.0)
    injury_occurred = False
    if random.random() < injury_risk / 100.0:
        injury_occurred = True
        injury_type = random.choice(["Minor training strain", "Moderate muscle pull", "Stress fracture"])
        injury_games = random.randint(1, 15) if "Minor" in injury_type else random.randint(10, 30)
        results["injuries"].append({"type": injury_type, "games_missed": injury_games})
        db.execute("UPDATE players SET injury_status=?, injury_games_remaining=? WHERE id=?",
                   (injury_type, injury_games, player_id))

    # Clear fatigue during offseason
    fatigue_cleared = min(player["fatigue"], random.uniform(60, 95))
    results["fatigue_cleared"] = round(fatigue_cleared, 1)

    # Apply all changes
    update_sql_parts = ["fatigue = MAX(0, fatigue - ?)", "updated_at = datetime('now')"]
    update_values = [fatigue_cleared]

    for attr, data in results["gains"].items():
        update_sql_parts.append(f"{attr} = ?")
        update_values.append(data["after"])

    update_values.append(player_id)
    db.execute(f"UPDATE players SET {', '.join(update_sql_parts)} WHERE id = ?", update_values)

    results["injury_occurred"] = injury_occurred
    return results

# ============================================================
# AGE PROGRESSION & NATURAL DECLINE
# ============================================================

def apply_aging(player_id: str) -> Dict:
    """Apply age-related attribute changes at end of season."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    age = player["age"] + 1
    changes = {}

    # Dynamic attributes naturally decline with age
    if age >= 30:
        decline_rate = (age - 29) * 0.8  # accelerates with age
        dynamic_attrs = [
            "vertical_jump", "speed", "lateral_quickness", "strength", "core_stability",
            "stamina", "durability", "first_step", "finishing"
        ]
        for attr in dynamic_attrs:
            decline = round(decline_rate * random.uniform(0.5, 1.5))
            if decline > 0:
                current = player[attr]
                changes[attr] = clamp(current - decline, 10, 99)

    # Mental attributes improve with experience
    if age <= 35:
        mental_attrs = ["bbiq", "composure", "leadership"]
        for attr in mental_attrs:
            gain = random.randint(0, 2)
            if gain > 0:
                current = player[attr]
                changes[attr] = clamp(current + gain, 20, 99)

    # Apply changes
    with get_db() as db:
        update_parts = ["age = ?", "updated_at = datetime('now')"]
        update_vals = [age]
        for attr, val in changes.items():
            update_parts.append(f"{attr} = ?")
            update_vals.append(val)
        update_vals.append(player_id)
        db.execute(f"UPDATE players SET {', '.join(update_parts)} WHERE id = ?", update_vals)

    return {"new_age": age, "attribute_changes": changes}

# ============================================================
# ECONOMY SYSTEM
# ============================================================

def get_endorsement_offers(player_id: str) -> List[Dict]:
    """Generate endorsement offers based on player fame and performance."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    fan = player["fan_base"]
    clout = player["clout"]
    perf_factor = (player["season_pts"] / max(1, player["season_games"])) / 25.0

    offers = []
    brand_pool = [
        ("Nike", 95, 8.0), ("Adidas", 90, 6.0), ("Under Armour", 75, 4.0),
        ("Puma", 70, 3.5), ("New Balance", 65, 2.5), ("Anta", 60, 3.0),
        ("Li-Ning", 60, 3.0), ("Jordan Brand", 98, 10.0), ("Peak", 50, 1.5),
        ("Gatorade", 80, 2.0), ("Beats by Dre", 70, 1.0), ("State Farm", 60, 1.5),
        ("Sprite", 65, 1.2), ("Tissot", 55, 0.8), ("Mercedes-Benz", 70, 1.5),
    ]

    for brand, prestige, base_value in random.sample(brand_pool, min(5, len(brand_pool))):
        if fan > prestige - 30:
            multi = perf_factor * (fan / 80.0) * (clout / 50.0)
            annual = round(base_value * max(0.3, multi) * random.uniform(0.8, 1.2), 2)
            if annual > 0.3:
                offers.append({
                    "brand": brand, "prestige": prestige,
                    "annual_value": annual, "years": random.choice([2, 3, 4, 5])
                })

    return sorted(offers, key=lambda o: o["annual_value"], reverse=True)

def sign_endorsement(player_id: str, brand_name: str, annual_value: float, years: int) -> Dict:
    with get_db() as db:
        db.execute("""
            INSERT INTO endorsements (player_id, brand_name, annual_value, years_remaining, prestige)
            VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(prestige), 50) FROM (SELECT 50) UNION ALL SELECT 50 LIMIT 1))
        """, (player_id, brand_name, annual_value, years))
        # Update wealth
        db.execute("UPDATE players SET wealth = wealth + ?, fan_base = MIN(100, fan_base + ?) WHERE id=?",
                   (annual_value, random.uniform(0.5, 2.0), player_id))
    return {"brand": brand_name, "annual_value": annual_value, "years": years, "status": "signed"}

def make_investment(player_id: str, name: str, amount: float, risk: str) -> Dict:
    """Make an off-court investment."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    if amount > player["wealth"]:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    risk_returns = {"Low": (0.03, 0.08, 0.02), "Medium": (-0.05, 0.20, 0.10), "High": (-0.30, 0.50, 0.25)}
    lo, hi, _ = risk_returns.get(risk, (0.0, 0.15, 0.08))
    annual_return = round(random.uniform(lo, hi), 3)

    with get_db() as db:
        db.execute("""
            INSERT INTO investments (player_id, name, amount_invested, current_value, annual_return, risk_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (player_id, name, amount, amount, annual_return, risk))
        db.execute("UPDATE players SET wealth = wealth - ? WHERE id=?", (amount, player_id))

    return {"name": name, "amount": amount, "annual_return": annual_return, "risk": risk}

# ============================================================
# MEDIA & CLOUT SYSTEM
# ============================================================

MEDIA_SCENARIOS = [
    {
        "id": "postgame_loss",
        "trigger": "after_loss",
        "question": "Tough loss tonight. What went wrong?",
        "choices": [
            {"text": "Take responsibility. 'I need to be better.'", "tone": "humble",
             "fan": 3, "clout": 1, "chemistry": 3, "mvp": 0},
            {"text": "Blame teammates. 'We didn't execute as a unit.'", "tone": "deflect",
             "fan": -5, "clout": -2, "chemistry": -8, "mvp": -3},
            {"text": "Dismiss the question. 'We'll be fine, next game.'", "tone": "arrogant",
             "fan": -1, "clout": 1, "chemistry": -2, "mvp": -1},
        ]
    },
    {
        "id": "mvp_campaign",
        "trigger": "mid_season",
        "question": "Do you think you deserve MVP consideration this year?",
        "choices": [
            {"text": "Stay humble. 'It's an honor just to be mentioned.'", "tone": "humble",
             "fan": 2, "clout": 3, "chemistry": 2, "mvp": 5},
            {"text": "Confident declaration. 'Absolutely. Look at my numbers.'", "tone": "arrogant",
             "fan": 3, "clout": 5, "chemistry": -3, "mvp": 8},
            {"text": "Deflect to team. 'We're winning, that's what matters.'", "tone": "diplomatic",
             "fan": 4, "clout": 2, "chemistry": 5, "mvp": 3},
        ]
    },
    {
        "id": "trade_rumors",
        "trigger": "random",
        "question": "There are rumors you're unhappy. Care to comment?",
        "choices": [
            {"text": "Shut it down. 'I'm committed to this team.'", "tone": "loyal",
             "fan": 5, "clout": -3, "chemistry": 5, "mvp": 0},
            {"text": "Keep it vague. 'I'm focused on basketball.'", "tone": "neutral",
             "fan": 0, "clout": 1, "chemistry": 0, "mvp": 0},
            {"text": "Fuel the fire. 'I want to win, wherever that is.'", "tone": "demanding",
             "fan": -8, "clout": 4, "chemistry": -10, "mvp": -2},
        ]
    },
    {
        "id": "social_media_controversy",
        "trigger": "random",
        "question": "Your old social media posts have resurfaced. Response?",
        "choices": [
            {"text": "Sincere apology. 'I've grown since then.'", "tone": "humble",
             "fan": 2, "clout": 2, "chemistry": 1, "mvp": 1},
            {"text": "Deny and attack. 'Fake news, haters gonna hate.'", "tone": "arrogant",
             "fan": -10, "clout": -5, "chemistry": 0, "mvp": -10},
            {"text": "Ignore it completely.", "tone": "silent",
             "fan": -2, "clout": 0, "chemistry": 0, "mvp": -3},
        ]
    },
    {
        "id": "championship_aspirations",
        "trigger": "playoffs",
        "question": "Is it championship or bust for you this year?",
        "choices": [
            {"text": "Confident. 'We have what it takes to win it all.'", "tone": "confident",
             "fan": 5, "clout": 4, "chemistry": 4, "mvp": 2},
            {"text": "Cautious. 'One game at a time.'", "tone": "humble",
             "fan": 1, "clout": 1, "chemistry": 2, "mvp": 1},
            {"text": "Guarantee. 'I promise we're winning the title.'", "tone": "guarantee",
             "fan": 8, "clout": 8, "chemistry": 2, "mvp": 5,
             "risk": "If you lose, fan_base drops 15."},
        ]
    },
]

def handle_media_event(player_id: str, scenario_id: str, choice_index: int) -> Dict:
    """Process a media interaction choice."""
    scenario = next((s for s in MEDIA_SCENARIOS if s["id"] == scenario_id), None)
    if not scenario or choice_index >= len(scenario["choices"]):
        raise HTTPException(status_code=400, detail="Invalid scenario or choice")

    choice = scenario["choices"][choice_index]

    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

        # Apply effects
        new_fan = clamp(player["fan_base"] + choice["fan"], 0, 100)
        new_clout = clamp(player["clout"] + choice["clout"], 0, 100)
        new_chem = clamp(player["chemistry"] + choice["chemistry"], 0, 100)
        new_mvp = clamp(player["mvp_votes"] + choice["mvp"], 0, 100)
        new_morale = clamp(player["morale"] + random.randint(-3, 5), 10, 100)

        db.execute("""
            UPDATE players SET fan_base=?, clout=?, chemistry=?, mvp_votes=?, morale=?, updated_at=datetime('now')
            WHERE id=?
        """, (new_fan, new_clout, new_chem, new_mvp, new_morale, player_id))

        # Record event
        db.execute("""
            INSERT INTO media_events (player_id, season_number, event_type, description, choice_made, fan_impact, clout_impact)
            VALUES (?, (SELECT current_season FROM league_state WHERE id=1), 'interview', ?, ?, ?, ?)
        """, (player_id, scenario["question"], choice["text"], choice["fan"], choice["clout"]))

    return {
        "scenario": scenario["question"],
        "choice": choice["text"],
        "effects": {
            "fan_base_change": choice["fan"],
            "clout_change": choice["clout"],
            "chemistry_change": choice["chemistry"],
            "mvp_votes_change": choice["mvp"],
            "new_fan_base": new_fan,
            "new_clout": new_clout,
        }
    }

def get_random_media_scenario(player_id: str) -> Dict:
    """Get a random media scenario appropriate for current game phase."""
    state = get_league_state()
    phase = state["current_phase"]

    if phase == "playoffs":
        candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("playoffs", "random")]
    elif phase == "regular_season" and state["games_played_in_season"] > 40:
        candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("mid_season", "random", "after_loss")]
    else:
        candidates = [s for s in MEDIA_SCENARIOS if s["trigger"] in ("random", "after_loss")]

    scenario = random.choice(candidates)
    return {"scenario": scenario, "phase": phase}

# ============================================================
# CLOUT ACTIONS (Team Influence)
# ============================================================

def request_trade(player_id: str, desired_team_id: int) -> Dict:
    """Use clout to request a trade to a specific team."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    clout = player["clout"]
    if clout < 30:
        return {"success": False, "message": "Not enough clout to demand a trade. Need at least 30 clout."}

    # Clout cost and success probability
    success_prob = min(0.9, clout / 120.0)
    success = random.random() < success_prob

    with get_db() as db:
        if success:
            db.execute("UPDATE players SET team_id=?, clout=MAX(0, clout-15), chemistry=50 WHERE id=?",
                       (desired_team_id, player_id))
            # Record event
            db.execute("""
                INSERT INTO career_progress (player_id, season_number, event_type, description)
                VALUES (?, (SELECT current_season FROM league_state WHERE id=1), 'trade_request',
                ?)
            """, (player_id, f"Successfully forced trade to {TEAMS[desired_team_id]['name']}"))
            return {"success": True, "new_team": TEAMS[desired_team_id]["name"],
                    "message": "Trade request granted! You've been moved."}
        else:
            db.execute("UPDATE players SET clout=MAX(0, clout-8), chemistry=MAX(10, chemistry-15), morale=MAX(10, morale-10) WHERE id=?",
                       (player_id,))
            return {"success": False,
                    "message": "Trade request denied. Management refused. Team chemistry and morale have suffered."}

def demand_coaching_change(player_id: str) -> Dict:
    """Use clout to push for coaching change."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    if player["clout"] < 50:
        return {"success": False, "message": "Need at least 50 clout to influence coaching decisions."}

    success = random.random() < 0.5
    with get_db() as db:
        if success:
            db.execute("UPDATE players SET clout=MAX(0, clout-20) WHERE id=?", (player_id,))
            return {"success": True, "message": "Management has agreed to make coaching changes in the offseason."}
        else:
            db.execute("UPDATE players SET clout=MAX(0, clout-5), chemistry=MAX(10, chemistry-10) WHERE id=?", (player_id,))
            return {"success": False, "message": "Organization sided with the coach. Your standing has been damaged."}

# ============================================================
# AWARDS SYSTEM
# ============================================================

def calculate_season_awards(player_id: str) -> Dict:
    """Calculate awards for the completed season."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    games = player["season_games"]
    if games < 10:
        return {"awards": [], "message": "Not enough games played for award consideration."}

    ppg = round(player["season_pts"] / games, 1)
    rpg = round(player["season_reb"] / games, 1)
    apg = round(player["season_ast"] / games, 1)
    spg = round(player["season_stl"] / games, 1)
    bpg = round(player["season_blk"] / games, 1)
    fg_pct = round(player["season_fgm"] / max(1, player["season_fga"]), 3)
    tp_pct = round(player["season_3pm"] / max(1, player["season_3pa"]), 3)
    ft_pct = round(player["season_ftm"] / max(1, player["season_fta"]), 3)

    awards = []
    mvp_score = 0

    # MVP consideration
    mvp_score += ppg * 0.8
    mvp_score += rpg * 0.5
    mvp_score += apg * 0.8
    mvp_score += spg * 3
    mvp_score += bpg * 3
    mvp_score += player["season_team_wins"] * 0.6
    mvp_score += player["mvp_votes"] * 0.3
    mvp_score += player["clout"] * 0.2

    if mvp_score > 70 and player["season_team_wins"] > 40:
        awards.append("MVP")
    elif mvp_score > 55:
        awards.append("All-NBA First Team")
    elif mvp_score > 42:
        awards.append("All-NBA Second Team")
    elif mvp_score > 32:
        awards.append("All-NBA Third Team")

    # Defensive awards
    def_score = spg * 4 + bpg * 5 + player["perimeter_defense"] * 0.1 + player["help_defense"] * 0.1 + player["rim_protection"] * 0.1
    if def_score > 35:
        awards.append("All-Defensive First Team")
    elif def_score > 25:
        awards.append("All-Defensive Second Team")
    if def_score > 42:
        awards.append("DPOY")

    # Rookie awards
    if player["experience"] == 0:
        if ppg > 15:
            awards.append("ROTY")
        awards.append("All-Rookie First Team")

    # Sixth Man (simplified: high PPG off bench)
    if 12 < ppg < 22 and games > 60:
        awards.append("Sixth Man of the Year")

    # Most Improved
    if ppg > 20 and player["experience"] >= 2:
        awards.append("Most Improved Player")

    # Record awards
    state = get_league_state()
    with get_db() as db:
        for award in awards:
            db.execute("""
                INSERT INTO awards (player_id, season_number, award_type, award_name)
                VALUES (?, ?, 'season', ?)
            """, (player_id, state["current_season"], award))

    return {"awards": awards, "mvp_score": round(mvp_score, 1), "stats": {"ppg": ppg, "rpg": rpg, "apg": apg, "spg": spg, "bpg": bpg, "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct}}

# ============================================================
# SEASON SUMMARY
# ============================================================

def finalize_season(player_id: str) -> Dict:
    """Finalize season stats and create season summary."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())

    games = max(1, player["season_games"])
    minutes = max(1, player["season_minutes"])
    mpg = round(minutes / games, 1)
    ppg = round(player["season_pts"] / games, 1)
    rpg = round(player["season_reb"] / games, 1)
    apg = round(player["season_ast"] / games, 1)
    spg = round(player["season_stl"] / games, 1)
    bpg = round(player["season_blk"] / games, 1)
    topg = round(player["season_tov"] / games, 1)
    fg_pct = round(player["season_fgm"] / max(1, player["season_fga"]), 3)
    tp_pct = round(player["season_3pm"] / max(1, player["season_3pa"]), 3)
    ft_pct = round(player["season_ftm"] / max(1, player["season_fta"]), 3)

    # Win shares (simplified)
    ws = round(player["season_team_wins"] * (ppg + rpg * 0.5 + apg * 0.5) / 150.0, 1)

    # BPM (simplified Box Plus/Minus)
    bpm = round((ppg * 0.4 + rpg * 0.3 + apg * 0.5 + spg * 1.5 + bpg * 1.5 - topg * 1.0) / (mpg / 36.0) - 2.0, 1)

    # VORP
    vorp = round(max(0, bpm + 2) * games / 82.0 * 1.5, 1)

    # PER estimation
    per = round(15 + (ppg - 15) * 0.8 + (rpg - 5) * 0.3 + (apg - 3) * 0.4 + (spg - 1) * 2 + (bpg - 0.5) * 2, 1)
    per = clamp(per, 0, 45)

    # TS%
    ts_denom = 2 * (player["season_fga"] + 0.44 * player["season_fta"])
    ts_pct = round(player["season_pts"] / max(1, ts_denom), 3)

    # USG%
    usg_pct = round(100 * (player["season_fga"] + 0.44 * player["season_fta"] + player["season_tov"]) * (48 / max(1, mpg)) / 500, 1)
    usg_pct = clamp(usg_pct, 5, 50)

    state = get_league_state()
    awards = calculate_season_awards(player_id)

    # Determine playoff result
    team_wins = player["season_team_wins"]
    playoff_result = None
    if team_wins >= 42:
        playoff_rounds = ["First Round Exit", "Conference Semifinals", "Conference Finals", "NBA Finals Loss", "NBA CHAMPION"]
        seed_strength = min(4, (team_wins - 40) // 8)
        outcome_idx = min(seed_strength + random.randint(-1, 1), 4)
        playoff_result = playoff_rounds[max(0, outcome_idx)]
        if playoff_result == "NBA CHAMPION":
            awards["awards"].append("NBA Champion")

    with get_db() as db:
        db.execute("""
            INSERT INTO season_summaries (player_id, season_number, team_id, age, games_played,
            games_started, mpg, ppg, rpg, apg, spg, bpg, topg, fg_pct, tp_pct, ft_pct,
            per, ts_pct, usg_pct, ws, bpm, vorp, team_wins, team_losses, playoff_result,
            role, awards)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (player_id, state["current_season"], player["team_id"], player["age"],
              games, games, mpg, ppg, rpg, apg, spg, bpg, topg, fg_pct, tp_pct, ft_pct,
              per, ts_pct, usg_pct, ws, bpm, vorp, player["season_team_wins"],
              player["season_team_losses"], playoff_result, player["role"], json.dumps(awards["awards"])))

        # Reset season counters
        db.execute("""
            UPDATE players SET season_pts=0, season_reb=0, season_ast=0, season_stl=0, season_blk=0,
            season_tov=0, season_fga=0, season_fgm=0, season_3pa=0, season_3pm=0, season_fta=0, season_ftm=0,
            season_games=0, season_minutes=0, season_fouls=0, season_team_wins=0, season_team_losses=0,
            hot_streak=0, cold_streak=0, injury_status=NULL, injury_games_remaining=0,
            fatigue=MAX(0, fatigue-50), injury_risk=MAX(0, injury_risk-30),
            experience = experience + 1, mvp_votes = 0
            WHERE id=?
        """, (player_id,))

    # Apply aging
    age_changes = apply_aging(player_id)

    return {
        "season": state["current_season"],
        "stats": {"ppg": ppg, "rpg": rpg, "apg": apg, "spg": spg, "bpg": bpg, "topg": topg,
                  "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct, "mpg": mpg},
        "advanced": {"per": per, "ts_pct": ts_pct, "usg_pct": usg_pct, "ws": ws, "bpm": bpm, "vorp": vorp},
        "team_record": f"{player['season_team_wins']}-{player['season_team_losses']}",
        "playoff_result": playoff_result,
        "awards": awards["awards"],
        "age_changes": age_changes
    }

# ============================================================
# CAREER OVERVIEW
# ============================================================

def get_career_overview(player_id: str) -> Dict:
    """Get complete career overview with all seasons and awards."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

        seasons = [dict(s) for s in db.execute(
            "SELECT * FROM season_summaries WHERE player_id=? ORDER BY season_number", (player_id,)
        ).fetchall()]

        awards = [dict(a) for a in db.execute(
            "SELECT * FROM awards WHERE player_id=? ORDER BY season_number DESC", (player_id,)
        ).fetchall()]

        career_games = sum(s["games_played"] for s in seasons)
        career_pts = sum(s["ppg"] * s["games_played"] for s in seasons)
        career_reb = sum(s["rpg"] * s["games_played"] for s in seasons)
        career_ast = sum(s["apg"] * s["games_played"] for s in seasons)

        # GOAT score calculation
        championships = sum(1 for a in awards if a["award_name"] == "NBA Champion")
        mvp_count = sum(1 for a in awards if a["award_name"] == "MVP")
        all_nba = sum(1 for a in awards if "All-NBA" in a["award_name"])
        all_star_est = max(0, mvp_count * 2 + all_nba)

        goat_score = (
            championships * 25 + mvp_count * 20 + all_nba * 8 +
            (career_pts / 1000) * 3 + (career_reb / 500) * 1 + (career_ast / 500) * 2
        )
        goat_pct = min(100, goat_score / 6.5)

        contracts = [dict(c) for c in db.execute(
            "SELECT * FROM contracts WHERE player_id=? ORDER BY season_number", (player_id,)
        ).fetchall()]

    return {
        "player": {"name": player["name"], "position": player["position"], "age": player["age"],
                   "height": player["height"], "weight": player["weight"], "team": TEAMS.get(player["team_id"], {}).get("name", "Free Agent"),
                   "experience": player["experience"], "clout": player["clout"], "fan_base": player["fan_base"],
                   "wealth": round(player["wealth"], 2), "morale": player["morale"]},
        "career_totals": {"games": career_games, "pts": round(career_pts), "reb": round(career_reb),
                          "ast": round(career_ast)},
        "goat_score": round(goat_pct, 1),
        "championships": championships,
        "mvps": mvp_count,
        "all_nba": all_nba,
        "seasons": seasons,
        "awards": awards,
        "contracts": contracts
    }

# ============================================================
# SAVE / LOAD SYSTEM
# ============================================================

def save_game(player_id: str, save_name: str, description: str = "") -> Dict:
    """Create a named save point."""
    # We persist everything in SQLite, so "saving" means recording a named restore point
    # In a full implementation, this would snapshot the entire DB state
    # For now, we record the current season/phase so the player can track saves
    state = get_league_state()
    save_id = str(uuid.uuid4())[:8]

    with get_db() as db:
        existing = db.execute("SELECT id FROM save_files WHERE player_id=? AND save_name=?", (player_id, save_name)).fetchone()
        if existing:
            db.execute("UPDATE save_files SET season_number=?, description=?, created_at=datetime('now') WHERE id=?",
                       (state["current_season"], description, existing["id"]))
            save_id = existing["id"]
        else:
            db.execute("INSERT INTO save_files (id, player_id, save_name, season_number, description) VALUES (?,?,?,?,?)",
                       (save_id, player_id, save_name, state["current_season"], description))

    return {"save_id": save_id, "save_name": save_name, "season": state["current_season"], "phase": state["current_phase"]}

def list_saves(player_id: str) -> List[Dict]:
    with get_db() as db:
        saves = [dict(s) for s in db.execute("SELECT * FROM save_files WHERE player_id=? ORDER BY created_at DESC", (player_id,)).fetchall()]
    return saves

def load_game(player_id: str) -> Dict:
    """Load the current state (since we use SQLite, state is always persisted)."""
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
    state = get_league_state()
    return {"player_id": player_id, "player_name": player["name"], "season": state["current_season"], "phase": state["current_phase"]}

def export_career_json(player_id: str) -> Dict:
    """Export entire career data as JSON."""
    career = get_career_overview(player_id)
    with get_db() as db:
        games = [dict(g) for g in db.execute(
            "SELECT * FROM game_logs WHERE player_id=? ORDER BY season_number, game_number", (player_id,)
        ).fetchall()]
        media = [dict(m) for m in db.execute(
            "SELECT * FROM media_events WHERE player_id=? ORDER BY created_at DESC LIMIT 50", (player_id,)
        ).fetchall()]
    career["game_logs"] = games
    career["media_events"] = media
    return career

# ============================================================
# FASTAPI APP & ROUTES
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Basketball Career Simulator", version="2.0.0", lifespan=lifespan)

@app.get("/api/health")
async def health():
    return {"status": "ok", "teams": len(TEAMS)}

# ── Player routes ──

class CreatePlayerRequest(BaseModel):
    name: str
    position: str
    age: int = 19
    team_id: int = 0

@app.post("/api/player/create")
async def api_create_player(req: CreatePlayerRequest):
    if req.position not in ["PG", "SG", "SF", "PF", "C"]:
        raise HTTPException(status_code=400, detail="Position must be PG, SG, SF, PF, or C")
    pid = create_player(req.name, req.position, req.age, req.team_id)
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone())
    return {"player_id": pid, "player": sanitize_player(player)}

@app.get("/api/player/{player_id}")
async def api_get_player(player_id: str):
    with get_db() as db:
        player = db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
    return {"player": sanitize_player(dict(player))}

@app.get("/api/player/{player_id}/attributes")
async def api_get_attributes(player_id: str):
    with get_db() as db:
        player = db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
    p = dict(player)
    return {
        "static_physicals": {
            "height": p["height"], "weight": p["weight"], "wingspan": p["wingspan"],
            "standing_reach": p["standing_reach"], "hand_size": p["hand_size"],
            "frame_build": p["frame_build"], "body_fat_pct": p["body_fat_pct"]
        },
        "dynamic_athleticism": {
            "vertical_jump": p["vertical_jump"], "speed": p["speed"],
            "lateral_quickness": p["lateral_quickness"], "strength": p["strength"],
            "core_stability": p["core_stability"], "stamina": p["stamina"], "durability": p["durability"]
        },
        "defense": {
            "perimeter_defense": p["perimeter_defense"], "help_defense": p["help_defense"],
            "steal": p["steal"], "rim_protection": p["rim_protection"], "box_out": p["box_out"]
        },
        "scoring": {
            "first_step": p["first_step"], "finishing": p["finishing"], "mid_range": p["mid_range"],
            "catch_shoot_3pt": p["catch_shoot_3pt"], "pull_up_3pt": p["pull_up_3pt"],
            "off_ball": p["off_ball"], "drawing_fouls": p["drawing_fouls"]
        },
        "playmaking": {
            "ball_security": p["ball_security"], "pnr_vision": p["pnr_vision"],
            "passing_accuracy": p["passing_accuracy"], "free_throw": p["free_throw"]
        },
        "mental": {
            "bbiq": p["bbiq"], "clutch_factor": p["clutch_factor"], "work_ethic": p["work_ethic"],
            "leadership": p["leadership"], "composure": p["composure"]
        }
    }

@app.put("/api/player/{player_id}/role")
async def api_set_role(player_id: str, role: str = Query(...)):
    valid_roles = ["Ball-Dominant Creator", "Off-Ball Finisher", "Rim Protector",
                   "Two-Way Wing", "3-and-D Specialist", "Point Forward", "Stretch Big", "Defensive Anchor"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {valid_roles}")
    with get_db() as db:
        db.execute("UPDATE players SET role=?, updated_at=datetime('now') WHERE id=?", (role, player_id))
    return {"role": role}

@app.put("/api/player/{player_id}/load-management")
async def api_toggle_load_management(player_id: str, enabled: bool = Query(...)):
    with get_db() as db:
        db.execute("UPDATE players SET load_management=?, updated_at=datetime('now') WHERE id=?", (int(enabled), player_id))
    return {"load_management": enabled}

# ── Game routes ──

@app.post("/api/game/simulate/{player_id}")
async def api_simulate_game(player_id: str, opponent_id: int = None, is_playoff: bool = False):
    result = simulate_game(player_id, opponent_id, is_playoff)
    return result

@app.post("/api/game/simulate-batch/{player_id}")
async def api_simulate_batch(player_id: str, count: int = Query(5, le=20)):
    """Simulate multiple games at once."""
    results = []
    for i in range(count):
        result = simulate_game(player_id)
        results.append(result)
    return {"games": results, "count": len(results)}

@app.get("/api/game/logs/{player_id}")
async def api_game_logs(player_id: str, season: int = None, limit: int = 20):
    with get_db() as db:
        if season:
            rows = db.execute(
                "SELECT * FROM game_logs WHERE player_id=? AND season_number=? ORDER BY game_number DESC LIMIT ?",
                (player_id, season, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM game_logs WHERE player_id=? ORDER BY season_number DESC, game_number DESC LIMIT ?",
                (player_id, limit)
            ).fetchall()
    return {"games": [dict(r) for r in rows]}

# ── Season routes ──

@app.get("/api/season/state")
async def api_season_state():
    state = get_league_state()
    return state

@app.post("/api/season/advance-phase")
async def api_advance_phase():
    advance_league_phase()
    state = get_league_state()
    return state

@app.post("/api/season/finalize/{player_id}")
async def api_finalize_season(player_id: str):
    return finalize_season(player_id)

@app.get("/api/season/summaries/{player_id}")
async def api_season_summaries(player_id: str):
    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM season_summaries WHERE player_id=? ORDER BY season_number", (player_id,)
        ).fetchall()]
    return {"seasons": rows}

@app.get("/api/season/schedule/{team_id}")
async def api_season_schedule(team_id: int):
    schedule = generate_season_schedule(team_id)
    return {"team_id": team_id, "team": TEAMS.get(team_id, {}).get("name"), "schedule": [{"opponent_id": oid, "opponent_name": TEAMS[oid]["name"], "opponent_abbr": TEAMS[oid]["abbr"], "opponent_overall": TEAMS[oid]["overall"]} for oid in schedule]}

# ── Training routes ──

@app.get("/api/training/programs")
async def api_training_programs():
    return {"programs": {k: {"description": v["description"], "primary": v["primary"], "secondary": v["secondary"], "intensity": v["intensity"], "injury_risk": v["injury_risk"]} for k, v in TRAINING_PROGRAMS.items()}}

@app.post("/api/training/apply/{player_id}")
async def api_apply_training(player_id: str, program: str = Query(...)):
    return apply_training(player_id, program)

# ── Economy routes ──

@app.get("/api/economy/endorsements/{player_id}")
async def api_endorsement_offers(player_id: str):
    return {"offers": get_endorsement_offers(player_id)}

@app.post("/api/economy/sign-endorsement/{player_id}")
async def api_sign_endorsement(player_id: str, brand: str = Query(...), annual_value: float = Query(...), years: int = Query(...)):
    return sign_endorsement(player_id, brand, annual_value, years)

@app.get("/api/economy/endorsements-active/{player_id}")
async def api_active_endorsements(player_id: str):
    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM endorsements WHERE player_id=? AND years_remaining > 0", (player_id,)
        ).fetchall()]
    return {"endorsements": rows}

@app.post("/api/economy/invest/{player_id}")
async def api_invest(player_id: str, name: str = Query(...), amount: float = Query(...), risk: str = Query("Medium")):
    return make_investment(player_id, name, amount, risk)

@app.get("/api/economy/investments/{player_id}")
async def api_investments(player_id: str):
    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM investments WHERE player_id=?", (player_id,)
        ).fetchall()]
    return {"investments": rows}

# ── Media routes ──

@app.get("/api/media/scenario/{player_id}")
async def api_media_scenario(player_id: str):
    return get_random_media_scenario(player_id)

@app.post("/api/media/respond/{player_id}")
async def api_media_respond(player_id: str, scenario_id: str = Query(...), choice_index: int = Query(...)):
    return handle_media_event(player_id, scenario_id, choice_index)

@app.get("/api/media/history/{player_id}")
async def api_media_history(player_id: str, limit: int = 20):
    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM media_events WHERE player_id=? ORDER BY created_at DESC LIMIT ?", (player_id, limit)
        ).fetchall()]
    return {"events": rows}

# ── Clout routes ──

@app.post("/api/clout/request-trade/{player_id}")
async def api_request_trade(player_id: str, desired_team_id: int = Query(...)):
    return request_trade(player_id, desired_team_id)

@app.post("/api/clout/coaching-change/{player_id}")
async def api_coaching_change(player_id: str):
    return demand_coaching_change(player_id)

# ── Career routes ──

@app.get("/api/career/{player_id}")
async def api_career(player_id: str):
    return get_career_overview(player_id)

@app.get("/api/career/export/{player_id}")
async def api_career_export(player_id: str):
    return export_career_json(player_id)

# ── Save / Load routes ──

@app.post("/api/save/{player_id}")
async def api_save(player_id: str, save_name: str = Query(...), description: str = Query("")):
    return save_game(player_id, save_name, description)

@app.get("/api/saves/{player_id}")
async def api_saves(player_id: str):
    return {"saves": list_saves(player_id)}

@app.get("/api/load/{player_id}")
async def api_load(player_id: str):
    return load_game(player_id)

# ── Team / League routes ──

@app.get("/api/teams")
async def api_teams():
    return {"teams": {str(k): v for k, v in TEAMS.items()}}

@app.get("/api/teams/{team_id}")
async def api_team(team_id: int):
    team = TEAMS.get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    stars = TEAM_STARS.get(team_id, [])
    return {"team": team, "stars": [{"name": s[0], "position": s[1], "rating": s[2]} for s in stars]}

@app.get("/api/league/standings")
async def api_standings():
    """Generate current season standings."""
    state = get_league_state()
    standings = []
    for tid, team in TEAMS.items():
        s = simulate_team_season(tid, state["current_season"])
        standings.append({
            "team_id": tid, "name": team["name"], "abbr": team["abbr"],
            "conference": team["conference"], "division": team["division"],
            "wins": s["wins"], "losses": s["losses"], "overall": team["overall"]
        })

    east = sorted([t for t in standings if t["conference"] == "East"], key=lambda x: x["wins"], reverse=True)
    west = sorted([t for t in standings if t["conference"] == "West"], key=lambda x: x["wins"], reverse=True)
    return {"east": east, "west": west}

@app.get("/api/player/{player_id}/season-stats")
async def api_player_season_stats(player_id: str):
    with get_db() as db:
        player = dict(db.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone())
    games = max(1, player["season_games"])
    minutes = max(1, player["season_minutes"])
    return {
        "games": games,
        "mpg": round(minutes / games, 1),
        "ppg": round(player["season_pts"] / games, 1),
        "rpg": round(player["season_reb"] / games, 1),
        "apg": round(player["season_ast"] / games, 1),
        "spg": round(player["season_stl"] / games, 1),
        "bpg": round(player["season_blk"] / games, 1),
        "topg": round(player["season_tov"] / games, 1),
        "fg_pct": round(player["season_fgm"] / max(1, player["season_fga"]), 3),
        "tp_pct": round(player["season_3pm"] / max(1, player["season_3pa"]), 3),
        "ft_pct": round(player["season_ftm"] / max(1, player["season_fta"]), 3),
        "team_wins": player["season_team_wins"],
        "team_losses": player["season_team_losses"],
    }

# ── Progress / Milestones ──

@app.get("/api/progress/{player_id}")
async def api_progress(player_id: str):
    with get_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM career_progress WHERE player_id=? ORDER BY created_at DESC LIMIT 30", (player_id,)
        ).fetchall()]
    return {"events": rows}

# ============================================================
# HELPERS
# ============================================================

def sanitize_player(p: Dict) -> Dict:
    """Remove internal fields and format for API response."""
    skip_keys = {"season_pts", "season_reb", "season_ast", "season_stl", "season_blk",
                 "season_tov", "season_fga", "season_fgm", "season_3pa", "season_3pm",
                 "season_fta", "season_ftm", "season_games", "season_minutes", "season_fouls",
                 "season_team_wins", "season_team_losses"}
    result = {}
    for k, v in p.items():
        if k not in skip_keys:
            if isinstance(v, float):
                result[k] = round(v, 2)
            else:
                result[k] = v
    result["team_name"] = TEAMS.get(p.get("team_id", 0), {}).get("name", "Free Agent")
    result["team_abbr"] = TEAMS.get(p.get("team_id", 0), {}).get("abbr", "FA")
    return result

# ============================================================
# STATIC FILES & MAIN
# ============================================================

# Mount static files if directory exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "BBall Career Simulator API", "docs": "/docs"}

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("""
    ┌──────────────────────────────────────────────┐
    │     BBALL CAREER SIMULATOR v2.0              │
    │  Deep Strategy Basketball Career RPG        │
    │                                              │
    │  Starting server at http://localhost:8765    │
    │  API Docs at http://localhost:8765/docs      │
    └──────────────────────────────────────────────┘
    """)
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
