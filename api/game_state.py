from fastapi import FastAPI, Depends, Response, HTTPException, status, Body
from pydantic import BaseModel, BaseSettings
import redis
import json
from typing import Optional


class Settings(BaseSettings):
    logging_config: str = ""
    openapi_url: str = ""

    class Config:
        env_file = "game_state.env"


settings = Settings()
app = FastAPI(root_path="/api/state", openapi_url=settings.openapi_url)
# start connection to redis server
r = redis.Redis(host="localhost", port=6379, db=0)

# defines a new game in request body
class Game(BaseModel):
    user_id: str
    game_id: int


# get game status
@app.get("/state/")
def get_game(user_id: str, game_id: int):
    res = r.hmget(user_id, game_id)
    # if game is already played return error
    if res[0] == None:
        raise HTTPException(status_code=400, detail="User has not started this game.")
    # gets game object from redis
    game_information = json.loads(res[0])
    return game_information


# start a new game
@app.post("/state/")
def new_game(game: Game):
    res = r.hmget(game.user_id, game.game_id)
    # create new game in json format so it can be set in redis
    new_game = {
        "status": "new",
        "user_id": game.user_id,
        "game_id": game.game_id,
        "guesses_left": 6,
        "words_guessed": [],
    }
    mapping = json.dumps(new_game)
    # set the new game object with user_id as the key
    r.hmset(
        game.user_id,
        {game.game_id: mapping},
    )
    return new_game


@app.post("/state/update")
def add_guess(guess: str, game: Game):
    res = r.hmget(game.user_id, game.game_id)
    # if game is already played return error
    if res[0] == None:
        raise HTTPException(status_code=400, detail="Failed to add guess")
    # gets game object from redis
    game_information = json.loads(res[0])
    if game_information["guesses_left"] == 0:
        raise HTTPException(status_code=400, detail="User has no guesses left")
    # modifies game_information
    game_information["status"] = "in-progress"
    game_information["guesses_left"] -= 1
    game_information["words_guessed"].append(guess)
    # save changes
    mapping = json.dumps(game_information)
    r.hmset(
        game.user_id,
        {game.game_id: mapping},
    )
    return game_information
