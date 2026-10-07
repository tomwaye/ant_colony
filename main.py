import pygame
import numpy

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

NUM_ANTS = 1000
SIZE_CELLS = 4

DEPOSIT_RATE = 2
WANDER_WEIGHT = 3
TURN_RATE = 7

SENSOR_DISANCE = 8 * SIZE_CELLS
SENSOR_ANGLE = numpy.pi / 4

EVAPORATION_RETENTION = 0.8
PHEREMONE_RETENTION = 0.9
PHEREMONE_STRENGTH = 1.0

SCALE = 255

BACKGROUND_COLOR = (10, 8, 22)
HOME_TRAIL_COLOR = (255, 60, 150)
FOOD_TRAIL_COLOR = (40, 220, 255)
NEST_COLOR = (255, 170, 50)
NEST_RIM_COLOR = (120, 60, 10)
FOOD_COLOR = (150, 255, 80)
FOOD_RIM_COLOR = (40, 90, 20)
ANT_SEARCHING_COLOR = (225, 220, 255)
ANT_CARRYING_COLOR = (150, 255, 80)
ANT_LOST_COLOR = (255, 120, 40)
WALL_COLOR = (90, 85, 110)
TEXT_COLOR = (200, 195, 230)

WALL_BRUSH_RADIUS = 3

class Ant:
    def __init__(self, nest_pos):
        self.pos = pygame.Vector2(nest_pos.x, nest_pos.y)
        self.heading = numpy.radians(numpy.random.uniform(0,360))
        self.speed = 50
        self.direction = pygame.Vector2()
        self.C = pygame.Vector2()
        self.L = pygame.Vector2()
        self.R = pygame.Vector2()
        self.searching = True
        self.lost = False
        self.food_inventory = 0
        self.pheremone_strength = PHEREMONE_STRENGTH
        self.pheremone_strength_threshold = numpy.random.uniform(0.05, 0.15)

    def sensor_pos(self, offset):
        angle = self.heading + offset
        d = pygame.Vector2(numpy.cos(angle), numpy.sin(angle))
        return self.pos + d * SENSOR_DISANCE

    def sense(self, grid, walls, pos):
        if walls.sample(pos):
            return -1
        return grid.sample(pos)

    def follow_grid(self, grid, walls, dt):
        pheremone_c = self.sense(grid, walls, self.C)
        pheremone_r = self.sense(grid, walls, self.R)
        pheremone_l = self.sense(grid, walls, self.L)

        if pheremone_c >= pheremone_r and pheremone_c >= pheremone_l:
            pass
        elif pheremone_r >= pheremone_c and pheremone_r >= pheremone_l:
            self.heading += TURN_RATE * dt
        else:
            self.heading -= TURN_RATE * dt

    def update(self, dt, home_grid, food_grid, walls, foods, nest):
        if self.searching and not self.lost:
            self.follow_grid(food_grid, walls, dt)
        else:
            self.follow_grid(home_grid, walls, dt)

        if self.searching:
            for food in foods:
                if self.pos.distance_to(food.pos) <= food.radius:
                    if self.food_inventory < 1 and food.quantity > 0:
                        self.food_inventory += 1
                        food.quantity -= 1
                        self.searching = False
                        self.lost = False
                        self.heading += numpy.pi
                        self.pheremone_strength = PHEREMONE_STRENGTH
        if not self.searching or self.lost:
            if self.pos.distance_to(nest.pos) <= nest.radius:
                if self.food_inventory > 0:
                    self.food_inventory = 0
                    self.searching = True
                    self.lost = False
                    self.heading += numpy.pi
                    nest.food_inventory += 1
                    self.pheremone_strength = PHEREMONE_STRENGTH
                if self.lost:
                    self.lost = False
                    self.searching = True
                    self.pheremone_strength = PHEREMONE_STRENGTH
                    self.heading += numpy.pi

        self.pheremone_strength *= PHEREMONE_RETENTION ** dt
        if not self.lost:
            if self.pheremone_strength < self.pheremone_strength_threshold and self.searching:
                self.heading += numpy.pi
                self.lost = True

        self.direction.x = numpy.cos(self.heading)
        self.direction.y = numpy.sin(self.heading)
        self.heading += numpy.random.uniform(-7,7) * WANDER_WEIGHT *dt

        new_pos = self.pos + self.direction * self.speed * dt
        if walls.sample(new_pos) and not walls.sample(self.pos):
            self.heading += numpy.random.choice((-1, 1)) * (numpy.pi/2) + numpy.random.uniform(-0.5, 0.5)
        else:
            self.pos = new_pos

        if self.pos.x >= SCREEN_WIDTH:
            self.pos.x = SCREEN_WIDTH
            self.heading = numpy.pi - self.heading
        elif self.pos.x <= 0:
            self.pos.x = 0
            self.heading = numpy.pi - self.heading
        if self.pos.y >= SCREEN_HEIGHT:
            self.pos.y = SCREEN_HEIGHT
            self.heading *= -1
        elif self.pos.y <= 0:
            self.pos.y = 0
            self.heading *= -1

        self.C = self.sensor_pos(0)
        self.L = self.sensor_pos(-SENSOR_ANGLE)
        self.R = self.sensor_pos(SENSOR_ANGLE)
        
    def draw(self, screen):
        if self.lost:
            pygame.draw.circle(screen, ANT_LOST_COLOR, self.pos, 1)
        elif self.searching:
            pygame.draw.circle(screen, ANT_SEARCHING_COLOR, self.pos, 1)
        else:
            pygame.draw.circle(screen, ANT_CARRYING_COLOR, self.pos, 1)

    def deposit(self, dt, home_grid, food_grid):
        if self.pheremone_strength > self.pheremone_strength_threshold:
            if self.searching:
                cell_index = home_grid.cell_index(self.pos)
                home_grid.cells[cell_index] += DEPOSIT_RATE * self.pheremone_strength * dt
            else:
                cell_index = food_grid.cell_index(self.pos)
                food_grid.cells[cell_index] += DEPOSIT_RATE * self.pheremone_strength * dt

class Nest:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.radius = 20
        self.food_inventory = 0

    def draw(self, screen):
        pygame.draw.circle(screen, NEST_RIM_COLOR, self.pos, self.radius + 4)
        pygame.draw.circle(screen, NEST_COLOR, self.pos, self.radius)

class Grid:
    def __init__(self, dtype=numpy.float32):
        cells_x = SCREEN_WIDTH // SIZE_CELLS
        cells_y = SCREEN_HEIGHT // SIZE_CELLS
        self.cells = numpy.zeros((cells_x, cells_y), dtype)

    def evaporate(self, dt):
        self.cells *= EVAPORATION_RETENTION ** dt

    def cell_index(self, pos):
        cell = [int(pos.x // SIZE_CELLS), int(pos.y // SIZE_CELLS)]
        clampedCellX = max(0, min(cell[0], self.cells.shape[0]-1))
        clampedCellY = max(0, min(cell[1], self.cells.shape[1]-1))
        return (clampedCellX, clampedCellY)

    def sample(self, pos):
        index = self.cell_index(pos)
        return self.cells[index]

    def paint(self, pos, radius, value):
        i, j = self.cell_index(pos)
        i0 = max(i - radius, 0)
        j0 = max(j - radius, 0)
        i1 = min(i + radius + 1, self.cells.shape[0])
        j1 = min(j + radius + 1, self.cells.shape[1])
        self.cells[i0:i1, j0:j1] = value

    def paint_line(self, start, end, radius, value):
        steps = max(1, int(start.distance_to(end) // SIZE_CELLS))
        for k in range(steps + 1):
            self.paint(start.lerp(end, k / steps), radius, value)

class PheromoneRenderer:
    def __init__(self, grid_shape):
        self.rgb = numpy.zeros((grid_shape + (3,)), numpy.uint8)
        self.surface = pygame.Surface(grid_shape)
        self.background = numpy.array(BACKGROUND_COLOR, numpy.float32)
        self.home_color = numpy.array(HOME_TRAIL_COLOR, numpy.float32)
        self.food_color = numpy.array(FOOD_TRAIL_COLOR, numpy.float32)

    def draw(self, screen, home_grid, food_grid, walls):
        home_bright = numpy.clip(home_grid.cells * SCALE / 255, 0, 1)[:, :, None]
        food_bright = numpy.clip(food_grid.cells * SCALE / 255, 0, 1)[:, :, None]
        color = self.background + home_bright * self.home_color + food_bright * self.food_color
        self.rgb[:] = numpy.clip(color, 0, 255)
        self.rgb[walls.cells] = WALL_COLOR
        pygame.surfarray.blit_array(self.surface, self.rgb)
        big = pygame.transform.scale(self.surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(big, (0,0))
       
class Food:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.quantity = 1000
        self.radius = 30

    def draw(self, screen):
        pygame.draw.circle(screen, FOOD_RIM_COLOR, self.pos, self.radius + 4)
        pygame.draw.circle(screen, FOOD_COLOR, self.pos, self.radius)

def render_text(screen, text, pos, color, font):
    text = font.render(text, 1, pygame.Color(color))
    screen.blit(text, pos)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
    clock = pygame.Clock()
    running = True

    font = pygame.font.SysFont("Comic Sans MS", 15)

    pygame.display.set_caption("ant colony")

    nest = Nest(pygame.Vector2(SCREEN_WIDTH/2,SCREEN_HEIGHT/2))
    ants = [Ant(nest.pos) for _ in range(NUM_ANTS)]
    home_grid = Grid()
    food_grid = Grid()
    walls = Grid(numpy.bool_)
    foods = [Food((200,200)), Food((500,500))]
    renderer = PheromoneRenderer(home_grid.cells.shape)
    last_mouse = None

    while running:
        dt = clock.tick(60)/1000
        fps = int(clock.get_fps())
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_f:
                    foods.append(Food(pygame.mouse.get_pos()))
                if event.key == pygame.K_c:
                    walls.cells[:] = False

        mouse = pygame.Vector2(pygame.mouse.get_pos())
        left, _, right = pygame.mouse.get_pressed()
        if left or right:
            start = last_mouse if last_mouse is not None else mouse
            walls.paint_line(start, mouse, WALL_BRUSH_RADIUS, bool(left))
            last_mouse = mouse
        else:
            last_mouse = None

        home_grid.cells[walls.cells] = 0
        food_grid.cells[walls.cells] = 0

        renderer.draw(screen, home_grid, food_grid, walls)

        nest.draw(screen)
        for food in foods:
            food.draw(screen)

        foods = [x for x in foods if x.quantity > 0]

        for ant in ants:
            ant.update(dt, home_grid, food_grid, walls, foods, nest)
            ant.draw(screen)
            ant.deposit(dt, home_grid, food_grid)

        home_grid.evaporate(dt)
        food_grid.evaporate(dt)

        render_text(screen, str(fps), (25,25), TEXT_COLOR, font)
        render_text(screen, "nest food: "+str(nest.food_inventory), (50, 25), TEXT_COLOR, font)
        render_text(screen, "left: wall  right: erase  F: food  C: clear walls", (25, SCREEN_HEIGHT - 25), TEXT_COLOR, font)

        pygame.display.flip()
    pygame.quit()
       

if __name__ == "__main__":
    main()