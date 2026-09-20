# -*- coding: utf-8 -*-
"""
ROS2 真机桥骨架（阶段 5 · 步骤 3）。

设计：
- 实现 BaseRobot.execute_task，载荷仍是同一套 TaskSpec
- 未安装 rclpy / 未初始化 ROS 时，不抛堆栈，返回友好失败或由 bootstrap 回退 mock
- 日后接入点：发布到 ROS_EXECUTE_TOPIC（默认 /robewhisper/execute_task）

本步不强制依赖 ROS 环境，保证普通开发机可运行。
"""

from __future__ import annotations

import json
from typing import Any

from config import settings
from core.schemas import ApiResult, TaskSpec
from plugins.robot.base import BaseRobot

FRIENDLY_BLOCKED = "思考遇到一些阻碍，请稍后再试。"
FRIENDLY_NO_ROS = "当前环境未就绪 ROS2（rclpy），已跳过真机发送。请安装并配置后再试。"


def ros_runtime_available() -> bool:
    """检测本机是否可 import rclpy（不真正 init 节点）。"""
    try:
        import rclpy  # noqa: F401

        return True
    except Exception:
        return False


class RosRobot(BaseRobot):
    """
    ROS2 execute_task 骨架。

    有 rclpy 时：尝试短生命周期节点发布 JSON 字符串（占位实现）。
    无 rclpy 时：execute_task 返回明确失败码，供上层决定是否回退。
    """

    def __init__(
        self,
        topic: str | None = None,
        domain_id: str | None = None,
    ) -> None:
        self._topic = (topic if topic is not None else settings.ROS_EXECUTE_TOPIC).strip() or (
            "/robewhisper/execute_task"
        )
        self._domain_id = (
            domain_id if domain_id is not None else settings.ROS_DOMAIN_ID
        ).strip()
        self._runtime_ok = ros_runtime_available()

    @property
    def name(self) -> str:
        return "ros_robot"

    def execute_task(self, task: TaskSpec) -> ApiResult:
        if not task.action:
            return ApiResult.fail("REJECTED", FRIENDLY_BLOCKED)

        if not self._runtime_ok:
            return ApiResult.fail(
                "INTERNAL",
                FRIENDLY_NO_ROS,
                data={
                    "robot": self.name,
                    "topic": self._topic,
                    "domain_id": self._domain_id,
                    "rclpy": False,
                },
            )

        # 占位：短生命周期发布 std_msgs/String（JSON）
        # 日后可改为自定义 msg / action client，而不改 TaskSpec。
        try:
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import String

            payload: dict[str, Any] = {
                "task_spec": task.to_dict(),
                "source": "robewhisper",
            }
            text = json.dumps(payload, ensure_ascii=False)

            if self._domain_id != "":
                # 仅在进程尚未 init 时设置；失败则忽略，由默认域继续
                try:
                    import os

                    os.environ.setdefault("ROS_DOMAIN_ID", self._domain_id)
                except Exception:
                    pass

            rclpy.init(args=None)
            node: Node | None = None
            try:
                node = Node("robewhisper_execute_bridge")
                pub = node.create_publisher(String, self._topic, 10)
                msg = String()
                msg.data = text
                pub.publish(msg)
                # 给 executor 极短自旋，提高发出概率
                rclpy.spin_once(node, timeout_sec=0.05)
            finally:
                if node is not None:
                    node.destroy_node()
                if rclpy.ok():
                    rclpy.shutdown()

            return ApiResult.success(
                f"ROS2 已向 {self._topic} 发布 action={task.action}",
                data={
                    "accepted": True,
                    "task_id": task.task_id,
                    "robot": self.name,
                    "topic": self._topic,
                    "domain_id": self._domain_id,
                    "rclpy": True,
                },
            )
        except Exception:
            return ApiResult.fail(
                "INTERNAL",
                FRIENDLY_BLOCKED,
                data={"robot": self.name, "topic": self._topic},
            )
