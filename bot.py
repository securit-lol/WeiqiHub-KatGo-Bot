import random
import subprocess
import sys
import time

import pyautogui

pyautogui.FAILSAFE = False

KATAGO_PATH = r"C:\Users\koval\Desktop\KataGo\katago.exe"
MODEL_PATH = r"C:\Users\koval\Desktop\KataGo\kata1-b28c512nbt-s13255194368-d5935380940.bin.gz"

ENABLE_CALIBRATION = False

# Pixels for the A19 and T1 intersections
TOP_LEFT_X = 78
TOP_LEFT_Y = 109
BOTTOM_RIGHT_X = 881
BOTTOM_RIGHT_Y = 912

# Delay before a move, in seconds
MIN_THINK_TIME = 0.5
MAX_THINK_TIME = 2.0

BOARD_SIZE = 19
COLUMNS = "ABCDEFGHJKLMNOPQRST"
STEP_X = (BOTTOM_RIGHT_X - TOP_LEFT_X) / (BOARD_SIZE - 1)
STEP_Y = (BOTTOM_RIGHT_Y - TOP_LEFT_Y) / (BOARD_SIZE - 1)

BLACK_MAX_BRIGHTNESS = 90
WHITE_MIN_BRIGHTNESS = 165
POLL_INTERVAL = 0.2
CONFIRMATIONS = 2

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


def calibrate():
    print("\nStar-point calibration")
    time.sleep(3)
    for name in ("D16", "Q16", "Q4", "D4"):
        x, y = to_pixels(*gtp_to_cell(name))
        pyautogui.moveTo(x, y, duration=0.5)
        if input(f"Is the cursor on point {name}? (y/n): ").strip().lower() != "y":
            sys.exit()
    pyautogui.moveTo(0, 0)


def choose_level():
    print("\nDifficulty:")
    for key, (description, _) in LEVELS.items():
        print(f"{key} - {description}")
    choice = input("Selection (1-5): ").strip()
    return LEVELS.get(choice, LEVELS["5"])[1]


class Engine:
    def __init__(self, overrides):
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        self.process = subprocess.Popen(
            [KATAGO_PATH, "gtp", "-model", MODEL_PATH, "-override-config", overrides],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, **kwargs,
        )
        self.send("name")

    def send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        lines = []
        for line in self.process.stdout:
            if line == "\n":
                break
            lines.append(line)
        return "".join(lines).strip()

    def genmove(self, color):
        started = time.time()
        reply = self.send(f"genmove {color}")
        return reply.split(" ")[1], time.time() - started

    def new_game(self):
        self.send("clear_board")
        self.send(f"boardsize {BOARD_SIZE}")
        self.send("time_settings 300 30 3")


def empty_board():
    return {(c, r): "empty" for c in range(BOARD_SIZE) for r in range(BOARD_SIZE)}


def scan_board():
    # Detect stones from the brightness of four points around each intersection
    img = pyautogui.screenshot()
    offset = int(STEP_X * 0.25)
    state = {}
    for col in range(BOARD_SIZE):
        for row in range(BOARD_SIZE):
            x, y = to_pixels(col, row)
            corners = [(x + dx, y + dy) for dx in (-offset, offset) for dy in (-offset, offset)]
            brightness = sum(sum(img.getpixel(p)) / 3 for p in corners) / 4
            if brightness < BLACK_MAX_BRIGHTNESS:
                state[(col, row)] = "b"
            elif brightness > WHITE_MIN_BRIGHTNESS:
                state[(col, row)] = "w"
            else:
                state[(col, row)] = "empty"
    return state


def wait_for_opponent(color, board):
    print(f"Waiting for the opponent's move ({color})... Ctrl+C resets the game")
    candidate = None
    matches = 0

    while True:
        time.sleep(POLL_INTERVAL)
        scanned = scan_board()
        added = []

        for pos, value in scanned.items():
            if board[pos] != "empty" and value == "empty":
                board[pos] = "empty"
            elif value == color and board[pos] != color:
                added.append(pos)

        if not added:
            candidate, matches = None, 0
            continue

        if added[0] == candidate:
            matches += 1
        else:
            candidate, matches = added[0], 1

        if matches >= CONFIRMATIONS:
            return cell_to_gtp(*candidate), scanned


def bot_move(engine, color, board):
    move, think_time = engine.genmove(color)

    if move.lower() == "resign":
        print("The bot resigned")
        return False, board

    if move.lower() == "pass":
        print("The bot passes, click pass in the client yourself")
        return True, board

    pause = random.uniform(MIN_THINK_TIME, MAX_THINK_TIME) - think_time
    if pause > 0:
        print(f"KataGo thought for {think_time:.1f} s, waiting another {pause:.1f} s")
        time.sleep(pause)
    else:
        print(f"KataGo thought for {think_time:.1f} s")

    print(f"Bot move: {move}")
    board = scan_board()
    col, row = gtp_to_cell(move)
    board[(col, row)] = color
    pyautogui.click(*to_pixels(col, row))
    pyautogui.moveTo(0, 0)
    return True, board


def play_game(engine, color):
    opponent = "w" if color == "b" else "b"
    engine.new_game()

    print("\nGame started, switch to the WeiqiHub window. Ctrl+C resets the game")
    time.sleep(2)
    pyautogui.moveTo(0, 0)
    time.sleep(1)

    board = empty_board()
    bot_to_move = color == "b"

    while True:
        if bot_to_move:
            playing, board = bot_move(engine, color, board)
            if not playing:
                return
        else:
            move, board = wait_for_opponent(opponent, board)
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
            pyautogui.moveTo(0, 0)
            time.sleep(1)


if __name__ == "__main__":
    main()
