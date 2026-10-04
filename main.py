import pygame
import numpy

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

NUM_ANTS = 25
SIZE_CELLS = 4

DEPOSIT_RATE = 2
WANDER_WEIGHT = 2

class Ant:
    def __init__(self, nest_pos):
        self.pos = pygame.Vector2(nest_pos.x, nest_pos.y)
        self.heading = numpy.radians(numpy.random.uniform(0,360))
        self.speed = 25
        self.direction = pygame.Vector2()

    def update(self, dt):
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
    def draw(self, screen):
        pygame.draw.circle(screen, "white", self.pos, 3)

    def deposit(self, cells, dt):
        cell = [int(self.pos.x // SIZE_CELLS), int(self.pos.y // SIZE_CELLS)]
        clampedCellX = max(0, min(cell[0], cells.shape[0]-1))
        clampedCellY = max(0, min(cell[1], cells.shape[1]-1))
        cells[clampedCellX, clampedCellY] += DEPOSIT_RATE * dt

class Nest:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)

    def draw(self, screen):
        pygame.draw.circle(screen, "red", self.pos, 20)

class Grid:
    def __init__(self):
        cells_x = SCREEN_WIDTH // SIZE_CELLS
        cells_y = SCREEN_HEIGHT // SIZE_CELLS
        self.cells = numpy.zeros((cells_x, cells_y), numpy.float32)
        


def render_text(screen, text, pos, color, font):
    text = font.render(text, 1, pygame.Color(color))
    screen.blit(text, pos)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
    clock = pygame.Clock()
    running = True

    nest = Nest(pygame.Vector2(SCREEN_WIDTH/2,SCREEN_HEIGHT/2))

    font = pygame.font.SysFont("Comic Sans MS", 15)

    pygame.display.set_caption("ant colony")

    ants = [Ant(nest.pos) for _ in range(NUM_ANTS)]

    grid = Grid()

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

        for ant in ants:
            ant.update(dt)
            ant.draw(screen)
            ant.deposit(grid.cells, dt)

        render_text(screen, str(fps), (25,25), "white", font)

        pygame.display.flip()
    pygame.quit()
       

if __name__ == "__main__":
    main()