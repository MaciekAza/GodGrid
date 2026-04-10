from __future__ import annotations

from dataclasses import dataclass


BLOCKED_SUBTYPES = {"water", "deep_ocean", "mountain_peak"}
DISLIKED_SUBTYPES = {"highland", "mountain_high"}

ANIMAL_LABELS = {
    "sheep": "Owce",
    "cow": "Krowy",
    "chicken": "Kury",
    "horse": "Konie",
}

ANIMAL_SPECS = {
    "sheep": {
        "color": (232, 232, 232),
        "start_count": 20,
        "maturity_age": 18.0,
        "max_age": 175.0,
        "move_interval": 0.55,
        "move_speed": 1.65,
        "breeding_rate": 0.085,
        "breeding_cooldown": 18.0,
        "accident_risk": 0.0013,
        "litter_size": (1, 2),
        "terrain_weights": {
            "grass": 1.10,
            "forest": 0.72,
            "highland": 0.30,
            "mountain_high": 0.08,
        },
    },
    "cow": {
        "color": (156, 112, 82),
        "start_count": 14,
        "maturity_age": 24.0,
        "max_age": 205.0,
        "move_interval": 0.72,
        "move_speed": 1.30,
        "breeding_rate": 0.060,
        "breeding_cooldown": 22.0,
        "accident_risk": 0.0010,
        "litter_size": (1, 1),
        "terrain_weights": {
            "grass": 1.05,
            "forest": 0.58,
            "highland": 0.26,
            "mountain_high": 0.06,
        },
    },
    "chicken": {
        "color": (252, 232, 108),
        "start_count": 28,
        "maturity_age": 11.0,
        "max_age": 120.0,
        "move_interval": 0.36,
        "move_speed": 2.20,
        "breeding_rate": 0.125,
        "breeding_cooldown": 10.0,
        "accident_risk": 0.0025,
        "litter_size": (1, 3),
        "terrain_weights": {
            "grass": 1.00,
            "forest": 0.65,
            "highland": 0.20,
            "mountain_high": 0.02,
        },
    },
    "horse": {
        "color": (98, 76, 58),
        "start_count": 10,
        "maturity_age": 27.0,
        "max_age": 240.0,
        "move_interval": 0.47,
        "move_speed": 1.95,
        "breeding_rate": 0.045,
        "breeding_cooldown": 26.0,
        "accident_risk": 0.0008,
        "litter_size": (1, 1),
        "terrain_weights": {
            "grass": 1.15,
            "forest": 0.44,
            "highland": 0.22,
            "mountain_high": 0.04,
        },
    },
}

ANIMAL_DRAW_ORDER = tuple(ANIMAL_SPECS.keys())
ANIMAL_POPULATION_CAP = 280

NEIGHBOR_STEPS = (
    (0, 0),
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
    (-1, -1),
    (1, -1),
    (-1, 1),
    (1, 1),
)


@dataclass(slots=True)
class Animal:
    species: str
    x: float
    y: float
    sex: int  # 0=female, 1=male
    age: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    move_speed: float = 1.0
    move_cooldown: float = 0.0
    breed_cooldown: float = 0.0
    stress: float = 0.0


def _is_passable(subtype: str) -> bool:
    return subtype not in BLOCKED_SUBTYPES


def _terrain_weight(species: str, subtype: str) -> float:
    spec = ANIMAL_SPECS[species]
    return spec["terrain_weights"].get(subtype, 0.24)


def _animal_cell(animal: Animal, width: int, height: int) -> tuple[int, int]:
    cx = int(animal.x + 0.5)
    cy = int(animal.y + 0.5)
    cx = max(0, min(width - 1, cx))
    cy = max(0, min(height - 1, cy))
    return cx, cy


def _choose_next_tile(species: str, current_x: int, current_y: int, subtype_map, rng) -> tuple[int, int]:
    h = len(subtype_map)
    w = len(subtype_map[0])

    best_x = current_x
    best_y = current_y
    best_score = -10_000.0

    for dx, dy in NEIGHBOR_STEPS:
        nx = current_x + dx
        ny = current_y + dy
        if nx < 0 or ny < 0 or nx >= w or ny >= h:
            continue

        subtype = subtype_map[ny][nx]
        if not _is_passable(subtype):
            continue

        score = _terrain_weight(species, subtype)
        if subtype in DISLIKED_SUBTYPES:
            score -= 0.55
        if dx == 0 and dy == 0:
            score -= 0.15
        score += rng.random() * 0.35

        if score > best_score:
            best_score = score
            best_x = nx
            best_y = ny

    return best_x, best_y


def _find_birth_tile(animal: Animal, subtype_map, rng, occupancy) -> tuple[int, int] | None:
    h = len(subtype_map)
    w = len(subtype_map[0])
    cx, cy = _animal_cell(animal, w, h)
    candidates = []

    for dx, dy in NEIGHBOR_STEPS:
        nx = cx + dx
        ny = cy + dy
        if nx < 0 or ny < 0 or nx >= w or ny >= h:
            continue

        subtype = subtype_map[ny][nx]
        if not _is_passable(subtype):
            continue

        score = _terrain_weight(animal.species, subtype) + rng.random() * 0.35
        if subtype in DISLIKED_SUBTYPES:
            score -= 0.45
        if occupancy.get((nx, ny), 0) >= 3:
            score -= 0.95

        candidates.append((score, nx, ny))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    top_n = min(3, len(candidates))
    _, bx, by = candidates[rng.randrange(top_n)]
    return bx, by


def _nearest_mate_cell(animal: Animal, cx: int, cy: int, spec, population_view) -> tuple[int, int] | None:
    if animal.age < spec["maturity_age"] or animal.breed_cooldown > 0.0:
        return None

    wanted_sex = 1 if animal.sex == 0 else 0
    best = None
    best_dist = 10_000
    for other_id, other_species, other_sex, other_ready, ox, oy in population_view:
        if other_id == id(animal):
            continue
        if other_species != animal.species:
            continue
        if other_sex != wanted_sex:
            continue
        if not other_ready:
            continue

        dist = abs(ox - cx) + abs(oy - cy)
        if dist > 8:
            continue
        if dist < best_dist:
            best_dist = dist
            best = (ox, oy)

    return best


def spawn_initial_animals(subtype_map, rng) -> list[Animal]:
    h = len(subtype_map)
    w = len(subtype_map[0])
    animals = []

    for species, spec in ANIMAL_SPECS.items():
        target = spec["start_count"]
        spawned = 0
        attempts = 0
        max_attempts = max(100, target * 70)

        while spawned < target and attempts < max_attempts:
            attempts += 1
            x = rng.randrange(w)
            y = rng.randrange(h)
            subtype = subtype_map[y][x]
            if not _is_passable(subtype):
                continue
            if subtype in DISLIKED_SUBTYPES and rng.random() < 0.80:
                continue

            animals.append(
                Animal(
                    species=species,
                    x=float(x),
                    y=float(y),
                    sex=rng.randrange(2),
                    age=rng.random() * spec["maturity_age"] * 1.10,
                    target_x=float(x),
                    target_y=float(y),
                    move_speed=spec["move_speed"] * rng.uniform(0.88, 1.12),
                    move_cooldown=rng.random() * spec["move_interval"],
                    breed_cooldown=rng.random() * spec["breeding_cooldown"],
                )
            )
            spawned += 1

    return animals


def step_animals(animals: list[Animal], subtype_map, dt_seconds: float, rng) -> bool:
    if not animals:
        return False

    h = len(subtype_map)
    w = len(subtype_map[0])
    changed = False
    survivors: list[Animal] = []
    cells: dict[int, tuple[int, int]] = {}
    population_view = []
    for candidate in animals:
        candidate_spec = ANIMAL_SPECS.get(candidate.species)
        if candidate_spec is None:
            continue
        pcx, pcy = _animal_cell(candidate, w, h)
        candidate_ready = candidate.age >= candidate_spec["maturity_age"] and candidate.breed_cooldown <= 0.0
        population_view.append((id(candidate), candidate.species, candidate.sex, candidate_ready, pcx, pcy))

    for animal in animals:
        spec = ANIMAL_SPECS.get(animal.species)
        if spec is None:
            changed = True
            continue

        animal.age += dt_seconds
        animal.move_cooldown -= dt_seconds
        animal.breed_cooldown = max(0.0, animal.breed_cooldown - dt_seconds)

        cx, cy = _animal_cell(animal, w, h)
        current_subtype = subtype_map[cy][cx]
        if not _is_passable(current_subtype):
            changed = True
            continue

        if current_subtype in DISLIKED_SUBTYPES:
            animal.stress += dt_seconds * 0.90
        else:
            animal.stress = max(0.0, animal.stress - dt_seconds * 0.55)

        if animal.stress > 14.0:
            stress_risk = min(0.85, 0.03 + (animal.stress - 14.0) * 0.03)
            if rng.random() < stress_risk * dt_seconds:
                changed = True
                continue

        if animal.age > spec["max_age"]:
            age_over = animal.age - spec["max_age"]
            age_risk = min(0.95, 0.08 + age_over * 0.02)
            if rng.random() < age_risk * dt_seconds:
                changed = True
                continue

        if rng.random() < spec["accident_risk"] * dt_seconds:
            changed = True
            continue

        target_reached = abs(animal.target_x - animal.x) + abs(animal.target_y - animal.y) <= 0.05
        if target_reached and animal.move_cooldown <= 0.0:
            mate_cell = _nearest_mate_cell(animal, cx, cy, spec, population_view)
            if mate_cell is not None:
                nx, ny = mate_cell
            else:
                nx, ny = _choose_next_tile(animal.species, cx, cy, subtype_map, rng)
            animal.target_x = max(0.0, min((w - 1) + 0.49, nx + rng.uniform(-0.24, 0.24)))
            animal.target_y = max(0.0, min((h - 1) + 0.49, ny + rng.uniform(-0.24, 0.24)))
            target_reached = False

        dx = animal.target_x - animal.x
        dy = animal.target_y - animal.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 0.001:
            step = min(dist, animal.move_speed * dt_seconds)
            prev_x = animal.x
            prev_y = animal.y
            animal.x += (dx / dist) * step
            animal.y += (dy / dist) * step
            if step >= dist:
                animal.x = animal.target_x
                animal.y = animal.target_y
                animal.move_cooldown = spec["move_interval"] * rng.uniform(1.15, 2.40)
            if abs(animal.x - prev_x) + abs(animal.y - prev_y) > 0.001:
                changed = True

        survivors.append(animal)
        cells[id(animal)] = _animal_cell(animal, w, h)

    cap = ANIMAL_POPULATION_CAP
    newborns: list[Animal] = []
    if survivors and len(survivors) < cap:
        adult_males: dict[str, list[Animal]] = {}
        for animal in survivors:
            spec = ANIMAL_SPECS[animal.species]
            if animal.sex != 1:
                continue
            if animal.age < spec["maturity_age"] or animal.breed_cooldown > 0.0:
                continue
            adult_males.setdefault(animal.species, []).append(animal)

        occupancy = {}
        for animal in survivors:
            key = cells[id(animal)]
            occupancy[key] = occupancy.get(key, 0) + 1

        for female in survivors:
            if len(survivors) + len(newborns) >= cap:
                break
            if female.sex != 0:
                continue

            spec = ANIMAL_SPECS[female.species]
            if female.age < spec["maturity_age"] or female.breed_cooldown > 0.0:
                continue

            fx, fy = cells[id(female)]
            partner = None
            for male in adult_males.get(female.species, []):
                if male.breed_cooldown > 0.0:
                    continue
                mx, my = cells[id(male)]
                if abs(mx - fx) <= 1 and abs(my - fy) <= 1:
                    partner = male
                    break
            if partner is None:
                continue

            if rng.random() > spec["breeding_rate"] * dt_seconds:
                continue

            birth_tile = _find_birth_tile(female, subtype_map, rng, occupancy)
            if birth_tile is None:
                continue

            female.breed_cooldown = spec["breeding_cooldown"] * rng.uniform(0.85, 1.20)
            partner.breed_cooldown = spec["breeding_cooldown"] * rng.uniform(0.70, 1.10)
            litter_min, litter_max = spec["litter_size"]
            litter_count = rng.randint(litter_min, litter_max)
            bx, by = birth_tile

            for _ in range(litter_count):
                if len(survivors) + len(newborns) >= cap:
                    break
                newborns.append(
                    Animal(
                        species=female.species,
                        x=float(bx),
                        y=float(by),
                        sex=rng.randrange(2),
                        age=0.0,
                        target_x=float(bx),
                        target_y=float(by),
                        move_speed=spec["move_speed"] * rng.uniform(0.88, 1.12),
                        move_cooldown=rng.random() * spec["move_interval"],
                        breed_cooldown=spec["breeding_cooldown"] * 0.40,
                    )
                )
                key = (bx, by)
                occupancy[key] = occupancy.get(key, 0) + 1

            if litter_count > 0:
                changed = True

    if newborns:
        survivors.extend(newborns)

    if len(survivors) != len(animals):
        changed = True

    animals[:] = survivors
    return changed


def animal_counts(animals: list[Animal]) -> dict[str, int]:
    counts = {species: 0 for species in ANIMAL_SPECS}
    for animal in animals:
        if animal.species in counts:
            counts[animal.species] += 1
    return counts
