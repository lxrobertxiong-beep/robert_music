# call-nr（通话降噪）

公开可复现骨架：契约、`DenoiseBackend` 接口，以及不依赖第三方二进制的 `identity` 推理。本目录**不**给出评测准入或榜单数字，也**不**包含厂商 SDK、固件或密钥。

## 能做什么

- **契约 A**（桌面评测 / 对照边界）`A_48k_480`：48 kHz、mono、10 ms = 480 samples。进程内与落盘 WAV 都是 little-endian float32。
- `identity` / `passthrough`：读 WAV → 转到契约 A → 按 480 样本逐帧原样返回 → 写 WAV。
- 可选钉版（缺依赖或权重时**明确报错**，不静默跳过，也不在本仓下载）：
  - RNNoise@v0.2，commit `904a876dce1f9ab8860c0a5000ed151f9f6eef58`
  - DeepFilterNet3@v0.5.6，PyPI `deepfilternet==0.5.6`，上游 commit `978576aa8400552a4ce9730838c635aa30db5e61`
  - GTCRN，短钉 `502ebfab`，完整 commit `502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73`（上游无 release tag）
  - Silero VAD，短钉 `066409f`，完整 commit `066409f3d9db45a30d21dfcbf9147826ffdd7052`（`v6.2.3-8-g066409f`：tag `v6.2.3` 之后 8 个提交，不是该 tag 本身）

## 不能做什么

- **契约 B** `B_16k_256`（16 kHz mono、256 samples，约 16 ms）只写在文档和 `PLUGIN.json` 里，供以后的适配层对照。本包不绑定厂商 SDK，也不假设固件图已经是 48 kHz。
- 不把受限评测仓、语料大集、权重或上游完整树拷进本树。GTCRN 的 `*.tar` 与 Silero 的 JIT 只放在本机路径。
- 不实现完整 AEC。控制字段 `ns_enable`、`vad_prob`、`aec_ref_pcm_*` 仍是占位，本骨架不消费它们。Silero VAD 只另写概率 CSV 和时间戳 JSON，不把 `vad_prob` 填进控制面。
- 延迟预算 `budget_alg_ms`、`budget_buffer_ms`、`budget_total_uplink_ms` 留给平台回填，这里不填数字。
- CI 只跑 identity 与契约 A。CI **不**安装 torch，**不**下载权重，**不**跑真实 GTCRN / Silero 推理。

## I/O 与流式注意

| 项 | 契约 A（本包实现） | 契约 B（仅文档） |
|----|--------------------|------------------|
| id | `A_48k_480` | `B_16k_256` |
| 采样率 | 48000 Hz | 16000 Hz |
| 帧 | 480 samples（10 ms） | 256 samples（约 16 ms） |
| 声道 | mono（多声道输入先取均值） | mono |

- `identity` 逐帧因果，`lookahead_frames = 0`，不读未来帧。`reset()` 在通话起止或模式切换时调用；identity 没有内部状态。
- 桌面 CLI 在音频线程之外做文件读写。以后的实时移植禁止在音频线程里堆分配或访问文件。
- 任意采样率的输入先转 mono，再经 `call_nr.io` 的 **soxr** 变到 48 kHz。已经是 48 kHz 时不再重采样。桌面 16 kHz ↔ 48 kHz 只走这一处，避免和评测侧各用一套重采样器。
- 契约 B 与契约 A 之间的 SRC 责任在未来适配层，本包不实现。
- RNNoise 原生边界是 48 kHz、480 samples、s16le raw（不是 WAV）。可选后端只在调用 demo 时做 float32 ↔ s16le，长度补到 480 的整数倍后再裁回。
- DeepFilterNet3 使用库的默认 look-ahead，**不是**零前瞻基线。上游的延迟补偿只影响输出对齐。脚本固定模型名 `DeepFilterNet3`，避免落到 DFN2。首次运行可能自行下载权重。
- GTCRN 是桌面整段路径：契约 A 的 48 kHz 经 soxr 到 16 kHz，再按上游 `infer.py` 做 STFT（`n_fft=512`、`hop=256`、`win=512`、`hann**0.5`），增强后回到 48 kHz 并对齐输入长度。`lookahead_frames` 为 `None`：这不是 10 ms 零前瞻基线。`torch>=2` 的 `istft` 需要复数谱，适配层会把模型输出的实部/虚部堆叠转成 complex。
- Silero VAD **不是**波形 `DenoiseBackend`。它把输入经 soxr 转到 16 kHz（窗 512，约 32 ms），写出 `t_sec,speech_prob` CSV，并在同目录写 `speech_timestamps.json`（`start`/`end` 为 16 kHz 样本下标）。加载只用本地 `hubconf.py`，不调用 `torch.hub`，因此缺文件时不会偷偷联网下载。

## 如何跑

系统包：Debian/Ubuntu 需要 `libsndfile1`（`soundfile` 的运行库）。

```bash
pip install -r algo/call-nr/requirements.txt
python algo/call-nr/scripts/infer.py --backend identity -i in.wav -o out.wav
# 等价：PYTHONPATH=algo/call-nr python -m call_nr --backend identity -i in.wav -o out.wav
bash algo/call-nr/scripts/setup_pins.sh
```

`identity` 成功时打印一行 `contract=A_48k_480`，并写出与输入等长（在 48 kHz 时间轴上）的 WAV。`--backend passthrough` 与 identity 同一条路径。

可选波形后端不在 CI 里安装：

```bash
# RNNoise：自行构建 v0.2，不要把二进制提交到本仓
export RNNOISE_DEMO=/path/to/examples/rnnoise_demo
# 或者 RNNOISE_ROOT 指向该 checkout（也可放在 algo/call-nr/third_party/rnnoise，已 gitignore）
python algo/call-nr/scripts/infer.py --backend rnnoise -i in.wav -o out.wav

# DeepFilterNet3：独立 venv（钉版声明 numpy<2）
pip install 'deepfilternet==0.5.6' 'deepfilterlib==0.5.6'
python algo/call-nr/scripts/infer.py --backend deepfilternet -i in.wav -o out.wav
```

构建 RNNoise demo 需要 `autoconf`、`automake`、`libtool`、`pkg-config`，然后在上游树里执行 `./autogen.sh && ./configure && make`。

### GTCRN（本地权重）

上游：<https://github.com/Xiaobin-Rong/gtcrn>，checkout `502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73`。仓内 `LICENSE` 为 MIT。权重文件名是 `checkpoints/model_trained_on_dns3.tar`（随该 commit 发布，约 580 KB）。本仓不保存这份文件。

```bash
git clone https://github.com/Xiaobin-Rong/gtcrn.git
cd gtcrn
git checkout 502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73
# 若 checkpoints/model_trained_on_dns3.tar 只有一两百字节，那是 Git LFS 指针：
git lfs pull
export GTCRN_ROOT="$PWD"
export CALL_NR_GTCRN_WEIGHTS="$PWD/checkpoints/model_trained_on_dns3.tar"
# 等价别名：export GTCRN_CHECKPOINT="$CALL_NR_GTCRN_WEIGHTS"
pip install torch einops   # 不要装进 CI
# 回到本仓根目录后再跑：
python algo/call-nr/scripts/infer.py --backend gtcrn -i in.wav -o out.wav
```

权重查找顺序（前两项一旦设置就必须指向真实文件，不会再静默改道）：

1. `CALL_NR_GTCRN_WEIGHTS`
2. `GTCRN_CHECKPOINT`
3. `$GTCRN_ROOT/checkpoints/model_trained_on_dns3.tar`
4. `algo/call-nr/third_party/gtcrn/checkpoints/model_trained_on_dns3.tar`（目录已 gitignore）
5. `~/.cache/call-nr/gtcrn/model_trained_on_dns3.tar`

代码查找顺序：`GTCRN_ROOT`，否则 `algo/call-nr/third_party/gtcrn`，否则 `~/.cache/call-nr/gtcrn/repo`（都要有根目录的 `gtcrn.py`）。若目录是 git checkout，`HEAD` 必须等于上面的完整 commit。

缺权重、缺 `gtcrn.py`、或缺少 `torch` / `einops` 时，CLI 退出码 **3**，stderr 写明缺哪一项、钉的 commit、以及该设置的环境变量。

### Silero VAD（本地 pin）

上游：<https://github.com/snakers4/silero-vad>，checkout `066409f3d9db45a30d21dfcbf9147826ffdd7052`。仓内 `LICENSE` 为 MIT。需要 `hubconf.py` 和 `src/silero_vad/data/silero_vad.jit`（约 2 MB；过小的文件会当作 LFS 指针拒绝）。

```bash
git clone https://github.com/snakers4/silero-vad.git
cd silero-vad
git checkout 066409f3d9db45a30d21dfcbf9147826ffdd7052
export SILERO_VAD_ROOT="$PWD"
# 也可以把同一棵树放到 ~/.cache/call-nr/silero-vad/
pip install torch   # 不要装进 CI
# 回到本仓根目录后再跑：
python algo/call-nr/scripts/run_silero_vad.py -i in.wav -o out/vad_probs.csv
# 等价：python algo/call-nr/scripts/infer.py --backend silero_vad -i in.wav -o out/vad_probs.csv
```

成功时写出 `out/vad_probs.csv`（列 `t_sec,speech_prob`）和同目录的 `speech_timestamps.json`。JSON 里的 `timestamps` 是上游 `get_speech_timestamps` 的结果，外加 `pin` 与 `sample_rate_hz`。这不是评测分数。

`SILERO_VAD_ROOT` 一旦设置，就只使用该目录。未设置时再看 `algo/call-nr/third_party/silero-vad` 和 `~/.cache/call-nr/silero-vad`。缺 checkout、缺 JIT 或缺 torch 时退出码 **3**。

## 钉版

| 名称 | 版本 | 引用 | 本仓 |
|------|------|------|------|
| RNNoise | v0.2 | `904a876dce1f9ab8860c0a5000ed151f9f6eef58` | 不内置；`RNNOISE_DEMO` / `RNNOISE_ROOT` |
| DeepFilterNet3 | v0.5.6 | `978576aa8400552a4ce9730838c635aa30db5e61`；`deepfilternet==0.5.6` | 可选 extra，不进默认依赖 |
| GTCRN | `502ebfab` | `502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73` | 不内置；`CALL_NR_GTCRN_WEIGHTS` 或 `GTCRN_CHECKPOINT`，代码 `GTCRN_ROOT` |
| Silero VAD | `v6.2.3-8-g066409f` | `066409f3d9db45a30d21dfcbf9147826ffdd7052` | 不内置；`SILERO_VAD_ROOT` |

`scripts/setup_pins.sh` 只核对 `PLUGIN.json` 里的上述引用。CI 不克隆上游、不下载权重。

## 公私边界

可以在本目录提交的是自研接口、identity 实现和钉版说明。不可以提交：厂商 SDK、调音包、密钥、固件（`.fw`）、闭源音效库、GTCRN / Silero 权重、上游完整树。可选第三方按上游许可证自行构建或安装，不 vendor 进 Git。`.gitignore` 忽略 `algo/call-nr/third_party/`、`*.tar`、`checkpoints/` 和 Silero 的 JIT / ONNX。受限评测仍在 `lxrobertxiong-beep/audio-algo-eval`，不拷进本仓。

注册信息见仓库根的 `control/plugin-registry.example.json`（`local_path` 为 `algo/call-nr`）。
