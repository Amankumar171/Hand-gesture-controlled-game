import unittest

from main import (
    BALL_RADIUS,
    HEIGHT,
    WIDTH,
    GameState,
    advance_ball,
    attempt_kick,
    foot_contacts_ball,
    map_hand_to_player,
    reset_ball,
    smooth_position,
    target_goal_x,
)


class GameLogicTests(unittest.TestCase):
    def test_hand_position_maps_to_field_and_smooths(self):
        self.assertEqual(map_hand_to_player(0.5, 0.5), (480.0, 320.0))
        x, y = smooth_position(100.0, 100.0, 500.0, 300.0, 0.05)
        self.assertGreater(x, 100.0)
        self.assertLess(x, 500.0)
        self.assertGreater(y, 100.0)
        self.assertLess(y, 300.0)

    def test_foot_collision_allows_contact_without_exact_center_alignment(self):
        state = GameState(player_x=300, player_y=300, ball_x=360, ball_y=300)
        self.assertTrue(foot_contacts_ball(state, target_goal_x(state)))

    def test_ball_outside_foot_reach_cannot_be_kicked(self):
        state = GameState(player_x=150, player_y=100, ball_x=480, ball_y=320)
        self.assertFalse(foot_contacts_ball(state, target_goal_x(state)))
        self.assertFalse(attempt_kick(state, 1.0, pinched=True))

    def test_pinch_held_until_contact_kicks_toward_right_goal(self):
        state = GameState(player_x=300, player_y=320, ball_x=360, ball_y=320)
        self.assertTrue(attempt_kick(state, 1.0, pinched=True))
        self.assertGreater(state.ball_vx, 0)
        self.assertEqual(state.ball_vy, 0)
        self.assertFalse(attempt_kick(state, 1.1, pinched=True))

    def test_swipe_kicks_toward_left_goal(self):
        state = GameState(player_x=600, player_y=320, ball_x=540, ball_y=320)
        self.assertEqual(target_goal_x(state), 0)
        self.assertTrue(attempt_kick(state, 1.0, swinging=True))
        self.assertLess(state.ball_vx, 0)

    def test_goal_scoring_and_reset_work_for_both_sides(self):
        for side, x, velocity in (
            ("right", WIDTH - BALL_RADIUS + 1, 100),
            ("left", BALL_RADIUS - 1, -100),
        ):
            with self.subTest(side=side):
                state = GameState(
                    ball_x=x,
                    ball_y=HEIGHT / 2,
                    ball_vx=velocity,
                )
                self.assertEqual(advance_ball(state, 0.01), side)
                self.assertEqual(state.score, 1)
                self.assertEqual(state.ball_x, WIDTH * 0.48)
                self.assertEqual(state.ball_vx, 0)

    def test_missed_goal_bounces_and_reset_clears_velocity(self):
        state = GameState(
            ball_x=WIDTH - BALL_RADIUS + 1,
            ball_y=100,
            ball_vx=100,
        )
        self.assertIsNone(advance_ball(state, 0.01))
        self.assertLess(state.ball_vx, 0)
        reset_ball(state)
        self.assertEqual(state.ball_y, HEIGHT / 2)
        self.assertEqual((state.ball_vx, state.ball_vy), (0, 0))

    def test_ball_crossing_outside_goal_mouth_does_not_score(self):
        state = GameState(
            ball_x=WIDTH - BALL_RADIUS + 1,
            ball_y=100,
            ball_vx=100,
        )
        self.assertIsNone(advance_ball(state, 0.01))
        self.assertEqual(state.score, 0)


if __name__ == "__main__":
    unittest.main()
