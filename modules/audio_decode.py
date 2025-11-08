import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def decode_to_wav16k(input_bytes: bytes) -> bytes:
    """
    Decode arbitrary compressed audio (e.g., webm/opus) to 16kHz mono PCM WAV.
    Prefer system ffmpeg; fall back to PyAV if available.
    """
    if _has_ffmpeg():
        return _decode_with_ffmpeg(input_bytes)
    try:
        return _decode_with_pyav(input_bytes)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("Audio decode failed (need ffmpeg or PyAV)") from e


def _decode_with_ffmpeg(input_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "in.bin"
        out_path = Path(td) / "out.wav"
        in_path.write_bytes(input_bytes)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(in_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)
        return out_path.read_bytes()


def _decode_with_pyav(input_bytes: bytes) -> bytes:
    import av  # type: ignore
    import numpy as np  # type: ignore
    import soundfile as sf  # type: ignore
    import io

    with av.open(io.BytesIO(input_bytes)) as container:
        resampler = None
        pcm = []
        for frame in container.decode(audio=0):
            if resampler is None:
                resampler = av.audio.resampler.AudioResampler(
                    format="s16",
                    layout="mono",
                    rate=16000,
                )
            rf = resampler.resample(frame)
            pcm.append(rf.to_ndarray())
        if not pcm:
            raise RuntimeError("No audio frames decoded")
        data = np.concatenate(pcm, axis=1).T  # shape (n, channels=1)
        buf = io.BytesIO()
        sf.write(buf, data, 16000, format="WAV", subtype="PCM_16")
        return buf.getvalue()

