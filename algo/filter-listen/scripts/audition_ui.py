#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Local desktop audition UI for filter-listen.

    pip install -r algo/filter-listen/requirements-ui.txt
    python algo/filter-listen/scripts/audition_ui.py

Opens http://127.0.0.1:7860 . Gradio is optional and is not imported until
this script builds the page, so unit tests and CI can import the package
without it. A bad path shows exit-2 text. A preset that needs AutoEq and
does not have it shows exit-3 text. The shipped LP / HP / PEQ presets do
not need AutoEq. Weights are not downloaded.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audition import UI_PRESETS, audition, default_out_dir

_INTRO = """
# filter-listen 桌面试听

上传 WAV，或填写本机路径。在 `passthrough` / `lowpass` / `highpass` / `peaking` / `example_compensation` 里选一个，并排听原声和处理后的结果，并下载 WAV。

这些预设都是现有 `peq_schema` 类型（或空 band）。`lowpass` / `highpass` 的 `gain` 仍必填，但 `peq.py` 忽略该字段（通带 0 dB）。处理走 `apply_peq_wav` 的同一条图：48 kHz / 480 帧、PEQ、soft limiter。limiter 是工程占位，**非听感定稿**。这里不下载权重，不 vendor AutoEq，也不宣称评测准入。`configs/peq_schema.json` 未改。

路径打不开或 WAV 读不了时，状态栏以 **exit 2** 开头。若某个预设把 `meta.generator` 标成 `autoeq` 且未安装 AutoEq，状态栏以 **exit 3** 开头（内置上面几项不是这条路径）。未安装 Gradio 时本脚本直接退出，不静默失败。
"""


def _component(factory, /, **kwargs):
    """Drop kwargs a newer Gradio added, so 4.44 and 6.x both construct."""
    allowed = inspect.signature(factory.__init__).parameters
    kept = {key: value for key, value in kwargs.items() if key in allowed}
    return factory(**kept)


def build_demo():
    """Build the Gradio page. Imports gradio; raises ImportError if it is absent."""
    import gradio as gr

    def on_run(upload, local_path, preset):
        result = audition(upload, local_path, preset)
        return result.input_wav, result.output_wav, result.output_wav, result.message

    with gr.Blocks(title="filter-listen audition") as demo:
        gr.Markdown(_INTRO)
        upload = gr.Audio(
            label="上传 WAV",
            sources=["upload"],
            type="filepath",
        )
        local_path = gr.Textbox(
            label="或本机 WAV 路径",
            placeholder="/path/to/in.wav",
            info="非空时优先于上传文件",
        )
        with gr.Row():
            preset = gr.Dropdown(
                choices=list(UI_PRESETS),
                value="passthrough",
                label="滤波预设",
            )
            run = gr.Button("运行", variant="primary")
        status = _component(
            gr.Textbox,
            label="状态",
            lines=6,
            max_lines=16,
            interactive=False,
        )
        with gr.Row():
            original = _component(
                gr.Audio,
                label="原声",
                type="filepath",
                interactive=False,
                buttons=["download"],
                format="wav",
            )
            processed = _component(
                gr.Audio,
                label="处理后",
                type="filepath",
                interactive=False,
                buttons=["download"],
                format="wav",
            )
        download = gr.File(label="下载处理后的 WAV")
        run.click(
            on_run,
            inputs=[upload, local_path, preset],
            outputs=[original, processed, download, status],
        )
    return demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audition_ui",
        description=(
            "Local filter-listen audition UI. Upload a WAV, pick an LP/HP/PEQ "
            "preset, play input and output, and download the processed WAV."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7860, help="port (default 7860)")
    args = parser.parse_args(argv)
    try:
        demo = build_demo()
    except ImportError as exc:
        print(
            "gradio is not installed. The audition UI is optional and is not part of CI.\n"
            "pip install -r algo/filter-listen/requirements-ui.txt\n"
            f"Detail: {exc}",
            file=sys.stderr,
        )
        return 1
    out_dir = default_out_dir()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=False,
        inbrowser=False,
        show_error=True,
        allowed_paths=[str(out_dir)],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
