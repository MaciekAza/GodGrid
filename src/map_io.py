import os

CHAR_TO_TILE = {
    "G": "grass",
    "W": "water",
    "O": "deep_ocean",
    "F": "forest",
    "H": "highland",
    "M": "mountain_high",
    "P": "mountain_peak",
}

TILE_TO_CHAR = {value: key for key, value in CHAR_TO_TILE.items()}

TILE_COLORS = {
    "grass": (50, 200, 50),
    "water": (50, 50, 200),
    "deep_ocean": (18, 36, 125),
    "forest": (20, 120, 20),
    "highland": (108, 134, 88),
    "mountain_high": (122, 122, 122),
    "mountain_peak": (198, 198, 198),
}


def map_path_from_project_root(src_file):
    base_path = os.path.dirname(os.path.dirname(src_file))
    return os.path.join(base_path, "data", "map.txt")


def load_map(map_path):
    mapa = []
    with open(map_path, "r") as f:
        for linia in f:
            row = [CHAR_TO_TILE[znak] for znak in linia.strip()]
            mapa.append(row)
    return mapa


def save_map(mapa, map_path):
    with open(map_path, "w") as f:
        for row in mapa:
            line = "".join(TILE_TO_CHAR.get(tile, "G") for tile in row)
            f.write(line + "\n")
    return map_path
