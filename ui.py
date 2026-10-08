"""On-screen panels and controls: settings sliders, the HUD, the tool bar, graphs, messages and recording."""
import os
import time

import numpy
import pygame

from config import *
from sim import food_radius

TOOLS = ("wall", "sugar", "protein", "sand", "water", "road", "boot", "spider")
PAINT_TOOLS = ("wall", "sand", "water", "road")
FOOD_TOOLS = {"sugar": (SUGAR, SUGAR_AMOUNTS), "protein": (PROTEIN, PROTEIN_AMOUNTS)}
CAPTURE_DIR = "captures"

def make_fonts():
    names = "helveticaneue,helvetica,arial,dejavusans"
    return pygame.font.SysFont(names, 15), pygame.font.SysFont(names, 12)

def render_text(screen, text, pos, color, font):
    screen.blit(font.render(text, True, color), pos)

def draw_panel(screen, rect):
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, PANEL_COLOR, panel.get_rect(), border_radius=10)
    pygame.draw.rect(panel, PANEL_BORDER_COLOR, panel.get_rect(), 1, border_radius=10)
    screen.blit(panel, rect)

def draw_pill(screen, font, text, center_top, color=TEXT_COLOR):
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(midtop=center_top).inflate(28, 10)
    draw_panel(screen, rect)
    screen.blit(rendered, rendered.get_rect(center=rect.center))
    return rect

def stamp():
    return time.strftime("%Y%m%d_%H%M%S")

class Slider:
    def __init__(self, label, attr, low, high, fmt):
        self.label = label
        self.attr = attr
        self.low = low
        self.high = high
        self.fmt = fmt

    @property
    def value(self):
        return getattr(settings, self.attr)

    def set(self, value):
        setattr(settings, self.attr, min(max(value, self.low), self.high))

    def fraction(self):
        return (self.value - self.low) / (self.high - self.low)

    def text(self):
        return self.fmt(self.value) if callable(self.fmt) else self.fmt.format(self.value)

def every(v):
    return "off" if v < 1 else f"{v:.0f}s"

class SettingsPanel:
    ROW = 26

    def __init__(self):
        bounds = dict(zip(GENES, GENE_BOUNDS))
        self.sliders = [
            Slider("ant speed", "speed", *bounds["speed"], "{:.0f}"),
            Slider("wander", "wander", *bounds["wander"], "{:.1f}"),
            Slider("turn towards food trail", "turn_food", *bounds["turn_food"], "{:.1f}"),
            Slider("turn towards home trail", "turn_home", *bounds["turn_home"], "{:.1f}"),
            Slider("sensor angle", "sensor_angle", *bounds["sensor_angle"], "{:.0f}°"),
            Slider("sensor distance", "sensor_distance", *bounds["sensor_distance"], "{:.0f}px"),
            Slider("deposit rate", "deposit_rate", 0, 8, "{:.1f}"),
            Slider("trail left after 1s", "evaporation_retention", 0.3, 0.99, "{:.2f}"),
            Slider("trail spread", "diffusion", 0, 3, "{:.2f}"),
            Slider("avoid rival trails", "territory", 0, 2, "{:.2f}"),
            Slider("food eaten per ant per s", "appetite", 0, 0.01, "{:.4f}"),
            Slider("food per new ant", "spawn_cost", 0.1, 5, "{:.1f}"),
            Slider("protein per new ant", "protein_cost", 0, 0.5, "{:.2f}"),
            Slider("lifespan", "lifespan", 20, 400, "{:.0f}s"),
            Slider("survives starving for", "starve_time", 2, 60, "{:.0f}s"),
            Slider("new food every", "food_spawn_interval", 0, 120, every),
            Slider("new spider every", "spider_interval", 0, 300, every),
            Slider("rain roughly every", "rain_interval", 0, 300, every),
            Slider("day length", "day_length", 0, 600, lambda v: "always day" if v < 10 else f"{v:.0f}s"),
            Slider("fight deadliness", "fight_rate", 0, 6, "{:.1f}"),
            Slider("mutation size", "mutation", 0, 0.3, "{:.2f}"),
        ]
        self.visible = False
        self.selected = 0
        self.dragging = None
        self.rect = pygame.Rect(SCREEN_WIDTH - 256, 16, 240, self.ROW * len(self.sliders) + 62)

    def track_rect(self, k):
        return pygame.Rect(self.rect.x + 14, self.rect.y + 40 + k * self.ROW + 15, self.rect.width - 28, 4)

    def blocks_mouse(self, pos):
        return self.visible and (self.rect.collidepoint(pos) or self.dragging is not None)

    def drag_to(self, x):
        slider = self.sliders[self.dragging]
        track = self.track_rect(self.dragging)
        slider.set(slider.low + (x - track.x) / track.width * (slider.high - slider.low))

    def handle_event(self, event):
        """Returns True if the panel used the event."""
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            for k in range(len(self.sliders)):
                if self.track_rect(k).inflate(0, 16).collidepoint(event.pos):
                    self.selected = self.dragging = k
                    self.drag_to(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging is not None:
            self.drag_to(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging is not None:
            self.dragging = None
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
            slider = self.sliders[self.selected]
            step = (slider.high - slider.low) / 40
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.sliders)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.sliders)
            elif event.key == pygame.K_LEFT:
                slider.set(slider.value - step)
            else:
                slider.set(slider.value + step)
            return True
        return False

    def draw(self, screen, fonts):
        if not self.visible:
            return
        font, small = fonts
        draw_panel(screen, self.rect)
        render_text(screen, "settings", (self.rect.x + 14, self.rect.y + 10), TEXT_COLOR, font)
        hint = small.render("arrows or drag", True, TEXT_DIM_COLOR)
        screen.blit(hint, (self.rect.right - 14 - hint.get_width(), self.rect.y + 13))
        for k, slider in enumerate(self.sliders):
            top = self.rect.y + 40 + k * self.ROW
            selected = k == self.selected
            render_text(screen, slider.label, (self.rect.x + 14, top), TEXT_COLOR if selected else TEXT_DIM_COLOR, small)
            value = small.render(slider.text(), True, TEXT_COLOR)
            screen.blit(value, (self.rect.right - 14 - value.get_width(), top))
            track = self.track_rect(k)
            pygame.draw.rect(screen, SLIDER_TRACK_COLOR, track, border_radius=2)
            filled = track.copy()
            filled.width = int(track.width * slider.fraction())
            pygame.draw.rect(screen, SLIDER_ACTIVE_COLOR if selected else SLIDER_FILL_COLOR, filled, border_radius=2)
            pygame.draw.circle(screen, TEXT_COLOR, (track.x + filled.width, track.centery), 5 if selected else 4)
        note = ("evolution on: the first six only seed new colonies" if settings.evolution
                else "E turns on evolution")
        render_text(screen, note, (self.rect.x + 14, self.rect.bottom - 22), TEXT_DIM_COLOR, small)

def draw_hud(screen, fonts, world, status):
    font, small = fonts
    colonies = world.colonies
    panel = pygame.Rect(16, 16, 300, 40 * max(len(colonies), 1) + 40)
    draw_panel(screen, panel)
    for k, colony in enumerate(colonies):
        y = panel.y + 10 + k * 40
        pygame.draw.circle(screen, colony.palette.nest, (panel.x + 18, y + 9), 5)
        render_text(screen, f"{colony.ant_count} ants", (panel.x + 32, y), TEXT_COLOR, font)
        stores = [(f"{int(colony.food)} food", STARVING_COLOR if colony.starving else TEXT_COLOR),
                  (f"   {int(colony.protein)} protein", TEXT_COLOR)]
        x = panel.right - 14
        for text, color in reversed(stores):
            rendered = font.render(text, True, color)
            x -= rendered.get_width()
            screen.blit(rendered, (x, y))
        workers, soldiers, scouts = colony.caste_counts
        render_text(screen, f"{workers} workers · {soldiers} soldiers · {scouts} scouts", (panel.x + 32, y + 19), TEXT_DIM_COLOR, small)
    if not colonies:
        render_text(screen, "every colony has died out (N to found one)", (panel.x + 14, panel.y + 12), TEXT_DIM_COLOR, small)
    render_text(screen, status, (panel.x + 14, panel.bottom - 22), TEXT_DIM_COLOR, small)
    return panel

def draw_toolbar(screen, fonts, tool, size_text, show_help):
    font, small = fonts
    pieces = []
    for k, name in enumerate(TOOLS):
        pieces.append((f"{k + 1} {name}", TEXT_COLOR if name == tool else TEXT_DIM_COLOR, name == tool))
    pieces.append((f"[ ] {size_text}", TEXT_DIM_COLOR, False))
    rendered = [(small.render(text, True, color), active) for text, color, active in pieces]
    gap = 14
    tools_width = sum(r.get_width() for r, _ in rendered) + gap * (len(rendered) - 1)

    lines = []
    if show_help:
        lines = [
            "right drag: erase    wheel: zoom    WASD or middle drag: pan    0: whole map    space: pause    - / +: speed",
            "N: new colony    E: evolution    R: rain    P: trails    G: graphs    Tab: settings    M: next preset",
            "ctrl+S / ctrl+O: save / load map    I: screenshot    V: record    H: hide help    Esc: quit",
        ]
    texts = [small.render(line, True, TEXT_DIM_COLOR) for line in lines]
    width = max([tools_width] + [t.get_width() for t in texts])
    rect = pygame.Rect(0, 0, width + 32, 26 + 16 * len(texts))
    rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 10)
    draw_panel(screen, rect)

    x = rect.centerx - tools_width // 2
    for text, active in rendered:
        if active:
            pygame.draw.rect(screen, SLIDER_TRACK_COLOR, text.get_rect(topleft=(x, rect.y + 6)).inflate(10, 4), border_radius=5)
        screen.blit(text, (x, rect.y + 6))
        x += text.get_width() + gap
    for k, text in enumerate(texts):
        screen.blit(text, text.get_rect(midtop=(rect.centerx, rect.y + 26 + k * 16)))

class GraphPanel:
    WIDTH = 300
    CHART_HEIGHT = 70

    def __init__(self):
        self.visible = False

    def draw(self, screen, fonts, world, top):
        if not self.visible:
            return
        font, small = fonts
        colonies = world.colonies
        genome_rows = len(colonies) + 1 if settings.evolution and colonies else 0
        rect = pygame.Rect(16, top, self.WIDTH, 2 * (self.CHART_HEIGHT + 30) + 12 + 16 * genome_rows)
        draw_panel(screen, rect)
        y = rect.y + 8
        for title, column in (("population", 1), ("food store", 2)):
            y = self.draw_chart(screen, small, world, title, column, rect.x + 12, y, rect.width - 24)
        if genome_rows:
            self.draw_genomes(screen, small, colonies, rect.x + 12, y + 4)

    def draw_chart(self, screen, small, world, title, column, x, y, width):
        render_text(screen, title, (x, y), TEXT_COLOR, small)
        chart = pygame.Rect(x, y + 18, width, self.CHART_HEIGHT)
        pygame.draw.rect(screen, SLIDER_TRACK_COLOR, chart, 1)
        series = [(colony.palette.nest, numpy.array(colony.history)) for colony in world.colonies if len(colony.history) > 1]
        peak = max([data[:, column].max() for _, data in series] + [1])
        label = small.render(f"{peak:.0f}", True, TEXT_DIM_COLOR)
        screen.blit(label, (chart.right - label.get_width(), y))
        start = world.time - HISTORY_SECONDS
        for color, data in series:
            xs = chart.x + (data[:, 0] - start) / HISTORY_SECONDS * chart.width
            ys = chart.bottom - 1 - data[:, column] / peak * (chart.height - 2)
            pygame.draw.lines(screen, color, False, numpy.stack([xs, ys], axis=1).tolist(), 2)
        return chart.bottom + 12

    def draw_genomes(self, screen, small, colonies, x, y):
        headings = ("speed", "wander", "food", "home", "angle", "reach")
        column = (self.WIDTH - 24 - 20) / len(headings)
        for k, heading in enumerate(headings):
            render_text(screen, heading, (x + 20 + k * column, y), TEXT_DIM_COLOR, small)
        for row, colony in enumerate(colonies):
            ty = y + 16 * (row + 1)
            pygame.draw.circle(screen, colony.palette.nest, (x + 6, ty + 7), 4)
            for k, value in enumerate(colony.genome):
                render_text(screen, f"{value:.1f}", (x + 20 + k * column, ty), TEXT_COLOR, small)

class Toasts:
    def __init__(self):
        self.messages = []

    def show(self, text, seconds=2.5):
        self.messages = (self.messages + [(text, time.time() + seconds)])[-3:]

    def draw(self, screen, fonts, top):
        now = time.time()
        self.messages = [(text, until) for text, until in self.messages if until > now]
        for text, _ in self.messages:
            top = draw_pill(screen, fonts[1], text, (SCREEN_WIDTH // 2, top)).bottom + 6

class Recorder:
    """Records the view to a GIF (with Pillow installed) or a folder of numbered PNG frames."""
    FPS = 15
    MAX_SECONDS = 30
    SIZE = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    def __init__(self):
        self.active = False

    def start(self):
        try:
            from PIL import Image
            self.image = Image
        except ImportError:
            self.image = None
        self.name = os.path.join(CAPTURE_DIR, f"recording_{stamp()}")
        os.makedirs(self.name if self.image is None else CAPTURE_DIR, exist_ok=True)
        self.frames = []
        self.count = 0
        self.timer = 1.0
        self.active = True

    def capture(self, screen, real_dt):
        """Returns a message if the recording stopped itself."""
        self.timer += real_dt
        if self.timer < 1 / self.FPS:
            return None
        self.timer = 0.0
        small = pygame.transform.smoothscale(screen, self.SIZE)
        if self.image is not None:
            frame = self.image.frombytes("RGB", self.SIZE, pygame.image.tobytes(small, "RGB"))
            self.frames.append(frame.quantize(colors=255, method=self.image.Quantize.FASTOCTREE))
        else:
            pygame.image.save(small, os.path.join(self.name, f"frame_{self.count:04d}.png"))
        self.count += 1
        if self.count >= self.FPS * self.MAX_SECONDS:
            return self.stop()
        return None

    def stop(self):
        self.active = False
        if self.image is None:
            return f"saved {self.count} frames to {self.name}/ (install Pillow for GIFs)"
        if not self.frames:
            return "nothing recorded"
        path = self.name + ".gif"
        self.frames[0].save(path, save_all=True, append_images=self.frames[1:], duration=int(1000 / self.FPS), loop=0)
        self.frames = []
        return f"saved {path}"

def save_screenshot(screen):
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    path = os.path.join(CAPTURE_DIR, f"screenshot_{stamp()}.png")
    pygame.image.save(screen, path)
    return path

def draw_cursor(screen, camera, mouse, tool, brush, food_amount, erasing):
    s = camera.scale
    if erasing:
        pygame.draw.circle(screen, STARVING_COLOR, mouse, (brush + 0.5) * SIZE_CELLS * s, 1)
    elif tool in PAINT_TOOLS:
        pygame.draw.circle(screen, WALL_LIGHT_COLOR, mouse, (brush + 0.5) * SIZE_CELLS * s, 1)
    elif tool in FOOD_TOOLS:
        kind = FOOD_TOOLS[tool][0]
        color = SUGAR_COLOR if kind == SUGAR else PROTEIN_COLOR
        pygame.draw.circle(screen, color, mouse, food_radius(food_amount, kind) * s, 1)
    elif tool == "boot":
        pygame.draw.circle(screen, STARVING_COLOR, mouse, BOOT_RADIUS * s, 2)
    else:
        pygame.draw.circle(screen, SPIDER_LEG_COLOR, mouse, 12 * s, 1)
