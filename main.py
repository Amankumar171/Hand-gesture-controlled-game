import math
import sys
import time
from dataclasses import dataclass


WIDTH = 960
HEIGHT = 640
GOAL_TOP = 220
GOAL_BOTTOM = 420
GOAL_CENTER_Y = (GOAL_TOP + GOAL_BOTTOM) / 2
BALL_RADIUS = 18
PLAYER_RADIUS = 34
FOOT_RADIUS = 11
FOOT_OFFSET = PLAYER_RADIUS * 0.72
KICK_CONTACT_MARGIN = 12
KICK_COOLDOWN = 0.45
KICK_SPEED = 780.0
SWIPE_SPEED = 700.0


@dataclass
class GameState:
    player_x: float = 210.0
    player_y: float = HEIGHT / 2
    ball_x: float = WIDTH / 2
    ball_y: float = HEIGHT / 2
    ball_vx: float = 0.0
    ball_vy: float = 0.0
    score: int = 0
    last_kick_time: float = -math.inf


def map_hand_to_player(hand_x, hand_y):
    return (
        55 + hand_x * (WIDTH - 110),
        55 + hand_y * (HEIGHT - 110),
    )


def smooth_position(current_x, current_y, target_x, target_y, delta_time):
    alpha = 1.0 - math.exp(-delta_time / 0.10)
    return (
        current_x + (target_x - current_x) * alpha,
        current_y + (target_y - current_y) * alpha,
    )


def target_goal_x(state):
    return WIDTH - 1 if state.player_x <= state.ball_x else 0


def foot_position(state, goal_x):
    facing = 1 if goal_x > state.player_x else -1
    return state.player_x + facing * FOOT_OFFSET, state.player_y


def foot_contacts_ball(state, goal_x):
    foot_x, foot_y = foot_position(state, goal_x)
    contact_distance = BALL_RADIUS + FOOT_RADIUS + KICK_CONTACT_MARGIN
    return math.hypot(state.ball_x - foot_x, state.ball_y - foot_y) <= contact_distance


def attempt_kick(state, now, pinched=False, swinging=False):
    if not (pinched or swinging) or now - state.last_kick_time < KICK_COOLDOWN:
        return False

    goal_x = target_goal_x(state)
    if not foot_contacts_ball(state, goal_x):
        return False

    direction_x = goal_x - state.ball_x
    direction_y = GOAL_CENTER_Y - state.ball_y
    direction_length = max(math.hypot(direction_x, direction_y), 1.0)
    state.ball_vx = KICK_SPEED * direction_x / direction_length
    state.ball_vy = KICK_SPEED * direction_y / direction_length
    state.last_kick_time = now
    return True


def reset_ball(state):
    state.ball_x = WIDTH * 0.48
    state.ball_y = HEIGHT / 2
    state.ball_vx = 0.0
    state.ball_vy = 0.0


def advance_ball(state, delta_time):
    state.ball_x += state.ball_vx * delta_time
    state.ball_y += state.ball_vy * delta_time
    drag = math.exp(-0.45 * delta_time)
    state.ball_vx *= drag
    state.ball_vy *= drag

    if state.ball_y < BALL_RADIUS:
        state.ball_y = BALL_RADIUS
        state.ball_vy = abs(state.ball_vy) * 0.72
    elif state.ball_y > HEIGHT - BALL_RADIUS:
        state.ball_y = HEIGHT - BALL_RADIUS
        state.ball_vy = -abs(state.ball_vy) * 0.72

    if state.ball_x <= BALL_RADIUS:
        if GOAL_TOP + BALL_RADIUS <= state.ball_y <= GOAL_BOTTOM - BALL_RADIUS:
            state.score += 1
            reset_ball(state)
            return "left"
        state.ball_x = BALL_RADIUS
        state.ball_vx = abs(state.ball_vx) * 0.72
    elif state.ball_x >= WIDTH - BALL_RADIUS:
        if GOAL_TOP + BALL_RADIUS <= state.ball_y <= GOAL_BOTTOM - BALL_RADIUS:
            state.score += 1
            reset_ball(state)
            return "right"
        state.ball_x = WIDTH - BALL_RADIUS
        state.ball_vx = -abs(state.ball_vx) * 0.72
    return None


def draw_text(cv2, frame, text, position, scale=0.7, color=(255, 255, 255), thickness=2):
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_field(cv2, frame):
    frame[:] = (42, 125, 48)
    line_color = (220, 235, 220)
    cv2.rectangle(frame, (0, 0), (WIDTH - 1, HEIGHT - 1), line_color, 4)
    cv2.line(frame, (WIDTH // 2, 0), (WIDTH // 2, HEIGHT), line_color, 2)
    cv2.circle(frame, (WIDTH // 2, HEIGHT // 2), 72, line_color, 2)
    cv2.rectangle(frame, (0, GOAL_TOP), (90, GOAL_BOTTOM), line_color, 2)
    cv2.rectangle(frame, (WIDTH - 90, GOAL_TOP), (WIDTH - 1, GOAL_BOTTOM), (240, 240, 240), 3)
    draw_text(cv2, frame, "GOAL", (14, GOAL_TOP - 10), 0.45)
    draw_text(cv2, frame, "GOAL", (WIDTH - 83, GOAL_TOP - 10), 0.45)


def main():
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
    except ImportError as error:
        print(
            f"Missing game dependency ({error.name}). Install the dependencies with: "
            "python -m pip install -r requirements.txt"
        )
        return 1

    camera = None
    hands = None
    try:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            print("Could not open the webcam. Check that it is connected and not in use.")
            return 1
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

        hands_api = mp.solutions.hands
        hands = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        drawing = mp.solutions.drawing_utils

        state = GameState()
        previous_time = time.monotonic()
        previous_player_position = (state.player_x, state.player_y)
        tracking_status = "SHOW ONE HAND TO CAMERA"
        message = ""
        message_until = 0.0
        next_camera_retry = 0.0

        while True:
            now = time.monotonic()
            delta_time = min(max(now - previous_time, 0.0), 0.05)
            previous_time = now
            ok, camera_frame = camera.read()
            landmarks = None
            hand_control_point = None
            pinched = False

            if ok and camera_frame is not None:
                camera_frame = cv2.flip(camera_frame, 1)
                camera_frame = cv2.resize(camera_frame, (WIDTH, HEIGHT))
                result = hands.process(cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB))
                if result.multi_hand_landmarks:
                    hand = result.multi_hand_landmarks[0]
                    handedness = result.multi_handedness
                    confidence = (
                        handedness[0].classification[0].score
                        if handedness and handedness[0].classification
                        else 1.0
                    )
                    if confidence >= 0.4:
                        landmarks = hand
                        hand_control_point = hand.landmark[9]
                        target_x, target_y = map_hand_to_player(
                            hand_control_point.x, hand_control_point.y
                        )
                        state.player_x, state.player_y = smooth_position(
                            state.player_x,
                            state.player_y,
                            target_x,
                            target_y,
                            delta_time,
                        )
                        thumb = hand.landmark[4]
                        index = hand.landmark[8]
                        pinched = math.hypot(thumb.x - index.x, thumb.y - index.y) < 0.065
                        tracking_status = "HAND TRACKING"
                    else:
                        tracking_status = "LOW TRACKING CONFIDENCE"
                else:
                    tracking_status = "SHOW ONE HAND TO CAMERA"
            else:
                tracking_status = "CAMERA ERROR - RETRYING"
                if now >= next_camera_retry:
                    camera.release()
                    camera = cv2.VideoCapture(0)
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                    next_camera_retry = now + 2.0

            player_speed = 0.0
            if delta_time > 0:
                player_speed = math.hypot(
                    state.player_x - previous_player_position[0],
                    state.player_y - previous_player_position[1],
                ) / delta_time
            previous_player_position = (state.player_x, state.player_y)
            kicked = attempt_kick(
                state,
                now,
                pinched=pinched,
                swinging=player_speed >= SWIPE_SPEED,
            )
            if kicked:
                message = "KICK!"
                message_until = now + 0.8

            scored_goal = advance_ball(state, delta_time)
            if scored_goal:
                message = f"GOAL - LEFT SIDE!" if scored_goal == "left" else "GOAL - RIGHT SIDE!"
                message_until = now + 1.5

            frame = camera_frame
            if frame is None or not ok:
                frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
            draw_field(cv2, frame)

            goal_x = target_goal_x(state)
            foot_x, foot_y = foot_position(state, goal_x)
            player_center = (int(state.player_x), int(state.player_y))
            cv2.circle(frame, player_center, PLAYER_RADIUS, (40, 80, 240), -1)
            cv2.circle(frame, player_center, PLAYER_RADIUS, (255, 255, 255), 2)
            cv2.line(
                frame,
                player_center,
                (int(foot_x), int(foot_y)),
                (20, 35, 120),
                5,
            )
            cv2.circle(frame, (int(foot_x), int(foot_y)), FOOT_RADIUS, (0, 190, 255), -1)
            cv2.circle(frame, (int(foot_x), int(foot_y)), FOOT_RADIUS, (255, 255, 255), 1)

            if landmarks is not None:
                control_x = int(hand_control_point.x * WIDTH)
                control_y = int(hand_control_point.y * HEIGHT)
                cv2.circle(frame, (control_x, control_y), 10, (255, 220, 0), -1)
                drawing.draw_landmarks(frame, landmarks, hands_api.HAND_CONNECTIONS)

            cv2.circle(frame, (int(state.ball_x), int(state.ball_y)), BALL_RADIUS, (245, 245, 245), -1)
            cv2.circle(frame, (int(state.ball_x), int(state.ball_y)), BALL_RADIUS, (30, 30, 30), 2)
            draw_text(cv2, frame, f"Goals: {state.score}", (22, 42), 0.9)
            target_name = "RIGHT" if goal_x > state.player_x else "LEFT"
            draw_text(cv2, frame, f"Target: {target_name} goal", (22, 76), 0.62)
            status_color = (
                (120, 255, 120)
                if tracking_status == "HAND TRACKING"
                else (100, 180, 255)
            )
            draw_text(cv2, frame, f"CAMERA: {'OK' if ok else 'ERROR'}", (22, 108), 0.52, status_color)
            draw_text(cv2, frame, f"TRACKING: {tracking_status}", (22, 134), 0.52, status_color)
            draw_text(cv2, frame, "Move hand to move | Pinch or quick swipe near the boot to kick", (18, HEIGHT - 42), 0.48)
            draw_text(cv2, frame, "Q or Esc: quit", (18, HEIGHT - 17), 0.48)
            if now < message_until:
                draw_text(cv2, frame, message, (WIDTH // 2 - 105, 48), 0.8, (255, 255, 180))

            cv2.imshow("Hand Gesture Controlled Soccer", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    except (cv2.error, RuntimeError) as error:
        print(f"The game encountered an error: {error}")
        return 1
    finally:
        if hands is not None:
            hands.close()
        if camera is not None:
            camera.release()
        if "cv2" in locals():
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
