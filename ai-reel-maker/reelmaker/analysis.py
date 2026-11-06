import math

import cv2
import numpy as np


def frame_quality(frame):
    """Fast, model-free visual quality estimate using OpenCV."""
    small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    contrast = float(gray.std())

    sharp_score = min(1.0, math.log1p(sharpness) / 8.0)
    exposure_score = max(0.0, 1.0 - abs(brightness - 127.0) / 127.0)
    contrast_score = min(1.0, contrast / 64.0)
    return 0.50 * sharp_score + 0.30 * exposure_score + 0.20 * contrast_score


def best_video_window(path, clip_seconds, sample_interval=0.5):
    """
    Sample a video and choose the highest-quality contiguous window.
    Returns (start_seconds, score). Falls back to the center if decoding fails.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return 0.0, 0.0

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    duration = frame_count / fps if fps > 0 else 0.0
    if duration <= 0:
        capture.release()
        return 0.0, 0.0

    samples = []
    timestamp = 0.0
    while timestamp < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
        ok, frame = capture.read()
        if ok and frame is not None:
            samples.append((timestamp, frame_quality(frame)))
        timestamp += sample_interval
    capture.release()

    if not samples:
        return max(0.0, (duration - clip_seconds) / 2.0), 0.0

    if duration <= clip_seconds:
        return 0.0, float(np.mean([score for _, score in samples]))

    starts = np.arange(0.0, max(0.0, duration - clip_seconds) + 0.001, sample_interval)
    best_start, best_score = 0.0, -1.0
    for start in starts:
        end = start + clip_seconds
        window_scores = [score for time, score in samples if start <= time <= end]
        if not window_scores:
            continue
        score = float(np.mean(window_scores))
        if score > best_score:
            best_start, best_score = float(start), score

    return best_start, max(0.0, best_score)


def photo_quality(path):
    image = cv2.imread(str(path))
    if image is None:
        return 0.0
    return frame_quality(image)
