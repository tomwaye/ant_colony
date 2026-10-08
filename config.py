"""Constants, colours and the live-tunable settings shared by every module."""
from collections import namedtuple

import numpy

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
WORLD_WIDTH = 1600
WORLD_HEIGHT = 1200
SIZE_CELLS = 4
GRID_SHAPE = (WORLD_WIDTH // SIZE_CELLS, WORLD_HEIGHT // SIZE_CELLS)

MAX_COLONIES = 3
START_ANTS = 500
MAX_ANTS = 12000

# the default genome: every ant carries its own copy of these (see GENES)
ANT_SPEED = 50
WANDER_WEIGHT = 3
TURN_RATE_FOOD = 10
TURN_RATE_HOME = 7
SENSOR_ANGLE = 45
SENSOR_DISTANCE = 8 * SIZE_CELLS

HOMING_RATE = 1.5
STEERING_GAIN = 3
DEPOSIT_RATE = 2
EVAPORATION_RETENTION = 0.8
DIFFUSION = 0.5
PHEROMONE_STRENGTH = 1.0
MAX_PHEROMONE = 3.0
TERRITORY = 0.5

# castes
WORKER, SOLDIER, SCOUT = 0, 1, 2
CASTE_ATTACK = numpy.array([1.0, 4.0, 0.5])
CASTE_DEFENCE = numpy.array([1.0, 3.0, 0.8])
CASTE_COST = numpy.array([1.0, 2.5, 1.0])
CASTE_WANDER = numpy.array([1.0, 1.0, 1.7])
CASTE_DEPOSIT = numpy.array([1.0, 0.6, 0.5])
CASTE_RETENTION = numpy.array([0.9, 0.93, 0.96])
START_CASTE_MIX = (0.85, 0.05, 0.10)

# colony economy
START_FOOD = 200
START_PROTEIN = 40
APPETITE = 0.001
SPAWN_COST = 0.5
PROTEIN_COST = 0.05
NO_PROTEIN_COST = 4
SPAWN_INTERVAL = 0.05
SPAWN_RESERVE_SECONDS = 240
LIFESPAN = 300
STARVE_TIME = 20
STARVE_RECOVERY = 10
CORPSE_TIME = 8
MAX_CORPSES = 4000

# what an ant can carry
SUGAR, PROTEIN, LOOT = 1, 2, 3
SUGAR_AMOUNTS = (100, 250, 500, 1000, 2000, 5000)
PROTEIN_AMOUNTS = (50, 100, 200, 300, 500, 1000)
PROTEIN_LIFETIME = 120
SUGAR_LIFETIME = 300
FOOD_SPAWN_INTERVAL = 25
PROTEIN_SPAWN_CHANCE = 0.4
MAX_FOOD_SOURCES = 10

# terrain
GROUND, SAND, WATER, ROAD, BRIDGE = 0, 1, 2, 3, 4
TERRAIN_SPEED = numpy.array([1.0, 0.5, 1.0, 1.6, 1.6])

# fighting and predators
FIGHT_CELL = 8
FIGHT_RATE = 0.4
SPIDER_INTERVAL = 90
SPIDER_SPEED = 40
SPIDER_SIGHT = 70
SPIDER_REACH = 7
SPIDER_EAT_COOLDOWN = 0.6
SPIDER_HEALTH = 30
SPIDER_LIFETIME = 120
SOLDIER_DAMAGE = 3.0
WORKER_DAMAGE = 0.3
BOOT_RADIUS = 18

# day, night and rain
DAY_LENGTH = 180
NIGHT_SPEED = 0.55
RAIN_INTERVAL = 90
RAIN_DURATION = 20
RAIN_WASH = 4

# evolution
MUTATION = 0.15
SELECTION_RATE = 0.03

HISTORY_SECONDS = 300
MAX_DT = 1 / 30
SPEEDS = (0.25, 0.5, 1, 2, 4, 8)

GENES = ("speed", "wander", "turn_food", "turn_home", "sensor_angle", "sensor_distance")
SPEED_GENE, WANDER_GENE, TURN_FOOD_GENE, TURN_HOME_GENE, ANGLE_GENE, DISTANCE_GENE = range(len(GENES))
GENE_BOUNDS = numpy.array([(10, 150), (0, 10), (0, 25), (0, 25), (5, 90), (4, 80)], numpy.float64)

class Settings:
    """Values that can be changed while running from the settings panel (Tab)."""
    def __init__(self):
        # genes: with evolution off every ant uses these; with it on they seed new colonies
        self.speed = ANT_SPEED
        self.wander = WANDER_WEIGHT
        self.turn_food = TURN_RATE_FOOD
        self.turn_home = TURN_RATE_HOME
        self.sensor_angle = SENSOR_ANGLE
        self.sensor_distance = SENSOR_DISTANCE

        self.deposit_rate = DEPOSIT_RATE
        self.evaporation_retention = EVAPORATION_RETENTION
        self.diffusion = DIFFUSION
        self.territory = TERRITORY
        self.appetite = APPETITE
        self.spawn_cost = SPAWN_COST
        self.protein_cost = PROTEIN_COST
        self.lifespan = LIFESPAN
        self.starve_time = STARVE_TIME
        self.food_spawn_interval = FOOD_SPAWN_INTERVAL
        self.spider_interval = SPIDER_INTERVAL
        self.rain_interval = RAIN_INTERVAL
        self.day_length = DAY_LENGTH
        self.fight_rate = FIGHT_RATE
        self.mutation = MUTATION
        self.evolution = False

    def genome(self):
        return numpy.array([getattr(self, gene) for gene in GENES], numpy.float64)

settings = Settings()

Palette = namedtuple("Palette", "nest rim home_trail food_trail ant")
PALETTES = (
    Palette(nest=(255, 170, 50), rim=(120, 60, 10), home_trail=(255, 60, 150), food_trail=(40, 220, 255), ant=(225, 220, 255)),
    Palette(nest=(255, 95, 70), rim=(110, 30, 20), home_trail=(255, 120, 20), food_trail=(255, 230, 70), ant=(255, 215, 180)),
    Palette(nest=(120, 200, 255), rim=(30, 60, 110), home_trail=(110, 90, 255), food_trail=(170, 255, 210), ant=(190, 240, 255)),
)

BACKGROUND_COLOR = (10, 8, 22)
NEST_HOLE_COLOR = (45, 20, 8)
STARVING_COLOR = (255, 70, 70)
SUGAR_COLOR = (150, 255, 80)
SUGAR_RIM_COLOR = (40, 90, 20)
PROTEIN_COLOR = (255, 130, 110)
PROTEIN_RIM_COLOR = (110, 40, 35)
SPOILED_COLOR = (95, 75, 55)
LOOT_COLOR = (255, 215, 0)
CORPSE_COLOR = (120, 110, 130)
WALL_COLOR = (90, 85, 110)
WALL_LIGHT_COLOR = (150, 145, 185)
WALL_DARK_COLOR = (45, 42, 62)
WALL_SHADOW_ALPHA = 120
SAND_COLOR = (82, 70, 48)
WATER_COLOR = (25, 60, 125)
WATER_LIGHT_COLOR = (70, 120, 200)
ROAD_COLOR = (70, 70, 86)
ROAD_LIGHT_COLOR = (115, 115, 135)
BRIDGE_COLOR = (125, 88, 52)
BRIDGE_DARK_COLOR = (85, 58, 32)
SPIDER_BODY_COLOR = (30, 22, 36)
SPIDER_LEG_COLOR = (175, 165, 190)
SPIDER_MARK_COLOR = (230, 40, 60)
NIGHT_TINT = (70, 85, 165)
RAIN_COLOR = (150, 170, 220)
TEXT_COLOR = (200, 195, 230)
TEXT_DIM_COLOR = (125, 120, 160)
PANEL_COLOR = (18, 14, 36, 200)
PANEL_BORDER_COLOR = (70, 62, 110, 200)
SLIDER_TRACK_COLOR = (45, 40, 75)
SLIDER_FILL_COLOR = (110, 100, 175)
SLIDER_ACTIVE_COLOR = (255, 170, 50)

GLOW_GAIN = 2.5
VIGNETTE_STRENGTH = 0.45
FOOD_PELLETS = 45
RAIN_DROPS = 350
