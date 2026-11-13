"""Synthesize clean 48 kHz stereo tactile UI & forge sound design tracks (WAV).

Produces subtle, broadcast-safe mechanical detents, checksum ticks, and warm
damped-steel harmonic accents synced to each video's exact scene cuts — zero
stock music loops and zero robotic TTS.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 48_000


def _clamp16(val: float) -> int:
    v = int(round(val * 32767.0))
    if v > 32767:
        return 32767
    if v < -32768:
        return -32768
    return v


def _mix(buf_l: list[float], buf_r: list[float], start_s: float, samples_l: list[float], samples_r: list[float]) -> None:
    idx0 = max(0, int(round(start_s * SAMPLE_RATE)))
    n = min(len(samples_l), len(buf_l) - idx0)
    for i in range(n):
        buf_l[idx0 + i] += samples_l[i]
        buf_r[idx0 + i] += samples_r[i]


def _forge_strike(amp: float = 0.20, dur: float = 0.48) -> tuple[list[float], list[float]]:
    """Warm, damped low-register steel harmonic strike for the 0.0s hook."""
    n = int(dur * SAMPLE_RATE)
    out_l: list[float] = []
    out_r: list[float] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        attack = min(1.0, t / 0.003)
        body = (
            0.55 * math.sin(2 * math.pi * 110.0 * t) * math.exp(-t * 6.5)
            + 0.28 * math.sin(2 * math.pi * 220.0 * t + 0.3) * math.exp(-t * 9.0)
            + 0.14 * math.sin(2 * math.pi * 329.6 * t + 0.7) * math.exp(-t * 13.0)
            + 0.12 * math.sin(2 * math.pi * 1320.0 * t) * math.exp(-t * 48.0)
        )
        s = amp * attack * body
        out_l.append(s * 1.02)
        out_r.append(s * 0.98)
    return out_l, out_r


def _detent_click(amp: float = 0.11, pitch_hz: float = 780.0) -> tuple[list[float], list[float]]:
    """Precision mechanical switch detent on scene transitions."""
    dur = 0.032
    n = int(dur * SAMPLE_RATE)
    out_l: list[float] = []
    out_r: list[float] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        s = amp * (
            0.65 * math.sin(2 * math.pi * pitch_hz * t) * math.exp(-t * 140.0)
            + 0.35 * math.sin(2 * math.pi * 145.0 * t) * math.exp(-t * 85.0)
        )
        out_l.append(s * 0.96)
        out_r.append(s * 1.04)
    return out_l, out_r


def _micro_tick(amp: float = 0.045, freq: float = 1420.0) -> tuple[list[float], list[float]]:
    dur = 0.014
    n = int(dur * SAMPLE_RATE)
    out: list[float] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        out.append(amp * math.sin(2 * math.pi * freq * t) * math.exp(-t * 240.0))
    return out, list(out)


def _verified_chime(amp: float = 0.15) -> tuple[list[float], list[float]]:
    """Restrained two-note warm fifth (D4 -> A4) when verification/end-slate locks."""
    dur = 0.62
    n = int(dur * SAMPLE_RATE)
    out_l = [0.0] * n
    out_r = [0.0] * n
    for note_start, freq in ((0.0, 293.66), (0.11, 440.0)):
        i0 = int(note_start * SAMPLE_RATE)
        for j in range(n - i0):
            t = j / SAMPLE_RATE
            att = min(1.0, t / 0.006)
            val = amp * att * (
                0.72 * math.sin(2 * math.pi * freq * t) * math.exp(-t * 5.8)
                + 0.28 * math.sin(2 * math.pi * (freq * 2.0) * t) * math.exp(-t * 11.0)
            )
            out_l[i0 + j] += val * 0.98
            out_r[i0 + j] += val * 1.02
    return out_l, out_r


def write_soundtrack(
    out_wav: Path,
    duration_s: float,
    cut_times: list[float],
    tick_windows: list[tuple[float, float]] | None = None,
) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(round(duration_s * SAMPLE_RATE))

    rng = random.Random(42)
    # Subtle -56 dBFS warm low-passed room floor so social encoders keep audio stream live
    prev_l = 0.0
    prev_r = 0.0
    buf_l = [0.0] * total_samples
    buf_r = [0.0] * total_samples
    for i in range(total_samples):
        prev_l = 0.92 * prev_l + 0.08 * (rng.uniform(-1.0, 1.0) * 0.0014)
        prev_r = 0.92 * prev_r + 0.08 * (rng.uniform(-1.0, 1.0) * 0.0014)
        buf_l[i] = prev_l
        buf_r[i] = prev_r

    # Hook strike at 0.04s
    s_l, s_r = _forge_strike(amp=0.22)
    _mix(buf_l, buf_r, 0.04, s_l, s_r)

    # Scene cut detents
    for idx, ct in enumerate(cut_times):
        if ct <= 0.15 or ct >= duration_s - 0.2:
            continue
        c_l, c_r = _detent_click(amp=0.11, pitch_hz=740.0 + (idx % 3) * 70.0)
        _mix(buf_l, buf_r, ct, c_l, c_r)

    # Optional terminal / hash tick bursts
    for start_t, end_t in tick_windows or []:
        t = start_t + 0.25
        step = 0.22
        k = 0
        while t < min(end_t - 0.3, duration_s - 0.5):
            tk_l, tk_r = _micro_tick(amp=0.042, freq=1280.0 + (k % 4) * 90.0)
            _mix(buf_l, buf_r, t, tk_l, tk_r)
            t += step
            k += 1

    # End-slate resolve chime on last cut
    if cut_times:
        last_cut = cut_times[-1]
        if 1.0 < last_cut < duration_s - 0.7:
            v_l, v_r = _verified_chime(amp=0.14)
            _mix(buf_l, buf_r, last_cut + 0.06, v_l, v_r)

    # Smooth 40ms fade-in and 120ms fade-out
    fade_in = int(0.04 * SAMPLE_RATE)
    fade_out = int(0.12 * SAMPLE_RATE)
    for i in range(min(fade_in, total_samples)):
        g = i / fade_in
        buf_l[i] *= g
        buf_r[i] *= g
    for i in range(min(fade_out, total_samples)):
        g = i / fade_out
        buf_l[total_samples - 1 - i] *= g
        buf_r[total_samples - 1 - i] *= g

    frames = bytearray(total_samples * 4)
    offset = 0
    for i in range(total_samples):
        struct.pack_into("<hh", frames, offset, _clamp16(buf_l[i]), _clamp16(buf_r[i]))
        offset += 4

    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames)

    return out_wav
