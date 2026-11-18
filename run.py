"""拾记 Recall Card 桌面启动入口。

双击 exe 之后：
1. 在本机找一个空闲端口启动服务；
2. 等页面能访问了，自动打开默认浏览器；
3. 这个黑窗口就是程序本体，关掉它程序就退出。

命令行参数：
  --port 端口    指定端口
  --no-browser   不自动打开浏览器
"""

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

DEFAULT_PORT = 8765
HOST = "127.0.0.1"

BANNER = r"""
  ____                _      ____            _
 |  _ \ ___  ___ __ _| |    / ___|__ _ _ __ | |_
 | |_) / _ \/ __/ _` | |   | |   / _` | '_ \| __|
 |  _ <  __/ (_| (_| | |   | |__| (_| | | | | |_
 |_| \_\___|\___\__,_|_|    \____\__,_|_| |_|\__|
"""


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((HOST, port)) == 0


def _pick_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        if not _port_open(port):
            return port
    raise SystemExit("没有找到可用端口，请关闭其他程序后重试。")


def _wait_ready(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    url = f"http://{HOST}:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def _open_when_ready(port: int) -> None:
    if _wait_ready(port):
        webbrowser.open(f"http://{HOST}:{port}/")


def main() -> None:
    args = sys.argv[1:]
    no_browser = "--no-browser" in args
    preferred = DEFAULT_PORT
    if "--port" in args:
        index = args.index("--port")
        if index + 1 < len(args):
            preferred = int(args[index + 1])

    # 已经开着就不再启动第二个实例，直接打开页面
    if _port_open(preferred) and _wait_ready(preferred, timeout=2.0):
        if not no_browser:
            webbrowser.open(f"http://{HOST}:{preferred}/")
        print(f"拾记已经在运行：http://{HOST}:{preferred}/", flush=True)
        return

    port = _pick_port(preferred)

    print(BANNER, flush=True)
    print("  拾记 Recall Card 已启动", flush=True)
    print(f"  地址：http://{HOST}:{port}/", flush=True)
    print(f"  数据保存在：{_data_dir_hint()}", flush=True)
    print("  用完直接关闭这个窗口即可。", flush=True)
    print(flush=True)

    if not no_browser:
        threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()

    try:
        from backend.main import app

        uvicorn.run(app, host=HOST, port=port, log_level="warning", access_log=False)
    except KeyboardInterrupt:
        pass
    finally:
        print("拾记已退出。", flush=True)


def _data_dir_hint() -> str:
    try:
        from backend.config import Settings

        return str(Settings().data_dir)
    except Exception:
        return os.environ.get("LOCALAPPDATA", ".") + os.sep + "RecallCard"


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # 双击运行时窗口一闪而过最让人懵，出错时停住等用户看完再关
        import traceback

        traceback.print_exc()
        try:
            input("\n启动失败，把上面的错误发给开发者。按回车键退出…")
        except Exception:
            pass
