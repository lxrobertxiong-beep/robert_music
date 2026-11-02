#!/usr/bin/env python3
"""Local desktop audition UI for call-nr.

    pip install -r algo/call-nr/requirements-ui.txt
    python algo/call-nr/scripts/audition_ui.py

Opens http://127.0.0.1:7860 . Gradio is optional and is not imported until
this script builds the page, so unit tests and CI can import the package
without it. Missing algorithm pins show the same exit-3 text as the CLI.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from call_nr.audition import UI_BACKENDS, audition, default_out_dir

_INTRO = """
# call-nr 桌面试听

上传 WAV，或填写本机路径。选算法后运行，并排听原声和处理后的结果，并下载 WAV。

`identity` 与 `passthrough` 不需要额外权重。`rnnoise`、`deepfilternet`、`gtcrn` 缺二进制、包或权重时，状态栏显示与命令行 **exit 3** 相同的原因（环境变量见 `algo/call-nr/README.md`）。这里不下载权重，也不是评测准入。Silero VAD 仍走 CLI（它写出 CSV，不是 WAV）。
"""


def _component(factory, /, **kwargs):
    """Drop kwargs a newer Gradio added, so 4.44 and 6.x both construct."""
    allowed = inspect.signature(factory.__init__).parameters
    kept = {key: value for key, value in kwargs.items() if key in allowed}
    return factory(**kept)


def build_demo():
    """Build the Gradio page. Imports gradio; raises ImportError if it is absent."""
    import gradio as gr

    def on_run(upload, local_path, backend):
        result = audition(upload, local_path, backend)
        return result.input_wav, result.output_wav, result.output_wav, result.message

    with gr.Blocks(title="call-nr audition") as demo:
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
            backend = gr.Dropdown(
                choices=list(UI_BACKENDS),
                value="identity",
                label="算法",
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
            inputs=[upload, local_path, backend],
            outputs=[original, processed, download, status],
        )
    return demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audition_ui",
        description=(
            "Local call-nr audition UI. Upload a WAV, pick a waveform backend, "
            "play input and output, and download the processed WAV."
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
            "pip install -r algo/call-nr/requirements-ui.txt\n"
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
