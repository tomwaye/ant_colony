import pygame
import numpy

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

NUM_ANTS = 500
SIZE_CELLS = 4

DEPOSIT_RATE = 2
WANDER_WEIGHT = 3
TURN_RATE = 7

SENSOR_DISANCE = 4 * SIZE_CELLS
SENSOR_ANGLE = numpy.pi / 4

EVAPORATION_RETENTION = 0.8

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
        self.food_inventory = 0

    def sensor_pos(self, offset):
        angle = self.heading + offset
        d = pygame.Vector2(numpy.cos(angle), numpy.sin(angle))
        return self.pos + d * SENSOR_DISANCE

    def update(self, dt, home_grid, food_grid, foods, nest):
        if self.searching:
            pheremone_c = food_grid.sample(self.C)
            pheremone_r = food_grid.sample(self.R)
            pheremone_l = food_grid.sample(self.L)

            if pheremone_c >= pheremone_r and pheremone_c >= pheremone_l:
                pass
            elif pheremone_r >= pheremone_c and pheremone_r >= pheremone_l:
                self.heading += TURN_RATE * dt
            else:
                self.heading -= TURN_RATE * dt

            for food in foods:
                if self.pos.distance_to(food.pos) <= food.radius:
                    if self.food_inventory < 1:
                        self.food_inventory += 1
                        food.quantity -= 1
                        self.searching = False
                        self.heading += numpy.pi


        else:
            pheremone_c = home_grid.sample(self.C)
            pheremone_r = home_grid.sample(self.R)
            pheremone_l = home_grid.sample(self.L)

            if pheremone_c >= pheremone_r and pheremone_c >= pheremone_l:
                pass
            elif pheremone_r >= pheremone_c and pheremone_r >= pheremone_l:
                self.heading += TURN_RATE * dt
            else:
                self.heading -= TURN_RATE * dt

            if self.pos.distance_to(nest.pos) <= nest.radius:
                if self.food_inventory > 0:
                    self.food_inventory = 0
                    self.searching = True
                    self.heading += numpy.pi
                    nest.food_inventory += 1

        self.direction.x = numpy.cos(self.heading)
        self.direction.y = numpy.sin(self.heading)
        self.heading += numpy.random.uniform(-7,7) * WANDER_WEIGHT *dt

        self.pos += self.direction * self.speed * dt

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
        if self.searching:
            pygame.draw.circle(screen, "white", self.pos, 1)
        else:
            pygame.draw.circle(screen, "green", self.pos, 1)

    def deposit(self, dt, home_grid, food_grid):
        if self.searching:
            cell_index = home_grid.cell_index(self.pos)
            home_grid.cells[cell_index] += DEPOSIT_RATE * dt
        else:
            cell_index = food_grid.cell_index(self.pos)
            food_grid.cells[cell_index] += DEPOSIT_RATE * dt

class Nest:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.radius = 20
        self.food_inventory

    def draw(self, screen):
        pygame.draw.circle(screen, "red", self.pos, self.radius)

class Grid:
    def __init__(self):
        cells_x = SCREEN_WIDTH // SIZE_CELLS
        cells_y = SCREEN_HEIGHT // SIZE_CELLS
        self.cells = numpy.zeros((cells_x, cells_y), numpy.float32)

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
        
class Food:
    def __init__(self):
        self.pos = pygame.Vector2(200,200)
        self.quantity = 1000
        self.radius = 30

    def draw(self, screen):
        pygame.draw.circle(screen, "blue", self.pos, self.radius)

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
    foods = [Food()]

    while running:
        dt = clock.tick(60)/1000
        fps = int(clock.get_fps())
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        screen.fill((0,0,0))

        nest.draw(screen)
        for food in foods:
            food.draw(screen)

        foods = [x for x in foods if x.quantity > 0]

        for ant in ants:
            ant.update(dt, home_grid, food_grid, foods, nest)
            ant.draw(screen)
            ant.deposit(dt, home_grid, food_grid)

        home_grid.evaporate(dt)
        food_grid.evaporate(dt)

        render_text(screen, str(fps), (25,25), "white", font)

        pygame.display.flip()
    pygame.quit()
       

if __name__ == "__main__":
    main()