from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


VIDEO_EVENTS = [1.0, 2.5, 4.0, 5.5, 7.0]
DEMO = {
    "video_events_seconds": VIDEO_EVENTS,
    "audio_events_seconds": [round(0.12 + 1.005 * value, 6) for value in VIDEO_EVENTS],
    "tolerance_ms": 40,
}


def estimate(video_events: list[float], audio_events: list[float], tolerance_ms: float = 40) -> dict:
    if len(video_events) != len(audio_events) or len(video_events) < 2:
        raise ValueError("video and audio event lists must have the same length and at least two events")
    x_mean = sum(video_events) / len(video_events)
    y_mean = sum(audio_events) / len(audio_events)
    denominator = sum((value - x_mean) ** 2 for value in video_events)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(video_events, audio_events)) / denominator
    intercept = y_mean - slope * x_mean
    residuals = [audio - (intercept + slope * video) for video, audio in zip(video_events, audio_events)]
    before_skew = [(audio - video) * 1000 for video, audio in zip(video_events, audio_events)]
    corrected = [(audio - intercept) / slope for audio in audio_events]
    after_skew = [(audio - video) * 1000 for video, audio in zip(video_events, corrected)]
    return {
        "event_pairs": len(video_events),
        "offset_ms": round(intercept * 1000, 3),
        "clock_ratio": round(slope, 8),
        "drift_ppm": round((slope - 1) * 1_000_000, 3),
        "max_skew_before_ms": round(max(abs(value) for value in before_skew), 3),
        "max_skew_after_model_ms": round(max(abs(value) for value in after_skew), 6),
        "fit_rmse_ms": round(math.sqrt(sum(value * value for value in residuals) / len(residuals)) * 1000, 6),
        "passed_before": max(abs(value) for value in before_skew) <= tolerance_ms,
        "passed_after_model": max(abs(value) for value in after_skew) <= tolerance_ms,
        "pairs": [{"video": video, "audio": audio, "skew_ms": round((audio - video) * 1000, 3)} for video, audio in zip(video_events, audio_events)],
        "scope": "Event-based synchronization; semantic mismatch and continuous speech alignment need content-aware features.",
    }


def analyze(payload: dict) -> dict:
    return estimate(list(map(float, payload["video_events_seconds"])), list(map(float, payload["audio_events_seconds"])), float(payload.get("tolerance_ms", 40)))


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"{binary} is required")
    return path


def synthesize(output: str | Path, offset_seconds: float = 0.12, clock_ratio: float = 1.005, duration: float = 8.4) -> Path:
    import cv2
    import numpy as np

    ffmpeg = _require("ffmpeg")
    output = Path(output)
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        video_path = directory_path / "video.mp4"
        audio_path = directory_path / "audio.wav"
        fps, width, height = 30, 640, 360
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        event_frames = {round(event * fps) for event in VIDEO_EVENTS}
        for frame_index in range(round(duration * fps)):
            image = np.zeros((height, width, 3), dtype=np.uint8)
            if any(abs(frame_index - event_frame) <= 1 for event_frame in event_frames):
                image[:] = 255
            cv2.putText(image, "AV SYNC FIXTURE", (180, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 150, 170), 2, cv2.LINE_AA)
            writer.write(image)
        writer.release()
        sample_rate = 48000
        samples = [0.0] * round(duration * sample_rate)
        for event in VIDEO_EVENTS:
            start = round((offset_seconds + clock_ratio * event) * sample_rate)
            for index in range(start, min(start + 480, len(samples))):
                samples[index] = 0.95 * math.sin(2 * math.pi * 1000 * (index - start) / sample_rate)
        with wave.open(str(audio_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, sample)) * 32767)) for sample in samples))
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video_path), "-i", str(audio_path), "-c:v", "copy", "-c:a", "aac", "-shortest", str(output)], check=True)
    return output


def _video_events(path: str | Path) -> list[float]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    bright = []
    frame = 0
    while True:
        ok, image = capture.read()
        if not ok:
            break
        if image.mean() > 180:
            bright.append(frame)
        frame += 1
    capture.release()
    groups = []
    for value in bright:
        if not groups or value > groups[-1][-1] + 1:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [sum(group) / len(group) / fps for group in groups]


def _audio_events(path: str | Path, sample_rate: int = 48000) -> list[float]:
    ffmpeg = _require("ffmpeg")
    completed = subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"], check=True, capture_output=True)
    values = struct.unpack(f"<{len(completed.stdout) // 4}f", completed.stdout)
    active = [index for index, value in enumerate(values) if abs(value) > 0.45]
    groups = []
    for index in active:
        if not groups or index > groups[-1][-1] + sample_rate * 0.05:
            groups.append([index])
        else:
            groups[-1].append(index)
    return [group[0] / sample_rate for group in groups]


def analyze_media(path: str | Path, tolerance_ms: float = 40) -> dict:
    video = _video_events(path)
    audio = _audio_events(path)
    count = min(len(video), len(audio))
    if count < 2:
        raise ValueError("media must contain at least two detectable flash/click pairs")
    result = estimate(video[:count], audio[:count], tolerance_ms)
    result["detected_video_events"] = len(video)
    result["detected_audio_events"] = len(audio)
    return result


def correct_media(source: str | Path, output: str | Path) -> dict:
    ffmpeg = _require("ffmpeg")
    before = analyze_media(source)
    offset = before["offset_ms"] / 1000
    ratio = before["clock_ratio"]
    if not 0 < ratio <= 2:
        raise ValueError("detected clock ratio is outside FFmpeg atempo range")
    if offset < 0:
        raise ValueError("negative offsets are not supported by this focused correction path")
    audio_filter = f"atrim=start={offset:.9f},asetpts=PTS-STARTPTS,atempo={ratio:.9f}"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", audio_filter, "-c:a", "aac", "-shortest", str(output)], check=True)
    after = analyze_media(output)
    return {"before": before, "after": after, "output": str(output)}
