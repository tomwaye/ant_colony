"""Saving and loading maps, and the preset scenarios."""
import base64
import json
import os

import numpy

from config import *
from sim import World

def save_map(world, path):
    """Save the map (walls, terrain, nests and food). Ants and trails aren't saved."""
    data = {
        "version": 1,
        "grid": list(GRID_SHAPE),
        "walls": base64.b64encode(numpy.packbits(world.walls)).decode("ascii"),
        "terrain": base64.b64encode(world.terrain.astype(numpy.int8).tobytes()).decode("ascii"),
        "colonies": [colony.pos.tolist() for colony in world.colonies],
        "foods": [{"pos": food.pos.tolist(), "amount": int(food.quantity), "kind": int(food.kind)} for food in world.foods],
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def load_map(path, seed=None):
    with open(path) as f:
        data = json.load(f)
    if tuple(data["grid"]) != GRID_SHAPE:
        raise ValueError(f"{path} was saved for a {data['grid']} grid, but this world is {list(GRID_SHAPE)}")
    world = World(seed)
    size = GRID_SHAPE[0] * GRID_SHAPE[1]
    world.walls = numpy.unpackbits(numpy.frombuffer(base64.b64decode(data["walls"]), numpy.uint8))[:size].reshape(GRID_SHAPE).astype(bool)
    world.terrain = numpy.frombuffer(base64.b64decode(data["terrain"]), numpy.int8).reshape(GRID_SHAPE).copy()
    for pos in data["colonies"]:
        world.add_colony(pos)
    for food in data["foods"]:
        world.add_food(food["pos"], food["amount"], food["kind"])
    return world

def preset_open(world):
    settings.food_spawn_interval = FOOD_SPAWN_INTERVAL
    world.add_colony((450, 600))
    world.add_colony((1150, 600))
    # a sugar source near each nest, contested ones in the middle, and protein on the flanks
    for pos in ((250, 380), (300, 860), (1350, 380), (1300, 860), (800, 300), (800, 900)):
        world.add_food(pos, 1000, SUGAR)
    world.add_food((800, 600), 500, PROTEIN)
    world.add_food((150, 600), 500, PROTEIN)
    world.add_food((1450, 600), 500, PROTEIN)
    world.paint("water", (560, 300), (620, 340), 10)
    world.paint("sand", (980, 820), (1100, 760), 9)

def preset_maze(world):
    settings.food_spawn_interval = FOOD_SPAWN_INTERVAL
    columns, rows, size = 8, 6, 200
    # recursive backtracker: start with every wall up, knock walls down along a random walk
    open_edges = set()
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        x, y = stack[-1]
        options = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= x + dx < columns and 0 <= y + dy < rows and (x + dx, y + dy) not in seen]
        if not options:
            stack.pop()
            continue
        nxt = options[world.rng.integers(len(options))]
        open_edges.add(frozenset(((x, y), nxt)))
        seen.add(nxt)
        stack.append(nxt)
    for x in range(columns):
        for y in range(rows):
            if x + 1 < columns and frozenset(((x, y), (x + 1, y))) not in open_edges:
                world.paint("wall", ((x + 1) * size, y * size), ((x + 1) * size, (y + 1) * size), 2)
            if y + 1 < rows and frozenset(((x, y), (x, y + 1))) not in open_edges:
                world.paint("wall", (x * size, (y + 1) * size), ((x + 1) * size, (y + 1) * size), 2)
    world.add_colony((100, 100))
    world.add_colony((1500, 1100))
    for cell, kind in (((7, 0), SUGAR), ((0, 5), SUGAR), ((3, 2), PROTEIN), ((4, 3), SUGAR), ((5, 1), SUGAR), ((2, 4), PROTEIN)):
        world.add_food(((cell[0] + 0.5) * size, (cell[1] + 0.5) * size), 1000 if kind == SUGAR else 400, kind)

def preset_corridor(world):
    """One colony at the top of a long zigzag corridor, with the food at the bottom."""
    settings.food_spawn_interval = 0
    for y, x0, x1 in ((300, 0, 1350), (600, 250, 1600), (900, 0, 1350)):
        world.paint("wall", (x0, y), (x1, y), 3)
    world.add_colony((120, 150))
    world.add_food((120, 1060), 5000, SUGAR)
    world.add_food((300, 1060), 1000, PROTEIN)

def preset_duel(world):
    """Two colonies and a single feeding ground between them."""
    settings.food_spawn_interval = 0
    world.add_colony((400, 600))
    world.add_colony((1200, 600))
    world.add_food((800, 560), 5000, SUGAR)
    world.add_food((800, 660), 1000, PROTEIN)

def preset_islands(world):
    """Colonies on islands. Only one bridge exists; build roads (tool 6) across the water for more."""
    settings.food_spawn_interval = FOOD_SPAWN_INTERVAL
    world.terrain[:] = WATER
    from sim import circle_mask
    for center, radius in (((350, 600), 230), ((1250, 600), 230), ((800, 260), 140), ((800, 940), 140)):
        world.terrain[circle_mask(center, radius)] = GROUND
    world.paint("road", (500, 760), (680, 900), 4)
    world.add_colony((350, 600))
    world.add_colony((1250, 600))
    world.add_food((800, 260), 400, PROTEIN)
    world.add_food((800, 940), 2000, SUGAR)
    world.add_food((300, 450), 500, SUGAR)
    world.add_food((1300, 750), 500, SUGAR)

PRESETS = {
    "open": preset_open,
    "maze": preset_maze,
    "corridor": preset_corridor,
    "duel": preset_duel,
    "islands": preset_islands,
}

def make_preset(name, seed=None):
    world = World(seed)
    PRESETS[name](world)
    return world
