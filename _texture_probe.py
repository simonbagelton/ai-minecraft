from pathlib import Path

from panda3d.core import loadPrcFileData

loadPrcFileData("", "window-type offscreen")
loadPrcFileData("", "win-size 512 512")

import main
from direct.showbase.ShowBaseGlobal import base
from PIL import Image
from ursina import Entity, Mesh, Vec3, camera, color, scene


def disable_scene() -> None:
    for entity in list(scene.entities):
        entity.enabled = False
    for child in camera.ui.children:
        child.enabled = False


def render_atlas_quad() -> Path:
    disable_scene()
    camera.enabled = True
    camera.parent = scene
    camera.position = (0, 0, 3)
    camera.look_at(Vec3(0, 0, 0))
    camera.orthographic = True
    camera.orthographic_scale = 2

    vertices = []
    triangles = []
    uvs = []
    normals = []
    normal, corners, uv_order = main.FACE_DEFS[4]
    main.add_face(vertices, triangles, uvs, normals, (0, 0, 0), "grass_top", normal, corners, uv_order)
    Entity(
        parent=scene,
        model=Mesh(vertices=vertices, triangles=triangles, uvs=uvs, normals=normals),
        texture=main.ATLAS_TEXTURE,
        color=color.white,
    )

    for _ in range(6):
        base.graphicsEngine.renderFrame()

    out = Path("tmp_texture_probe") / "atlas_quad.png"
    out.parent.mkdir(exist_ok=True)
    base.screenshot(str(out), defaultFilename=False)
    return out


def summarize(path: Path) -> None:
    image = Image.open(path).convert("RGBA")
    colors = image.getcolors(maxcolors=1000000)
    colors = sorted(colors or [], reverse=True)
    print(path)
    print("center", image.getpixel((image.width // 2, image.height // 2)))
    print("top colors", colors[:8])


def render_world() -> Path:
    for child in camera.ui.children:
        child.enabled = False
    main.selector.enabled = False
    camera.enabled = True
    camera.parent = scene
    camera.position = (0, main.terrain_height(0, 0) + 8, -12)
    camera.look_at(Vec3(0, main.terrain_height(0, 0), 0))
    camera.orthographic = False

    for _ in range(8):
        base.graphicsEngine.renderFrame()

    out = Path("tmp_texture_probe") / "world.png"
    out.parent.mkdir(exist_ok=True)
    base.screenshot(str(out), defaultFilename=False)
    return out


if __name__ == "__main__":
    summarize(render_atlas_quad())
    summarize(render_world())
