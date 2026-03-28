import random
import os

WIDTH = 100
HEIGHT = 100

def generuj_mape():
    mapa = []

    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            # tworzymy płynniejsze wartości zamiast totalnego randoma
            val = random.random()

            # lekka korekta żeby robić "plamy"
            if x > 0:
                val = (val + random.random()) / 2
            if y > 0:
                val = (val + random.random()) / 2

            # przypisanie terenu
            if val < 0.3:
                tile = "W"  # woda
            elif val < 0.6:
                tile = "G"  # grass
            elif val < 0.8:
                tile = "F"  # forest
            else:
                tile = "M"  # mountain

            row.append(tile)
        mapa.append(row)

    return mapa


def zapisz_mape(mapa):
    base_path = os.path.dirname(os.path.dirname(__file__))
    map_path = os.path.join(base_path, "data", "map.txt")
    with open(map_path, "w") as f:
        for row in mapa:
            f.write("".join(row) + "\n")


if __name__ == "__main__":
    mapa = generuj_mape()
    zapisz_mape(mapa)
    print("Mapa wygenerowana!")