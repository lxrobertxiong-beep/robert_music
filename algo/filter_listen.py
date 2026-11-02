"""Import bridge for ``algo/filter-listen``.

The on-disk directory is hyphenated so it matches the plugin id. Python
cannot import that path directly; this module loads ``peq`` and ``graph``
from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent / "filter-listen"


def _load():
    root = str(_MODULE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    # Drop cached top-level names so this bridge binds the in-repo modules.
    for name in ("peq", "graph"):
        existing = sys.modules.get(name)
        existing_file = getattr(existing, "__file__", "") if existing else ""
        if existing is not None and not str(existing_file).startswith(root):
            del sys.modules[name]
    import graph
    import peq

    return peq, graph


_peq, _graph = _load()

Biquad = _peq.Biquad
PeqCascade = _peq.PeqCascade
peq_from_dict = _peq.peq_from_dict
AudioGraph = _graph.AudioGraph
GraphConfig = _graph.GraphConfig
peq = _peq
graph = _graph

__all__ = [
    "AudioGraph",
    "Biquad",
    "GraphConfig",
    "PeqCascade",
    "graph",
    "peq",
    "peq_from_dict",
]
