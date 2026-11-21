import unittest

import numpy as np

from backend.services.pose_estimator_service import PoseEstimatorService


class FakeEyeCascade:
    def __init__(self, detections):
        self.detections = detections

    def empty(self):
        return False

    def detectMultiScale(self, *_args, **_kwargs):
        return self.detections


class PoseRollTests(unittest.TestCase):
    def setUp(self):
        self.service = PoseEstimatorService()
        self.frame = np.full((200, 200), 127, dtype=np.uint8)

    def test_roll_uses_eye_line_slope(self):
        self.service._eye_cascade = FakeEyeCascade([
            (20, 20, 20, 20),
            (80, 30, 20, 20),
        ])

        roll, landmarks = self.service._estimate_roll(
            self.frame,
            [20, 20, 160, 160],
        )

        self.assertAlmostEqual(roll, 9.46, places=1)
        self.assertEqual(len(landmarks), 2)

    def test_roll_is_null_without_two_reliable_eyes(self):
        self.service._eye_cascade = FakeEyeCascade([(35, 25, 20, 20)])

        roll, landmarks = self.service._estimate_roll(
            self.frame,
            [20, 20, 160, 160],
        )

        self.assertIsNone(roll)
        self.assertIsNone(landmarks)

    def test_payload_maps_roll_to_lateral_flexion(self):
        payload = self.service._build_detection_payload(
            {"box": [10, 20, 110, 120], "confidence": 0.95},
            tilt=5.0,
            pan=-8.0,
            roll=12.5,
            eye_landmarks=[{"x": 35, "y": 45}, {"x": 80, "y": 55}],
        )

        self.assertEqual(payload["cervical_angles"]["raw_roll"], 12.5)
        self.assertEqual(
            payload["assessment_angles"]["left_lateral_flexion_angle"],
            12.5,
        )
        self.assertEqual(
            payload["assessment_angles"]["right_lateral_flexion_angle"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
