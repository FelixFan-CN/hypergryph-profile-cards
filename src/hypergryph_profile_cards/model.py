"""配置对应的数据模型。

渲染层只接受这里的对象，不读全局常量、不读 YAML、不联网，
因此可以纯函数式地单测。
"""

from __future__ import annotations

from dataclasses import dataclass, field


def parse_color(value, path: str = "color") -> tuple[int, int, int]:
    """接受 "#RRGGBB" 或 [r, g, b]，统一成 RGB 元组。"""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    raise ValueError(f"{path} 需要是 #RRGGBB 或 [r, g, b]，当前为 {value!r}")


# ---------- 主题 ----------


@dataclass(frozen=True)
class FontPair:
    """一组字体：粗体与常规体各一个文件路径。"""

    bold: str
    regular: str

    @classmethod
    def from_dict(cls, data: dict) -> FontPair:
        return cls(bold=str(data["bold"]), regular=str(data["regular"]))


@dataclass(frozen=True)
class TextSlot:
    """一个文字元素的定位与样式。

    anchor 为 None 时按 (x, y) 绝对定位；
    为 "name_right" 时表示紧跟在昵称右侧（用 gap 控制间距、dy 微调基线），
    用于复现「缄雨默#7160 Lv.105」这种联动排版。
    """

    x: float = 0.0
    y: float = 0.0
    size: int = 20
    bold: bool = False
    alpha: int = 255
    prefix: str = ""
    empty: str = ""
    anchor: str | None = None
    gap: float = 0.0
    dy: float = 0.0
    column_width: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> TextSlot:
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            size=int(data.get("size", 20)),
            bold=bool(data.get("bold", False)),
            alpha=int(data.get("alpha", 255)),
            prefix=str(data.get("prefix", "")),
            empty=str(data.get("empty", "")),
            anchor=data.get("anchor"),
            gap=float(data.get("gap", 0.0)),
            dy=float(data.get("dy", 0.0)),
            column_width=(
                None if data.get("column_width") is None else float(data["column_width"])
            ),
        )


@dataclass(frozen=True)
class FadeOverlay:
    """单向渐隐遮罩。(位置比例, 不透明度[0-1]) 的列表。"""

    enabled: bool = True
    color: tuple[int, int, int] = (0, 0, 0)
    stops: tuple[tuple[float, float], ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> FadeOverlay:
        return cls(
            enabled=bool(data.get("enabled", True)),
            color=parse_color(data.get("color", (0, 0, 0)), "overlays.*.color"),
            stops=tuple((float(p), float(a)) for p, a in data.get("stops", ())),
        )


@dataclass(frozen=True)
class BlurOverlay:
    """局部高斯模糊（毛玻璃）。默认关闭。"""

    enabled: bool = False
    radius: int = 12
    region: tuple[int, int, int, int] = (0, 0, 0, 0)

    @classmethod
    def from_dict(cls, data: dict) -> BlurOverlay:
        region = data.get("region") or (0, 0, 0, 0)
        return cls(
            enabled=bool(data.get("enabled", False)),
            radius=int(data.get("radius", 12)),
            region=tuple(int(v) for v in region),
        )


@dataclass(frozen=True)
class BackgroundSpec:
    """底图探测与缩放裁切规则。"""

    anchor: str = "right"
    paths: tuple[str, ...] = ()
    fallback_top: tuple[int, int, int] = (30, 30, 40)
    fallback_bottom: tuple[int, int, int] = (12, 16, 20)

    @classmethod
    def from_dict(cls, data: dict) -> BackgroundSpec:
        gradient = data.get("fallback_gradient") or {}
        return cls(
            anchor=str(data.get("anchor", "right")),
            paths=tuple(str(p) for p in data.get("paths", ())),
            fallback_top=tuple(gradient.get("top", (30, 30, 40))),
            fallback_bottom=tuple(gradient.get("bottom", (12, 16, 20))),
        )


@dataclass(frozen=True)
class Theme:
    """一张卡片的全部外观参数。"""

    width: int = 1200
    height: int = 400
    text_color: tuple[int, int, int] = (255, 255, 255)
    shadow_enabled: bool = True
    shadow_alpha: int = 200
    shadow_offset: tuple[int, int] = (2, 2)
    fonts: tuple[FontPair, ...] = ()
    font_dir: str | None = None
    background: BackgroundSpec = field(default_factory=BackgroundSpec)
    slots: dict[str, TextSlot] = field(default_factory=dict)
    left_fade: FadeOverlay = field(default_factory=FadeOverlay)
    bottom_fade: FadeOverlay = field(default_factory=FadeOverlay)
    blur: BlurOverlay = field(default_factory=BlurOverlay)

    def slot(self, name: str) -> TextSlot:
        if name not in self.slots:
            raise KeyError(f"主题缺少文字槽位：{name}")
        return self.slots[name]


# ---------- 卡片 ----------


@dataclass(frozen=True)
class StatSpec:
    """一个统计项：取哪个字段、用什么标签、怎么格式化。"""

    label: str
    field: str | None = None
    template: str | None = None
    prefix: str = ""
    suffix: str = ""
    format: str = "number"  # number | text | template
    thousands: bool = False
    hide_if_empty: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> StatSpec:
        if not data.get("field") and not data.get("template"):
            raise ValueError("stats 条目必须提供 field 或 template")
        return cls(
            label=str(data.get("label", "")),
            field=data.get("field"),
            template=data.get("template"),
            prefix=str(data.get("prefix", "")),
            suffix=str(data.get("suffix", "")),
            format=str(data.get("format", "number")),
            thousands=bool(data.get("thousands", False)),
            hide_if_empty=bool(data.get("hide_if_empty", True)),
        )


@dataclass(frozen=True)
class CardSpec:
    """一张卡片：身份信息 + 展示项 + 该卡生效的主题。"""

    id: str
    title: str
    output: str
    theme: Theme
    enabled: bool = True
    uid: str = ""
    stats: tuple[StatSpec, ...] = ()
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CardValues:
    """渲染一张卡所需的全部数据（已格式化，渲染层不再做业务判断）。"""

    nickname: str
    level_text: str
    uid_text: str
    stats: tuple[tuple[str, str], ...] = ()
