"""Drawing the world: a camera over a map bigger than the window, terrain, trails, ants and weather."""
import numpy
import pygame

from config import *
from sim import soften

MIN_ZOOM = max(SCREEN_WIDTH / WORLD_WIDTH, SCREEN_HEIGHT / WORLD_HEIGHT)
MAX_ZOOM = 4.0

class Camera:
    def __init__(self):
        self.zoom = 1.0
        self.center = numpy.array([WORLD_WIDTH / 2, WORLD_HEIGHT / 2])
        self.update()

    def update(self):
        self.zoom = min(max(self.zoom, MIN_ZOOM), MAX_ZOOM)
        w = min(WORLD_WIDTH, round(SCREEN_WIDTH / self.zoom))
        h = min(WORLD_HEIGHT, round(SCREEN_HEIGHT / self.zoom))
        x = int(min(max(self.center[0] - w / 2, 0), WORLD_WIDTH - w))
        y = int(min(max(self.center[1] - h / 2, 0), WORLD_HEIGHT - h))
        self.rect = pygame.Rect(x, y, w, h)
        self.center = numpy.array([x + w / 2, y + h / 2])
        self.scale_x = SCREEN_WIDTH / w
        self.scale_y = SCREEN_HEIGHT / h
        self.scale = (self.scale_x + self.scale_y) / 2

    def to_screen(self, x, y):
        return (x - self.rect.x) * self.scale_x, (y - self.rect.y) * self.scale_y

    def to_world(self, screen_pos):
        return numpy.array([self.rect.x + screen_pos[0] / self.scale_x, self.rect.y + screen_pos[1] / self.scale_y])

    def zoom_at(self, screen_pos, factor):
        """Zoom while keeping the point under the cursor where it is."""
        before = self.to_world(screen_pos)
        self.zoom *= factor
        self.update()
        self.center += before - self.to_world(screen_pos)
        self.update()

    def pan(self, dx, dy):
        self.center += (dx / self.scale_x, dy / self.scale_y)
        self.update()

    def look_at(self, pos, zoom=None):
        if zoom is not None:
            self.zoom = zoom
        self.center = numpy.array(pos, numpy.float64)
        self.update()

def array_to_surface(rgb):
    surface = pygame.Surface(rgb.shape[:2])
    pygame.surfarray.blit_array(surface, numpy.clip(rgb, 0, 255).astype(numpy.uint8))
    return surface

def make_glow(radius, color, intensity):
    radius = max(int(radius), 2)
    xs = numpy.arange(radius * 2) - radius + 0.5
    falloff = numpy.clip(1 - numpy.sqrt(xs[:, None] ** 2 + xs[None, :] ** 2) / radius, 0, 1) ** 2
    return array_to_surface(numpy.array(color)[None, None, :] * falloff[:, :, None] * intensity)

def upscale(values, factor):
    """Bilinear upscale by a whole factor. Done in numpy so any region lines up exactly with its neighbours."""
    for axis in (0, 1):
        n = values.shape[axis]
        coords = (numpy.arange(n * factor) + 0.5) / factor - 0.5
        low = numpy.clip(numpy.floor(coords).astype(numpy.intp), 0, n - 1)
        high = numpy.clip(low + 1, 0, n - 1)
        frac = numpy.clip(coords - numpy.floor(coords), 0, 1)
        shape = [1, 1]
        shape[axis] = -1
        frac = frac.reshape(shape)
        values = numpy.take(values, low, axis=axis) * (1 - frac) + numpy.take(values, high, axis=axis) * frac
    return values

def shifted(mask, dx, dy):
    """mask moved by (dx, dy) pixels, padding with False."""
    out = numpy.zeros_like(mask)
    w, h = mask.shape
    out[max(dx, 0):w + min(dx, 0), max(dy, 0):h + min(dy, 0)] = mask[max(-dx, 0):w - max(dx, 0), max(-dy, 0):h - max(dy, 0)]
    return out

class Renderer:
    def __init__(self, seed=None):
        rng = numpy.random.default_rng(seed)
        self.grain = rng.uniform(-1, 1, (WORLD_WIDTH, WORLD_HEIGHT)).astype(numpy.float32)
        self.background = self.make_background(rng)
        self.vignette = self.make_vignette()
        self.layer = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT), pygame.SRCALPHA)
        self.layer_walls = None
        self.layer_terrain = None
        self.pellets = {}
        self.glows = {}
        self.rain_drops = rng.uniform(0, 1, (RAIN_DROPS, 2)) * (SCREEN_WIDTH, SCREEN_HEIGHT)
        self.ant_colors = self.make_ant_colors()

    def make_background(self, rng):
        # dark ground with soft blotches and fine grain so it doesn't look like a flat void
        blotches = upscale(rng.random((WORLD_WIDTH // 50, WORLD_HEIGHT // 50)), 50) - 0.5
        shade = blotches * 14 + self.grain * 3
        return array_to_surface(numpy.array(BACKGROUND_COLOR) + shade[:, :, None]).convert()

    def make_vignette(self):
        xs = numpy.linspace(-1, 1, SCREEN_WIDTH)
        ys = numpy.linspace(-1, 1, SCREEN_HEIGHT)
        factor = numpy.clip(1 - VIGNETTE_STRENGTH * (xs[:, None] ** 2 + ys[None, :] ** 2) / 2, 0, 1) * 255
        return array_to_surface(numpy.repeat(factor[:, :, None], 3, axis=2)).convert()

    def make_ant_colors(self):
        # [colony, caste, lost] -> colour; soldiers wear the nest colour, lost ants are dimmed
        colors = numpy.zeros((MAX_COLONIES, 3, 2, 3), numpy.uint8)
        for k, palette in enumerate(PALETTES):
            for caste, color in ((WORKER, palette.ant), (SOLDIER, palette.nest), (SCOUT, palette.ant)):
                colors[k, caste, 0] = color
                colors[k, caste, 1] = tuple(c // 2 for c in color)
        return colors

    # ---- terrain and walls ----

    def refresh_layer(self, world):
        """Rebuild only the part of the terrain layer that changed since last frame."""
        if self.layer_walls is None:
            changed = numpy.ones(GRID_SHAPE, bool)
        else:
            changed = (world.walls != self.layer_walls) | (world.terrain != self.layer_terrain)
        if not changed.any():
            return
        cols = numpy.nonzero(changed.any(axis=1))[0]
        rows = numpy.nonzero(changed.any(axis=0))[0]
        self.build_region(world, cols[0], cols[-1] + 1, rows[0], rows[-1] + 1)
        self.layer_walls = world.walls.copy()
        self.layer_terrain = world.terrain.copy()

    def build_region(self, world, i0, i1, j0, j1):
        margin = 3
        a0, a1 = max(i0 - margin, 0), min(i1 + margin, GRID_SHAPE[0])
        b0, b1 = max(j0 - margin, 0), min(j1 + margin, GRID_SHAPE[1])
        terrain = world.terrain[a0:a1, b0:b1]
        x0, y0 = a0 * SIZE_CELLS, b0 * SIZE_CELLS
        w, h = (a1 - a0) * SIZE_CELLS, (b1 - b0) * SIZE_CELLS
        grain = self.grain[x0:x0 + w, y0:y0 + h]

        def smooth(cells):
            # smooth the blocky grid into rounded outlines (the max keeps lone cells visible)
            if not cells.any():
                return numpy.zeros((w, h), bool)
            cells = cells.astype(numpy.float32)
            return upscale(numpy.maximum(soften(cells), cells * 0.6), SIZE_CELLS) > 0.5

        rgb = numpy.zeros((w, h, 3), numpy.float32)
        alpha = numpy.zeros((w, h), numpy.uint8)

        sand = smooth(terrain == SAND)
        rgb[sand] = numpy.array(SAND_COLOR) + grain[sand][:, None] * 12
        alpha[sand] = 210

        water = smooth(terrain == WATER)
        if water.any():
            ripple = numpy.sin(((numpy.arange(h)[None, :] + y0) + (numpy.arange(w)[:, None] + x0) * 0.3) * 0.25 + grain * 0.8)
            rgb[water] = numpy.array(WATER_COLOR) + ripple[water][:, None] * 4
            shore = water & ~(shifted(water, 2, 2) & shifted(water, -2, -2) & shifted(water, 2, -2) & shifted(water, -2, 2))
            rgb[shore] = WATER_LIGHT_COLOR
            alpha[water] = 235

        road = smooth(terrain == ROAD)
        rgb[road] = numpy.array(ROAD_COLOR) + grain[road][:, None] * 5
        rgb[road & ~shifted(road, 2, 2)] = ROAD_LIGHT_COLOR
        alpha[road] = 255

        bridge = smooth(terrain == BRIDGE)
        if bridge.any():
            planks = ((numpy.arange(w)[:, None] + x0 + numpy.arange(h)[None, :] + y0) // 5) % 2 == 0
            rgb[bridge] = BRIDGE_COLOR
            rgb[bridge & planks] = BRIDGE_DARK_COLOR
            alpha[bridge] = 255

        # walls on top, lit from the top left with a drop shadow
        wall = smooth(world.walls[a0:a1, b0:b1])
        shadow = shifted(wall, 5, 5) & ~wall
        rgb[shadow] *= 0.4
        alpha[shadow] = numpy.maximum(alpha[shadow], WALL_SHADOW_ALPHA)
        rgb[wall] = numpy.array(WALL_COLOR) + grain[wall][:, None] * 8
        rgb[wall & ~shifted(wall, -2, -2)] = WALL_DARK_COLOR
        rgb[wall & ~shifted(wall, 2, 2)] = WALL_LIGHT_COLOR
        alpha[wall] = 255

        # copy the inside of the region (not its margin) into the layer
        ix0, iy0 = (i0 - a0) * SIZE_CELLS, (j0 - b0) * SIZE_CELLS
        ix1, iy1 = ix0 + (i1 - i0) * SIZE_CELLS, iy0 + (j1 - j0) * SIZE_CELLS
        pixels = pygame.surfarray.pixels3d(self.layer)
        pixels_alpha = pygame.surfarray.pixels_alpha(self.layer)
        px0, py0 = i0 * SIZE_CELLS, j0 * SIZE_CELLS
        pixels[px0:px0 + ix1 - ix0, py0:py0 + iy1 - iy0] = numpy.clip(rgb[ix0:ix1, iy0:iy1], 0, 255)
        pixels_alpha[px0:px0 + ix1 - ix0, py0:py0 + iy1 - iy0] = alpha[ix0:ix1, iy0:iy1]
        del pixels, pixels_alpha

    # ---- drawing ----

    def view_of(self, surface, camera):
        return pygame.transform.scale(surface.subsurface(camera.rect), (SCREEN_WIDTH, SCREEN_HEIGHT))

    def draw(self, screen, world, camera, show_trails, dt):
        self.refresh_layer(world)
        screen.blit(self.view_of(self.background, camera), (0, 0))
        screen.blit(self.view_of(self.layer, camera), (0, 0))
        # night darkens the ground; trails, food and ants are drawn after so they still glow
        self.draw_darkness(screen, world)
        if show_trails:
            self.draw_trails(screen, world, camera)
        for food in world.foods:
            self.draw_food(screen, food, camera)
        for colony in world.colonies:
            self.draw_nest(screen, colony, camera)
        self.draw_corpses(screen, world, camera)
        self.draw_ants(screen, world, camera)
        for spider in world.spiders:
            self.draw_spider(screen, spider, camera)
        self.draw_rain(screen, world, dt)
        screen.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_MULT)

    def draw_trails(self, screen, world, camera):
        if not world.colonies:
            return
        rect = camera.rect
        i0, i1 = max(rect.x // SIZE_CELLS - 1, 0), min(rect.right // SIZE_CELLS + 2, GRID_SHAPE[0])
        j0, j1 = max(rect.y // SIZE_CELLS - 1, 0), min(rect.bottom // SIZE_CELLS + 2, GRID_SHAPE[1])
        color = numpy.zeros((i1 - i0, j1 - j0, 3), numpy.float32)
        for colony in world.colonies:
            # 1 - e^-x keeps faint trails visible while strong ones saturate gently
            home = soften(1 - numpy.exp(-world.home[colony.id, i0:i1, j0:j1] * GLOW_GAIN))
            food = soften(1 - numpy.exp(-world.food[colony.id, i0:i1, j0:j1] * GLOW_GAIN))
            color += home[:, :, None] * numpy.array(colony.palette.home_trail, numpy.float32)
            color += food[:, :, None] * numpy.array(colony.palette.food_trail, numpy.float32)
        size = (round((i1 - i0) * SIZE_CELLS * camera.scale_x), round((j1 - j0) * SIZE_CELLS * camera.scale_y))
        glow = pygame.transform.smoothscale(array_to_surface(color), size)
        screen.blit(glow, camera.to_screen(i0 * SIZE_CELLS, j0 * SIZE_CELLS), special_flags=pygame.BLEND_ADD)

    def glow(self, radius, color, intensity):
        key = (int(radius), color, intensity)
        if key not in self.glows:
            if len(self.glows) > 200:
                self.glows.clear()
            self.glows[key] = make_glow(radius, color, intensity)
        return self.glows[key]

    def draw_nest(self, screen, colony, camera):
        center = camera.to_screen(*colony.pos)
        s = camera.scale
        palette = colony.palette
        rim = palette.rim
        if colony.starving and (pygame.time.get_ticks() // 400) % 2:
            rim = STARVING_COLOR
        glow = self.glow(colony.radius * 4 * s, palette.nest, 0.35)
        screen.blit(glow, glow.get_rect(center=center), special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(screen, rim, center, (colony.radius + 4) * s)
        pygame.draw.circle(screen, palette.nest, center, colony.radius * s)
        pygame.draw.circle(screen, palette.rim, center, colony.radius * 0.5 * s)
        pygame.draw.circle(screen, NEST_HOLE_COLOR, center, colony.radius * 0.5 * s - 2)

    def food_pellets(self, food):
        """A pile of pellets, nearest the middle first, so the pile shrinks inwards as it's eaten."""
        if food.id not in self.pellets:
            rng = numpy.random.default_rng(food.id)
            count = int(numpy.clip(FOOD_PELLETS * (food.radius / 30) ** 2, 8, 120))
            distance = numpy.sort(numpy.sqrt(rng.random(count))) * food.radius * 0.8
            angle = rng.uniform(0, 2 * numpy.pi, count)
            offsets = numpy.stack([numpy.cos(angle) * distance, numpy.sin(angle) * distance], axis=1)
            self.pellets[food.id] = (offsets, rng.uniform(3.5, 6, count), rng.uniform(0.75, 1, count))
        return self.pellets[food.id]

    def draw_food(self, screen, food, camera):
        center = camera.to_screen(*food.pos)
        reach = (food.radius + 10) * camera.scale
        if not (-reach < center[0] < SCREEN_WIDTH + reach and -reach < center[1] < SCREEN_HEIGHT + reach):
            return
        s = camera.scale
        base, rim = (SUGAR_COLOR, SUGAR_RIM_COLOR) if food.kind == SUGAR else (PROTEIN_COLOR, PROTEIN_RIM_COLOR)
        # protein browns as it spoils
        fresh = food.freshness
        base = tuple(int(b * fresh + s_ * (1 - fresh)) for b, s_ in zip(base, SPOILED_COLOR))
        glow = self.glow(food.radius * 3 * s, base, round(0.25 * fresh, 2))
        screen.blit(glow, glow.get_rect(center=center), special_flags=pygame.BLEND_ADD)

        offsets, radii, shades = self.food_pellets(food)
        remaining = int(numpy.ceil(len(offsets) * food.quantity / food.max_quantity))
        points = [(center[0] + dx * s, center[1] + dy * s) for dx, dy in offsets[:remaining]]
        for point, radius in zip(points, radii):
            pygame.draw.circle(screen, rim, point, (radius + 1.5) * s)
        highlight = tuple(min(255, c + 70) for c in base)
        for point, radius, shade in zip(points, radii, shades):
            pygame.draw.circle(screen, tuple(int(c * shade) for c in base), point, radius * s)
            pygame.draw.circle(screen, highlight, (point[0] - s, point[1] - s), radius * 0.35 * s)

    def visible(self, positions, camera, pad):
        rect = camera.rect
        return ((positions[:, 0] >= rect.x - pad) & (positions[:, 0] < rect.right + pad) &
                (positions[:, 1] >= rect.y - pad) & (positions[:, 1] < rect.bottom + pad))

    def plot(self, pixels, xs, ys, colors):
        xs = xs.astype(numpy.intp)
        ys = ys.astype(numpy.intp)
        inside = (xs >= 0) & (xs < SCREEN_WIDTH) & (ys >= 0) & (ys < SCREEN_HEIGHT)
        pixels[xs[inside], ys[inside]] = colors[inside] if colors.ndim == 2 else colors

    def draw_ants(self, screen, world, camera):
        """Every ant is a few pixels written straight into the screen, no draw calls."""
        ants = world.ants
        if not len(ants):
            return
        shown = self.visible(ants.pos, camera, 6)
        if not shown.any():
            return
        pos = ants.pos[shown]
        heading = ants.heading[shown]
        caste = ants.caste[shown]
        carrying = ants.carrying[shown]
        colors = self.ant_colors[ants.colony[shown], caste, ants.lost[shown].astype(numpy.intp)]
        dx, dy = numpy.cos(heading), numpy.sin(heading)
        length = numpy.array([4.0, 5.0, 3.0])[caste]
        sx, sy = camera.to_screen(pos[:, 0], pos[:, 1])

        pixels = pygame.surfarray.pixels3d(screen)
        samples = max(3, int(numpy.ceil(5 * camera.scale)) + 1)
        thick = caste == SOLDIER if camera.scale < 2 else numpy.ones(len(pos), bool)
        for t in numpy.linspace(-0.6, 0.4, samples):
            bx = sx + dx * t * length * camera.scale_x
            by = sy + dy * t * length * camera.scale_y
            self.plot(pixels, bx, by, colors)
            self.plot(pixels, bx[thick] - dy[thick], by[thick] + dx[thick], colors[thick])

        loaded = carrying > 0
        if loaded.any():
            crumb = numpy.array([(0, 0, 0), SUGAR_COLOR, PROTEIN_COLOR, LOOT_COLOR], numpy.uint8)[carrying[loaded]]
            hx = sx[loaded] + dx[loaded] * (0.4 * length[loaded] + 1.2) * camera.scale_x
            hy = sy[loaded] + dy[loaded] * (0.4 * length[loaded] + 1.2) * camera.scale_y
            for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                self.plot(pixels, hx + ox, hy + oy, crumb)
        del pixels

    def draw_corpses(self, screen, world, camera):
        if not len(world.corpses):
            return
        shown = self.visible(world.corpses, camera, 2)
        if not shown.any():
            return
        fade = 1 - (world.time - world.corpse_times[shown]) / CORPSE_TIME
        background = numpy.array(BACKGROUND_COLOR)
        colors = (background + (numpy.array(CORPSE_COLOR) - background) * fade[:, None]).astype(numpy.uint8)
        sx, sy = camera.to_screen(world.corpses[shown, 0], world.corpses[shown, 1])
        pixels = pygame.surfarray.pixels3d(screen)
        for ox, oy in ((0, 0), (1, 0), (0, 1)):
            self.plot(pixels, sx + ox, sy + oy, colors)
        del pixels

    def draw_spider(self, screen, spider, camera):
        center = numpy.array(camera.to_screen(*spider.pos))
        s = camera.scale
        forward = numpy.array([numpy.cos(spider.heading), numpy.sin(spider.heading)])
        side = numpy.array([-forward[1], forward[0]])
        for k in range(4):
            for sign in (-1, 1):
                swing = numpy.sin(spider.stride * 0.35 + k * 1.6 + (sign > 0) * numpy.pi) * 0.25
                angle = (0.55 + k * 0.45 + swing) * sign
                reach = forward * numpy.cos(angle) + side * numpy.sin(angle)
                knee = center + reach * 9 * s + forward * 3 * s
                foot = center + reach * 16 * s - forward * (k - 1.5) * 2 * s
                pygame.draw.lines(screen, SPIDER_LEG_COLOR, False, [center, knee, foot], max(1, int(1.5 * s)))
        pygame.draw.circle(screen, SPIDER_LEG_COLOR, center - forward * 5 * s, 7.5 * s)
        pygame.draw.circle(screen, SPIDER_BODY_COLOR, center - forward * 5 * s, 6.5 * s)
        pygame.draw.circle(screen, SPIDER_MARK_COLOR, center - forward * 5 * s, 2.2 * s)
        pygame.draw.circle(screen, SPIDER_LEG_COLOR, center + forward * 4 * s, 4.5 * s)
        pygame.draw.circle(screen, SPIDER_BODY_COLOR, center + forward * 4 * s, 3.5 * s)
        if spider.health < SPIDER_HEALTH:
            bar = pygame.Rect(0, 0, 24 * s, max(2, 2 * s))
            bar.center = (center[0], center[1] - 16 * s)
            pygame.draw.rect(screen, SPIDER_BODY_COLOR, bar)
            bar.width = int(bar.width * max(spider.health, 0) / SPIDER_HEALTH)
            pygame.draw.rect(screen, SPIDER_MARK_COLOR, bar)

    def draw_darkness(self, screen, world):
        darkness = (1 - world.light) * 0.85 + world.rain * 0.2
        if darkness > 0.01:
            tint = [int(255 + (n - 255) * min(darkness, 1)) for n in NIGHT_TINT]
            screen.fill(tint, special_flags=pygame.BLEND_MULT)

    def draw_rain(self, screen, world, dt):
        drops = int(RAIN_DROPS * world.rain)
        if drops:
            self.rain_drops += numpy.array([-120, 700]) * dt
            self.rain_drops %= (SCREEN_WIDTH, SCREEN_HEIGHT)
            for x, y in self.rain_drops[:drops]:
                pygame.draw.line(screen, RAIN_COLOR, (x, y), (x - 3, y + 14))
