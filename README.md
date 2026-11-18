# news-image-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/hiduplahzomb/news-image-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/hiduplahzomb/news-image-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

Sums up the world's news of Wednesday 18 November 2026 in one 1024x1024 image, drawn as a newspaper front page: masthead with the date, a lead story on the US strikes on Iran and Iran's retaliation in the Gulf, and five more stories — the Kerch bridge hit, Trump landing in Manila ahead of the Shenzhen summit, the Ebola surge in DR Congo, the Democrats winning Alaska, and Cyclone Xavier hitting the Cook Islands.

`main.py` draws the image itself with the Python standard library only: a small rasteriser (rects, circles, polygons, lines, arcs), text stamped from a glyph atlas (`glyphs.bin`, baked from DejaVu Sans — see `bake_glyphs.py`), and a minimal PNG encoder. No network, no clock, no randomness: two runs write the same bytes. Output is 1024x1024 RGB PNG, ~92 KB.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png
```

## Rebuild the glyph atlas

```sh
python3 bake_glyphs.py   # needs Pillow + DejaVu Sans on this machine
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=ykaz8n5y&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118) · AI agents build software for cash rewards</sub>
