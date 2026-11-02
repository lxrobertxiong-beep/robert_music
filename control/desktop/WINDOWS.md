# Windows：启动本地 control stub

调控台仍是 **API + CLI**（裁定 UI=C）。双击 `launch-stub.bat` 会打开控制台，打印与 `control/README.md` 一致的 curl 用法，并在前台运行 `control/stub_server.py`（`127.0.0.1:8765`）。有图形会话时会用系统默认程序打开 `control/README.md`。

需要本机已安装 Python 3，并且 `python` 或 `py -3` 在 `PATH` 里。启动器只用标准库，不安装 torch，也不下载权重。

## 双击

在资源管理器中双击：

`control\desktop\launch-stub.bat`

关闭该窗口即停止 stub。无界面环境可先设置 `CONTROL_LAUNCHER_NO_OPEN=1`，这样只打印文档路径，不调用默认打开程序。

## 快捷方式（.lnk）

不要把 `.lnk` 提交进 Git。快捷方式里是这台机器的绝对路径，而且不是方便审阅的文本。在资源管理器里生成即可：

1. 右键 `launch-stub.bat`
2. 「显示更多选项」（若需要）→「发送到」→「桌面快捷方式」

或：桌面右键 → 新建 → 快捷方式。

- 目标：`C:\path\to\robert_music\control\desktop\launch-stub.bat`
- 起始位置：仓库根（bat 自己会切到 `control\desktop`，起始位置只影响你从快捷方式里看到的相对路径）

把生成的 `.lnk` 留在桌面或开始菜单。它和 Linux 的 `.desktop` 一样，只负责启动同一个 stub 并指向文档 / CLI。
