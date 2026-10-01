**English** | [简体中文](README.zh-CN.md)

# hypergryph-profile-cards

Render your *Arknights* and *Arknights: Endfield* player data into a profile card, refreshed every day.

![Example](docs/example-arknights.png)

> The background in the image above is a synthetic test image bundled with the repo. Swap in your own game artwork and you get the finished look.

- **Everything visual is configurable**: canvas size, the position and font size of every element, text color and opacity, fade overlays, drop shadow, blur, fonts, background crop anchor — all in a single YAML file, no code changes.
- **Configure once, update daily**: GitHub Actions fetches the data, re-renders, and commits the result back to your repo on a schedule.
- **Two ways to use it**: add a 5-line workflow that references this Action, or copy the template repo and make it your own.

## Quick start

**1. Create a repo named after your username**

The repo must be named `your-username/your-username` for GitHub to show its README on your profile.

**2. Add the config and backgrounds**

```text
your-repo/
├── profile-cards.yaml        # config (copy from templates/profile-repo/)
├── assets/
│   ├── arknights-bg.png      # Arknights background (bring your own, 3:1 recommended)
│   └── endfield-bg.png       # Endfield background (bring your own)
└── .github/workflows/
    └── profile-cards.yml     # workflow
```

**3. Enable write permissions for Actions**

Repo Settings → Actions → General → Workflow permissions → select **Read and write permissions**, otherwise the Action cannot commit the generated cards back.

Then trigger the workflow manually, or run it locally:

```bash
pip install -r requirements.txt
python -m hypergryph_profile_cards
```

### About credentials

| Game | What you need | How to get it |
| --- | --- | --- |
| Arknights | Repo secret `SKLAND_TOKEN` | See "Getting a Skland token" below |
| Endfield | UID only, no credentials | The 9-digit UID in-game or in your Skland binding list |

`SKLAND_TOKEN` is equivalent to your account login session — **store it in GitHub Secrets only, never put it in a config file or commit it to your repo**.

<details>
<summary>Getting a Skland token</summary>

```bash
python -m hypergryph_profile_cards.tools.get_token password   # phone number + password
python -m hypergryph_profile_cards.tools.get_token code       # phone number + SMS code
```

Once you have the token, write it to a secret:

```bash
gh secret set SKLAND_TOKEN --repo your-username/your-username --body "<token>"
```

Signing in to Skland again invalidates the old token, so just re-run this when that happens.

</details>

## Usage 1: Reference this Action

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

> `v1` is a floating tag that always points to the latest v1.x. For production, pin a full version (e.g. `v1.0.0`) or a specific commit SHA to avoid surprises from upstream updates.

**Inputs**

| Input | Default | Description |
| --- | --- | --- |
| `config` | `profile-cards.yaml` | Config file path (relative to `root`) |
| `root` | Workspace root | Base directory used to resolve backgrounds, output and config |
| `assets-dir` | `assets` | Directory containing backgrounds |
| `output-dir` | empty | Output directory; when empty, the `output` from the config is used |
| `python-version` | `3.12` | Python version to use |
| `only` | empty | Render only the given card ids, comma-separated |
| `strict` | `false` | Fail the step if any card fails |
| `cache-fonts` | `true` | Cache the CJK font |
| `commit` | `false` | Let this Action commit the output |
| `commit-message` | `chore: update profile cards` | Commit message |
| `commit-paths` | empty | Paths passed to `git add` |

**Outputs**: `produced`, `failed`, `skipped`, `changed`, `summary`.

## Usage 2: Template repo

Copy [`templates/profile-repo/`](templates/profile-repo/) into your own repo — its `requirements.txt` already depends on this project. Use this route when you want to deeply customize the theme, pin a version, or change the data layer.

## Configuration

The config file is looked up in this order: `profile-cards.yaml` → `.yml` → `.json` → `config.json`.

**To see every available option without digging through the docs**:

```bash
python -m hypergryph_profile_cards --print-config
```

It prints the **fully merged, effective config** after presets are applied — copy it back and edit any part of it. For a quick start, use `--init`.

### Cards

```yaml
version: 1

cards:
  - id: arknights              # determines the background filename ({id}-bg.*)
    title: Arknights           # name shown in logs and the summary
    enabled: true
    uid: "${ARKNIGHTS_UID:-}"  # supports env var interpolation; when empty, the default role from the binding list is used
    output: assets/arknights-card.png
    options:
      six_star_rarity_index: 5 # rarity >= this value counts as a "6-star"; set it to 4 for 5-star and above
      elite_two_phase: 2       # phase required for Elite 2
    theme_overrides: {}        # override the theme for this card only, see "Theme"
    stats:                     # order is the display order
      - { field: register_days,   label: Days since joined }
      - { template: "{ap_current} / {ap_max}", label: Current sanity }
```

Each entry in `stats`:

| Key | Description |
| --- | --- |
| `field` | A field name, see the table below |
| `template` | Combine multiple fields, e.g. `"{ap_current} / {ap_max}"`; only `{field}` placeholders are supported |
| `label` | The small label under the number |
| `prefix` / `suffix` | Prefix and suffix, e.g. `suffix: " ops"` |
| `format` | `number` / `text` |
| `thousands` | Whether to add thousands separators to numbers |
| `hide_if_empty` | Whether to hide this cell when the value is missing; default `true` |

### Available fields

<details>
<summary>Arknights (<code>id: arknights</code>)</summary>

`nickname` `level` `uid` `register_days` `main_stage` `ap` `ap_current` `ap_max`
`operator_count` `six_star_count` `elite_two_count` `skin_count` `furniture_count`
`daily` `weekly`

</details>

<details>
<summary>Endfield (<code>id: endfield</code>)</summary>

`nickname` `level` `world_level` `signature` `short_id` `uid` `play_days`
`main_mission` `domain_level` `character_count` `weapon_count` `doc_count`
`achievement` `showcase_count`

</details>

### Theme

A theme only needs the keys you want to change; everything else inherits from the preset.

```yaml
theme:
  preset: hoyocard              # currently the only built-in preset, equivalent to the default look
  canvas: { width: 1200, height: 400 }
  text_color: "#FFFFFF"         # [255, 255, 255] is also accepted
  shadow: { enabled: true, alpha: 200, offset: [2, 2] }
  fonts:
    candidates:
      - { bold: fonts/NotoSansSC-Bold.otf, regular: fonts/NotoSansSC-Regular.otf }
  background:
    anchor: right               # left | center | right — which side the overflow is cropped from
    paths: ["{id}-bg.png", "{id}-bg.jpg"]
    fallback_gradient: { top: [30, 34, 40], bottom: [12, 16, 22] }
  slots:
    name:       { x: 40, y: 30, size: 40, bold: true, alpha: 255, empty: "Unknown" }
    level:      { size: 22, bold: true, alpha: 215, prefix: "Lv.", anchor: name_right, gap: 12, dy: 16 }
    uid:        { x: 40, y: 88, size: 18, alpha: 180, prefix: "UID: " }
    stat_value: { x: 40, y: 282, size: 42, bold: true, alpha: 255, column_width: 152 }
    stat_label: { x: 40, y: 342, size: 22, alpha: 185, column_width: 152 }
  overlays:
    left_fade:   { enabled: true, stops: [[0.0, 0.80], [0.42, 0.52], [0.75, 0.12], [1.0, 0.03]] }
    bottom_fade: { enabled: true, stops: [[0.0, 0.72], [0.20, 0.38], [0.52, 0.0]] }
    blur:        { enabled: false, radius: 12, region: [0, 0, 760, 400] }
```

A few notes:

- `x` / `y` inside `slots` are the top-left coordinates; `alpha` is the text opacity (0-255).
- `level` uses `anchor: name_right` to sit right after the nickname; `gap` is the spacing and `dy` is the vertical offset relative to the nickname.
- `overlays.*.stops` is a list of `[position ratio, opacity]`. `left_fade` runs from 0 at the left edge to 1 at the right edge; `bottom_fade` runs from 0 at the bottom to 1 at the top.
- `blur` is a frosted-glass effect, off by default. When enabled, only the `region` is blurred and the rest stays sharp.
- `background.anchor` decides which side is cropped when the background is not 3:1. Use `right` when the subject is on the right.
- Each card can override any theme key via `theme_overrides`.

More examples live in [`examples/`](examples/): `minimal` is a 6-line starter config, and `advanced` demonstrates changing the canvas, swapping colors, disabling overlays, enabling blur, combining fields, and overriding the theme per card.

## Supported games

| id | Game | Data source | Credentials |
| --- | --- | --- | --- |
| `arknights` | Arknights | Skland (unofficial API) | `SKLAND_TOKEN` |
| `endfield` | Arknights: Endfield | [Enka.Network](https://enka.network/?ef) | None, UID only |

These two are built in. Adding another game means changing the data layer — each module under `src/hypergryph_profile_cards/fetch/` handles one game, and a new module just needs to be registered in `COLLECTORS` in `orchestrator.py`; the visual layer does not need to change.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Logs say "background not found" and the card becomes a solid color | `assets/{id}-bg.png` is missing or misnamed. The background must be committed to the repo for CI to find it |
| Chinese text renders as boxes, or a missing-font error appears | The font is not ready. Locally, remove the entries in `theme.fonts.candidates` that do not exist, or download Noto Sans SC into `fonts/` as the error suggests |
| The Arknights card says "skipped: SKLAND_TOKEN not configured" | The secret is missing or misnamed |
| Skland returns "invalid device information" | The mutable signing constants need updating; see the comment at the top of `skland/client.py` |
| Enka returns 429 | Third-party rate limiting — retry later; only that one card is affected |
| The Action ran but the profile image did not change | Check that Settings → Actions → General grants Read and write permissions |

## FAQ

**Will I get banned?**
This project only reads public profile data; it never logs into the game or changes any account state. It does use unofficial APIs, so judge the risk yourself.

**Can I skip committing to the repo?**
Yes. Leave `commit` empty or set it to `false`, then point `output-dir` somewhere else and handle the output yourself.

**Can I use a private repo?**
Yes, but the profile README must live in a public repo to be shown, so the usual setup is a public repo holding the README and images.

**What are the background requirements?**
3:1 (e.g. 1200×400) is recommended, with the subject on the right. Other ratios work too — they are cropped according to `background.anchor`.

## Development

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest
```

`tests/baseline/` holds the pixel baseline from before the refactor, to make sure the default look is never broken by accident. That comparison only runs on machines with Microsoft YaHei installed (font rasterization differs across platforms); the remaining assertions are cross-platform.

## License and notices

The code is licensed under [MIT](LICENSE).

**This project bundles no game assets.** The example images and test backgrounds are generated programmatically by `tests/make_fixtures.py`. *Arknights*, *Arknights: Endfield*, and their character artwork, icons and names are the property of Hypergryph and related rights holders; the MIT license does not cover them. If you use official assets in your own repo, judge the risk yourself and bear it.

**API availability**: Skland is an unofficial Hypergryph API whose signing algorithm and fields may change at any time; Enka.Network is a third-party community service that may be rate-limited, changed, or shut down. This project makes no availability guarantees.

**Account safety**: `SKLAND_TOKEN` is equivalent to a login session — keep it in GitHub Secrets only. Any consequences arising from API changes, rate limiting, or account actions are the user's own responsibility.