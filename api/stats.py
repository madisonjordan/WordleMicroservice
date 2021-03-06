import sqlite3
import uuid
import datetime
import logging.config
import redis
import json
from typing import Optional

from fastapi import FastAPI, Depends, Response, HTTPException, status, Request
from pydantic import BaseModel, BaseSettings

# use UUID in table
sqlite3.register_converter("GUID", lambda b: uuid.UUID(bytes_le=b))
sqlite3.register_adapter(uuid.UUID, lambda u: u.bytes_le)


class Settings(BaseSettings):
    database_dir: str = "./var/"
    logging_config: str = "./etc/logging.ini"
    shards: int = 3
    openapi_url: str = "/openapi.json"

    class Config:
        env_file = "./stats.env"


class Game(BaseModel):
    user_id: str
    game_id: int = int(datetime.date.today().strftime("%Y%m%d"))
    finished: Optional[datetime.date] = datetime.date.today()
    guesses: int
    won: bool


class User(BaseModel):
    username: str
    user_id: Optional[str]


class UserStats(BaseModel):
    currentStreak: int
    maxStreak: int
    guesses: dict
    winPercentage: float
    gamesPlayed: int
    gamesWon: int
    averageGuesses: float


def getShardId(string_uuid):
    curr_uuid = uuid.UUID(string_uuid)
    return curr_uuid.int % settings.shards


settings = Settings()
app = FastAPI(
    servers=[
        {"url": "http://127.0.0.1:5300"},
        {"url": "http://127.0.0.1:5301"},
        {"url": "http://127.0.0.1:5302"},
    ],
    root_path="/api/statistics",
    openapi_url=settings.openapi_url,
)

r = redis.Redis(
    host="localhost", port=6379, db=0, charset="utf-8", decode_responses=True
)


@app.get("/users/")
def list_users():
    for shard in range(settings.shards):
        db = sqlite3.connect(f"{settings.database_dir}stats{shard}.db")
        users = db.execute("SELECT * FROM users LIMIT 100")
        yield {"stats_db": shard, "users": users.fetchall()}


@app.get("/users/{username}", response_model=User)
def get_user_id(username: str):
    for shard in range(settings.shards):
        db = sqlite3.connect(f"{settings.database_dir}stats{shard}.db")
        cur = db.execute(
            "SELECT * FROM users WHERE username=:username LIMIT 1", [username]
        )
        user = cur.fetchone()
        if user:
            result = {"username": user[1], "user_id": user[0]}
            break
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist",
        )
    return result


# get user stats by user_id
@app.get("/users/{user_id}/stats", response_model=UserStats)
def get_stats(user_id: str):
    shard = getShardId(user_id)
    db = sqlite3.connect(f"{settings.database_dir}stats{shard}.db")
    max_streak = db.execute(
        "SELECT streak FROM streaks WHERE user_id=:user_id ORDER BY streak DESC LIMIT 1",
        [user_id],
    )
    # streaks for this user
    max_streak = max_streak.fetchone()
    if not max_streak:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No game stats found for this user",
        )
    curr_streak = db.execute(
        "SELECT streak FROM streaks WHERE user_id = ? ORDER BY ending DESC LIMIT 1",
        [user_id],
    )
    curr_streak = curr_streak.fetchone()
    # num games
    games_played = db.execute(
        "SELECT COUNT(*) FROM games WHERE user_id = ? LIMIT 1", [user_id]
    )
    games_played = games_played.fetchone()
    # num wins and losses
    wins = db.execute("SELECT wins FROM wins WHERE user_id = ? LIMIT 1", [user_id])
    wins = wins.fetchone()
    losses = games_played[0] - wins[0]
    # count of guesses in each win, or count of fails
    guesses = db.execute(
        "SELECT guesses, COUNT(guesses) FROM games WHERE user_id = ? AND won = TRUE GROUP BY guesses",
        [user_id],
    )
    guesses_query = guesses.fetchall()
    guesses = {}
    for i in range(len(guesses_query)):
        num_guesses = guesses_query[i][1]
        key = guesses_query[i][0]
        entry = {key: num_guesses}
        guesses.update(entry)
    guesses.update({"failed": losses})
    # average guesses for wins
    sum = 0
    guess_keys = list(guesses.keys())
    guess_values = list(guesses.values())
    for i in range(len(guess_keys) - 1):
        sum += guess_keys[i] * guess_values[i]
    avg_guesses = sum / wins[0]

    avg_wins = wins[0] / games_played[0]

    return {
        "currentStreak": curr_streak[0],
        "maxStreak": max_streak[0],
        "guesses": guesses,
        "winPercentage": avg_wins,
        "gamesPlayed": games_played[0],
        "gamesWon": wins[0],
        "averageGuesses": avg_guesses,
    }


@app.post("/users/", status_code=status.HTTP_201_CREATED)
def create_game_stats(game: Game, response: Response):
    g = dict(game)
    user = g.get("user_id")
    shard = getShardId(user)
    db = sqlite3.connect(f"{settings.database_dir}stats{shard}.db")
    try:
        cur = db.execute(
            """
            INSERT INTO games(user_id, game_id, finished, guesses, won)
            VALUES(:user_id, :game_id, :finished, :guesses, :won)
            """,
            g,
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return g


@app.get("/top10/streaks/all")
def top10_streaks_all_time():
    top10streaks = r.zrevrange(name="streaks", start=0, end=9, withscores=True)
    result = json.dumps(top10streaks)
    top10 = json.loads(result)
    return top10


@app.get("/top10/wins")
def top10_wins():
    top10wins = r.zrevrange(name="wins", start=0, end=9, withscores=True)
    result = json.dumps(top10wins)
    top10 = json.loads(result)
    return top10
