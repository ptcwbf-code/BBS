"""
Beast Arena - 巨兽之战 Backend Server
FastAPI + SQLite backend for player accounts, team persistence, battle history, and leaderboard.
"""
import sqlite3, json, os, uuid, hashlib, time
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Config ──────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beast_arena.db")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Beast Arena API", version="2.0.0")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── Database ─────────────────────────────────────────────────
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
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL, avatar_emoji TEXT DEFAULT '🦖',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login TEXT NOT NULL DEFAULT (datetime('now')),
            total_games INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0, draws INTEGER NOT NULL DEFAULT 0,
            total_rounds_played INTEGER NOT NULL DEFAULT 0,
            favorite_animal TEXT, xp INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS saved_teams (
            id TEXT PRIMARY KEY, player_id TEXT NOT NULL, name TEXT NOT NULL,
            mode TEXT NOT NULL, team_mode TEXT NOT NULL DEFAULT 'custom',
            animal_names TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS battles (
            id TEXT PRIMARY KEY, player_id TEXT NOT NULL,
            mode TEXT NOT NULL, team_mode TEXT NOT NULL,
            battlefield TEXT NOT NULL, player_team TEXT NOT NULL,
            enemy_team TEXT NOT NULL, winner TEXT NOT NULL,
            rounds INTEGER NOT NULL, battle_log TEXT NOT NULL,
            event_count INTEGER NOT NULL DEFAULT 0,
            total_damage_dealt INTEGER NOT NULL DEFAULT 0,
            total_damage_taken INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_battles_player ON battles(player_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_saved_teams_player ON saved_teams(player_id);
        """)
    print("[DB] Database initialized.")


# ── Models ───────────────────────────────────────────────────
class PlayerCreate(BaseModel):
    username: str; password: str; display_name: str; avatar_emoji: str = "🦖"

class PlayerLogin(BaseModel):
    username: str; password: str

class SaveTeam(BaseModel):
    player_id: str; name: str; mode: str; team_mode: str = "custom"; animal_names: list[str]

class BattleRecord(BaseModel):
    player_id: str; mode: str; team_mode: str; battlefield: str
    player_team: list[str]; enemy_team: list[str]; winner: str
    rounds: int; battle_log: list[str]
    event_count: int = 0; total_damage_dealt: int = 0; total_damage_taken: int = 0


# ── Helpers ──────────────────────────────────────────────────
def hash_password(pw: str) -> str: return hashlib.sha256(pw.encode()).hexdigest()

def verify_player(player_id: str) -> dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="Player not found")
        return dict(row)


# ── API: Player ──────────────────────────────────────────────
@api.post("/players/register")
def register_player(data: PlayerCreate):
    if len(data.username) < 3 or len(data.username) > 20:
        raise HTTPException(status_code=400, detail="Username must be 3-20 characters")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    player_id = str(uuid.uuid4())
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO players (id, username, password_hash, display_name, avatar_emoji) VALUES (?, ?, ?, ?, ?)",
                (player_id, data.username, hash_password(data.password), data.display_name, data.avatar_emoji),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already taken")
    return {"player_id": player_id, "username": data.username, "display_name": data.display_name}


@api.post("/players/login")
def login_player(data: PlayerLogin):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM players WHERE username = ? AND password_hash = ?",
            (data.username, hash_password(data.password)),
        ).fetchone()
    if not row: raise HTTPException(status_code=401, detail="Invalid username or password")
    with get_db() as db:
        db.execute("UPDATE players SET last_login = datetime('now') WHERE id = ?", (row["id"],))
    return dict(row)


@api.get("/players/{player_id}")
def get_player(player_id: str): return verify_player(player_id)


@api.get("/players/{player_id}/stats")
def get_player_stats(player_id: str):
    p = verify_player(player_id)
    with get_db() as db:
        recent = db.execute(
            "SELECT winner, COUNT(*) as cnt FROM battles WHERE player_id = ? GROUP BY winner",
            (player_id,),
        ).fetchall()
        fav = db.execute(
            "SELECT player_team FROM battles WHERE player_id = ? ORDER BY created_at DESC LIMIT 50",
            (player_id,),
        ).fetchall()
    from collections import Counter
    animal_counter = Counter()
    for r in fav:
        try:
            team = json.loads(r["player_team"])
            for a in team: animal_counter[a] += 1
        except (json.JSONDecodeError, TypeError): pass
    win_rate = round(p["wins"] / max(1, p["total_games"]) * 100, 1)
    return {**p, "win_rate": win_rate, "top_animals": animal_counter.most_common(5), "recent_results": [dict(r) for r in recent]}


# ── API: Leaderboard ─────────────────────────────────────────
@api.get("/leaderboard")
def get_leaderboard(sort_by: str = Query("wins", pattern="^(wins|win_rate|level|total_games)$"), limit: int = 20):
    with get_db() as db:
        rows = db.execute(
            f"""SELECT id, username, display_name, avatar_emoji, level, xp,
                       total_games, wins, losses, draws,
                       ROUND(CAST(wins AS REAL) / MAX(1, total_games) * 100, 1) as win_rate
                FROM players WHERE total_games > 0 ORDER BY {sort_by} DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── API: Saved Teams ─────────────────────────────────────────
@api.get("/players/{player_id}/teams")
def get_saved_teams(player_id: str):
    verify_player(player_id)
    with get_db() as db:
        rows = db.execute("SELECT * FROM saved_teams WHERE player_id = ? ORDER BY updated_at DESC", (player_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try: d["animal_names"] = json.loads(d["animal_names"])
        except json.JSONDecodeError: d["animal_names"] = []
        result.append(d)
    return result


@api.post("/players/{player_id}/teams")
def save_team(player_id: str, data: SaveTeam):
    verify_player(player_id)
    team_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO saved_teams (id, player_id, name, mode, team_mode, animal_names) VALUES (?, ?, ?, ?, ?, ?)",
            (team_id, player_id, data.name, data.mode, data.team_mode, json.dumps(data.animal_names)),
        )
    return {"id": team_id, "name": data.name}


@api.put("/teams/{team_id}")
def update_team(team_id: str, data: SaveTeam):
    with get_db() as db:
        row = db.execute("SELECT * FROM saved_teams WHERE id = ?", (team_id,)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="Team not found")
        db.execute(
            "UPDATE saved_teams SET name=?, mode=?, animal_names=?, updated_at=datetime('now') WHERE id=?",
            (data.name, data.mode, json.dumps(data.animal_names), team_id),
        )
    return {"id": team_id, "name": data.name}


@api.delete("/teams/{team_id}")
def delete_team(team_id: str):
    with get_db() as db: db.execute("DELETE FROM saved_teams WHERE id = ?", (team_id,))
    return {"deleted": True}


# ── API: Battle History ──────────────────────────────────────
@api.get("/players/{player_id}/battles")
def get_battle_history(player_id: str, limit: int = 50, offset: int = 0):
    verify_player(player_id)
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM battles WHERE player_id = ?", (player_id,)).fetchone()[0]
        rows = db.execute(
            "SELECT id, mode, team_mode, battlefield, player_team, enemy_team, winner, rounds, event_count, total_damage_dealt, total_damage_taken, created_at FROM battles WHERE player_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (player_id, limit, offset),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try: d["player_team"] = json.loads(d["player_team"]); d["enemy_team"] = json.loads(d["enemy_team"])
        except json.JSONDecodeError: pass
        result.append(d)
    return {"battles": result, "total": total}


@api.get("/battles/{battle_id}")
def get_battle_detail(battle_id: str):
    with get_db() as db:
        row = db.execute("SELECT * FROM battles WHERE id = ?", (battle_id,)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="Battle not found")
    d = dict(row)
    try:
        d["player_team"] = json.loads(d["player_team"]); d["enemy_team"] = json.loads(d["enemy_team"])
        d["battle_log"] = json.loads(d["battle_log"])
    except json.JSONDecodeError: pass
    return d


@api.post("/battles")
def record_battle(data: BattleRecord):
    battle_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            """INSERT INTO battles (id, player_id, mode, team_mode, battlefield, player_team, enemy_team,
               winner, rounds, battle_log, event_count, total_damage_dealt, total_damage_taken)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (battle_id, data.player_id, data.mode, data.team_mode, data.battlefield,
             json.dumps(data.player_team), json.dumps(data.enemy_team),
             data.winner, data.rounds, json.dumps(data.battle_log),
             data.event_count, data.total_damage_dealt, data.total_damage_taken),
        )
        if data.winner == "player":
            db.execute("UPDATE players SET wins=wins+1, total_games=total_games+1, total_rounds_played=total_rounds_played+?, xp=xp+? WHERE id=?",
                       (data.rounds, data.rounds * 10, data.player_id))
        elif data.winner == "enemy":
            db.execute("UPDATE players SET losses=losses+1, total_games=total_games+1, total_rounds_played=total_rounds_played+?, xp=xp+? WHERE id=?",
                       (data.rounds, max(1, data.rounds // 2) * 10, data.player_id))
        else:
            db.execute("UPDATE players SET draws=draws+1, total_games=total_games+1, total_rounds_played=total_rounds_played+?, xp=xp+? WHERE id=?",
                       (data.rounds, data.rounds * 5, data.player_id))
        row = db.execute("SELECT xp, level FROM players WHERE id = ?", (data.player_id,)).fetchone()
        new_level = max(1, int((row["xp"] / 100) ** 0.6) + 1)
        if new_level > row["level"]:
            db.execute("UPDATE players SET level = ? WHERE id = ?", (new_level, data.player_id))
    return {"id": battle_id, "saved": True}


# ── Register API router ──────────────────────────────────────
app.include_router(api)


# ── Static file serving ──────────────────────────────────────
@app.get("/{path_str:path}")
async def serve_frontend(path_str: str):
    """Serve static assets and index.html for SPA routing."""
    if path_str.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    target = os.path.join(STATIC_DIR, path_str if path_str else "index.html")
    if os.path.isfile(target):
        return FileResponse(target)
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")


# ── Startup ──────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8767, log_level="info")
