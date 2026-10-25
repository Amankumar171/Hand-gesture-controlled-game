# Hand Gesture Controlled Soccer

A small webcam soccer game built with Python, OpenCV, and MediaPipe Hands. Move
your hand to steer the player, then pinch or make a quick hand swipe while the
player's boot is near the ball to kick. Score in either goal.

## Requirements

- Python 3.9–3.12
- A webcam

## Setup

Create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Show one hand to the camera. Move your palm to steer the player and bring the
highlighted boot close to the ball. Pinch your thumb and index finger together,
or make a quick swipe, to shoot toward the goal on the side opposite the player.
The score and current target are shown on screen. Press **Q** or **Esc** to quit.

If the webcam does not open, check that another application is not using it and
that camera access is enabled for Python. If a camera disconnects while playing,
the game displays a camera error and retries the connection.

## Test

Run the gameplay logic tests with:

```powershell
python -m unittest discover -s tests -v
```
