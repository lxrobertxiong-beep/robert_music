# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""M2 OSS AI filter / listening compensation — portable PEQ + graph stubs.

Import the hyphenated directory via ``algo.filter_listen`` (see that module).
When this directory is on ``sys.path``, ``peq`` and ``graph`` import directly.
"""

from __future__ import annotations

from graph import AudioGraph, GraphConfig
from peq import Biquad, PeqCascade, peq_from_dict

__version__ = "0.1.0"

__all__ = [
    "AudioGraph",
    "Biquad",
    "GraphConfig",
    "PeqCascade",
    "peq_from_dict",
]
