"""Optional and built-in denoise backends."""

from __future__ import annotations

from call_nr.pipeline import DenoiseBackend, IdentityBackend, PassThroughBackend

_ALIASES = {
    "identity": "identity",
    "passthrough": "passthrough",
    "pass-through": "passthrough",
    "rnnoise": "rnnoise",
    "deepfilternet": "deepfilternet",
    "deepfilternet3": "deepfilternet",
    "dfn": "deepfilternet",
    "dfn3": "deepfilternet",
    "gtcrn": "gtcrn",
}

_SILERO_NAMES = {"silero_vad", "silero", "vad"}


def get_backend(name: str) -> DenoiseBackend:
    """Return a backend by CLI name. Optional backends may still raise later."""
    key = _ALIASES.get(name.strip().lower())
    if key is None:
        known = "identity, passthrough, rnnoise, deepfilternet, gtcrn"
        extra = ""
        if name.strip().lower() in _SILERO_NAMES:
            extra = (
                " silero_vad is not a waveform DenoiseBackend; "
                "use scripts/run_silero_vad.py (or --backend silero_vad on the CLI)."
            )
        raise ValueError(f"unknown backend {name!r}; expected one of: {known}.{extra}")
    if key == "identity":
        return IdentityBackend()
    if key == "passthrough":
        return PassThroughBackend()
    if key == "rnnoise":
        from call_nr.backends.rnnoise import RNNoiseBackend

        return RNNoiseBackend()
    if key == "gtcrn":
        from call_nr.backends.gtcrn import GTCRNBackend

        return GTCRNBackend()
    from call_nr.backends.deepfilternet import DeepFilterNetBackend

    return DeepFilterNetBackend()
