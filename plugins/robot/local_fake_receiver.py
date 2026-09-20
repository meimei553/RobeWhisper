# -*- coding: utf-8 -*-
"""
本地假接收端（第 11 期 · 步骤 2；第 12 期 · 步骤 2 可选回传轨迹）

仅联调用：接收 HttpRobot 的 POST，校验最小契约，回 {ok, message}。
默认不随 Streamlit 启动；需手动：

  python -m plugins.robot.local_fake_receiver
  # 指定端口：python -m plugins.robot.local_fake_receiver --port 9000
  # 第12期验真轨迹优先：加 --with-trajectory（回传合格演示轨迹，不是真臂）

实验室真节点未就绪时，用本脚本验收「软件侧能真发通」；
加 --with-trajectory 时可在本机验收「RSR 吃到真轨迹来源」。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_PATH = "/execute_task"


def build_demo_robot_trajectory(
    payload: dict[str, Any] | None = None,
    *,
    frames: int = 4,
    joint_dim: int = 2,
) -> list[dict[str, Any]]:
    """
    造一条形状合格的演示轨迹（供 --with-trajectory）。
    优先用 task_spec.suggested_joint_targets 作起点；否则用固定短序列。
    注意：这是假接收端演示数据，不是实验室真臂采样。
    """
    spec = (payload or {}).get("task_spec") if isinstance(payload, dict) else None
    if not isinstance(spec, dict):
        spec = {}

    base: list[float] = []
    raw_joints = spec.get("suggested_joint_targets")
    if isinstance(raw_joints, list) and raw_joints:
        for x in raw_joints[:64]:
            try:
                base.append(float(x))
            except (TypeError, ValueError):
                base.append(0.0)
    if not base:
        dim = max(1, min(int(joint_dim), 64))
        base = [0.1 + 0.05 * i for i in range(dim)]

    n = max(1, min(int(frames), 200))
    out: list[dict[str, Any]] = []
    for i in range(n):
        scale = 1.0 + 0.02 * i
        joints = [float(x) * scale + 0.01 * i for x in base]
        out.append({"t": float(i), "joint_positions": joints})
    return out


def _make_handler(
    path: str = DEFAULT_PATH,
    *,
    with_trajectory: bool = False,
) -> type[BaseHTTPRequestHandler]:
    """生成请求处理器；可注入到 HTTPServer，供烟雾测试复用。"""

    class FakeRobotHandler(BaseHTTPRequestHandler):
        # 最近一次请求体（烟雾断言用）
        last_body: bytes = b""
        last_path: str = ""
        last_ack: dict[str, Any] = {}
        # 是否回传演示轨迹（由工厂在类创建后写入，勿在注解默认里引用外层参数）
        with_trajectory = False

        def do_POST(self) -> None:  # noqa: N802
            from core.robot_bridge_contract import (
                normalize_execute_ack,
                validate_execute_request,
            )

            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            FakeRobotHandler.last_body = raw
            FakeRobotHandler.last_path = self.path

            # 路径宽松：精确匹配或任意以 execute_task 结尾均可
            parsed = urlparse(self.path)
            path_ok = parsed.path == path or parsed.path.rstrip("/").endswith("execute_task")

            payload: dict[str, Any]
            try:
                loaded = json.loads(raw.decode("utf-8") if raw else "{}")
                payload = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError:
                payload = {}

            if not path_ok:
                ack = {"ok": False, "message": f"路径不支持：{self.path}，请 POST 到 {path}"}
            else:
                ok, msg = validate_execute_request(payload)
                if ok:
                    action = str((payload.get("task_spec") or {}).get("action") or "")
                    if FakeRobotHandler.with_trajectory:
                        ack = {
                            "ok": True,
                            "message": (
                                f"假接收端已确认 action={action}"
                                "（含演示轨迹，非真臂采样）"
                            ),
                            "trajectory": build_demo_robot_trajectory(payload),
                        }
                    else:
                        # 第11期默认：只回 ok/message，无 trajectory → RSR 走伪对照保底
                        ack = {
                            "ok": True,
                            "message": f"假接收端已确认 action={action}",
                        }
                else:
                    ack = {"ok": False, "message": f"契约校验失败：{msg}"}

            # 统一走 normalize，保证字段形状与契约一致
            ack = normalize_execute_ack(ack)
            FakeRobotHandler.last_ack = ack

            body = json.dumps(ack, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            # 只读探测：步骤4可能用；不执行动作
            tip = {
                "ok": True,
                "message": "假接收端在线（GET 仅探测，请用 POST /execute_task）",
                "service": "robewhisper_local_fake_receiver",
                "with_trajectory": bool(FakeRobotHandler.with_trajectory),
            }
            body = json.dumps(tip, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            # 联调时可看控制台；默认安静一点，只打一行摘要
            try:
                print(f"[fake-robot] {args[0]}")
            except Exception:
                return

    FakeRobotHandler.with_trajectory = bool(with_trajectory)
    return FakeRobotHandler


def start_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    *,
    daemon_thread: bool = False,
    with_trajectory: bool = False,
) -> tuple[ThreadingHTTPServer, threading.Thread | None, type[BaseHTTPRequestHandler]]:
    """
    启动假接收端。
    返回 (server, thread|None, handler_cls)；烟雾可用 handler_cls.last_body 断言。
    daemon_thread=True 时在后台线程 serve；False 则由调用方自行 serve_forever。
    with_trajectory=True 时成功响应带合格演示轨迹（第12期）。
    """
    handler_cls = _make_handler(path, with_trajectory=with_trajectory)
    server = ThreadingHTTPServer((host, port), handler_cls)
    if daemon_thread:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, handler_cls
    return server, None, handler_cls


def endpoint_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, path: str = DEFAULT_PATH) -> str:
    """拼出 ROBOT_EXECUTE_ENDPOINT 用的完整 URL。"""
    p = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{port}{p}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="RobeWhisper 本地假接收端（联调专用）")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口，默认 9000")
    parser.add_argument("--path", default=DEFAULT_PATH, help="路径，默认 /execute_task")
    parser.add_argument(
        "--with-trajectory",
        action="store_true",
        help="成功时回传合格演示轨迹（第12期验真轨迹优先；不是真臂）",
    )
    args = parser.parse_args(argv)

    url = endpoint_url(args.host, args.port, args.path)
    print("假接收端已启动（本机假装的接收端，只测软件通不通，不会动真机械臂）")
    if args.with_trajectory:
        print("已开 --with-trajectory：成功响应会带演示轨迹（供 RSR 走真轨迹来源）")
    else:
        print("默认不回轨迹：勾选 RSR 时会走伪对照保底（与第11期一致）")
    print("请用记事本改项目里的 .env，填下面三行，然后重启网站：")
    print("  USE_REAL_ROBOT=true")
    print("  ROBOT_BACKEND=http")
    print(f"  ROBOT_EXECUTE_ENDPOINT={url}")
    print("停止本窗口：按 Ctrl+C")
    print("演示结束后请改回：USE_REAL_ROBOT=false 且 ROBOT_BACKEND=mock，再重启网站")

    server, _, _ = start_server(
        args.host,
        args.port,
        args.path,
        daemon_thread=False,
        with_trajectory=bool(args.with_trajectory),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止假接收端")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
