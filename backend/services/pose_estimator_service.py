"""
Head-pose based cervical angle estimation service.

This service uses the trained RealHePoNet pose estimator bundled under
``backend/ml/model_weights/headpose`` and OpenCV DNN face detector artifacts in
the same folder. ``headpose_final/models`` is kept only as a legacy fallback for
older workspaces.
"""

import base64
import os
import sys
from math import atan2, degrees, radians, sin
from pathlib import Path
from threading import Lock

import cv2
import numpy as np


class PoseEstimatorService:
    """Lazy-loaded head pose estimator for image and camera-frame inference."""

    IN_SIZE = 64
    CONFIDENCE_THRESHOLD = 0.15

    IMG_MEAN = 0.408808
    IMG_STD = 0.237583
    TILT_MEAN = -0.041212
    TILT_STD = 0.323931
    PAN_MEAN = -0.000276
    PAN_STD = 0.540958
    RESCALE = 90.0

    def __init__(self):
        workspace_root = Path(__file__).resolve().parents[3]
        self.backend_root = Path(__file__).resolve().parents[1]
        self.headpose_root = workspace_root / "headpose_final"
        self.ssd_people_root = workspace_root / "ssd_people"
        self.models_dir = self.backend_root / "ml" / "model_weights" / "headpose"
        self.legacy_models_dir = self.headpose_root / "models"

        self.pose_weights_path = self._resolve_model_file("pose-estimator.h5")
        self.detector_prototxt_path = self._resolve_model_file("deploy.prototxt")
        self.detector_weights_path = self._resolve_model_file("res10_300x300_ssd_iter_140000.caffemodel")

        self._pose_model = None
        self._detector_net = None
        self._profile_cascade = None
        self._eye_cascade = None
        self._tf_graph = None
        self._tf_session = None
        self._keras_backend = None
        self._load_lock = Lock()
        self._predict_lock = Lock()
        self._landmark_lock = Lock()

    def model_status(self):
        """Return model source and availability information for diagnostics."""
        files_available = {
            "pose_weights": self.pose_weights_path.exists(),
            "detector_prototxt": self.detector_prototxt_path.exists(),
            "detector_weights": self.detector_weights_path.exists(),
            "backend_models_dir": self.models_dir.exists(),
            "ssd_people_checkout": self.ssd_people_root.exists(),
        }
        ready_for_inference = all(
            files_available[name]
            for name in ["pose_weights", "detector_prototxt", "detector_weights"]
        )
        return {
            "loaded": self._pose_model is not None and self._detector_net is not None,
            "ready_for_inference": ready_for_inference,
            "backend_models_dir": str(self.models_dir),
            "legacy_models_dir": str(self.legacy_models_dir),
            "headpose_root": str(self.headpose_root),
            "ssd_people_root": str(self.ssd_people_root),
            "pose_weights": str(self.pose_weights_path),
            "detector_prototxt": str(self.detector_prototxt_path),
            "detector_weights": str(self.detector_weights_path),
            "runtime": {
                "python_prefix": sys.prefix,
                "python_executable": sys.executable,
            },
            "capabilities": {
                "image_upload": True,
                "image_path": True,
                "camera_mjpeg_overlay": True,
                "camera_json_status_stream": True,
                "estimated_angles": ["tilt", "pan", "roll"],
                "model_angles": ["tilt", "pan"],
                "geometric_angles": ["roll"],
                "nullable_angles": ["roll"],
                "roll_source": "opencv_eye_line",
                "unsupported_angles": [],
                "health_status_basis": "current-frame max(abs(tilt), abs(pan), abs(roll when available))",
            },
            "limitations": [
                "当前 RealHePoNet 权重输出 tilt/pan；roll 由双眼中心连线几何估计。",
                "侧脸、遮挡或双眼识别不可靠时 roll 返回 null，不伪造为 0。",
                "实时健康状态基于当前帧姿态角，不等同于完整六方向活动度评估。",
                "TensorFlow 1.15 可在 CPU 上运行；缺少 CUDA 10/cuDNN 7 时不会注册 GPU。",
            ],
            "files_available": files_available,
        }

    def estimate_image_path(self, image_path, draw=True, confidence_threshold=None):
        """Estimate pose for an image file path."""
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"无法读取图片: {image_path}")
        return self.estimate_frame(frame, draw=draw, confidence_threshold=confidence_threshold)

    def estimate_image_bytes(self, image_bytes, draw=True, confidence_threshold=None):
        """Estimate pose for uploaded image bytes."""
        data = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("无法解析上传的图片")
        return self.estimate_frame(frame, draw=draw, confidence_threshold=confidence_threshold)

    def estimate_frame(self, frame, draw=True, confidence_threshold=None):
        """Estimate tilt, pan and eye-line roll for every detected head."""
        self._ensure_loaded()

        threshold = self.CONFIDENCE_THRESHOLD if confidence_threshold is None else confidence_threshold
        bboxes = self._detect_heads(frame, threshold)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        annotated = frame.copy() if draw else None

        detections = []
        for bbox in bboxes:
            crop = self._crop_head(gray, bbox["box"])
            if crop is None:
                continue

            tilt, pan = self._predict_pose(crop)
            roll, eye_landmarks = self._estimate_roll(gray, bbox["box"])
            detection = self._build_detection_payload(
                bbox,
                tilt,
                pan,
                roll=roll,
                eye_landmarks=eye_landmarks,
            )
            detections.append(detection)

            if annotated is not None:
                self._draw_detection(annotated, detection)

        primary = self._select_primary_detection(detections)
        response = {
            "frame": {
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
            },
            "detection_count": len(detections),
            "detections": detections,
            "primary_detection": primary,
            "summary": self._build_result_summary(primary, len(detections)),
            "model_status": self.model_status(),
        }

        if annotated is not None:
            response["annotated_frame"] = annotated

        return response

    def encode_annotated_image(self, annotated_frame):
        """Encode an annotated BGR frame as a data URL for JSON responses."""
        ok, buffer = cv2.imencode(".jpg", annotated_frame)
        if not ok:
            raise ValueError("标注图片编码失败")
        encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def to_json_payload(self, result):
        """Return an API-safe copy without raw image arrays."""
        return {key: value for key, value in result.items() if key != "annotated_frame"}

    def draw_no_detection(self, frame):
        """Draw a stable overlay for frames where no head is detected."""
        cv2.putText(
            frame,
            "No head detected",
            (20, 40),
            cv2.FONT_HERSHEY_DUPLEX,
            0.9,
            (0, 0, 255),
            2,
            lineType=cv2.LINE_AA,
        )
        return frame

    def _ensure_loaded(self):
        with self._load_lock:
            if self._pose_model is not None and self._detector_net is not None:
                return

            missing = [
                str(path)
                for path in [
                    self.pose_weights_path,
                    self.detector_prototxt_path,
                    self.detector_weights_path,
                ]
                if not path.exists()
            ]
            if missing:
                raise FileNotFoundError("缺少模型权重文件: " + ", ".join(missing))

            if str(self.backend_root) not in sys.path:
                sys.path.insert(0, str(self.backend_root))

            import tensorflow as tf
            from tensorflow.keras import backend as keras_backend
            from ml.headpose_architectures import mpatacchiola_generic

            model = mpatacchiola_generic(
                self.IN_SIZE,
                num_conv_blocks=6,
                num_filters_start=32,
                num_dense_layers=1,
                dense_layer_size=512,
            )
            model.load_weights(str(self.pose_weights_path))

            self._pose_model = model
            self._tf_graph = tf.get_default_graph() if hasattr(tf, "get_default_graph") else None
            self._tf_session = (
                keras_backend.get_session()
                if hasattr(keras_backend, "get_session")
                else None
            )
            self._keras_backend = keras_backend
            self._detector_net = cv2.dnn.readNetFromCaffe(
                str(self.detector_prototxt_path),
                str(self.detector_weights_path),
            )
            self._profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_profileface.xml"
            )
            self._eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml"
            )

    def _detect_heads(self, frame, confidence_threshold):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123], False, False)
        self._detector_net.setInput(blob)
        detections = self._detector_net.forward()

        boxes = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence <= confidence_threshold:
                continue

            xmin = int(detections[0, 0, i, 3] * w)
            ymin = int(detections[0, 0, i, 4] * h)
            xmax = int(detections[0, 0, i, 5] * w)
            ymax = int(detections[0, 0, i, 6] * h)
            box_h = ymax - ymin
            ymin = max(0, ymin - int(box_h * 0.6))
            boxes.append({"box": self._clip_box([xmin, ymin, xmax, ymax], w, h), "confidence": confidence})

        boxes = self._dedupe_boxes(boxes)

        # The profile cascade is a fallback. Running both detectors on the same
        # frame can produce two boxes for one head and wastes time in webcam mode.
        if not boxes and self._profile_cascade is not None and not self._profile_cascade.empty():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            profiles = self._profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=4,
                minSize=(40, 40),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            for (x, y, bw, bh) in profiles:
                y_exp = max(0, y - int(bh * 0.6))
                boxes.append({
                    "box": self._clip_box([x, y_exp, x + bw, y + bh], w, h),
                    "confidence": None,
                })

        return self._dedupe_boxes(boxes)

    def _resolve_model_file(self, filename):
        backend_path = self.models_dir / filename
        if backend_path.exists():
            return backend_path
        return self.legacy_models_dir / filename

    def _crop_head(self, gray, box):
        h, w = gray.shape[:2]
        xmin, ymin, xmax, ymax = box
        bw = xmax - xmin
        bh = ymax - ymin
        if bw <= 0 or bh <= 0:
            return None

        side = min(bw, bh)
        cx = (xmin + xmax) // 2
        cy = (ymin + ymax) // 2
        half = side // 2

        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w - 1, cx + half)
        y2 = min(h - 1, cy + half)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        return cv2.resize(crop, (self.IN_SIZE, self.IN_SIZE), interpolation=cv2.INTER_LINEAR)

    def _predict_pose(self, crop):
        norm = ((crop / 255.0) - self.IMG_MEAN) / self.IMG_STD
        norm = np.reshape(norm, (1, norm.shape[0], norm.shape[1], 1))
        with self._predict_lock:
            if self._tf_graph is not None:
                with self._tf_graph.as_default():
                    if self._tf_session is not None and hasattr(self._keras_backend, "set_session"):
                        self._keras_backend.set_session(self._tf_session)
                    pred = self._pose_model.predict(norm, verbose=0)
            else:
                pred = self._pose_model.predict(norm, verbose=0)

        tilt = (pred[0, 0] * self.TILT_STD + self.TILT_MEAN) * self.RESCALE
        pan = (pred[0, 1] * self.PAN_STD + self.PAN_MEAN) * self.RESCALE
        return float(tilt), float(pan)

    def _estimate_roll(self, gray, box):
        """Estimate head roll from a reliable pair of detected eye centers."""
        if self._eye_cascade is None or self._eye_cascade.empty():
            return None, None

        frame_h, frame_w = gray.shape[:2]
        xmin, ymin, xmax, ymax = self._clip_box(box, frame_w, frame_h)
        width = xmax - xmin
        height = ymax - ymin
        if width < 48 or height < 48:
            return None, None

        # The DNN head box is expanded above the face. Keep the search around
        # the expected eye band to avoid nostril and mouth false positives.
        search_top = max(0, ymin + int(height * 0.16))
        search_bottom = min(frame_h, ymin + int(height * 0.72))
        search_left = max(0, xmin + int(width * 0.04))
        search_right = min(frame_w, xmax - int(width * 0.04))
        roi = gray[search_top:search_bottom, search_left:search_right]
        if roi.size == 0:
            return None, None

        roi = cv2.equalizeHist(roi)
        min_eye = max(12, int(min(width, height) * 0.075))
        with self._landmark_lock:
            eyes = self._eye_cascade.detectMultiScale(
                roi,
                scaleFactor=1.08,
                minNeighbors=5,
                minSize=(min_eye, min_eye),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )

        candidates = []
        for ex, ey, ew, eh in eyes:
            candidates.append({
                "x": search_left + ex + ew / 2.0,
                "y": search_top + ey + eh / 2.0,
                "width": float(ew),
                "height": float(eh),
            })

        best_pair = None
        best_score = None
        for first_index, first in enumerate(candidates):
            for second in candidates[first_index + 1:]:
                left, right = sorted((first, second), key=lambda eye: eye["x"])
                horizontal_gap = right["x"] - left["x"]
                vertical_gap = abs(right["y"] - left["y"])
                mean_size = (left["width"] + right["width"]) / 2.0
                size_ratio = min(left["width"], right["width"]) / max(
                    left["width"], right["width"]
                )

                if not width * 0.18 <= horizontal_gap <= width * 0.72:
                    continue
                if vertical_gap > height * 0.22 or size_ratio < 0.55:
                    continue

                center_x = (left["x"] + right["x"]) / 2.0
                expected_center_x = (xmin + xmax) / 2.0
                center_penalty = abs(center_x - expected_center_x) / max(width, 1)
                vertical_penalty = vertical_gap / max(height, 1)
                spacing_penalty = abs(horizontal_gap / max(width, 1) - 0.38)
                size_bonus = mean_size / max(width, 1)
                score = center_penalty + vertical_penalty + spacing_penalty - size_bonus * 0.15
                if best_score is None or score < best_score:
                    best_score = score
                    best_pair = (left, right)

        if best_pair is None:
            return None, None

        left, right = best_pair
        roll = degrees(atan2(right["y"] - left["y"], right["x"] - left["x"]))
        if abs(roll) > 45:
            return None, None

        landmarks = [
            {"x": int(round(left["x"])), "y": int(round(left["y"]))},
            {"x": int(round(right["x"])), "y": int(round(right["y"]))},
        ]
        return float(roll), landmarks

    def _build_detection_payload(self, bbox, tilt, pan, roll=None, eye_landmarks=None):
        health_status = self._build_health_status(tilt, pan, roll)
        direction = {
            "vertical": "flexion" if tilt >= 0 else "extension",
            "rotation": "left_rotation" if pan >= 0 else "right_rotation",
            "lateral": None if roll is None else (
                "left_lateral_flexion" if roll >= 0 else "right_lateral_flexion"
            ),
        }
        cervical_angles = {
            "tilt_angle": round(abs(tilt), 2),
            "rotation_angle": round(abs(pan), 2),
            "roll_angle": None if roll is None else round(abs(roll), 2),
            "raw_tilt": round(tilt, 2),
            "raw_pan": round(pan, 2),
            "raw_roll": None if roll is None else round(roll, 2),
        }
        assessment_angles = {
            "flexion_angle": round(max(tilt, 0.0), 2),
            "extension_angle": round(abs(min(tilt, 0.0)), 2),
            "left_lateral_flexion_angle": None if roll is None else round(max(roll, 0.0), 2),
            "right_lateral_flexion_angle": None if roll is None else round(abs(min(roll, 0.0)), 2),
            "left_rotation_angle": round(max(pan, 0.0), 2),
            "right_rotation_angle": round(abs(min(pan, 0.0)), 2),
        }
        return {
            "box": {
                "xmin": int(bbox["box"][0]),
                "ymin": int(bbox["box"][1]),
                "xmax": int(bbox["box"][2]),
                "ymax": int(bbox["box"][3]),
            },
            "confidence": bbox["confidence"],
            "direction": direction,
            "cervical_angles": cervical_angles,
            "assessment_angles": assessment_angles,
            "health_status": health_status,
            "roll_estimation": {
                "source": "opencv_eye_line",
                "available": roll is not None,
                "eye_landmarks": eye_landmarks,
            },
        }

    def _build_result_summary(self, primary_detection, detection_count):
        if primary_detection is None:
            return {
                "detected": False,
                "detection_count": detection_count,
                "message": "未检测到头部，无法估计颈椎角度",
                "angles": None,
                "health_status": None,
            }

        angles = primary_detection["cervical_angles"]
        health = primary_detection["health_status"]
        return {
            "detected": True,
            "detection_count": detection_count,
            "tilt_degrees": angles["raw_tilt"],
            "pan_degrees": angles["raw_pan"],
            "roll_degrees": angles["raw_roll"],
            "tilt_abs_degrees": angles["tilt_angle"],
            "pan_abs_degrees": angles["rotation_angle"],
            "roll_abs_degrees": angles["roll_angle"],
            "max_current_angle": health["max_current_angle"],
            "health_grade": health["grade"],
            "health_level": health["level"],
            "health_message": health["message"],
            "recommendation": health["recommendation"],
            "angles": angles,
            "assessment_angles": primary_detection["assessment_angles"],
            "health_status": health,
        }

    def _draw_detection(self, frame, detection):
        box = detection["box"]
        xmin, ymin, xmax, ymax = box["xmin"], box["ymin"], box["xmax"], box["ymax"]
        angles = detection["cervical_angles"]
        health = detection["health_status"]
        color = self._status_color(health["grade"])

        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2, lineType=cv2.LINE_AA)
        roll_label = "--" if angles["raw_roll"] is None else f"{angles['raw_roll']:.2f}"
        label = f"TILT {angles['raw_tilt']:.2f}  PAN {angles['raw_pan']:.2f}  ROLL {roll_label}"
        cv2.putText(
            frame,
            label,
            (xmin, max(24, ymin - 10)),
            cv2.FONT_HERSHEY_DUPLEX,
            0.55,
            color,
            1,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"STATUS {health['grade'].upper()}",
            (xmin, min(frame.shape[0] - 12, ymax + 24)),
            cv2.FONT_HERSHEY_DUPLEX,
            0.55,
            color,
            1,
            lineType=cv2.LINE_AA,
        )

        centerx = int((xmin + xmax) / 2)
        centery = int((ymin + ymax) / 2)
        max_arrow_len = max(10, (xmax - xmin + 1) / 2)
        offset_x = -1 * int(sin(radians(angles["raw_pan"])) * max_arrow_len)
        offset_y = -1 * int(sin(radians(angles["raw_tilt"])) * max_arrow_len)
        cv2.arrowedLine(
            frame,
            (centerx, centery),
            (centerx + offset_x, centery + offset_y),
            color,
            2,
            line_type=cv2.LINE_AA,
        )

    def _build_health_status(self, tilt, pan, roll=None):
        angle_values = [abs(tilt), abs(pan)]
        if roll is not None:
            angle_values.append(abs(roll))
        max_angle = max(angle_values)
        if max_angle <= 15:
            grade = "normal"
            grade_score = 1
            level = "正常"
            message = "当前头颈姿态偏转较小"
            recommendation = "继续保持自然放松姿态"
        elif max_angle <= 30:
            grade = "mild"
            grade_score = 2
            level = "轻度"
            message = "当前头颈姿态有轻度偏转"
            recommendation = "建议调整坐姿，避免长时间保持同一角度"
        elif max_angle <= 45:
            grade = "moderate"
            grade_score = 3
            level = "中度"
            message = "当前头颈姿态偏转明显"
            recommendation = "建议及时回正并休息颈部"
        else:
            grade = "severe"
            grade_score = 4
            level = "重度"
            message = "当前头颈姿态偏转过大"
            recommendation = "建议停止当前动作，必要时寻求专业评估"

        return {
            "grade": grade,
            "grade_score": grade_score,
            "level": level,
            "message": message,
            "recommendation": recommendation,
            "basis": "基于当前帧 tilt/pan/可用 roll 最大绝对角的实时姿态状态，非完整六方向医学诊断",
            "max_current_angle": round(max_angle, 2),
        }

    @staticmethod
    def _status_color(grade):
        colors = {
            "normal": (0, 200, 0),
            "mild": (0, 220, 255),
            "moderate": (0, 140, 255),
            "severe": (0, 0, 255),
        }
        return colors.get(grade, (0, 255, 0))

    def _select_primary_detection(self, detections):
        if not detections:
            return None
        return max(
            detections,
            key=lambda item: (
                item["confidence"] if item["confidence"] is not None else 0.0,
                (item["box"]["xmax"] - item["box"]["xmin"]) * (item["box"]["ymax"] - item["box"]["ymin"]),
            ),
        )

    def _dedupe_boxes(self, boxes):
        boxes = [
            item
            for item in boxes
            if item["box"][2] > item["box"][0] and item["box"][3] > item["box"][1]
        ]
        boxes.sort(
            key=lambda item: (
                item["confidence"] is not None,
                item["confidence"] or 0.0,
                (item["box"][2] - item["box"][0]) * (item["box"][3] - item["box"][1]),
            ),
            reverse=True,
        )

        kept = []
        for candidate in boxes:
            if all(self._iou(candidate["box"], item["box"]) <= 0.3 for item in kept):
                kept.append(candidate)
        return kept

    @staticmethod
    def _clip_box(box, width, height):
        xmin, ymin, xmax, ymax = box
        return [
            max(0, min(width - 1, int(xmin))),
            max(0, min(height - 1, int(ymin))),
            max(0, min(width - 1, int(xmax))),
            max(0, min(height - 1, int(ymax))),
        ]

    @staticmethod
    def _iou(box_a, box_b):
        xa = max(box_a[0], box_b[0])
        ya = max(box_a[1], box_b[1])
        xb = min(box_a[2], box_b[2])
        yb = min(box_a[3], box_b[3])
        inter = max(0, xb - xa) * max(0, yb - ya)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        denom = area_a + area_b - inter
        return inter / denom if denom > 0 else 0


pose_estimator_service = PoseEstimatorService()
