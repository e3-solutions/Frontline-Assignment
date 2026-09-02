import numpy as np
from scipy.signal import butter, sosfilt, lfilter

# ─────────────────────────────────────────────
#  LPC helpers
# ─────────────────────────────────────────────

def pre_emphasis(frame: np.ndarray, coef: float = 0.97) -> np.ndarray:
    """
    High-frequency boost before LPC analysis.
    LPC naturally fits low freqs better; pre-emphasis flattens the spectrum
    so formants above 1kHz are captured with equal accuracy.
    """
    return np.append(frame[0], frame[1:] - coef * frame[:-1])


def de_emphasis(frame: np.ndarray, coef: float = 0.97) -> np.ndarray:
    """Inverse of pre_emphasis — restores natural spectral balance after synthesis."""
    out = np.zeros_like(frame)
    out[0] = frame[0]
    for i in range(1, len(frame)):
        out[i] = frame[i] + coef * out[i - 1]
    return out


def lpc_analyze(frame: np.ndarray, order: int) -> np.ndarray:
    """LPC via autocorrelation + Levinson-Durbin. Returns [1, a1, ..., a_order]."""
    n = len(frame)
    r = np.array([np.dot(frame[:n - k], frame[k:]) for k in range(order + 1)])

    if r[0] < 1e-12:
        return np.concatenate([[1.0], np.zeros(order)])

    a = np.zeros(order)
    e = r[0]
    for i in range(order):
        if e < 1e-12:
            break
        lam = -np.dot(a[:i], r[i:0:-1]) - r[i + 1]
        k = lam / e
        a_new = a.copy()
        a_new[i] = k
        for j in range(i):
            a_new[j] = a[j] + k * a[i - 1 - j]
        a = a_new
        e *= (1.0 - k ** 2)

    return np.concatenate([[1.0], a])


def lpc_stabilize(lpc: np.ndarray, margin: float = 0.97) -> np.ndarray:
    """Reflect poles with |z| >= margin inside the unit circle."""
    roots = np.roots(lpc)
    magnitudes = np.abs(roots)
    unstable = magnitudes >= margin
    if np.any(unstable):
        roots[unstable] *= margin / magnitudes[unstable]
    stabilized = np.real(np.poly(roots))
    stabilized /= stabilized[0]
    return stabilized.astype(np.float64)


def bandwidth_expand(lpc: np.ndarray, gamma: float = 0.985) -> np.ndarray:
    """
    Multiply a[k] by gamma^k — moves poles toward origin, widening formant bandwidths.
    Whispers have broader, more diffuse formants than voiced speech.
    gamma: 0.97 = very breathy | 0.985 = natural whisper | 0.995 = tight/close to original
    """
    order = len(lpc) - 1
    factors = gamma ** np.arange(order + 1)
    return lpc * factors


def lpc_residual(frame: np.ndarray, lpc: np.ndarray) -> np.ndarray:
    """Compute the LPC prediction residual (excitation signal)."""
    return lfilter(lpc, [1.0], frame)


# ─────────────────────────────────────────────
#  Streaming Whisper  (LPC-based, high quality)
# ─────────────────────────────────────────────

class StreamingWhisperLPC:
    """
    High-quality voiced-to-whisper conversion using LPC vocoder.

    Quality improvements over basic version:
      * Pre/de-emphasis     — accurate formant capture across full frequency range
      * sqrt(Hann) window   — correct OLA amplitude reconstruction (no level pumping)
      * Bandwidth expansion — wider formants = natural whisper breathiness
      * Residual-shaped noise — excitation gain matched to per-frame residual energy
      * LPC order 18        — finer spectral detail at 24kHz
      * 75%+ overlap        — smoother transitions, fewer artefacts
    """

    def __init__(
        self,
        sr: int = 24000,
        frame_ms: int = 25,
        hop_ms: int = 6,
        lpc_order: int = 18,
        whisper_volume: float = 0.28,
        pre_emph_coef: float = 0.97,
        bw_gamma: float = 0.985,
    ):
        self.sr             = sr
        self.lpc_order      = lpc_order
        self.whisper_volume = whisper_volume
        self.pre_emph_coef  = pre_emph_coef
        self.bw_gamma       = bw_gamma

        self.frame_len = int(sr * frame_ms / 1000)
        self.hop_len   = int(sr * hop_ms  / 1000)
        self.overlap   = self.frame_len - self.hop_len

        # sqrt(Hann) — correct window for OLA with high overlap ratios
        self.window = np.sqrt(np.hanning(self.frame_len)).astype(np.float64)

        self.in_buffer  = np.array([], dtype=np.float64)
        self.out_buffer = np.zeros(self.frame_len, dtype=np.float64)

        self.shelf_sos   = butter(2, 3500 / (sr / 2), btype="high", output="sos")
        self.shelf_state = np.zeros((self.shelf_sos.shape[0], 2))

        self.hp_sos   = butter(2, 250 / (sr / 2), btype="high", output="sos")
        self.hp_state = np.zeros((self.hp_sos.shape[0], 2))

        self.bp_sos = butter(
            4, [600 / (sr / 2), 9000 / (sr / 2)], btype="band", output="sos"
        )

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        frame = frame.astype(np.float64)

        # 1. Pre-emphasis + window
        emphasized = pre_emphasis(frame, self.pre_emph_coef)
        windowed   = emphasized * self.window

        # 2. LPC analysis
        lpc = lpc_analyze(windowed, self.lpc_order)

        # 3. Bandwidth expansion — widens formants for whisper character
        lpc = bandwidth_expand(lpc, self.bw_gamma)

        # 4. Stability guarantee
        lpc = lpc_stabilize(lpc)

        # 5. Residual-shaped noise excitation
        residual  = lpc_residual(windowed, lpc)
        res_rms   = np.sqrt(np.mean(residual ** 2) + 1e-12)

        noise     = np.random.normal(0, 1, size=self.frame_len)
        noise     = sosfilt(self.bp_sos, noise)
        noise_rms = np.sqrt(np.mean(noise ** 2) + 1e-12)
        noise    *= res_rms / noise_rms   # match per-frame energy

        # 6. LPC synthesis: all-pole filter H(z) = 1/A(z)
        zi = np.zeros(len(lpc) - 1)
        synth, _ = lfilter([1.0], lpc, noise, zi=zi)

        # NOTE: de-emphasis intentionally skipped for whisper.
        # Restoring low-frequency energy makes whispers sound heavy/muddy.
        # Whispers are naturally bright — we keep the pre-emphasised spectral tilt.

        # 8. NaN/Inf guard
        if not np.isfinite(synth).all():
            synth = np.zeros(self.frame_len, dtype=np.float64)

        return synth * self.window

    def process(self, pcm_bytes: bytes) -> bytes:
        incoming = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float64)
        incoming /= 32768.0

        self.in_buffer = np.concatenate([self.in_buffer, incoming])

        output_samples = []

        while len(self.in_buffer) >= self.frame_len:
            frame          = self.in_buffer[:self.frame_len]
            self.in_buffer = self.in_buffer[self.hop_len:]

            whisper_frame = self._process_frame(frame)

            self.out_buffer += whisper_frame
            output_samples.append(self.out_buffer[:self.hop_len].copy())
            self.out_buffer[:-self.hop_len] = self.out_buffer[self.hop_len:]
            self.out_buffer[-self.hop_len:] = 0.0

        if not output_samples:
            return b""

        out = np.concatenate(output_samples).astype(np.float32)

        # Remove low rumble
        out, self.hp_state = sosfilt(self.hp_sos, out, zi=self.hp_state)

        # Add whisper airiness
        high_part, self.shelf_state = sosfilt(self.shelf_sos, out, zi=self.shelf_state)
        out = out + 0.45 * high_part

        out *= self.whisper_volume
        out  = np.tanh(out * 2.0) / 2.0
        out  = np.clip(out, -1.0, 1.0)
        return (out * 32767).astype(np.int16).tobytes()


# ─────────────────────────────────────────────
#  Quick test: file → whisper → file
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import soundfile as sf
    import librosa

    INPUT_FILE  = "/Users/nitishjoshi/Downloads/Alessia_Cara's_voice.wav"
    OUTPUT_FILE = "whisper_streaming_lpc.wav"
    TARGET_SR   = 24000
    CHUNK_MS    = 40

    print("Loading...")
    x, fs = sf.read(INPUT_FILE)
    if x.ndim > 1:
        x = np.mean(x, axis=1)
    if fs != TARGET_SR:
        x = librosa.resample(x, orig_sr=fs, target_sr=TARGET_SR)
        fs = TARGET_SR

    chunk_size = int(fs * CHUNK_MS / 1000)
    processor  = StreamingWhisperLPC(
        sr=fs,
        whisper_volume=0.28,   # 0.15 = very soft | 0.28 = natural | 0.45 = loud
        lpc_order=18,
        bw_gamma=0.985,        # 0.97 = very breathy | 0.985 = natural | 0.995 = tight
    )

    print("Processing...")
    out_chunks = []
    for i in range(0, len(x), chunk_size):
        chunk   = x[i : i + chunk_size]
        pcm_in  = (np.clip(chunk, -1, 1) * 32767).astype(np.int16).tobytes()
        pcm_out = processor.process(pcm_in)
        if pcm_out:
            out_chunks.append(
                np.frombuffer(pcm_out, dtype=np.int16).astype(np.float32) / 32767
            )

    result = np.concatenate(out_chunks).astype(np.float32)
    sf.write(OUTPUT_FILE, result, fs, subtype="PCM_24")
    print(f"Saved -> {OUTPUT_FILE}")
