"""运行上下文：路径、环境、过滤条件等与外观无关的运行参数。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass
class RunContext:
    root: str
    assets_dir: str = "assets"
    output_dir: str | None = None
    only: tuple[str, ...] = ()
    strict: bool = False
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def resolve_assets_root(self) -> str:
        """底图目录：相对路径基于仓库根解析。"""
        if os.path.isabs(self.assets_dir):
            return self.assets_dir
        return os.path.join(self.root, self.assets_dir)

    def resolve_output(self, output: str) -> str:
        """产物路径：output_dir 覆盖时只取文件名。"""
        if self.output_dir:
            base = (
                self.output_dir
                if os.path.isabs(self.output_dir)
                else os.path.join(self.root, self.output_dir)
            )
            return os.path.join(base, os.path.basename(output))
        return output if os.path.isabs(output) else os.path.join(self.root, output)

    def env_value(self, name: str) -> str:
        return (self.env.get(name) or "").strip()
