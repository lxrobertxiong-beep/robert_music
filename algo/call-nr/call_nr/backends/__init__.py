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
}


def get_backend(name: str) -> DenoiseBackend:
    """Return a backend by CLI name. Optional backends may still raise later."""
    key = _ALIASES.get(name.strip().lower())
    if key is None:
        known = "identity, passthrough, rnnoise, deepfilternet"
        raise ValueError(f"unknown backend {name!r}; expected one of: {known}")
    if key == "identity":
        return IdentityBackend()
    if key == "passthrough":
        return PassThroughBackend()
    if key == "rnnoise":
        from call_nr.backends.rnnoise import RNNoiseBackend

        return RNNoiseBackend()
    from call_nr.backends.deepfilternet import DeepFilterNetBackend

    return DeepFilterNetBackend()
