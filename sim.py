"""The simulation: ants as numpy arrays, colonies, food, terrain, predators and weather.

Nothing here imports pygame, so it can run headless. Positions are numpy arrays of (x, y)
in world pixels; grids are indexed [x cell, y cell].
"""
import itertools
from collections import deque

import numpy

from config import *

def soften(values):
    """Light 3x3 blur over the last two axes."""
    out = values.copy()
    out[..., 1:-1, :] = (values[..., :-2, :] + 2 * values[..., 1:-1, :] + values[..., 2:, :]) / 4
    result = out.copy()
    result[..., 1:-1] = (out[..., :-2] + 2 * out[..., 1:-1] + out[..., 2:]) / 4
    return result

def cells_of(xs, ys):
    ix = numpy.clip((xs // SIZE_CELLS).astype(numpy.intp), 0, GRID_SHAPE[0] - 1)
    iy = numpy.clip((ys // SIZE_CELLS).astype(numpy.intp), 0, GRID_SHAPE[1] - 1)
    return ix, iy

def cell_of(pos):
    return (int(min(max(pos[0] // SIZE_CELLS, 0), GRID_SHAPE[0] - 1)),
            int(min(max(pos[1] // SIZE_CELLS, 0), GRID_SHAPE[1] - 1)))

def disc_mask(pos, radius):
    """A brush stamp: the grid region around pos and a disc mask within it."""
    i, j = cell_of(pos)
    i0, j0 = max(i - radius, 0), max(j - radius, 0)
    i1, j1 = min(i + radius + 1, GRID_SHAPE[0]), min(j + radius + 1, GRID_SHAPE[1])
    ii, jj = numpy.ogrid[i0:i1, j0:j1]
    return (slice(i0, i1), slice(j0, j1)), (ii - i) ** 2 + (jj - j) ** 2 <= radius ** 2 + radius

def line_points(start, end):
    start, end = numpy.asarray(start, numpy.float64), numpy.asarray(end, numpy.float64)
    steps = max(1, int(numpy.hypot(*(end - start)) // SIZE_CELLS))
    return [start + (end - start) * k / steps for k in range(steps + 1)]

def circle_mask(center, radius):
    xs = (numpy.arange(GRID_SHAPE[0]) + 0.5) * SIZE_CELLS
    ys = (numpy.arange(GRID_SHAPE[1]) + 0.5) * SIZE_CELLS
    return (xs[:, None] - center[0]) ** 2 + (ys[None, :] - center[1]) ** 2 <= radius ** 2

def nearest_open(blocked, pos):
    i, j = cell_of(pos)
    for r in range(1, max(GRID_SHAPE)):
        i0, j0 = max(i - r, 0), max(j - r, 0)
        free = numpy.argwhere(~blocked[i0:i + r + 1, j0:j + r + 1]) + (i0, j0)
        if len(free):
            ci, cj = free[numpy.argmin(((free - (i, j)) ** 2).sum(axis=1))]
            return numpy.array([(ci + 0.5) * SIZE_CELLS, (cj + 0.5) * SIZE_CELLS])
    return numpy.array(pos, numpy.float64)

def turn_towards(heading, desired, max_turn):
    diff = (desired - heading + numpy.pi) % (2 * numpy.pi) - numpy.pi
    return heading + numpy.clip(diff, -max_turn, max_turn)

def food_radius(amount, kind):
    typical = 1000 if kind == SUGAR else 300
    return float(numpy.clip(30 * numpy.sqrt(amount / typical), 10, 55))

class Ants:
    """Every ant in the world, one numpy array per property."""
    FIELDS = ("pos", "heading", "colony", "caste", "carrying", "lost", "strength",
              "threshold", "age", "hardiness", "energy", "genes")

    def __init__(self):
        self.pos = numpy.zeros((0, 2))
        self.heading = numpy.zeros(0)
        self.colony = numpy.zeros(0, numpy.intp)
        self.caste = numpy.zeros(0, numpy.intp)
        self.carrying = numpy.zeros(0, numpy.int8)
        self.lost = numpy.zeros(0, bool)
        self.strength = numpy.zeros(0)
        self.threshold = numpy.zeros(0)
        self.age = numpy.zeros(0)
        self.hardiness = numpy.zeros(0)
        self.energy = numpy.zeros(0)
        self.genes = numpy.zeros((0, len(GENES)))

    def __len__(self):
        return len(self.heading)

    def keep(self, mask):
        for name in self.FIELDS:
            setattr(self, name, getattr(self, name)[mask])

    def add(self, rng, colony, castes, genes, ages):
        count = len(castes)
        new = {
            "pos": numpy.repeat(colony.pos[None, :], count, axis=0),
            "heading": rng.uniform(0, 2 * numpy.pi, count),
            "colony": numpy.full(count, colony.id),
            "caste": castes,
            "carrying": numpy.zeros(count),
            "lost": numpy.zeros(count, bool),
            "strength": numpy.full(count, PHEROMONE_STRENGTH),
            "threshold": rng.uniform(0.05, 0.15, count),
            "age": ages,
            "hardiness": rng.uniform(0.7, 1.3, count),
            "energy": numpy.ones(count),
            "genes": genes,
        }
        for name in self.FIELDS:
            old = getattr(self, name)
            setattr(self, name, numpy.concatenate([old, numpy.asarray(new[name]).astype(old.dtype)]))

class Colony:
    def __init__(self, cid, pos, genome):
        self.id = cid
        self.palette = PALETTES[cid]
        self.pos = numpy.array(pos, numpy.float64)
        self.radius = 20
        self.food = float(START_FOOD)
        self.protein = float(START_PROTEIN)
        self.genome = genome.copy()
        self.starving = False
        self.spawn_timer = 0.0
        self.threat = 0.0
        self.delivery_rate = 0.0
        self.losses = self.deliveries = self.raided = 0
        self.born = self.died = 0
        self.ant_count = 0
        self.caste_counts = numpy.zeros(3, numpy.intp)
        self.history = deque(maxlen=HISTORY_SECONDS)

    def choose_caste(self, caste_counts):
        """Hatch soldiers when under attack and scouts when food is hard to find."""
        total = max(caste_counts.sum(), 1)
        soldier_target = min(max(0.05 + 0.04 * self.threat, 0.05), 0.4)
        scout_target = 0.25 if self.delivery_rate < 0.5 else 0.08
        if caste_counts[SOLDIER] / total < soldier_target:
            return SOLDIER
        if caste_counts[SCOUT] / total < scout_target:
            return SCOUT
        return WORKER

class Food:
    ids = itertools.count()

    def __init__(self, pos, amount, kind=SUGAR):
        self.id = next(Food.ids)
        self.pos = numpy.array(pos, numpy.float64)
        self.kind = kind
        self.max_quantity = amount
        self.quantity = amount
        self.radius = food_radius(amount, kind)
        self.idle = 0.0  # seconds since an ant last took from it

    @property
    def freshness(self):
        return max(0.0, 1 - self.idle / self.lifetime)

    @property
    def lifetime(self):
        return PROTEIN_LIFETIME if self.kind == PROTEIN else SUGAR_LIFETIME

    def spoiled(self):
        """Food left untouched for too long goes off (protein) or dries up (sugar)."""
        return self.idle >= self.lifetime

class Spider:
    def __init__(self, pos, rng):
        self.pos = numpy.array(pos, numpy.float64)
        self.heading = rng.uniform(0, 2 * numpy.pi)
        self.health = SPIDER_HEALTH
        self.cooldown = 0.0
        self.age = 0.0
        self.stride = 0.0

class World:
    def __init__(self, seed=None):
        self.rng = numpy.random.default_rng(seed)
        self.walls = numpy.zeros(GRID_SHAPE, bool)
        self.terrain = numpy.zeros(GRID_SHAPE, numpy.int8)
        self.home = numpy.zeros((MAX_COLONIES,) + GRID_SHAPE, numpy.float32)
        self.food = numpy.zeros((MAX_COLONIES,) + GRID_SHAPE, numpy.float32)
        self.ants = Ants()
        self.slots = [None] * MAX_COLONIES
        self.foods = []
        self.spiders = []
        self.corpses = numpy.zeros((0, 2))
        self.corpse_times = numpy.zeros(0)
        self.time = 0.0
        self.light = 1.0
        self.rain = 0.0
        self.rain_left = 0.0
        self.food_timer = 0.0
        self.spider_timer = 0.0
        self.history_timer = 0.0

    @property
    def colonies(self):
        return [colony for colony in self.slots if colony is not None]

    def blocked(self):
        return self.walls | (self.terrain == WATER)

    def nest_positions(self):
        positions = numpy.zeros((MAX_COLONIES, 2))
        for colony in self.colonies:
            positions[colony.id] = colony.pos
        return positions

    # ---- editing ----

    def add_colony(self, pos):
        pos = numpy.asarray(pos, numpy.float64)
        free = [k for k, colony in enumerate(self.slots) if colony is None]
        if not free or any(numpy.hypot(*(colony.pos - pos)) < 80 for colony in self.colonies):
            return None
        colony = Colony(free[0], pos, settings.genome())
        self.slots[colony.id] = colony
        castes = self.rng.choice(3, START_ANTS, p=START_CASTE_MIX)
        ages = self.rng.uniform(0, LIFESPAN * 0.6, START_ANTS)  # staggered so they don't all die at once
        self.ants.add(self.rng, colony, castes, self.new_genes(colony, START_ANTS), ages)
        colony.ant_count = START_ANTS
        self.clear_around()
        return colony

    def add_food(self, pos, amount, kind=SUGAR):
        self.foods.append(Food(pos, amount, kind))
        self.clear_around()

    def add_spider(self, pos):
        self.spiders.append(Spider(pos, self.rng))

    def paint(self, kind, start, end, radius):
        for point in line_points(start, end):
            region, disc = disc_mask(point, radius)
            if kind == "wall":
                self.walls[region][disc] = True
                continue
            terrain = self.terrain[region]
            if kind == "road":
                # road laid over water becomes a bridge
                current = terrain[disc]
                terrain[disc] = numpy.where((current == WATER) | (current == BRIDGE), BRIDGE, ROAD)
            else:
                terrain[disc] = {"sand": SAND, "water": WATER}[kind]
        self.clear_around()

    def erase(self, start, end, radius):
        for point in line_points(start, end):
            region, disc = disc_mask(point, radius)
            self.walls[region][disc] = False
            self.terrain[region][disc] = GROUND
        end = numpy.asarray(end, numpy.float64)
        reach = radius * SIZE_CELLS
        self.foods = [food for food in self.foods if numpy.hypot(*(food.pos - end)) > food.radius + reach]
        self.spiders = [spider for spider in self.spiders if numpy.hypot(*(spider.pos - end)) > reach + 8]

    def clear_map(self):
        self.walls[:] = False
        self.terrain[:] = GROUND

    def clear_around(self):
        """Keep nests and food reachable: no walls or water on top of them."""
        for center, radius in [(c.pos, c.radius + 4) for c in self.colonies] + [(f.pos, f.radius + 4) for f in self.foods]:
            mask = circle_mask(center, radius)
            self.walls[mask] = False
            self.terrain[mask & (self.terrain == WATER)] = GROUND

    def stomp(self, pos, radius=BOOT_RADIUS):
        if len(self.ants):
            d2 = ((self.ants.pos - numpy.asarray(pos)) ** 2).sum(axis=1)
            self.kill(d2 <= radius ** 2, violent=True)

    def toggle_rain(self):
        self.rain_left = 0.0 if self.rain_left > 0 else RAIN_DURATION

    # ---- simulation ----

    def new_genes(self, colony, count):
        if not settings.evolution:
            return numpy.repeat(settings.genome()[None, :], count, axis=0)
        mutated = colony.genome * numpy.exp(self.rng.normal(0, settings.mutation, (count, len(GENES))))
        return numpy.clip(mutated, GENE_BOUNDS[:, 0], GENE_BOUNDS[:, 1])

    def speed_factor(self):
        return NIGHT_SPEED + (1 - NIGHT_SPEED) * self.light

    def kill(self, mask, violent=False):
        if not mask.any():
            return
        self.add_corpses(self.ants.pos[mask])
        deaths = numpy.bincount(self.ants.colony[mask], minlength=MAX_COLONIES)
        for colony in self.colonies:
            colony.died += deaths[colony.id]
            if violent:
                colony.losses += deaths[colony.id]
        self.ants.keep(~mask)

    def add_corpses(self, positions):
        self.corpses = numpy.concatenate([self.corpses, positions])[-MAX_CORPSES:]
        self.corpse_times = numpy.concatenate([self.corpse_times, numpy.full(len(positions), self.time)])[-MAX_CORPSES:]

    def step(self, dt):
        self.time += dt
        self.update_weather(dt)
        if not settings.evolution:
            genome = settings.genome()
            self.ants.genes[:] = genome
            for colony in self.colonies:
                colony.genome = genome.copy()
        for colony in self.colonies:
            colony.losses = colony.deliveries = colony.raided = 0

        self.feed_and_age(dt)
        self.move(dt)
        self.fight(dt)
        self.update_spiders(dt)
        self.update_food(dt)
        self.update_colonies(dt)

        recent = self.time - self.corpse_times < CORPSE_TIME
        if not recent.all():
            self.corpses, self.corpse_times = self.corpses[recent], self.corpse_times[recent]

    def update_weather(self, dt):
        if settings.day_length >= 10:
            phase = (self.time / settings.day_length) % 1
            self.light = 0.575 + 0.425 * numpy.cos(2 * numpy.pi * phase)  # 1 at noon, 0.15 at midnight
        else:
            self.light = 1.0
        if self.rain_left > 0:
            self.rain_left -= dt
        elif settings.rain_interval >= 1 and self.rng.random() < dt / settings.rain_interval:
            self.rain_left = RAIN_DURATION
        target = 1.0 if self.rain_left > 0 else 0.0
        self.rain += (target - self.rain) * min(1.0, dt / 3)

    def feed_and_age(self, dt):
        """The colony feeds everyone from its store, sugar first and protein if that runs out.
        Ants go hungry in proportion to the shortfall, so a colony that's slightly short
        shrinks slowly instead of dying all at once."""
        ants = self.ants
        # faster ants burn more food, so evolution can't just make everyone sprint
        upkeep = numpy.bincount(ants.colony, weights=ants.genes[:, SPEED_GENE] / ANT_SPEED,
                                minlength=MAX_COLONIES) * settings.appetite * dt
        shortfall = numpy.zeros(MAX_COLONIES)
        for colony in self.colonies:
            need = upkeep[colony.id]
            sugar = min(colony.food, need)
            protein = min(colony.protein, need - sugar)
            colony.food -= sugar
            colony.protein -= protein
            shortfall[colony.id] = 1 - (sugar + protein) / need if need > 0 else 0.0
            colony.starving = shortfall[colony.id] > 0.01
        ants.age += dt
        hunger = shortfall[ants.colony]
        ants.energy = numpy.minimum(1.0, ants.energy + dt * (1 - hunger) / STARVE_RECOVERY
                                    - dt * hunger / (settings.starve_time * ants.hardiness))
        self.kill((ants.energy <= 0) | (ants.age >= settings.lifespan * ants.hardiness))

    def move(self, dt):
        ants = self.ants
        blocked = self.blocked()
        soft_home = soften(self.home)
        soft_food = soften(self.food)

        # pheromone spreads a little into neighbouring cells
        spread = min(settings.diffusion * dt, 1.0)
        self.home *= 1 - spread
        self.home += spread * soft_home
        self.food *= 1 - spread
        self.food += spread * soft_food

        if len(ants):
            self.steer(ants, blocked, soft_home, soft_food, dt)
            self.pick_up_and_deliver(ants)
            self.walk(ants, blocked, dt)
            self.deposit(ants, dt)

        # evaporate, and wipe anything under walls or water, in one multiply
        retention = settings.evaporation_retention ** (dt * (1 + RAIN_WASH * self.rain))
        keep = (~blocked).astype(numpy.float32) * numpy.float32(retention)
        numpy.minimum(self.home, MAX_PHEROMONE, out=self.home)
        numpy.minimum(self.food, MAX_PHEROMONE, out=self.food)
        self.home *= keep
        self.food *= keep

    def steer(self, ants, blocked, soft_home, soft_food, dt):
        # a wall was painted on top of these ants: pop them out to the nearest open cell
        ix, iy = cells_of(ants.pos[:, 0], ants.pos[:, 1])
        for i in numpy.nonzero(blocked[ix, iy])[0]:
            ants.pos[i] = nearest_open(blocked, ants.pos[i])

        c = ants.colony
        searching = ants.carrying == 0
        soldier = ants.caste == SOLDIER
        seek_food = searching & ~ants.lost & ~soldier
        raid = searching & ~ants.lost & soldier
        all_home = soft_home.sum(axis=0)

        # three sensors, each reading a 3x3 patch (the softened grid) a little ahead
        angle = numpy.radians(ants.genes[:, ANGLE_GENE])
        distance = ants.genes[:, DISTANCE_GENE]
        readings = []
        for offset in (-angle, 0, angle):
            a = ants.heading + offset
            sx = ants.pos[:, 0] + numpy.cos(a) * distance
            sy = ants.pos[:, 1] + numpy.sin(a) * distance
            six, siy = cells_of(sx, sy)
            own_home = soft_home[c, six, siy]
            rival_home = all_home[six, siy] - own_home
            # foragers follow food trails and shy away from rivals' territory; soldiers hunt it out
            value = numpy.where(seek_food, soft_food[c, six, siy] - settings.territory * rival_home,
                                numpy.where(raid, rival_home, own_home))
            outside = (sx < 0) | (sx >= WORLD_WIDTH) | (sy < 0) | (sy >= WORLD_HEIGHT)
            readings.append(numpy.where(outside | blocked[six, siy], -1.0, value))
        left, centre, right = readings

        # turn harder the more one side beats the other (full turn once it's ~33% stronger)
        side = numpy.clip(STEERING_GAIN * (right - left) / (numpy.maximum(numpy.abs(right), numpy.abs(left)) + 1e-6), -1, 1)
        side[centre >= numpy.maximum(left, right)] = 0
        turn_rate = numpy.where(seek_food | raid, ants.genes[:, TURN_FOOD_GENE], ants.genes[:, TURN_HOME_GENE])
        ants.heading += turn_rate * side * dt

        # lost ants and soldiers with loot fall back on a rough sense of where the nest is
        homing = ants.lost | (ants.carrying == LOOT)
        if homing.any():
            to_nest = self.nest_positions()[c[homing]] - ants.pos[homing]
            desired = numpy.arctan2(to_nest[:, 1], to_nest[:, 0])
            ants.heading[homing] = turn_towards(ants.heading[homing], desired, HOMING_RATE * dt)

    def pick_up_and_deliver(self, ants):
        for food in self.foods:
            if food.quantity <= 0:
                continue
            near = ((ants.pos - food.pos) ** 2).sum(axis=1) <= food.radius ** 2
            take = numpy.nonzero(near & (ants.carrying == 0) & (ants.caste != SOLDIER))[0][:int(food.quantity)]
            if len(take):
                food.quantity -= len(take)
                food.idle = 0.0
                ants.carrying[take] = food.kind
                ants.lost[take] = False
                ants.heading[take] += numpy.pi
                ants.strength[take] = PHEROMONE_STRENGTH

        for colony in self.colonies:
            near = ((ants.pos - colony.pos) ** 2).sum(axis=1) <= colony.radius ** 2
            if not near.any():
                continue
            own = ants.colony == colony.id

            deliver = near & own & (ants.carrying > 0)
            if deliver.any():
                kinds = ants.carrying[deliver]
                colony.food += numpy.count_nonzero((kinds == SUGAR) | (kinds == LOOT))
                colony.protein += numpy.count_nonzero(kinds == PROTEIN)
                foragers = deliver & (ants.carrying != LOOT)
                colony.deliveries += numpy.count_nonzero(foragers)
                if settings.evolution and foragers.any():
                    # selection: the genes of ants that actually bring food home pull the colony's genome
                    weight = 1 - (1 - SELECTION_RATE) ** numpy.count_nonzero(foragers)
                    colony.genome += weight * (ants.genes[foragers].mean(axis=0) - colony.genome)
                ants.carrying[deliver] = 0
                ants.heading[deliver] += numpy.pi

            returned = near & own & (deliver | ants.lost)
            ants.lost[returned] = False
            ants.strength[returned] = PHEROMONE_STRENGTH
            ants.heading[returned & ~deliver] += numpy.pi

            # rival soldiers raid the store
            raid = numpy.nonzero(near & ~own & (ants.caste == SOLDIER) & (ants.carrying == 0) & ~ants.lost)[0]
            raid = raid[:int(colony.food)]
            if len(raid):
                colony.food -= len(raid)
                colony.raided += len(raid)
                ants.carrying[raid] = LOOT
                ants.heading[raid] += numpy.pi
                ants.strength[raid] = PHEROMONE_STRENGTH

    def walk(self, ants, blocked, dt):
        ants.strength *= CASTE_RETENTION[ants.caste] ** dt
        newly_lost = ~ants.lost & (ants.strength < ants.threshold)
        ants.heading[newly_lost & (ants.carrying == 0)] += numpy.pi
        ants.lost |= newly_lost

        n = len(ants)
        ants.heading += self.rng.uniform(-7, 7, n) * ants.genes[:, WANDER_GENE] * CASTE_WANDER[ants.caste] * dt
        ants.heading %= 2 * numpy.pi

        ix, iy = cells_of(ants.pos[:, 0], ants.pos[:, 1])
        speed = ants.genes[:, SPEED_GENE] * TERRAIN_SPEED[self.terrain[ix, iy]] * self.speed_factor()
        nx = ants.pos[:, 0] + numpy.cos(ants.heading) * speed * dt
        ny = ants.pos[:, 1] + numpy.sin(ants.heading) * speed * dt

        hit_x = (nx <= 0) | (nx >= WORLD_WIDTH)
        ants.heading[hit_x] = numpy.pi - ants.heading[hit_x]
        hit_y = (ny <= 0) | (ny >= WORLD_HEIGHT)
        ants.heading[hit_y] = -ants.heading[hit_y]
        nx = numpy.clip(nx, 0, WORLD_WIDTH)
        ny = numpy.clip(ny, 0, WORLD_HEIGHT)

        nix, niy = cells_of(nx, ny)
        hit = blocked[nix, niy]
        hits = numpy.count_nonzero(hit)
        if hits:
            ants.heading[hit] += self.rng.choice((-1, 1), hits) * (numpy.pi / 2) + self.rng.uniform(-0.5, 0.5, hits)
        ants.pos[~hit, 0] = nx[~hit]
        ants.pos[~hit, 1] = ny[~hit]

    def deposit(self, ants, dt):
        laying = (ants.strength > ants.threshold) & (ants.carrying != LOOT)
        amount = settings.deposit_rate * ants.strength * CASTE_DEPOSIT[ants.caste] * dt
        ix, iy = cells_of(ants.pos[:, 0], ants.pos[:, 1])
        for grid, which in ((self.home, laying & (ants.carrying == 0)), (self.food, laying & (ants.carrying > 0))):
            numpy.add.at(grid, (ants.colony[which], ix[which], iy[which]), amount[which])

    def fight(self, dt):
        """Rival ants sharing a small patch of ground fight; soldiers hit harder and take more killing."""
        ants = self.ants
        if len(ants) == 0 or len(self.colonies) < 2:
            return
        fw, fh = WORLD_WIDTH // FIGHT_CELL, WORLD_HEIGHT // FIGHT_CELL
        fx = numpy.clip((ants.pos[:, 0] // FIGHT_CELL).astype(numpy.intp), 0, fw - 1)
        fy = numpy.clip((ants.pos[:, 1] // FIGHT_CELL).astype(numpy.intp), 0, fh - 1)
        patch = fx * fh + fy
        attack = numpy.zeros((MAX_COLONIES, fw * fh))
        numpy.add.at(attack, (ants.colony, patch), CASTE_ATTACK[ants.caste])
        enemy = attack.sum(axis=0)[patch] - attack[ants.colony, patch]
        contested = enemy > 0
        if not contested.any():
            return
        chance = 1 - numpy.exp(-settings.fight_rate * enemy[contested] / CASTE_DEFENCE[ants.caste[contested]] * dt)
        dies = numpy.zeros(len(ants), bool)
        dies[contested] = self.rng.random(numpy.count_nonzero(contested)) < chance
        self.kill(dies, violent=True)

    def update_spiders(self, dt):
        blocked = self.blocked()
        for spider in self.spiders:
            spider.age += dt
            spider.cooldown -= dt
            ants = self.ants
            if len(ants):
                offset = ants.pos - spider.pos
                d2 = (offset ** 2).sum(axis=1)
                nearest = int(numpy.argmin(d2))
                if d2[nearest] < SPIDER_SIGHT ** 2:
                    spider.heading = turn_towards(spider.heading, numpy.arctan2(*offset[nearest][::-1]), 4 * dt)
                # ants bite back, soldiers much harder
                close = d2 <= (SPIDER_REACH + 5) ** 2
                bites = numpy.where(ants.caste[close] == SOLDIER, SOLDIER_DAMAGE, WORKER_DAMAGE)
                spider.health -= bites.sum() * dt
                if d2[nearest] <= SPIDER_REACH ** 2 and spider.cooldown <= 0:
                    victim = numpy.zeros(len(ants), bool)
                    victim[nearest] = True
                    self.kill(victim, violent=True)
                    spider.cooldown = SPIDER_EAT_COOLDOWN
            spider.heading += self.rng.uniform(-3, 3) * dt
            step = numpy.array([numpy.cos(spider.heading), numpy.sin(spider.heading)]) * SPIDER_SPEED * dt
            new = spider.pos + step
            if not (0 <= new[0] < WORLD_WIDTH and 0 <= new[1] < WORLD_HEIGHT) or blocked[cell_of(new)]:
                spider.heading += numpy.pi / 2 + self.rng.uniform(-0.5, 0.5)
            else:
                spider.pos = new
                spider.stride += SPIDER_SPEED * dt
        dead = [spider for spider in self.spiders if spider.health <= 0]
        if dead:
            self.add_corpses(numpy.array([spider.pos for spider in dead]))
        self.spiders = [spider for spider in self.spiders if spider.health > 0 and spider.age < SPIDER_LIFETIME]

    def update_food(self, dt):
        for food in self.foods:
            food.idle += dt
        self.foods = [food for food in self.foods if food.quantity > 0 and not food.spoiled()]

        if settings.food_spawn_interval >= 1:
            self.food_timer += dt
            if self.food_timer >= settings.food_spawn_interval:
                self.food_timer = 0.0
                if len(self.foods) < MAX_FOOD_SOURCES:
                    self.spawn_random_food()

        if settings.spider_interval >= 1:
            self.spider_timer += dt
            if self.spider_timer >= settings.spider_interval:
                self.spider_timer = 0.0
                edge = self.rng.integers(4)
                along = self.rng.random()
                x = (along * WORLD_WIDTH, along * WORLD_WIDTH, 5, WORLD_WIDTH - 5)[edge]
                y = (5, WORLD_HEIGHT - 5, along * WORLD_HEIGHT, along * WORLD_HEIGHT)[edge]
                if not self.blocked()[cell_of((x, y))]:
                    self.add_spider((x, y))

    def spawn_random_food(self):
        blocked = self.blocked()
        for _ in range(50):
            # near a colony, within the distance foragers actually roam
            if self.colonies:
                colony = self.colonies[self.rng.integers(len(self.colonies))]
                angle = self.rng.uniform(0, 2 * numpy.pi)
                pos = colony.pos + numpy.array([numpy.cos(angle), numpy.sin(angle)]) * self.rng.uniform(150, 450)
            else:
                pos = self.rng.uniform((60, 60), (WORLD_WIDTH - 60, WORLD_HEIGHT - 60))
            if not (60 <= pos[0] <= WORLD_WIDTH - 60 and 60 <= pos[1] <= WORLD_HEIGHT - 60) or blocked[cell_of(pos)]:
                continue
            if any(numpy.hypot(*(colony.pos - pos)) < 150 for colony in self.colonies):
                continue
            if any(numpy.hypot(*(food.pos - pos)) < 100 for food in self.foods):
                continue
            if self.rng.random() < PROTEIN_SPAWN_CHANCE:
                self.add_food(pos, int(self.rng.choice((200, 300, 400))), PROTEIN)
            else:
                self.add_food(pos, int(self.rng.choice((500, 1000, 1500))), SUGAR)
            return

    def update_colonies(self, dt):
        ants = self.ants
        counts = numpy.bincount(ants.colony, minlength=MAX_COLONIES)
        caste_counts = numpy.bincount(ants.colony * 3 + ants.caste, minlength=MAX_COLONIES * 3).reshape(MAX_COLONIES, 3)
        room = MAX_ANTS - len(ants)
        smoothing = 1 - numpy.exp(-dt / 10)

        for colony in self.colonies:
            colony.threat += ((colony.losses + colony.raided) / dt - colony.threat) * smoothing
            colony.delivery_rate += (colony.deliveries / dt - colony.delivery_rate) * smoothing

            # breed when there's food to spare beyond a minute of upkeep. Each new ant costs food
            # (sugar first, then protein) plus a little protein for the brood. Without protein
            # the brood can still be raised on sugar alone, but at several times the cost
            reserve = counts[colony.id] * settings.appetite * SPAWN_RESERVE_SECONDS
            colony.spawn_timer += dt
            castes = []
            while colony.spawn_timer >= SPAWN_INTERVAL:
                colony.spawn_timer -= SPAWN_INTERVAL
                if len(castes) >= room:
                    continue
                caste = colony.choose_caste(caste_counts[colony.id] + numpy.bincount(numpy.array(castes, numpy.intp), minlength=3))
                cost = settings.spawn_cost * CASTE_COST[caste]
                protein = settings.protein_cost * CASTE_COST[caste]
                if colony.protein >= protein and colony.food + colony.protein >= cost + protein + reserve:
                    colony.protein -= protein
                    sugar = min(colony.food, cost)
                    colony.food -= sugar
                    colony.protein -= cost - sugar
                    castes.append(caste)
                elif colony.protein < protein and colony.food >= cost * NO_PROTEIN_COST + reserve:
                    colony.food -= cost * NO_PROTEIN_COST
                    castes.append(caste)
            if castes:
                self.ants.add(self.rng, colony, numpy.array(castes), self.new_genes(colony, len(castes)), numpy.zeros(len(castes)))
                colony.born += len(castes)
                room -= len(castes)
                caste_counts[colony.id] += numpy.bincount(numpy.array(castes, numpy.intp), minlength=3)
            colony.ant_count = int(caste_counts[colony.id].sum())
            colony.caste_counts = caste_counts[colony.id].copy()

            if colony.ant_count == 0 and (colony.food < settings.spawn_cost or colony.protein < settings.protein_cost):
                self.slots[colony.id] = None
                self.home[colony.id] = 0
                self.food[colony.id] = 0

        self.history_timer += dt
        if self.history_timer >= 1:
            self.history_timer -= 1
            for colony in self.colonies:
                colony.history.append((self.time, colony.ant_count, colony.food, colony.protein))
