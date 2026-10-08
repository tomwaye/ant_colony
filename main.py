"""Ant colony simulation.

    python main.py                       open the window
    python main.py --preset maze         start from a preset (open, maze, corridor, duel, islands)
    python main.py --headless --seconds 600 --seed 1 --csv run.csv
                                         run without a window and print colony stats
"""
import argparse
import csv
import os
import time

import numpy

from config import *
import maps

SAVE_PATH = os.path.join("maps", "saved.json")

def build_world(args, seed):
    if args.map:
        return maps.load_map(args.map, seed)
    return maps.make_preset(args.preset, seed)

def describe(colony):
    workers, soldiers, scouts = colony.caste_counts
    return (f"ants {colony.ant_count:5d} (w {workers} s {soldiers} sc {scouts})  "
            f"food {colony.food:6.0f}  protein {colony.protein:5.0f}{'  STARVING' if colony.starving else ''}")

def run_headless(args, seed):
    world = build_world(args, seed)
    dt = 1 / 30
    steps = int(args.seconds / dt)
    report_every = max(1, int(args.report / dt))
    rows = []
    started = time.perf_counter()
    print(f"seed {seed}, preset {args.map or args.preset}, {args.seconds:.0f}s, evolution {'on' if settings.evolution else 'off'}")
    for step in range(1, steps + 1):
        world.step(dt)
        if step % report_every == 0 or step == steps:
            weather = ("night" if world.light < 0.35 else "day") + (", rain" if world.rain > 0.5 else "")
            print(f"t={world.time:6.0f}s  " + " | ".join(describe(c) for c in world.colonies)
                  + f" | {len(world.foods)} food sources, {len(world.spiders)} spiders, {weather}")
            for colony in world.colonies:
                workers, soldiers, scouts = colony.caste_counts
                rows.append([round(world.time, 2), colony.id + 1, colony.ant_count, workers, soldiers, scouts,
                             round(colony.food, 1), round(colony.protein, 1), colony.born, colony.died]
                            + [round(g, 3) for g in colony.genome])
            if not world.colonies:
                print("every colony has died out")
                break
    elapsed = time.perf_counter() - started
    print(f"simulated {world.time:.0f}s in {elapsed:.1f}s ({world.time / elapsed:.1f}x real time)")
    if args.csv:
        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "colony", "ants", "workers", "soldiers", "scouts", "food", "protein", "born", "died"] + list(GENES))
            writer.writerows(rows)
        print(f"wrote {args.csv}")

def run_window(args, seed):
    import pygame
    import ui
    from render import Camera, Renderer, MIN_ZOOM

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("ant colony")
    clock = pygame.Clock()
    fonts = ui.make_fonts()

    world = build_world(args, seed)
    renderer = Renderer(seed)
    camera = Camera()
    panel = ui.SettingsPanel()
    graph = ui.GraphPanel()
    toasts = ui.Toasts()
    recorder = ui.Recorder()
    preset_names = list(maps.PRESETS)
    preset_index = preset_names.index(args.preset)

    def focus():
        if world.colonies:
            camera.look_at(numpy.mean([c.pos for c in world.colonies], axis=0), 1.0)
        else:
            camera.look_at((WORLD_WIDTH / 2, WORLD_HEIGHT / 2), MIN_ZOOM)
    focus()

    tool = "wall"
    brush = 4
    amount_index = {SUGAR: SUGAR_AMOUNTS.index(1000), PROTEIN: PROTEIN_AMOUNTS.index(300)}
    speed_index = SPEEDS.index(1)
    paused = False
    show_trails = True
    show_help = True
    last_mouse = None
    panning = False
    running = True

    while running:
        real_dt = clock.tick(60) / 1000
        # clamp dt so a stalled frame can't teleport ants through walls
        dt = min(real_dt, MAX_DT)
        mouse = pygame.mouse.get_pos()
        world_mouse = camera.to_world(mouse)
        ctrl = pygame.key.get_mods() & (pygame.KMOD_CTRL | pygame.KMOD_META)
        food_kind, amounts = ui.FOOD_TOOLS.get(tool, (SUGAR, SUGAR_AMOUNTS))
        food_amount = amounts[amount_index[food_kind]]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if panel.handle_event(event):
                continue
            if event.type == pygame.KEYDOWN:
                key = event.key
                command = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
                if command and key == pygame.K_s:
                    maps.save_map(world, SAVE_PATH)
                    toasts.show(f"saved map to {SAVE_PATH}")
                elif command and key == pygame.K_o:
                    try:
                        world = maps.load_map(SAVE_PATH, seed)
                        focus()
                        toasts.show(f"loaded {SAVE_PATH}")
                    except (OSError, ValueError) as error:
                        toasts.show(f"couldn't load map: {error}")
                elif key == pygame.K_ESCAPE:
                    running = False
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    speed_index = min(speed_index + 1, len(SPEEDS) - 1)
                elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed_index = max(speed_index - 1, 0)
                elif key == pygame.K_p:
                    show_trails = not show_trails
                elif key == pygame.K_TAB:
                    panel.visible = not panel.visible
                elif key == pygame.K_g:
                    graph.visible = not graph.visible
                elif key == pygame.K_h:
                    show_help = not show_help
                elif key == pygame.K_e:
                    settings.evolution = not settings.evolution
                    toasts.show("evolution on: new ants inherit their colony's genes, with mutations" if settings.evolution
                                else "evolution off: every ant uses the settings panel values")
                elif key == pygame.K_r:
                    world.toggle_rain()
                    toasts.show("rain" if world.rain_left > 0 else "rain stopping")
                elif key == pygame.K_n:
                    if world.add_colony(world_mouse) is None:
                        toasts.show("can't found a colony there (three at most, not too close to another)")
                elif key == pygame.K_c:
                    world.clear_map()
                elif key == pygame.K_m:
                    preset_index = (preset_index + 1) % len(preset_names)
                    world = maps.make_preset(preset_names[preset_index], seed)
                    focus()
                    toasts.show(f"preset: {preset_names[preset_index]}")
                elif key == pygame.K_0:
                    camera.look_at((WORLD_WIDTH / 2, WORLD_HEIGHT / 2), MIN_ZOOM)
                elif key == pygame.K_i:
                    toasts.show(f"saved {ui.save_screenshot(screen)}")
                elif key == pygame.K_v:
                    if recorder.active:
                        toasts.show(recorder.stop())
                    else:
                        recorder.start()
                elif pygame.K_1 <= key <= pygame.K_8:
                    tool = ui.TOOLS[key - pygame.K_1]
                elif key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                    change = 1 if key == pygame.K_RIGHTBRACKET else -1
                    if tool in ui.FOOD_TOOLS:
                        amount_index[food_kind] = int(numpy.clip(amount_index[food_kind] + change, 0, len(amounts) - 1))
                    else:
                        brush = int(numpy.clip(brush + change, 1, 20))
            if event.type == pygame.MOUSEWHEEL:
                camera.zoom_at(mouse, 1.15 ** event.y)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                panning = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                panning = False
            if event.type == pygame.MOUSEMOTION and panning:
                camera.pan(-event.rel[0], -event.rel[1])
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not panel.blocks_mouse(event.pos):
                if tool in ui.FOOD_TOOLS:
                    world.add_food(camera.to_world(event.pos), food_amount, food_kind)
                elif tool == "spider":
                    world.add_spider(camera.to_world(event.pos))

        keys = pygame.key.get_pressed()
        if not ctrl:
            pan_x = (keys[pygame.K_d] or (keys[pygame.K_RIGHT] and not panel.visible)) - (keys[pygame.K_a] or (keys[pygame.K_LEFT] and not panel.visible))
            pan_y = (keys[pygame.K_s] or (keys[pygame.K_DOWN] and not panel.visible)) - (keys[pygame.K_w] or (keys[pygame.K_UP] and not panel.visible))
            if pan_x or pan_y:
                camera.pan(pan_x * 700 * real_dt, pan_y * 700 * real_dt)

        left, _, right = pygame.mouse.get_pressed()
        if (left or right) and not panel.blocks_mouse(mouse) and not panning:
            start = last_mouse if last_mouse is not None else world_mouse
            if right:
                world.erase(start, world_mouse, brush)
            elif tool in ui.PAINT_TOOLS:
                world.paint(tool, start, world_mouse, brush)
            elif tool == "boot":
                world.stomp(world_mouse)
            last_mouse = world_mouse
        else:
            last_mouse = None

        if not paused:
            # run fast speeds as several small steps so ants still can't skip through walls
            sim_dt = dt * SPEEDS[speed_index]
            steps = int(numpy.ceil(sim_dt / MAX_DT))
            for _ in range(steps):
                world.step(sim_dt / steps)

        renderer.draw(screen, world, camera, show_trails, real_dt)
        if recorder.active:
            message = recorder.capture(screen, real_dt)
            if message:
                toasts.show(message)
        if not panel.blocks_mouse(mouse):
            ui.draw_cursor(screen, camera, mouse, tool, brush, food_amount, right)

        light = "day" if world.light > 0.7 else "dusk" if world.light > 0.35 else "night"
        status = (f"{int(clock.get_fps())} fps   ×{SPEEDS[speed_index]:g}   {light}{', rain' if world.rain > 0.3 else ''}"
                  f"   evolution {'on' if settings.evolution else 'off'}")
        hud = ui.draw_hud(screen, fonts, world, status)
        graph.draw(screen, fonts, world, hud.bottom + 10)
        size_text = f"amount {food_amount}" if tool in ui.FOOD_TOOLS else f"brush {brush}"
        ui.draw_toolbar(screen, fonts, tool, size_text, show_help)
        panel.draw(screen, fonts)
        top = 16
        if paused:
            top = ui.draw_pill(screen, fonts[0], "paused", (SCREEN_WIDTH // 2, top)).bottom + 6
        if recorder.active:
            top = ui.draw_pill(screen, fonts[1], f"● recording {recorder.count / recorder.FPS:.0f}s (V to stop)",
                               (SCREEN_WIDTH // 2, top), STARVING_COLOR).bottom + 6
        toasts.draw(screen, fonts, top)

        pygame.display.flip()

    if recorder.active:
        print(recorder.stop())
    pygame.quit()

def main():
    parser = argparse.ArgumentParser(description="Ant colony simulation")
    parser.add_argument("--seed", type=int, help="random seed, for repeatable runs")
    parser.add_argument("--preset", choices=list(maps.PRESETS), default="open", help="starting scenario")
    parser.add_argument("--map", help="start from a saved map file")
    parser.add_argument("--evolution", action="store_true", help="start with evolution on")
    parser.add_argument("--headless", action="store_true", help="run without a window and print stats")
    parser.add_argument("--seconds", type=float, default=300, help="headless: simulated seconds to run")
    parser.add_argument("--report", type=float, default=10, help="headless: seconds between reports")
    parser.add_argument("--csv", help="headless: also write colony stats to this CSV file")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else int(numpy.random.default_rng().integers(1_000_000))
    settings.evolution = args.evolution
    if args.headless:
        run_headless(args, seed)
    else:
        run_window(args, seed)

if __name__ == "__main__":
    main()
