# Thingdos Voxel

A small Minecraft-style voxel sandbox written in Python with Ursina.

The world streams procedurally generated chunks around the player as you explore. Water is rendered as a non-solid surface instead of a mineable block.
Chunks are loaded over multiple frames while exploring to reduce stutter.

## Run

With `uv`:

```powershell
uv run main.py
```

With Python installed:

```powershell
py -m pip install -r requirements.txt
py main.py
```

## Controls

- `WASD` to move
- Mouse to look
- `Space` to jump
- Left click to break a block
- Right click to place a block
- Number keys `1` through `8` or mouse wheel to change block
- `C` to toggle crafting
- `Esc` to release the mouse
- `Q` to quit

The red pips are health and the orange pips are hunger. Moving, sprinting, and jumping drain hunger; sprinting stops when hunger gets low, and movement slows when it is empty. Falling too far causes damage. Zombies spawn at night and attack when they get close.

## Crafting

Open crafting with `C`, then press a recipe number:

- `1`: 1 wood -> 4 planks
- `2`: 2 sand -> 1 glass
- `3`: 2 dirt + 1 leaves -> 1 grass

## Textures

Block textures live in `assets/textures`. Regenerate them with:

```powershell
uv run python texture_assets.py
```
