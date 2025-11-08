import io
import math
import os
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass
class EmotionSnapshot:
    pitch_hz: Optional[float]
    confidence: float
    emotion_estimate: Optional[str]


class EmotionAIWorker:
    """
    Lightweight Emotion AI Phase 1 worker.

    - Estimates pitch via zero-crossing on 16-bit PCM WAV.
    - Generates simple confidence score.
    - Maps energy + pitch to coarse emotion tags (for debug/phase-1).
    """

    def __init__(self) -> None:
        self.pitch_floor_hz = int(os.getenv("EMOTION_PITCH_FLOOR", "80"))
        self.pitch_ceil_hz = int(os.getenv("EMOTION_PITCH_CEIL", "400"))
        self.sample_rate = 16000  # decode_to_wav16k guarantees 16k mono

    def analyze(self, wav_bytes: bytes, avg_energy: float, peak_energy: float) -> EmotionSnapshot:
        pitch_hz, confidence = self._estimate_pitch(wav_bytes)
        emotion = self._estimate_emotion(avg_energy, peak_energy, pitch_hz, confidence)
        return EmotionSnapshot(pitch_hz=pitch_hz, confidence=confidence, emotion_estimate=emotion)

    def _estimate_pitch(self, wav_bytes: bytes) -> tuple[Optional[float], float]:
        if len(wav_bytes) <= 44:
            return None, 0.0
        try:
            pcm = np.frombuffer(wav_bytes[44:], dtype="<i2").astype(np.float32)
        except ValueError:
            return None, 0.0
        if pcm.size < 256:
            return None, 0.0
        pcm -= pcm.mean()
        max_amp = np.max(np.abs(pcm)) if pcm.size else 0.0
        if max_amp == 0:
            return None, 0.0
        pcm /= max_amp
        zero_crossings = np.where(np.diff(np.sign(pcm)))[0]
        if zero_crossings.size < 2:
            return None, 0.0
        periods = np.diff(zero_crossings) / self.sample_rate
        periods = periods[(periods > 0) & (periods < 0.02)]
        if periods.size == 0:
            return None, 0.0
        period = float(np.median(periods))
        if period <= 0:
            return None, 0.0
        pitch = 1.0 / period
        if not (self.pitch_floor_hz <= pitch <= self.pitch_ceil_hz):
            return None, 0.2
        confidence = max(0.2, min(1.0, float(periods.size) / 25.0))
        return pitch, confidence

    def _estimate_emotion(
        self,
        avg_energy: float,
        peak_energy: float,
        pitch_hz: Optional[float],
        confidence: float,
    ) -> Optional[str]:
        if avg_energy >= 65 and (pitch_hz or 0) >= 180:
            return "excited"
        if avg_energy <= 35 and (pitch_hz or 0) <= 140:
            return "soft"
        if confidence < 0.3:
            return None
        if peak_energy >= 80:
            return "intense"
        return "neutral"

    def to_payload(self, snapshot: EmotionSnapshot) -> Dict[str, float]:
        payload: Dict[str, float] = {}
        if snapshot.pitch_hz is not None:
            payload["pitch_hz"] = float(snapshot.pitch_hz)
        payload["emotion_confidence"] = float(snapshot.confidence)
        return payload

