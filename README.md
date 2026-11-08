# WeiqiHub-KatGo-Bot

Bot for playing Go in the WeiqiHub client. It watches the screen, detects the opponent's moves, calculates a response in KataGo, and clicks the required point. It was designed for WeiqiHub, but should also work with another client after adjusting the board coordinates

## Requirements

- Python 3.12
- `katago.exe`. For NVIDIA cards, use a build with `cuda` or `tensorrt` in its name
- A `.bin.gz` weights file, such as `kata1-b28...bin.gz`. Do not unpack it

Put `katago.exe`, the weights file, and `bot.py` in one folder, for example `C:\GoBot`

## Installing libraries

The script needs libraries for mouse control and screenshots. Open Command Prompt (`Win + R`, then `cmd`) and run:

```cmd
pip install pyautogui Pillow pyscreeze
```

## Configuration

The configuration block is at the beginning of `bot.py`. Open the file in Notepad or any editor and adjust the parameters:

| Parameter | Value |
| --- | --- |
| `KATAGO_PATH` | Full path to `katago.exe`, for example `r"C:\GoBot\katago.exe"` |
| `MODEL_PATH` | Full path to the weights file, for example `r"C:\GoBot\kata1-b28...bin.gz"` |
| `ENABLE_CALIBRATION` | `True`: before starting, the bot moves the mouse over points so you can check calibration. `False`: skip the check |
| `MIN_THINK_TIME`, `MAX_THINK_TIME` | Bounds for the delay before a move, in seconds. The bot chooses a random value from this range so moves do not look mechanical |

### Board coordinates

The script needs to know which screen pixels contain the board

1. Open WeiqiHub with an empty board in full-screen mode and do not move the window afterward
2. Press `Print Screen`
3. Paste the screenshot into Paint (`Ctrl + V`)
4. Move the cursor to the top-left intersection, point A19. Its coordinates will appear in the lower-left corner of Paint, for example `70, 109`
5. Find the bottom-right intersection, point T1, in the same way. Suppose its coordinates are `889, 928`
6. Enter the values in the configuration:

```python
TOP_LEFT_X = 78        # X coordinate of A19
TOP_LEFT_Y = 109       # Y coordinate of A19
BOTTOM_RIGHT_X = 881   # X coordinate of T1
BOTTOM_RIGHT_Y = 919   # Y coordinate of T1
```

Save the file

## Running

1. In Command Prompt, go to the bot folder: `cd C:\GoBot`
2. Run the script:

   ```cmd
   python bot.py
   ```

3. Enter a difficulty level from 1 (weakest) to 5 (strongest)
4. Wait for the message `Engine ready`. The neural network takes a few seconds to load into video memory
5. Enter `b` if you are playing black, or `w` if you are playing white
6. Switch to the WeiqiHub window. The cursor will move to the top-left corner of the screen so it does not obstruct the board

The bot will then detect the opponent's move and respond with a click

## Controls

- `Ctrl + C` in the console: reset the game. The script stays open, clears the internal board, and asks for the color again. Useful when the game has ended or the opponent has resigned
- `q` in the color selection menu: exit the program

## Limitations

- While a game is in progress, do not open anything over the board: windows, notifications, or menus. The bot checks the screen five times per second and may mistake a dark browser window for an opponent's stone
- The bot detects when stones disappear from the board, meaning they were captured. It may occasionally make a mistake if the client has a slow capture animation
- If the bot decides to pass, it will write this in the console but will not click the pass button. Click it yourself in the client
