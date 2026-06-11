from __future__ import annotations

import random
from dataclasses import dataclass
from math import cos, floor, pi, sin
from panda3d.core import TransparencyAttrib
from ursina import (
    AmbientLight,
    Button,
    DirectionalLight,
    Entity,
    Mesh,
    Sky,
    Text,
    Texture,
    Ursina,
    Vec2,
    Vec3,
    application,
    camera,
    color,
    destroy,
    held_keys,
    load_texture,
    mouse,
    scene,
    time,
    window,
)
from ursina.prefabs.first_person_controller import FirstPersonController

from texture_assets import (
    ATLAS_COLUMNS,
    ATLAS_PATH,
    ATLAS_ROWS,
    TEXTURE_DIR,
    TEXTURE_NAMES,
    TEXTURE_SIZE,
    ensure_texture_atlas,
)


WATER_LEVEL = 1
MAX_REACH = 7
SEED = 1842
CHUNK_SIZE = 12
VIEW_DISTANCE_CHUNKS = 3
UNLOAD_DISTANCE_CHUNKS = VIEW_DISTANCE_CHUNKS + 1
INITIAL_CHUNK_RADIUS = 1
MAX_CHUNK_LOADS_PER_FRAME = 1
MAX_CHUNK_UNLOADS_PER_FRAME = 2
RAY_STEP = 0.04

MAX_HEALTH = 20.0
MAX_HUNGER = 20.0
SPRINT_HUNGER_THRESHOLD = 6.0
DAY_LENGTH_SECONDS = 180.0
MAX_ZOMBIES = 8
ZOMBIE_SPAWN_INTERVAL = 4.0


@dataclass(frozen=True)
class BlockKind:
    name: str
    tint: color.Color
    solid: bool = True
    removable: bool = True
    opaque: bool = True


@dataclass(frozen=True)
class BlockHit:
    position: tuple[int, int, int]
    normal: Vec3


@dataclass(frozen=True)
class CraftRecipe:
    name: str
    output: str
    output_count: int
    ingredients: dict[str, int]


BLOCKS = {
    "grass": BlockKind("Grass", color.rgb(86, 154, 78)),
    "dirt": BlockKind("Dirt", color.rgb(125, 84, 52)),
    "stone": BlockKind("Stone", color.rgb(116, 118, 122)),
    "sand": BlockKind("Sand", color.rgb(210, 194, 128)),
    "wood": BlockKind("Wood", color.rgb(125, 79, 43)),
    "planks": BlockKind("Planks", color.rgb(150, 98, 48)),
    "leaves": BlockKind("Leaves", color.rgba(68, 145, 76, 225)),
    "glass": BlockKind("Glass", color.rgba(178, 230, 255, 120), opaque=False),
    "bedrock": BlockKind("Bedrock", color.rgb(38, 38, 44), removable=False),
}

HOTBAR = ["grass", "dirt", "stone", "sand", "wood", "planks", "leaves", "glass"]
TEXTURE_INDEX = {name: index for index, name in enumerate(TEXTURE_NAMES)}
PREVIEW_TEXTURES = {
    "grass": "grass_side",
    "wood": "log_side",
}
CRAFT_RECIPES = (
    CraftRecipe("Planks", "planks", 4, {"wood": 1}),
    CraftRecipe("Glass", "glass", 1, {"sand": 2}),
    CraftRecipe("Grass", "grass", 1, {"dirt": 2, "leaves": 1}),
)

ensure_texture_atlas()

app = Ursina(title="Thingdos Voxel", borderless=False)
window.color = color.rgb(142, 202, 230)
window.fps_counter.enabled = True
window.exit_button.visible = False
scene.fog_color = color.rgb(142, 202, 230)
scene.fog_density = 0.018

ATLAS_TEXTURE: Texture | str | None = None
TEXTURES: dict[str, Texture | str] = {}

world: dict[tuple[int, int, int], str] = {}
chunk_blocks: dict[tuple[int, int], set[tuple[int, int, int]]] = {}
chunks: dict[tuple[int, int], "Chunk"] = {}
placed_blocks: dict[tuple[int, int, int], str] = {}
removed_blocks: set[tuple[int, int, int]] = set()
current_stream_center: tuple[int, int] | None = None
pending_chunk_loads: set[tuple[int, int]] = set()
pending_chunk_unloads: set[tuple[int, int]] = set()

selected_hotbar_index = 0
hotbar_slots: list[Button] = []
slot_labels: list[Text] = []
count_labels: list[Text] = []
health_pips: list[Entity] = []
hunger_pips: list[Entity] = []
crafting_panel: Text | None = None
crafting_open = False
inventory = {block_id: 0 for block_id in HOTBAR}
health = MAX_HEALTH
hunger = MAX_HUNGER
day_time = 0.25
zombie_spawn_timer = 0.0
zombies: list["Zombie"] = []
was_grounded = True
fall_peak_y = 0.0
damage_cooldown = 0.0
sun: DirectionalLight
ambient_light: AmbientLight
player: FirstPersonController

UV_DEFAULT = (0, 1, 2, 3)
UV_ROTATED = (0, 3, 2, 1)
TRIANGLE_ORDER = (0, 2, 1, 0, 3, 2)
FACE_DEFS = (
    (Vec3(0, 1, 0), ((-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5)), UV_ROTATED),
    (Vec3(0, -1, 0), ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5)), UV_DEFAULT),
    (Vec3(1, 0, 0), ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5)), UV_ROTATED),
    (Vec3(-1, 0, 0), ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)), UV_DEFAULT),
    (Vec3(0, 0, 1), ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)), UV_DEFAULT),
    (Vec3(0, 0, -1), ((-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)), UV_ROTATED),
)
WATER_FACE = FACE_DEFS[0]


def load_project_texture(path) -> Texture | str:
    texture = load_texture(path.name, folder=path.parent, filtering="nearest")
    if not texture:
        texture = Texture(path, filtering="nearest")
    if texture:
        texture.filtering = "nearest"
        return texture
    return "white_cube"


def load_block_textures() -> None:
    global ATLAS_TEXTURE

    ATLAS_TEXTURE = load_project_texture(ATLAS_PATH)

    for texture_name in TEXTURE_NAMES:
        TEXTURES[texture_name] = load_project_texture(TEXTURE_DIR / f"{texture_name}.png")


def hash_float(x: int, z: int, salt: int = 0) -> float:
    value = (x * 374761393 + z * 668265263 + SEED * 1442695041 + salt * 1274126177) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF


def terrain_height(x: int, z: int) -> int:
    hills = sin(x * 0.08 + SEED * 0.01) * 2.1 + cos(z * 0.075 - SEED * 0.02) * 1.9
    ridges = sin((x + z) * 0.14) * 1.1 + cos((x - z) * 0.17) * 0.9
    detail = (hash_float(x, z, 4) - 0.5) * 1.2
    return max(0, min(9, int(3 + hills + ridges + detail)))


def should_tree(x: int, z: int) -> bool:
    height = terrain_height(x, z)
    far_from_spawn = abs(x) > 4 or abs(z) > 4
    return far_from_spawn and height > WATER_LEVEL and hash_float(x, z, 9) < 0.028


def grid_key(value: Vec3 | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, Vec3):
        return round(value.x), round(value.y), round(value.z)
    return value


def point_to_block(value: Vec3) -> tuple[int, int, int]:
    return floor(value.x + 0.5), floor(value.y + 0.5), floor(value.z + 0.5)


def chunk_key_for(position: tuple[int, int, int]) -> tuple[int, int]:
    x, _, z = position
    return x // CHUNK_SIZE, z // CHUNK_SIZE


def chunk_bounds(chunk_key: tuple[int, int]) -> tuple[range, range]:
    cx, cz = chunk_key
    x_start = cx * CHUNK_SIZE
    z_start = cz * CHUNK_SIZE
    return range(x_start, x_start + CHUNK_SIZE), range(z_start, z_start + CHUNK_SIZE)


def chunk_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def desired_chunk_keys(center: tuple[int, int]) -> set[tuple[int, int]]:
    return {
        (center[0] + dx, center[1] + dz)
        for dx in range(-VIEW_DISTANCE_CHUNKS, VIEW_DISTANCE_CHUNKS + 1)
        for dz in range(-VIEW_DISTANCE_CHUNKS, VIEW_DISTANCE_CHUNKS + 1)
    }


def block_at(position: tuple[int, int, int] | Vec3) -> str | None:
    return world.get(grid_key(position))


def add_inventory(block_id: str, count: int = 1) -> None:
    if block_id not in inventory:
        inventory[block_id] = 0
    inventory[block_id] += count
    update_inventory_ui()


def consume_inventory(block_id: str, count: int = 1) -> bool:
    if inventory.get(block_id, 0) < count:
        return False
    inventory[block_id] -= count
    update_inventory_ui()
    return True


def can_craft(recipe: CraftRecipe) -> bool:
    return all(inventory.get(block_id, 0) >= count for block_id, count in recipe.ingredients.items())


def craft_recipe(index: int) -> bool:
    if index < 0 or index >= len(CRAFT_RECIPES):
        return False

    recipe = CRAFT_RECIPES[index]
    if not can_craft(recipe):
        return False

    for block_id, count in recipe.ingredients.items():
        inventory[block_id] -= count
    inventory[recipe.output] = inventory.get(recipe.output, 0) + recipe.output_count
    update_inventory_ui()
    update_crafting_panel()
    return True


def set_loaded_block(position: tuple[int, int, int], block_id: str) -> None:
    chunk_key = chunk_key_for(position)
    world[position] = block_id
    chunk_blocks.setdefault(chunk_key, set()).add(position)


def remove_loaded_block(position: tuple[int, int, int]) -> None:
    world.pop(position, None)
    positions = chunk_blocks.get(chunk_key_for(position))
    if positions:
        positions.discard(position)


def set_generated_block(position: tuple[int, int, int], block_id: str) -> None:
    if position in removed_blocks or position in placed_blocks or position in world:
        return
    set_loaded_block(position, block_id)


def add_block(position: tuple[int, int, int] | Vec3, block_id: str, rebuild: bool = True) -> bool:
    key = grid_key(position)
    if key in world:
        return False

    placed_blocks[key] = block_id
    removed_blocks.discard(key)
    if chunk_key_for(key) in chunks:
        set_loaded_block(key, block_id)
    if rebuild:
        rebuild_affected_chunks(key)
    return True


def remove_block(position: tuple[int, int, int]) -> str | None:
    block_id = world.get(position)
    if not block_id or not BLOCKS[block_id].removable:
        return None

    if position in placed_blocks:
        placed_blocks.pop(position, None)
    else:
        removed_blocks.add(position)
    remove_loaded_block(position)
    rebuild_affected_chunks(position)
    return block_id


def terrain_block_for(x: int, y: int, z: int, height: int) -> str:
    if y == -1:
        return "bedrock"
    if y == height and height <= WATER_LEVEL:
        return "sand"
    if y == height:
        return "grass"
    if y >= height - 2:
        return "dirt"
    return "stone"


def procedural_tree_blocks(x: int, z: int):
    ground_y = terrain_height(x, z)
    trunk_height = 4 + int(hash_float(x, z, 13) * 2)

    for y in range(ground_y + 1, ground_y + trunk_height + 1):
        yield (x, y, z), "wood"

    crown_center = ground_y + trunk_height
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(-1, 2):
                if abs(dx) + abs(dz) + max(dy, 0) <= 4:
                    yield (x + dx, crown_center + dy, z + dz), "leaves"


def generate_chunk_blocks(chunk_key: tuple[int, int]) -> None:
    x_range, z_range = chunk_bounds(chunk_key)
    chunk_blocks.setdefault(chunk_key, set())

    for x in x_range:
        for z in z_range:
            height = terrain_height(x, z)
            for y in range(-1, height + 1):
                set_generated_block((x, y, z), terrain_block_for(x, y, z, height))

    for tree_x in range(x_range.start - 2, x_range.stop + 2):
        for tree_z in range(z_range.start - 2, z_range.stop + 2):
            if not should_tree(tree_x, tree_z):
                continue
            for position, block_id in procedural_tree_blocks(tree_x, tree_z):
                px, _, pz = position
                if x_range.start <= px < x_range.stop and z_range.start <= pz < z_range.stop:
                    set_generated_block(position, block_id)

    for position, block_id in placed_blocks.items():
        if chunk_key_for(position) == chunk_key:
            set_loaded_block(position, block_id)


def uv_corners(block_id: str, order: tuple[int, int, int, int]) -> tuple[tuple[float, float], ...]:
    index = TEXTURE_INDEX[block_id]
    col = index % ATLAS_COLUMNS
    row = index // ATLAS_COLUMNS
    atlas_width = ATLAS_COLUMNS * TEXTURE_SIZE
    atlas_height = ATLAS_ROWS * TEXTURE_SIZE
    inset_u = 0.35 / atlas_width
    inset_v = 0.35 / atlas_height
    u0 = col / ATLAS_COLUMNS + inset_u
    u1 = (col + 1) / ATLAS_COLUMNS - inset_u
    v0 = 1 - (row + 1) / ATLAS_ROWS + inset_v
    v1 = 1 - row / ATLAS_ROWS - inset_v
    corners = ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
    return tuple(corners[index] for index in order)


def texture_for_face(block_id: str, normal: Vec3) -> str:
    if block_id == "grass":
        if normal.y > 0:
            return "grass_top"
        if normal.y < 0:
            return "dirt"
        return "grass_side"
    if block_id == "wood":
        if normal.y != 0:
            return "log_top"
        return "log_side"
    return block_id


def preview_texture(block_id: str) -> str:
    return PREVIEW_TEXTURES.get(block_id, block_id)


def is_transparent_visual(block_id: str) -> bool:
    return not BLOCKS[block_id].opaque


def visual_face_visible(block_id: str, neighbor_id: str | None) -> bool:
    if neighbor_id is None:
        return True

    current = BLOCKS[block_id]
    neighbor = BLOCKS[neighbor_id]
    if current.opaque:
        return not neighbor.opaque
    return neighbor_id != block_id and not neighbor.opaque


def collision_face_visible(block_id: str, neighbor_id: str | None) -> bool:
    if not BLOCKS[block_id].solid:
        return False
    return neighbor_id is None or not BLOCKS[neighbor_id].solid


def add_face(
    vertices: list[Vec3],
    triangles: list[int],
    uvs: list[tuple[float, float]],
    normals: list[Vec3],
    block_position: tuple[int, int, int],
    texture_name: str,
    normal: Vec3,
    corners: tuple[tuple[float, float, float], ...],
    uv_order: tuple[int, int, int, int],
) -> None:
    base = len(vertices)
    x, y, z = block_position
    for corner in corners:
        vertices.append(Vec3(x + corner[0], y + corner[1], z + corner[2]))
        normals.append(normal)
    triangles.extend(base + index for index in TRIANGLE_ORDER)
    uvs.extend(uv_corners(texture_name, uv_order))


def has_water_surface(x: int, z: int) -> bool:
    return terrain_height(x, z) < WATER_LEVEL and (x, WATER_LEVEL, z) not in world


def add_water_surfaces(
    vertices: list[Vec3],
    triangles: list[int],
    uvs: list[tuple[float, float]],
    normals: list[Vec3],
    chunk_key: tuple[int, int],
) -> None:
    normal, corners, uv_order = WATER_FACE
    x_range, z_range = chunk_bounds(chunk_key)
    for x in x_range:
        for z in z_range:
            if has_water_surface(x, z):
                add_face(vertices, triangles, uvs, normals, (x, WATER_LEVEL, z), "water", normal, corners, uv_order)


def build_chunk_mesh(
    chunk_key: tuple[int, int],
    collision_only: bool = False,
    transparent_layer: bool = False,
) -> Mesh:
    vertices: list[Vec3] = []
    triangles: list[int] = []
    uvs: list[tuple[float, float]] = []
    normals: list[Vec3] = []

    for position in chunk_blocks.get(chunk_key, set()):
        block_id = world.get(position)
        if not block_id:
            continue
        if not collision_only and is_transparent_visual(block_id) != transparent_layer:
            continue

        bx, by, bz = position
        for normal, corners, uv_order in FACE_DEFS:
            neighbor_pos = (bx + int(normal.x), by + int(normal.y), bz + int(normal.z))
            neighbor_id = world.get(neighbor_pos)
            visible = (
                collision_face_visible(block_id, neighbor_id)
                if collision_only
                else visual_face_visible(block_id, neighbor_id)
            )
            if visible:
                texture_name = texture_for_face(block_id, normal)
                add_face(vertices, triangles, uvs, normals, position, texture_name, normal, corners, uv_order)

    if transparent_layer and not collision_only:
        add_water_surfaces(vertices, triangles, uvs, normals, chunk_key)

    return Mesh(vertices=vertices, triangles=triangles, uvs=uvs, normals=normals, static=True)


class Chunk:
    def __init__(self, key: tuple[int, int]):
        self.key = key
        self.visual_opaque = Entity(parent=scene, texture=ATLAS_TEXTURE, color=color.white)
        self.visual_transparent = Entity(parent=scene, texture=ATLAS_TEXTURE, color=color.white)
        self.visual_opaque.setTransparency(TransparencyAttrib.MNone)
        self.visual_transparent.setTransparency(TransparencyAttrib.MAlpha)
        self.visual_transparent.setBin("transparent", 10)
        self.visual_transparent.setDepthWrite(False)
        self.collision = Entity(parent=scene, visible=False)

    def rebuild(self) -> None:
        opaque_mesh = build_chunk_mesh(self.key, collision_only=False, transparent_layer=False)
        self.visual_opaque.model = opaque_mesh
        self.visual_opaque.texture = ATLAS_TEXTURE
        self.visual_opaque.enabled = bool(opaque_mesh.vertices)

        transparent_mesh = build_chunk_mesh(self.key, collision_only=False, transparent_layer=True)
        self.visual_transparent.model = transparent_mesh
        self.visual_transparent.texture = ATLAS_TEXTURE
        self.visual_transparent.enabled = bool(transparent_mesh.vertices)

        collision_mesh = build_chunk_mesh(self.key, collision_only=True)
        self.collision.collider = None
        self.collision.model = collision_mesh
        self.collision.enabled = bool(collision_mesh.vertices)
        if collision_mesh.vertices:
            self.collision.collider = "mesh"

    def destroy(self) -> None:
        destroy(self.visual_opaque)
        destroy(self.visual_transparent)
        destroy(self.collision)


def rebuild_chunk(key: tuple[int, int]) -> None:
    chunk = chunks.get(key)
    if chunk:
        chunk.rebuild()


def rebuild_affected_chunks(position: tuple[int, int, int]) -> None:
    x, y, z = position
    affected = {
        chunk_key_for((x, y, z)),
        chunk_key_for((x + 1, y, z)),
        chunk_key_for((x - 1, y, z)),
        chunk_key_for((x, y, z + 1)),
        chunk_key_for((x, y, z - 1)),
    }
    for key in affected:
        rebuild_chunk(key)


def load_chunk(key: tuple[int, int]) -> None:
    if key in chunks:
        return

    chunks[key] = Chunk(key)
    generate_chunk_blocks(key)
    rebuild_chunk(key)

    for neighbor in ((key[0] + 1, key[1]), (key[0] - 1, key[1]), (key[0], key[1] + 1), (key[0], key[1] - 1)):
        rebuild_chunk(neighbor)


def unload_chunk(key: tuple[int, int]) -> None:
    chunk = chunks.pop(key, None)
    if chunk:
        chunk.destroy()

    for position in chunk_blocks.pop(key, set()):
        world.pop(position, None)

    for neighbor in ((key[0] + 1, key[1]), (key[0] - 1, key[1]), (key[0], key[1] + 1), (key[0], key[1] - 1)):
        rebuild_chunk(neighbor)


def stream_chunks(center: tuple[int, int], immediate: bool = False) -> None:
    global current_stream_center

    wanted = desired_chunk_keys(center)
    pending_chunk_loads.intersection_update(wanted)
    pending_chunk_unloads.difference_update(wanted)

    missing = wanted.difference(chunks)
    if immediate:
        for key in sorted(missing, key=lambda key: (chunk_distance(key, center), key[0], key[1])):
            load_chunk(key)
    else:
        pending_chunk_loads.update(missing)
        if center in pending_chunk_loads:
            pending_chunk_loads.remove(center)
            load_chunk(center)

    for key in list(chunks):
        if chunk_distance(key, center) > UNLOAD_DISTANCE_CHUNKS:
            pending_chunk_unloads.add(key)
    pending_chunk_loads.difference_update(pending_chunk_unloads)

    current_stream_center = center


def process_chunk_jobs() -> None:
    if current_stream_center is None:
        return

    for _ in range(MAX_CHUNK_LOADS_PER_FRAME):
        if not pending_chunk_loads:
            break
        key = min(pending_chunk_loads, key=lambda key: (chunk_distance(key, current_stream_center), key[0], key[1]))
        pending_chunk_loads.remove(key)
        if chunk_distance(key, current_stream_center) <= VIEW_DISTANCE_CHUNKS:
            load_chunk(key)

    for _ in range(MAX_CHUNK_UNLOADS_PER_FRAME):
        if not pending_chunk_unloads:
            break
        key = max(pending_chunk_unloads, key=lambda key: (chunk_distance(key, current_stream_center), key[0], key[1]))
        pending_chunk_unloads.remove(key)
        if key in chunks and chunk_distance(key, current_stream_center) > UNLOAD_DISTANCE_CHUNKS:
            unload_chunk(key)


def load_initial_chunks(center: tuple[int, int]) -> None:
    for dx in range(-INITIAL_CHUNK_RADIUS, INITIAL_CHUNK_RADIUS + 1):
        for dz in range(-INITIAL_CHUNK_RADIUS, INITIAL_CHUNK_RADIUS + 1):
            load_chunk((center[0] + dx, center[1] + dz))
    stream_chunks(center)


def make_hotbar() -> None:
    start_x = -0.28
    for index, block_id in enumerate(HOTBAR):
        x = start_x + index * 0.08
        slot = Button(
            parent=camera.ui,
            text="",
            model="quad",
            color=color.rgba(18, 20, 24, 178),
            highlight_color=color.rgba(38, 42, 48, 210),
            pressed_color=color.rgba(52, 58, 66, 230),
            position=(x, -0.43),
            scale=(0.068, 0.068),
        )
        Entity(
            parent=slot,
            model="quad",
            texture=TEXTURES.get(preview_texture(block_id), "white_cube"),
            color=color.white,
            position=(0, 0, -0.01),
            scale=(0.58, 0.58),
        )
        label = Text(
            str(index + 1),
            parent=slot,
            origin=(0, 0),
            position=(-0.33, 0.28, -0.02),
            scale=0.45,
            color=color.rgba(245, 245, 245, 190),
        )
        count_label = Text(
            "",
            parent=slot,
            origin=(0.5, -0.5),
            position=(0.35, -0.33, -0.02),
            scale=0.42,
            color=color.rgba(245, 245, 245, 220),
        )
        hotbar_slots.append(slot)
        slot_labels.append(label)
        count_labels.append(count_label)


def update_hotbar() -> None:
    for index, slot in enumerate(hotbar_slots):
        if index == selected_hotbar_index:
            slot.color = color.rgba(238, 238, 224, 220)
        else:
            slot.color = color.rgba(18, 20, 24, 178)


def update_inventory_ui() -> None:
    for index, block_id in enumerate(HOTBAR):
        if index < len(count_labels):
            count = inventory.get(block_id, 0)
            count_labels[index].text = str(count) if count else ""
    update_crafting_panel()


def make_hunger_ui() -> None:
    start_x = 0.19
    for index in range(10):
        pip = Entity(
            parent=camera.ui,
            model="quad",
            color=color.rgb(218, 126, 38),
            position=(start_x + index * 0.032, -0.35, -0.02),
            scale=(0.022, 0.036),
        )
        hunger_pips.append(pip)


def make_health_ui() -> None:
    start_x = -0.50
    for index in range(10):
        pip = Entity(
            parent=camera.ui,
            model="quad",
            color=color.rgb(196, 44, 42),
            position=(start_x + index * 0.032, -0.35, -0.02),
            scale=(0.024, 0.036),
        )
        health_pips.append(pip)


def update_health_ui() -> None:
    for index, pip in enumerate(health_pips):
        value = health - index * 2
        if value >= 2:
            pip.color = color.rgb(206, 45, 42)
        elif value > 0:
            pip.color = color.rgb(116, 38, 38)
        else:
            pip.color = color.rgba(38, 24, 24, 190)


def update_hunger_ui() -> None:
    for index, pip in enumerate(hunger_pips):
        value = hunger - index * 2
        if value >= 2:
            pip.color = color.rgb(226, 133, 42)
        elif value > 0:
            pip.color = color.rgb(142, 83, 40)
        else:
            pip.color = color.rgba(38, 32, 28, 190)


def make_crafting_ui() -> None:
    global crafting_panel

    crafting_panel = Text(
        "",
        parent=camera.ui,
        origin=(-0.5, 0.5),
        position=(-0.50, 0.28, -0.03),
        scale=0.72,
        color=color.rgba(245, 245, 235, 235),
        background=True,
    )
    crafting_panel.enabled = False
    update_crafting_panel()


def update_crafting_panel() -> None:
    if crafting_panel is None:
        return

    lines = ["Crafting"]
    for index, recipe in enumerate(CRAFT_RECIPES, start=1):
        ingredients = " + ".join(f"{count} {BLOCKS[block_id].name}" for block_id, count in recipe.ingredients.items())
        status = "ready" if can_craft(recipe) else "missing"
        lines.append(f"{index}. {ingredients} -> {recipe.output_count} {BLOCKS[recipe.output].name} [{status}]")
    crafting_panel.text = "\n".join(lines)


def toggle_crafting() -> None:
    global crafting_open

    crafting_open = not crafting_open
    if crafting_panel:
        crafting_panel.enabled = crafting_open
        update_crafting_panel()


def daylight_amount() -> float:
    return max(0.0, sin(day_time * 2 * pi))


def is_night() -> bool:
    return daylight_amount() < 0.24


def lerp(a: float, b: float, amount: float) -> float:
    return a + (b - a) * amount


def lerp_rgb(day: tuple[int, int, int], night: tuple[int, int, int], night_amount: float) -> color.Color:
    return color.rgb(
        int(lerp(day[0], night[0], night_amount)),
        int(lerp(day[1], night[1], night_amount)),
        int(lerp(day[2], night[2], night_amount)),
    )


def update_day_night() -> None:
    global day_time

    day_time = (day_time + time.dt / DAY_LENGTH_SECONDS) % 1.0
    daylight = daylight_amount()
    night_amount = 1.0 - daylight

    window.color = lerp_rgb((142, 202, 230), (12, 18, 42), night_amount * 0.88)
    scene.fog_color = window.color
    sun.color = color.rgba(255, int(lerp(210, 110, night_amount)), int(lerp(170, 125, night_amount)), int(lerp(50, 255, daylight)))
    ambient_light.color = color.rgba(
        int(lerp(90, 20, night_amount)),
        int(lerp(95, 24, night_amount)),
        int(lerp(105, 45, night_amount)),
        110,
    )
    sun.rotation_x = day_time * 360 - 90
    sun.rotation_y = 35


class Zombie:
    def __init__(self, position: Vec3):
        self.root = Entity(parent=scene, position=position)
        self.body = Entity(parent=self.root, model="cube", color=color.rgb(42, 105, 54), position=(0, 0.85, 0), scale=(0.75, 1.1, 0.38))
        self.head = Entity(parent=self.root, model="cube", color=color.rgb(52, 126, 65), position=(0, 1.55, 0), scale=(0.55, 0.55, 0.55))
        self.left_arm = Entity(parent=self.root, model="cube", color=color.rgb(39, 92, 51), position=(-0.55, 1.05, 0.05), scale=(0.22, 0.85, 0.22))
        self.right_arm = Entity(parent=self.root, model="cube", color=color.rgb(39, 92, 51), position=(0.55, 1.05, 0.05), scale=(0.22, 0.85, 0.22))
        self.health = 12.0
        self.attack_cooldown = 0.0

    @property
    def position(self) -> Vec3:
        return self.root.position

    def destroy(self) -> None:
        destroy(self.root)

    def damage(self, amount: float) -> bool:
        self.health -= amount
        if self.health <= 0:
            add_inventory("wood", 1)
            self.destroy()
            return True
        self.head.color = color.rgb(95, 155, 84)
        return False

    def update(self) -> bool:
        self.attack_cooldown = max(0.0, self.attack_cooldown - time.dt)
        to_player = Vec3(player.x - self.root.x, 0, player.z - self.root.z)
        distance_to_player = to_player.length()

        if distance_to_player > 80 or not is_night():
            self.destroy()
            return False

        if distance_to_player > 0.1:
            direction = to_player.normalized()
            next_x = self.root.x + direction.x * 2.0 * time.dt
            next_z = self.root.z + direction.z * 2.0 * time.dt
            ground = terrain_height(round(next_x), round(next_z))
            if ground > WATER_LEVEL:
                self.root.x = next_x
                self.root.z = next_z
                self.root.y = ground + 0.05
                self.root.look_at(Vec3(player.x, self.root.y, player.z))

        if distance_to_player < 1.55 and self.attack_cooldown <= 0:
            apply_damage(2.0)
            self.attack_cooldown = 1.2

        return True


def spawn_zombie() -> None:
    if len(zombies) >= MAX_ZOMBIES:
        return

    player_chunk = chunk_key_for(point_to_block(player.position))
    spawn_chunks = [
        key for key in chunks
        if 1 <= chunk_distance(key, player_chunk) <= VIEW_DISTANCE_CHUNKS
    ]
    if not spawn_chunks:
        return

    for _ in range(12):
        chunk_key = random.choice(spawn_chunks)
        x_range, z_range = chunk_bounds(chunk_key)
        x = random.randrange(x_range.start, x_range.stop)
        z = random.randrange(z_range.start, z_range.stop)
        if (Vec3(x, 0, z) - Vec3(player.x, 0, player.z)).length() < 12:
            continue
        ground = terrain_height(x, z)
        if ground <= WATER_LEVEL:
            continue
        zombies.append(Zombie(Vec3(x, ground + 0.05, z)))
        return


def update_zombies() -> None:
    global zombie_spawn_timer

    zombie_spawn_timer -= time.dt
    if is_night() and zombie_spawn_timer <= 0:
        spawn_zombie()
        zombie_spawn_timer = ZOMBIE_SPAWN_INTERVAL

    for zombie in list(zombies):
        if not zombie.update():
            zombies.remove(zombie)


def targeted_zombie() -> Zombie | None:
    origin = camera.world_position
    direction = camera.forward.normalized()
    closest_zombie = None
    closest_distance = MAX_REACH + 1

    for zombie in zombies:
        center = zombie.position + Vec3(0, 1.05, 0)
        to_center = center - origin
        forward_distance = to_center.dot(direction)
        if forward_distance < 0 or forward_distance > MAX_REACH:
            continue
        closest_point = origin + direction * forward_distance
        if (closest_point - center).length() < 0.75 and forward_distance < closest_distance:
            closest_zombie = zombie
            closest_distance = forward_distance

    return closest_zombie


def selected_block_id() -> str:
    return HOTBAR[selected_hotbar_index]


def respawn_player() -> None:
    global health, hunger, was_grounded, fall_peak_y

    health = MAX_HEALTH
    hunger = MAX_HUNGER
    player.position = Vec3(0, terrain_height(0, 0) + 4, 0)
    stream_chunks(chunk_key_for(point_to_block(player.position)), immediate=True)
    was_grounded = True
    fall_peak_y = player.y
    for zombie in list(zombies):
        zombie.destroy()
    zombies.clear()
    update_health_ui()
    update_hunger_ui()


def apply_damage(amount: float) -> None:
    global health, damage_cooldown

    if amount <= 0 or damage_cooldown > 0:
        return
    health = max(0.0, health - amount)
    damage_cooldown = 0.35
    update_health_ui()
    if health <= 0:
        respawn_player()


def update_fall_damage() -> None:
    global was_grounded, fall_peak_y

    grounded = bool(getattr(player, "grounded", False))
    if not grounded:
        if was_grounded:
            fall_peak_y = player.y
        else:
            fall_peak_y = max(fall_peak_y, player.y)
    elif not was_grounded:
        fall_distance = fall_peak_y - player.y
        if fall_distance > 3.2:
            apply_damage((fall_distance - 3.0) * 2.0)
    was_grounded = grounded


selector = Entity(
    model="cube",
    color=color.rgba(255, 255, 255, 90),
    scale=1.02,
    wireframe=True,
    collider=None,
    enabled=False,
)


def dominant_axis_normal(direction: Vec3) -> Vec3:
    axes = (
        (abs(direction.x), -1 if direction.x > 0 else 1, 0, 0),
        (abs(direction.y), 0, -1 if direction.y > 0 else 1, 0),
        (abs(direction.z), 0, 0, -1 if direction.z > 0 else 1),
    )
    _, x, y, z = max(axes, key=lambda item: item[0])
    return Vec3(x, y, z)


def targeted_block() -> BlockHit | None:
    origin = camera.world_position
    direction = camera.forward.normalized()
    last_key = point_to_block(origin)

    for step in range(int(MAX_REACH / RAY_STEP)):
        point = origin + direction * (step * RAY_STEP)
        key = point_to_block(point)
        if key in world:
            normal = Vec3(last_key[0] - key[0], last_key[1] - key[1], last_key[2] - key[2])
            if normal == Vec3(0, 0, 0):
                normal = dominant_axis_normal(direction)
            return BlockHit(key, normal)
        last_key = key

    return None


def place_against(hit: BlockHit) -> None:
    destination = (
        hit.position[0] + int(hit.normal.x),
        hit.position[1] + int(hit.normal.y),
        hit.position[2] + int(hit.normal.z),
    )
    if block_at(destination):
        return

    player_feet = point_to_block(player.position)
    player_head = point_to_block(player.position + Vec3(0, 1, 0))
    if destination in (player_feet, player_head):
        return

    if not consume_inventory(selected_block_id(), 1):
        return

    add_block(destination, selected_block_id())


def input(key: str) -> None:
    global selected_hotbar_index

    if key == "q":
        application.quit()
        return

    if key == "escape":
        mouse.locked = False
        return

    if key == "c":
        toggle_crafting()
        return

    if key == "left mouse down":
        zombie = targeted_zombie()
        if zombie:
            if zombie.damage(6.0) and zombie in zombies:
                zombies.remove(zombie)
            return
        hit = targeted_block()
        if hit:
            block_id = remove_block(hit.position)
            if block_id:
                add_inventory(block_id, 1)
        return

    if key == "right mouse down":
        hit = targeted_block()
        if hit:
            place_against(hit)
        return

    if key == "scroll up":
        selected_hotbar_index = (selected_hotbar_index + 1) % len(HOTBAR)
        update_hotbar()
        return

    if key == "scroll down":
        selected_hotbar_index = (selected_hotbar_index - 1) % len(HOTBAR)
        update_hotbar()
        return

    if crafting_open and key in [str(i) for i in range(1, len(CRAFT_RECIPES) + 1)]:
        craft_recipe(int(key) - 1)
        return

    if key in [str(i) for i in range(1, len(HOTBAR) + 1)]:
        selected_hotbar_index = int(key) - 1
        update_hotbar()


def update_chunk_streaming() -> None:
    center = chunk_key_for(point_to_block(player.position))
    if center != current_stream_center:
        stream_chunks(center)
    process_chunk_jobs()


def update_hunger(moving: bool, sprinting: bool) -> None:
    global hunger

    drain = 0.018
    if moving:
        drain += 0.045
    if sprinting:
        drain += 0.09
    if held_keys["space"]:
        drain += 0.025

    hunger = max(0.0, hunger - drain * time.dt)
    update_hunger_ui()


def update() -> None:
    global damage_cooldown

    update_day_night()
    update_chunk_streaming()
    update_zombies()
    damage_cooldown = max(0.0, damage_cooldown - time.dt)

    hit = targeted_block()
    if hit:
        selector.position = Vec3(*hit.position)
        selector.enabled = True
    else:
        selector.enabled = False

    if player.y < -20:
        player.position = Vec3(0, terrain_height(0, 0) + 4, 0)
        stream_chunks(chunk_key_for(point_to_block(player.position)))

    moving = held_keys["w"] or held_keys["a"] or held_keys["s"] or held_keys["d"]
    sprinting = bool(held_keys["left shift"] and moving and hunger > SPRINT_HUNGER_THRESHOLD)
    if hunger <= 0:
        player.speed = 3.2
    elif sprinting:
        player.speed = 10
    else:
        player.speed = 6

    update_hunger(bool(moving), sprinting)
    update_fall_damage()

    bob = sin(time.time() * 2.2) * 0.008
    camera.ui.y = bob if moving else 0


load_block_textures()
load_initial_chunks((0, 0))

Sky()
sun = DirectionalLight(y=8, z=4, shadows=True)
sun.look_at(Vec3(1, -1.5, -1))
ambient_light = AmbientLight(color=color.rgba(100, 100, 110, 90))

player = FirstPersonController()
player.position = Vec3(0, terrain_height(0, 0) + 4, 0)
player.speed = 6
player.jump_height = 1.4
player.gravity = 0.75
player.mouse_sensitivity = Vec2(38, 38)
player.cursor.visible = False

Text("+", parent=camera.ui, origin=(0, 0), scale=1.45, color=color.rgba(255, 255, 255, 210))
make_hotbar()
update_hotbar()
update_inventory_ui()
make_health_ui()
update_health_ui()
make_hunger_ui()
update_hunger_ui()
make_crafting_ui()
update_day_night()

if __name__ == "__main__":
    app.run()
