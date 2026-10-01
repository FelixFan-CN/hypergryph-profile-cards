#!/usr/bin/env bash
# 下载渲染中文字所需的思源黑体到字体目录。
# 已存在就跳过，因此配合 actions/cache 可以做到只在首次下载。
set -euo pipefail

FONT_DIR="${FONT_DIR:-${PROFILE_CARDS_FONT_DIR:-}}"
if [ -z "$FONT_DIR" ]; then
  echo "FONT_DIR 未设置，跳过字体准备" >&2
  exit 0
fi

mkdir -p "$FONT_DIR"

BASE="https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC"
for name in NotoSansSC-Bold.otf NotoSansSC-Regular.otf; do
  target="$FONT_DIR/$name"
  if [ -s "$target" ]; then
    continue
  fi
  echo "下载字体 $name"
  curl -fsSL -o "$target" "$BASE/$name"
done

echo "字体已就绪：$FONT_DIR"