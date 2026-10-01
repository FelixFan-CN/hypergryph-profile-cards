# hypergryph-profile-cards

把《明日方舟》与《明日方舟：终末地》的玩家数据渲染成个人主页名片，每天自动刷新。

![示例](docs/example-arknights.png)

> 上图用的底图是仓库自带的合成测试图。换成你自己的游戏立绘后就是成品效果。

- **外观全部可配置**：画布尺寸、每个元素的坐标与字号、文字颜色与透明度、渐隐遮罩、投影、毛玻璃、字体、底图裁切锚点——都在一个 YAML 里，不用改代码。
- **一次配置，每天自动更新**：GitHub Actions 定时拉数据、重新渲染、commit 回仓库。
- **两种用法**：加 5 行 workflow 引用本 Action，或者把模板仓库复制一份自己改。

## 快速开始

**1. 建一个与你用户名同名的仓库**

仓库名必须是 `你的用户名/你的用户名`，GitHub 才会把它的 README 显示在你的主页上。

**2. 放入配置与底图**

```text
你的仓库/
├── profile-cards.yaml        # 配置（从 templates/profile-repo/ 复制）
├── assets/
│   ├── arknights-bg.png      # 明日方舟底图（自备，建议 3:1）
│   └── endfield-bg.png       # 终末地底图（自备）
└── .github/workflows/
    └── profile-cards.yml     # workflow
```

**3. 打开 Actions 写权限**

仓库 Settings → Actions → General → Workflow permissions 选 **Read and write permissions**，否则 Action 无法把生成的名片提交回来。

然后手动触发一次 workflow，或在本地跑：

```bash
pip install -r requirements.txt
python -m hypergryph_profile_cards
```

### 关于凭证

| 游戏 | 需要什么 | 怎么拿 |
| --- | --- | --- |
| 明日方舟 | 仓库 Secret `SKLAND_TOKEN` | 见下方「获取森空岛 token」 |
| 终末地 | 只要 UID，无需凭证 | 游戏内或森空岛绑定列表里的 9 位 UID |

`SKLAND_TOKEN` 等同你的账号登录态，**只能放 GitHub Secrets，绝不要写进配置文件或提交到仓库**。

<details>
<summary>获取森空岛 token</summary>

```bash
python -m hypergryph_profile_cards.tools.get_token password   # 手机号 + 密码
python -m hypergryph_profile_cards.tools.get_token code       # 手机号 + 短信验证码
```

拿到 token 后写进 Secret：

```bash
gh secret set SKLAND_TOKEN --repo 你的用户名/你的用户名 --body "<token>"
```

重新登录森空岛会让旧 token 失效，届时重新执行一次即可。

</details>

## 用法一：引用本 Action

```yaml
name: Update profile cards
on:
  schedule: [{ cron: "17 20 * * *" }]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  cards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: FelixFan-CN/hypergryph-profile-cards@v1
        env:
          SKLAND_TOKEN: ${{ secrets.SKLAND_TOKEN }}
        with:
          config: profile-cards.yaml
          commit: true
```

> `v1` 是浮动标签，始终指向最新的 v1.x。生产环境建议换成完整版本号（如 `v1.0.0`）或具体 commit SHA，避免上游更新带来的意外变化。

**输入**

| 输入 | 默认值 | 说明 |
| --- | --- | --- |
| `config` | `profile-cards.yaml` | 配置文件路径（相对 `root`） |
| `root` | 工作区根目录 | 底图、产物与配置的解析基准 |
| `assets-dir` | `assets` | 底图所在目录 |
| `output-dir` | 空 | 产物目录；留空则沿用配置里的 `output` |
| `python-version` | `3.12` | 使用的 Python 版本 |
| `only` | 空 | 只渲染指定卡片 id，逗号分隔 |
| `strict` | `false` | 任意一张卡失败就让步骤失败 |
| `cache-fonts` | `true` | 缓存中文字体 |
| `commit` | `false` | 由本 Action 提交产物 |
| `commit-message` | `chore: update profile cards` | 提交信息 |
| `commit-paths` | 空 | `git add` 的路径 |

**输出**：`produced`、`failed`、`skipped`、`changed`、`summary`。

## 用法二：模板仓库

把 [`templates/profile-repo/`](templates/profile-repo/) 复制成你自己的仓库，`requirements.txt` 里已经写好了对本项目的依赖。想深度定制主题、锁定版本、或改动数据层时用这种方式。

## 配置

配置文件按以下顺序查找：`profile-cards.yaml` → `.yml` → `.json` → `config.json`。

**想知道有哪些可配置项，不用翻文档**：

```bash
python -m hypergryph_profile_cards --print-config
```

它会打印合并了预设之后的**完整生效配置**，复制回去改任意一处即可。想快速起步则用 `--init`。

### 卡片

```yaml
version: 1

cards:
  - id: arknights              # 决定底图文件名（{id}-bg.*）
    title: 明日方舟             # 日志与摘要里显示的名字
    enabled: true
    uid: "${ARKNIGHTS_UID:-}"  # 支持环境变量插值；留空会自动取绑定列表里的默认角色
    output: assets/arknights-card.png
    options:
      six_star_rarity_index: 5 # 星级不低于该值即计入「六星」，改成 4 就是五星及以上
      elite_two_phase: 2       # 精英二所需的阶段
    theme_overrides: {}        # 只给这张卡覆盖主题，见「主题」
    stats:                     # 顺序即展示顺序
      - { field: register_days,   label: 入职天数 }
      - { template: "{ap_current} / {ap_max}", label: 当前理智 }
```

`stats` 每一项：

| 键 | 说明 |
| --- | --- |
| `field` | 可取字段名，见下表 |
| `template` | 组合多个字段，如 `"{ap_current} / {ap_max}"`；只支持 `{字段}` 占位符 |
| `label` | 数字下方的小标签 |
| `prefix` / `suffix` | 前后缀，如 `suffix: " 名"` |
| `format` | `number` / `text` |
| `thousands` | 数字是否加千分位 |
| `hide_if_empty` | 取不到值时是否隐藏这一格，默认 `true` |

### 可用字段

<details>
<summary>明日方舟（<code>id: arknights</code>）</summary>

`nickname` `level` `uid` `register_days` `main_stage` `ap` `ap_current` `ap_max`
`operator_count` `six_star_count` `elite_two_count` `skin_count` `furniture_count`
`daily` `weekly`

</details>

<details>
<summary>终末地（<code>id: endfield</code>）</summary>

`nickname` `level` `world_level` `signature` `short_id` `uid` `play_days`
`main_mission` `domain_level` `character_count` `weapon_count` `doc_count`
`achievement` `showcase_count`

</details>

### 主题

主题可以只写要改的键，其余继承预设。

```yaml
theme:
  preset: hoyocard              # 目前内置这一个预设，等价于默认外观
  canvas: { width: 1200, height: 400 }
  text_color: "#FFFFFF"         # 也支持 [255, 255, 255]
  shadow: { enabled: true, alpha: 200, offset: [2, 2] }
  fonts:
    candidates:
      - { bold: fonts/NotoSansSC-Bold.otf, regular: fonts/NotoSansSC-Regular.otf }
  background:
    anchor: right               # left | center | right，决定多余部分从哪边裁掉
    paths: ["{id}-bg.png", "{id}-bg.jpg"]
    fallback_gradient: { top: [30, 34, 40], bottom: [12, 16, 22] }
  slots:
    name:       { x: 40, y: 30, size: 40, bold: true, alpha: 255, empty: "未知" }
    level:      { size: 22, bold: true, alpha: 215, prefix: "Lv.", anchor: name_right, gap: 12, dy: 16 }
    uid:        { x: 40, y: 88, size: 18, alpha: 180, prefix: "UID: " }
    stat_value: { x: 40, y: 282, size: 42, bold: true, alpha: 255, column_width: 152 }
    stat_label: { x: 40, y: 342, size: 22, alpha: 185, column_width: 152 }
  overlays:
    left_fade:   { enabled: true, stops: [[0.0, 0.80], [0.42, 0.52], [0.75, 0.12], [1.0, 0.03]] }
    bottom_fade: { enabled: true, stops: [[0.0, 0.72], [0.20, 0.38], [0.52, 0.0]] }
    blur:        { enabled: false, radius: 12, region: [0, 0, 760, 400] }
```

几个要点：

- `slots` 里的 `x` / `y` 是左上角坐标；`alpha` 是文字不透明度（0-255）。
- `level` 用 `anchor: name_right` 表示紧跟在昵称右侧，`gap` 是间距，`dy` 是相对昵称的纵向偏移。
- `overlays.*.stops` 是 `[位置比例, 不透明度]` 列表。`left_fade` 从左边 0 到右边 1；`bottom_fade` 从底部 0 到顶部 1。
- `blur` 是毛玻璃，默认关闭。打开后只对 `region` 区域做高斯模糊，其余部分保持清晰。
- `background.anchor` 决定底图比例不是 3:1 时裁哪边。主体在右侧就用 `right`。
- 每张卡可以用 `theme_overrides` 单独覆盖任意主题键。

更多示例见 [`examples/`](examples/)：`minimal` 是 6 行起步配置，`advanced` 演示了改画布、换配色、关遮罩、开毛玻璃、组合字段、按卡覆盖主题。

## 支持的游戏

| id | 游戏 | 数据来源 | 需要凭证 |
| --- | --- | --- | --- |
| `arknights` | 明日方舟 | 森空岛（非官方接口） | `SKLAND_TOKEN` |
| `endfield` | 明日方舟：终末地 | [Enka.Network](https://enka.network/?ef) | 无，只要 UID |

目前这两款是内置的。要接入别的游戏需要改数据层代码——`src/hypergryph_profile_cards/fetch/` 下每个模块负责一款游戏，新增模块后在 `orchestrator.py` 的 `COLLECTORS` 里登记即可；外观部分不需要动。

## 故障排查

| 现象 | 原因与处理 |
| --- | --- |
| 日志出现「未找到底图」，卡片变成纯色 | `assets/{id}-bg.png` 不存在或文件名不对。底图必须提交进仓库，CI 才能取到 |
| 中文显示成方块或报找不到字体 | 字体没准备好。本地可删掉 `theme.fonts.candidates` 里不存在的项，或按报错提示下载思源黑体到 `fonts/` |
| 明日方舟那张显示「跳过：未配置 SKLAND_TOKEN」 | Secret 没设置或名字不对 |
| 森空岛返回「设备信息无效」 | 签名相关的可变常量需要更新，见 `skland/client.py` 顶部注释 |
| Enka 返回 429 | 第三方服务限流，稍后重试即可；只有该张卡受影响 |
| Action 跑完但主页图片没变 | 检查 Settings → Actions → General 是否给了 Read and write 权限 |

## FAQ

**会被封号吗？**
本项目只读取公开的个人资料数据，不涉及登录游戏、不改动任何账号状态。但它使用的是非官方接口，风险请自行判断。

**能不能不提交到仓库？**
可以。把 `commit` 留空或设为 `false`，然后用 `output-dir` 指定别的路径，自己处理产物。

**能用私有仓库吗？**
可以，但主页 README 必须是公开仓库才能显示，所以通常做法是公开仓库放 README 与图片。

**底图有什么要求？**
建议 3:1（如 1200×400），主体放在右侧。其它比例也能用，会按 `background.anchor` 裁切。

## 开发

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest
```

`tests/baseline/` 里保存了重构前的像素基线，用来保证默认外观不被意外改坏。该比对只在装有微软雅黑的机器上执行（字体栅格化跨平台不一致），其余断言跨平台通用。

## 许可与声明

代码以 [MIT](LICENSE) 授权。

**本项目不包含任何游戏素材。** 示例图与测试底图均由 `tests/make_fixtures.py` 程序化生成。《明日方舟》《明日方舟：终末地》及其角色立绘、图标、名称的版权归鹰角网络（Hypergryph）及相关权利人所有，MIT 授权不覆盖这些内容。若你在自己的仓库里使用官方素材，请自行判断并承担相应风险。

**接口可用性**：森空岛为鹰角非公开接口，签名算法与字段可能随时变更；Enka.Network 是第三方社区服务，可能限流、变更或停止服务。本项目不提供可用性承诺。

**账号安全**：`SKLAND_TOKEN` 等同登录态，请只放在 GitHub Secrets 中。因接口变更、限流或账号处置造成的任何后果由使用者自负。