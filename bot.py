import random
import subprocess
import sys
import time
from itertools import takewhile

import pyautogui

pyautogui.FAILSAFE = False

KATAGO_PATH = r"C:\Users\koval\Desktop\KataGo\katago.exe"
MODEL_PATH = r"C:\Users\koval\Desktop\KataGo\kata1-b28c512nbt-s13255194368-d5935380940.bin.gz"

ENABLE_CALIBRATION = False

# Pixels for the A19 and T1 intersections
TOP_LEFT_X, TOP_LEFT_Y = 78, 109
BOTTOM_RIGHT_X, BOTTOM_RIGHT_Y = 881, 912

# Delay before a move, in seconds
MIN_THINK_TIME = 0.5
MAX_THINK_TIME = 2.0

BOARD_SIZE = 19
COLUMNS = "ABCDEFGHJKLMNOPQRST"
STEP_X = (BOTTOM_RIGHT_X - TOP_LEFT_X) / (BOARD_SIZE - 1)
STEP_Y = (BOTTOM_RIGHT_Y - TOP_LEFT_Y) / (BOARD_SIZE - 1)
POINTS = [(c, r) for c in range(BOARD_SIZE) for r in range(BOARD_SIZE)]

BLACK_MAX_BRIGHTNESS = 90
WHITE_MIN_BRIGHTNESS = 165
POLL_INTERVAL = 0.2
CONFIRMATIONS = 2

MAX_RETRIES = 5

LEVELS = {
    "1": ("Very weak, almost random moves", "maxVisits=1,chosenMoveTemperature=1.0"),
    "2": ("Beginner, frequent mistakes", "maxVisits=5,chosenMoveTemperature=0.6"),
    "3": ("Amateur", "maxVisits=25,chosenMoveTemperature=0.2"),
    "4": ("Dan level", "maxVisits=150,chosenMoveTemperature=0.0"),
    "5": ("Maximum thinking level", "maxVisits=1000,chosenMoveTemperature=0.0"),
}


def to_pixels(col, row):
    return int(TOP_LEFT_X + col * STEP_X), int(TOP_LEFT_Y + row * STEP_Y)


def gtp_to_cell(move):
    return COLUMNS.index(move[0].upper()), BOARD_SIZE - int(move[1:])


def cell_to_gtp(col, row):
    return f"{COLUMNS[col]}{BOARD_SIZE - row}"


def park_mouse():
    pyautogui.moveTo(0, 0)


def calibrate():
    print("\nStar-point calibration")
    time.sleep(3)
    for name in ("D16", "Q16", "Q4", "D4"):
        pyautogui.moveTo(*to_pixels(*gtp_to_cell(name)), duration=0.5)
        if input(f"Is the cursor on point {name}? (y/n): ").strip().lower() != "y":
            sys.exit()
    park_mouse()


def choose_level():
    print("\nDifficulty:")
    for key, (description, _) in LEVELS.items():
        print(f"{key} - {description}")
    choice = input("Selection (1-5): ").strip()
    return LEVELS.get(choice, LEVELS["5"])[1]


class Engine:
    def __init__(self, overrides):
        self.process = subprocess.Popen(
            [KATAGO_PATH, "gtp", "-model", MODEL_PATH, "-override-config", overrides],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        self.send("name")

    def send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        return "".join(takewhile(lambda line: line != "\n", self.process.stdout)).strip()

    def genmove(self, color):
        started = time.time()
        reply = self.send(f"genmove {color}")
        parts = reply.split(" ")
        if len(parts) < 2:
            sys.exit(f"\n[ERROR] KataGo returned an invalid response: '{reply}'\n"
                     "The engine either crashed or is not ready. Exiting.")
        return parts[1], time.time() - started

    def new_game(self):
        self.send("clear_board")
        self.send(f"boardsize {BOARD_SIZE}")
        self.send("time_settings 300 30 3")


def empty_board():
    return {pos: "empty" for pos in POINTS}


def classify(brightness):
    if brightness < BLACK_MAX_BRIGHTNESS:
        return "b"
    if brightness > WHITE_MIN_BRIGHTNESS:
        return "w"
    return "empty"


def scan_board():
    # Detect stones from the brightness of four points around each intersection
    img = pyautogui.screenshot()
    offset = int(STEP_X * 0.25)
    state = {}
    for pos in POINTS:
        x, y = to_pixels(*pos)
        corners = [(x + dx, y + dy) for dx in (-offset, offset) for dy in (-offset, offset)]
        state[pos] = classify(sum(sum(img.getpixel(p)) for p in corners) / 12)
    return state


def update_board_from_scan(board, scanned):
    missed = {}
    for pos, value in scanned.items():
        if board[pos] != "empty" and value == "empty":
            board[pos] = "empty"
        elif board[pos] == "empty" and value != "empty":
            missed[pos] = value
    return missed


def sync_stones(engine, board, stones):
    for pos, color in stones.items():
        board[pos] = color
        engine.send(f"play {color} {cell_to_gtp(*pos)}")
        print(f"Synced stone: {color} {cell_to_gtp(*pos)}")


def sync_existing_stones(engine, board):
    scanned = scan_board()
    stones = {pos: v for pos, v in scanned.items() if v != "empty"}
    sync_stones(engine, board, dict(sorted(stones.items(), key=lambda s: s[1])))
    values = list(stones.values())
    return "b" if values.count("b") <= values.count("w") else "w"


def wait_for_opponent(color, board):
    print(f"Waiting for the opponent's move ({color})... Ctrl+C resets the game")
    candidate, matches = None, 0
    prev_scan = dict(board)

    while True:
        time.sleep(POLL_INTERVAL)
        scanned = scan_board()
        update_board_from_scan(board, scanned)

        new_this_tick = [
            pos for pos, value in scanned.items()
            if value == color and board[pos] != color and prev_scan[pos] != color
        ]
        if len(new_this_tick) == 1:
            candidate, matches = new_this_tick[0], 1
        elif candidate and scanned[candidate] == color:
            matches += 1
        elif candidate:
            candidate, matches = None, 0
        prev_scan = scanned

        if candidate and matches >= CONFIRMATIONS:
            board.update({pos: value for pos, value in scanned.items() if value != "empty"})
            return cell_to_gtp(*candidate)


def request_free_move(engine, color, board):
    total_think = 0.0
    for _ in range(MAX_RETRIES):
        move, think_time = engine.genmove(color)
        total_think += think_time
        if move.lower() in ("resign", "pass"):
            return move, total_think

        cell = gtp_to_cell(move)
        scanned = scan_board()
        missed = update_board_from_scan(board, scanned)
        if scanned[cell] == "empty":
            return move, total_think

        print(f"Bot wanted {move}, but that point is occupied. Syncing the missed stone(s) and asking for another move")
        reply = engine.send("undo")
        if not reply.startswith("="):
            print(f"[WARNING] undo failed: '{reply}'")
        missed.setdefault(cell, scanned[cell])
        sync_stones(engine, board, missed)
    return None, total_think


def bot_move(engine, color, board):
    move, think_time = request_free_move(engine, color, board)

    if move is None:
        print("[ERROR] The bot could not find a free point to play. Stopping this game")
        return False
    if move.lower() == "resign":
        print("The bot resigned")
        return False
    if move.lower() == "pass":
        print("The bot passes, click pass in the client yourself")
        return True

    message = f"KataGo thought for {think_time:.1f} s"
    pause = random.uniform(MIN_THINK_TIME, MAX_THINK_TIME) - think_time
    if pause > 0:
        print(f"{message}, waiting another {pause:.1f} s")
        time.sleep(pause)
    else:
        print(message)

    print(f"Bot move: {move}")
    cell = gtp_to_cell(move)
    board[cell] = color
    pyautogui.click(*to_pixels(*cell))
    park_mouse()
    return True


def play_game(engine, color):
    opponent = "w" if color == "b" else "b"
    engine.new_game()

    print("\nGame started, switch to the WeiqiHub window. Ctrl+C resets the game")
    time.sleep(2)
    park_mouse()
    time.sleep(1)

    board = empty_board()
    bot_to_move = sync_existing_stones(engine, board) == color

    while True:
        if bot_to_move:
            if not bot_move(engine, color, board):
                return
        else:
            move = wait_for_opponent(opponent, board)
            print(f"Opponent move: {move}")
            engine.send(f"play {opponent} {move}")
        bot_to_move = not bot_to_move


def main():
    if ENABLE_CALIBRATION:
        calibrate()

    overrides = choose_level()
    print("\nLoading KataGo...")
    engine = Engine(overrides)
    print("Engine ready")

    while True:
        try:
            color = input("\nWhich color should the bot play? (b, w, or q to exit): ").strip().lower()
            if color == "q":
                engine.send("quit")
                return
            if color not in ("b", "w"):
                print("Enter b or w")
                continue
            play_game(engine, color)
        except KeyboardInterrupt:
            print("\nGame interrupted, board reset")
            park_mouse()
            time.sleep(1)


if __name__ == "__main__":
    main()
