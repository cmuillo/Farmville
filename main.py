import json
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk
except Exception:  # Pillow es opcional; si no existe se usa texto en botones
    Image = None
    ImageTk = None

try:
    from tkVideoPlayer import TkinterVideo
except Exception:  # El video de fondo es opcional
    TkinterVideo = None


# -----------------------------------------------------------------------------
# Configuracion general del juego
# -----------------------------------------------------------------------------

GRID_SIZE = 10
INITIAL_COINS = 100
NEW_TERRAIN_COST = 20000
SAVE_FILE = Path("data/savegame.json")
IMAGES_DIR = Path("assets/images")
VIDEO_FILE = Path("assets/video/menu.mp4")
MENU_BG_FILES = [
    Path("assets/images/menu.jpg"),
    Path("assets/images/menu.png"),
    Path("assets/images/menu_background.png"),
]


@dataclass
class ProductDefinition:
    key: str
    name: str
    category: str
    price: int
    production_time: int = 0
    gain: int = 0
    one_shot: bool = False
    image_file: str = ""
    short: str = ""

    @property
    def is_productive(self) -> bool:
        return self.production_time > 0 and self.gain > 0


# Catalogo oficial solicitado en el enunciado
PRODUCTS: Dict[str, ProductDefinition] = {
    # Plantaciones (one_shot para cumplir comprar->sembrar->cosechar->comprar)
    "trigo": ProductDefinition("trigo", "Trigo", "plantacion", 20, 30, 35, True, "trigo.png", "TR"),
    "maiz": ProductDefinition("maiz", "Maiz", "plantacion", 35, 60, 60, True, "maiz.png", "MZ"),
    "zanahoria": ProductDefinition("zanahoria", "Zanahoria", "plantacion", 50, 90, 90, True, "zanahoria.png", "ZA"),
    "tomate": ProductDefinition("tomate", "Tomate", "plantacion", 75, 120, 130, True, "tomate.png", "TO"),
    "papa": ProductDefinition("papa", "Papa", "plantacion", 100, 180, 180, True, "papa.png", "PA"),
    # Animales
    "gallina": ProductDefinition("gallina", "Gallina", "animal", 150, 120, 250, False, "gallina.png", "GA"),
    "pato": ProductDefinition("pato", "Pato", "animal", 250, 180, 400, False, "pato.png", "PT"),
    "oveja": ProductDefinition("oveja", "Oveja", "animal", 400, 300, 650, False, "oveja.png", "OV"),
    "cerdo": ProductDefinition("cerdo", "Cerdo", "animal", 700, 420, 1100, False, "cerdo.png", "CE"),
    "vaca": ProductDefinition("vaca", "Vaca", "animal", 1000, 600, 1700, False, "vaca.png", "VA"),
    # Arboles
    "manzano": ProductDefinition("manzano", "Manzano", "arbol", 120, 180, 200, False, "manzano.png", "MN"),
    "naranjo": ProductDefinition("naranjo", "Naranjo", "arbol", 180, 240, 320, False, "naranjo.png", "NR"),
    "limonero": ProductDefinition("limonero", "Limonero", "arbol", 250, 300, 450, False, "limonero.png", "LM"),
    "cacaotero": ProductDefinition("cacaotero", "Cacaotero",  "arbol", 500, 480, 850, False, "cacaotero.png", "CC"),
    "cafetal": ProductDefinition("cafetal", "Cafetal", "arbol", 800, 600, 1400, False, "cafetal.png", "CF"),
    # Decorativos
    "cerca": ProductDefinition("cerca", "Cerca", "decorativo", 50, 0, 0, False, "cerca.png", "CR"),
    "banco": ProductDefinition("banco", "Banco", "decorativo", 100, 0, 0, False, "banco.png", "BC"),
    "fuente": ProductDefinition("fuente", "Fuente", "decorativo", 250, 0, 0, False, "fuente.png", "FT"),
    "estatua": ProductDefinition("estatua", "Estatua", "decorativo", 500, 0, 0, False, "estatua.png", "ES"),
    "molino_decorativo": ProductDefinition("molino_decorativo", "Molino Decorativo", "decorativo", 1000, 0, 0, False, "molino_decorativo.png", "MD"),
}

CONSUMABLES = {
    "pesticida": {"name": "Pesticida", "price": 80, "image": "pesticida.png"},
    "medicina": {"name": "Medicina", "price": 120, "image": "medicina.png"},
}


# -----------------------------------------------------------------------------
# Modelo orientado a objetos con herencia y polimorfismo
# -----------------------------------------------------------------------------


class FarmEntity:
    """Clase base de cualquier elemento colocable en la granja."""

    def __init__(self, definition: ProductDefinition) -> None:
        self.definition = definition

    def required_cure(self) -> Optional[str]:
        return None

    def is_one_shot(self) -> bool:
        return self.definition.one_shot


class PlantEntity(FarmEntity):
    def required_cure(self) -> Optional[str]:
        return "pesticida"


class TreeEntity(FarmEntity):
    def required_cure(self) -> Optional[str]:
        return "pesticida"


class AnimalEntity(FarmEntity):
    def required_cure(self) -> Optional[str]:
        return "medicina"


class DecorativeEntity(FarmEntity):
    pass


def create_entity(definition: ProductDefinition) -> FarmEntity:
    """Factory polimorfica para crear la subclase correcta segun categoria."""
    if definition.category == "plantacion":
        return PlantEntity(definition)
    if definition.category == "arbol":
        return TreeEntity(definition)
    if definition.category == "animal":
        return AnimalEntity(definition)
    return DecorativeEntity(definition)


@dataclass
class PlacedItem:
    item_id: str
    product_key: str
    terrain_index: int
    row: int
    col: int
    animal_name: str = ""
    remaining_seconds: int = 0
    ready: bool = False
    ready_wait_seconds: int = 0
    condition: Optional[str] = None  # pest | disease
    condition_remaining: int = 0
    dead: bool = False

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "product_key": self.product_key,
            "terrain_index": self.terrain_index,
            "row": self.row,
            "col": self.col,
            "animal_name": self.animal_name,
            "remaining_seconds": self.remaining_seconds,
            "ready": self.ready,
            "ready_wait_seconds": self.ready_wait_seconds,
            "condition": self.condition,
            "condition_remaining": self.condition_remaining,
            "dead": self.dead,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlacedItem":
        return cls(
            item_id=data["item_id"],
            product_key=data["product_key"],
            terrain_index=data["terrain_index"],
            row=data["row"],
            col=data["col"],
            animal_name=data.get("animal_name", ""),
            remaining_seconds=data.get("remaining_seconds", 0),
            ready=data.get("ready", False),
            ready_wait_seconds=data.get("ready_wait_seconds", 0),
            condition=data.get("condition"),
            condition_remaining=data.get("condition_remaining", 0),
            dead=data.get("dead", False),
        )


@dataclass
class Terrain:
    index: int
    grid: List[List[Optional[str]]] = field(
        default_factory=lambda: [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    )

    def to_dict(self) -> dict:
        return {"index": self.index, "grid": self.grid}

    @classmethod
    def from_dict(cls, data: dict) -> "Terrain":
        return cls(index=data["index"], grid=data["grid"])


@dataclass
class Statistics:
    total_generated: int = 0
    total_products_bought: int = 0
    products_bought_by_type: Dict[str, int] = field(default_factory=dict)
    products_gain_by_type: Dict[str, int] = field(default_factory=dict)
    total_play_seconds: int = 0

    def to_dict(self) -> dict:
        return {
            "total_generated": self.total_generated,
            "total_products_bought": self.total_products_bought,
            "products_bought_by_type": self.products_bought_by_type,
            "products_gain_by_type": self.products_gain_by_type,
            "total_play_seconds": self.total_play_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Statistics":
        return cls(
            total_generated=data.get("total_generated", 0),
            total_products_bought=data.get("total_products_bought", 0),
            products_bought_by_type=data.get("products_bought_by_type", {}),
            products_gain_by_type=data.get("products_gain_by_type", {}),
            total_play_seconds=data.get("total_play_seconds", 0),
        )


@dataclass
class GameState:
    player_name: str
    coins: int
    terrains: List[Terrain]
    current_terrain_index: int
    items: Dict[str, PlacedItem]
    inventory: Dict[str, int]
    auto_harvest: bool
    statistics: Statistics
    log_entries: List[str]

    @classmethod
    def new(cls, player_name: str) -> "GameState":
        return cls(
            player_name=player_name,
            coins=INITIAL_COINS,
            terrains=[Terrain(index=0)],
            current_terrain_index=0,
            items={},
            inventory={"pesticida": 0, "medicina": 0},
            auto_harvest=False,
            statistics=Statistics(),
            log_entries=["Partida nueva creada."],
        )

    def to_dict(self) -> dict:
        return {
            "player_name": self.player_name,
            "coins": self.coins,
            "terrains": [t.to_dict() for t in self.terrains],
            "current_terrain_index": self.current_terrain_index,
            "items": {k: v.to_dict() for k, v in self.items.items()},
            "inventory": self.inventory,
            "auto_harvest": self.auto_harvest,
            "statistics": self.statistics.to_dict(),
            "log_entries": self.log_entries[-200:],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        return cls(
            player_name=data["player_name"],
            coins=data["coins"],
            terrains=[Terrain.from_dict(t) for t in data["terrains"]],
            current_terrain_index=data.get("current_terrain_index", 0),
            items={k: PlacedItem.from_dict(v) for k, v in data.get("items", {}).items()},
            inventory=data.get("inventory", {"pesticida": 0, "medicina": 0}),
            auto_harvest=data.get("auto_harvest", False),
            statistics=Statistics.from_dict(data.get("statistics", {})),
            log_entries=data.get("log_entries", []),
        )


# -----------------------------------------------------------------------------
# Persistencia JSON
# -----------------------------------------------------------------------------


def save_game(state: GameState) -> None:
    SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SAVE_FILE.open("w", encoding="utf-8") as fp:
        json.dump(state.to_dict(), fp, ensure_ascii=False, indent=2)


def load_game() -> Optional[GameState]:
    if not SAVE_FILE.exists():
        return None
    with SAVE_FILE.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return GameState.from_dict(data)


def delete_save() -> None:
    if SAVE_FILE.exists():
        SAVE_FILE.unlink()


# -----------------------------------------------------------------------------
# Hilo por parcela productiva
# -----------------------------------------------------------------------------


class ProductionThread(threading.Thread):
    def __init__(self, engine: "GameEngine", item_id: str) -> None:
        super().__init__(daemon=True)
        self.engine = engine
        self.item_id = item_id
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set() and self.engine.running:
            time.sleep(1)
            if self.stop_event.is_set() or not self.engine.running:
                break
            self.engine.tick_item(self.item_id)

    def stop(self) -> None:
        self.stop_event.set()


class GameEngine:
    def __init__(self, state: GameState, logger: Optional[Callable[[str], None]] = None) -> None:
        self.state = state
        self.running = True
        self.lock = threading.RLock()
        self.threads: Dict[str, ProductionThread] = {}
        self.logger = logger

    def log(self, text: str) -> None:
        with self.lock:
            line = f"[{time.strftime('%H:%M:%S')}] {text}"
            self.state.log_entries.append(line)
            self.state.log_entries = self.state.log_entries[-200:]
        if self.logger:
            self.logger(line)

    def is_valid_position(self, row: int, col: int) -> bool:
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def get_current_terrain(self) -> Terrain:
        return self.state.terrains[self.state.current_terrain_index]

    def get_item_at(self, terrain_index: int, row: int, col: int) -> Optional[PlacedItem]:
        terrain = self.state.terrains[terrain_index]
        item_id = terrain.grid[row][col]
        if not item_id:
            return None
        return self.state.items.get(item_id)

    def can_buy(self, amount: int) -> bool:
        return self.state.coins >= amount

    def spend(self, amount: int) -> bool:
        if self.state.coins < amount:
            return False
        self.state.coins -= amount
        return True

    def buy_product(self, product_key: str) -> Tuple[bool, str]:
        if product_key in CONSUMABLES:
            price = CONSUMABLES[product_key]["price"]
            if not self.spend(price):
                return False, "No tienes monedas suficientes."
            self.state.inventory[product_key] = self.state.inventory.get(product_key, 0) + 1
            self.state.statistics.total_products_bought += 1
            self.state.statistics.products_bought_by_type[product_key] = (
                self.state.statistics.products_bought_by_type.get(product_key, 0) + 1
            )
            self.log(f"Compraste 1 {CONSUMABLES[product_key]['name']}.")
            return True, "Consumible comprado y enviado al inventario."

        definition = PRODUCTS[product_key]
        if not self.spend(definition.price):
            return False, "No tienes monedas suficientes."
        self.state.inventory[product_key] = self.state.inventory.get(product_key, 0) + 1
        self.state.statistics.total_products_bought += 1
        self.state.statistics.products_bought_by_type[product_key] = (
            self.state.statistics.products_bought_by_type.get(product_key, 0) + 1
        )
        self.log(f"Compraste {definition.name}. Se agrego al inventario.")
        return True, "Producto comprado y enviado al inventario. Ahora puedes colocarlo en una celda."

    def place_item(
        self,
        product_key: str,
        terrain_index: int,
        row: int,
        col: int,
        animal_name: str = "",
        from_inventory: bool = False,
    ) -> Tuple[bool, str]:
        if not self.is_valid_position(row, col):
            return False, "Posicion invalida."
        terrain = self.state.terrains[terrain_index]
        if terrain.grid[row][col] is not None:
            return False, "La celda no esta libre."

        if from_inventory:
            if self.state.inventory.get(product_key, 0) <= 0:
                return False, "No hay unidades en inventario."
            self.state.inventory[product_key] -= 1

        definition = PRODUCTS[product_key]
        item_id = str(uuid.uuid4())
        item = PlacedItem(
            item_id=item_id,
            product_key=product_key,
            terrain_index=terrain_index,
            row=row,
            col=col,
            animal_name=animal_name.strip(),
            remaining_seconds=definition.production_time,
        )
        self.state.items[item_id] = item
        terrain.grid[row][col] = item_id

        if definition.is_productive:
            self.start_thread(item_id)

        friendly = definition.name
        if definition.category == "animal" and item.animal_name:
            friendly = f"{friendly} ({item.animal_name})"
        self.log(f"Colocado: {friendly} en terreno {terrain_index + 1}, fila {row + 1}, columna {col + 1}.")
        return True, "Producto colocado correctamente."

    def remove_to_inventory(self, terrain_index: int, row: int, col: int) -> Tuple[bool, str]:
        with self.lock:
            item = self.get_item_at(terrain_index, row, col)
            if not item:
                return False, "No hay nada para retirar."
            definition = PRODUCTS[item.product_key]
            self.state.inventory[item.product_key] = self.state.inventory.get(item.product_key, 0) + 1
            self._remove_item(item)
            self.log(f"{definition.name} enviado al inventario.")
            return True, "Elemento retirado y enviado al inventario."

    def clear_cell(self, terrain_index: int, row: int, col: int) -> Tuple[bool, str]:
        with self.lock:
            item = self.get_item_at(terrain_index, row, col)
            if not item:
                return False, "No hay nada para limpiar."
            self._remove_item(item)
            self.log("Celda limpiada manualmente.")
            return True, "Celda limpiada."

    def _remove_item(self, item: PlacedItem) -> None:
        terrain = self.state.terrains[item.terrain_index]
        terrain.grid[item.row][item.col] = None
        self.state.items.pop(item.item_id, None)
        self.stop_thread(item.item_id)

    def buy_terrain(self) -> Tuple[bool, str]:
        with self.lock:
            if not self.spend(NEW_TERRAIN_COST):
                return False, "No tienes monedas suficientes para comprar terreno."
            idx = len(self.state.terrains)
            self.state.terrains.append(Terrain(index=idx))
            self.log(f"Compraste el terreno {idx + 1}.")
            return True, f"Terreno {idx + 1} comprado con exito."

    def set_current_terrain(self, idx: int) -> bool:
        if 0 <= idx < len(self.state.terrains):
            self.state.current_terrain_index = idx
            return True
        return False

    def start_thread(self, item_id: str) -> None:
        item = self.state.items.get(item_id)
        if not item:
            return
        definition = PRODUCTS[item.product_key]
        if not definition.is_productive:
            return
        if item_id in self.threads and self.threads[item_id].is_alive():
            return
        th = ProductionThread(self, item_id)
        self.threads[item_id] = th
        th.start()

    def start_all_threads(self) -> None:
        for item_id in list(self.state.items.keys()):
            self.start_thread(item_id)

    def stop_thread(self, item_id: str) -> None:
        th = self.threads.pop(item_id, None)
        if th:
            th.stop()

    def stop_all_threads(self) -> None:
        self.running = False
        for th in list(self.threads.values()):
            th.stop()
        self.threads.clear()

    def cure_item(self, terrain_index: int, row: int, col: int) -> Tuple[bool, str]:
        with self.lock:
            item = self.get_item_at(terrain_index, row, col)
            if not item:
                return False, "No hay elemento en la celda."
            definition = PRODUCTS[item.product_key]
            entity = create_entity(definition)
            needed = entity.required_cure()
            if not item.condition:
                return False, "Este elemento no tiene plaga/enfermedad."
            if not needed:
                return False, "Este elemento no requiere cura."
            if self.state.inventory.get(needed, 0) <= 0:
                return False, f"Necesitas {needed} en inventario."
            self.state.inventory[needed] -= 1
            item.condition = None
            item.condition_remaining = 0
            self.log(f"Aplicaste {needed} a {definition.name}.")
            return True, "Elemento curado."

    def harvest(self, item: PlacedItem, automatic: bool = False) -> Tuple[bool, str]:
        with self.lock:
            if item.item_id not in self.state.items:
                return False, "Elemento ya no existe."
            if item.dead:
                return False, "Elemento muerto."
            if not item.ready:
                return False, "Aun no esta listo."

            definition = PRODUCTS[item.product_key]
            self.state.coins += definition.gain
            self.state.statistics.total_generated += definition.gain
            self.state.statistics.products_gain_by_type[item.product_key] = (
                self.state.statistics.products_gain_by_type.get(item.product_key, 0) + definition.gain
            )

            item.ready = False
            item.ready_wait_seconds = 0

            if definition.one_shot:
                self.log(
                    f"Cosecha {'automatica' if automatic else 'manual'} de {definition.name}: +{definition.gain} monedas."
                )
                self._remove_item(item)
                return True, "Cosechado. Como es plantacion de un solo uso, la celda queda libre."

            item.remaining_seconds = definition.production_time
            self.log(
                f"Recoleccion {'automatica' if automatic else 'manual'} de {definition.name}: +{definition.gain} monedas."
            )
            return True, "Produccion recolectada."

    def collect_ready_items(self) -> int:
        """Recolecta automaticamente todos los items listos y devuelve cuántos se recolectaron."""
        with self.lock:
            ready_ids = [it.item_id for it in self.state.items.values() if it.ready and not it.dead]

        harvested = 0
        for item_id in ready_ids:
            item = self.state.items.get(item_id)
            if item and item.ready and not item.dead:
                ok, _ = self.harvest(item, automatic=True)
                if ok:
                    harvested += 1
        return harvested

    def tick_item(self, item_id: str) -> None:
        """Este metodo es llamado por cada hilo por parcela productiva cada segundo."""
        with self.lock:
            item = self.state.items.get(item_id)
            if not item:
                return
            if item.dead:
                return

            definition = PRODUCTS[item.product_key]
            entity = create_entity(definition)

            # Si hay plaga/enfermedad, el tiempo de cura corre y la produccion se detiene.
            if item.condition:
                item.condition_remaining -= 1
                if item.condition_remaining <= 0:
                    item.dead = True
                    self.log(f"{definition.name} murio por no aplicar cura a tiempo.")
                return

            # Evento aleatorio de plaga o enfermedad
            if definition.is_productive and not item.ready and random.random() < 0.003:
                cure = entity.required_cure()
                if cure:
                    item.condition = "plaga" if cure == "pesticida" else "enfermedad"
                    item.condition_remaining = 90
                    self.log(
                        f"{definition.name} tiene {item.condition}. Aplica {cure} en 90s o morira."
                    )
                    return

            # Cuenta normal de produccion
            if definition.is_productive and not item.ready:
                item.remaining_seconds -= 1
                if item.remaining_seconds <= 0:
                    item.remaining_seconds = 0
                    item.ready = True
                    item.ready_wait_seconds = 0
                    self.log(f"{definition.name} esta listo para recolectar.")
                    if self.state.auto_harvest:
                        self.harvest(item, automatic=True)
                return

            # Si el producto ya estaba listo y luego se activa auto recoleccion,
            # tambien debe recolectarse sin esperar a otro ciclo de produccion.
            if item.ready and self.state.auto_harvest:
                self.harvest(item, automatic=True)
                return

            # Si esta listo y no hay auto-harvest, puede daÃ±arse por no recolectar.
            if item.ready and not self.state.auto_harvest:
                item.ready_wait_seconds += 1
                if item.ready_wait_seconds >= 90:
                    if definition.one_shot:
                        self.log(f"La cosecha de {definition.name} se dano y se perdio.")
                        self._remove_item(item)
                    else:
                        self.log(f"Se perdio una produccion de {definition.name} por no recolectar a tiempo.")
                        item.ready = False
                        item.ready_wait_seconds = 0
                        item.remaining_seconds = definition.production_time


# -----------------------------------------------------------------------------
# Interfaz grafica Tkinter
# -----------------------------------------------------------------------------


def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    mm = seconds // 60
    ss = seconds % 60
    return f"{mm:02d}:{ss:02d}"


class MenuView(tk.Frame):
    def __init__(self, master: tk.Tk, app: "FarmApp") -> None:
        super().__init__(master, bg="#06a10d")
        self.app = app
        self.bg_label = None
        self.bg_photo = None
        self.bg_source_image = None
        self.logo_img = None
        self.panel = None
        self._build()

    def _refresh_background(self) -> None:
        if not (self.bg_label and self.bg_source_image and Image and ImageTk):
            return
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        resized = self.bg_source_image.resize((w, h))
        self.bg_photo = ImageTk.PhotoImage(resized)
        self.bg_label.configure(image=self.bg_photo)

    def _on_resize(self, _event: tk.Event) -> None:
        self._refresh_background()
        self._position_panel()

    def _position_panel(self) -> None:
        if not self.panel:
            return
        available_h = max(self.winfo_height(), 1)
        panel_h = min(max(available_h - 40, 520), 640)
        self.panel.place_configure(x=18, rely=0.5, anchor="w", width=470, height=panel_h)

    def _build(self) -> None:
        self.pack(fill="both", expand=True)

        # Fondo del menu por imagen fija.
        menu_bg = next((p for p in MENU_BG_FILES if p.exists()), None)
        if menu_bg:
            try:
                if Image and ImageTk:
                    self.bg_source_image = Image.open(menu_bg)
                    # Imagen inicial temporal; luego se ajusta al tamano real de la ventana.
                    self.bg_photo = ImageTk.PhotoImage(self.bg_source_image)
                else:
                    self.bg_photo = tk.PhotoImage(file=str(menu_bg))
                self.bg_label = tk.Label(self, image=self.bg_photo, bd=0)
                self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
                if self.bg_source_image is not None:
                    self.bind("<Configure>", self._on_resize)
                    self.after(10, self._refresh_background)
            except Exception:
                self.configure(bg="#06a10d")

        panel = tk.Frame(self, bg="#f5f5f5", bd=0, padx=22, pady=14)
        panel.place(x=18, rely=0.5, anchor="w", width=470, height=560)
        self.panel = panel
        self.after(20, self._position_panel)

        content = tk.Frame(panel, bg="#f5f5f5")
        content.pack(fill="both", expand=True)

        footer = tk.Frame(panel, bg="#f5f5f5")
        footer.pack(side="bottom", fill="x", pady=(8, 0))

        heading_color = "#3f3f3f"

        logo_path = IMAGES_DIR / "logo.png"
        if Image and logo_path.exists():
            try:
                img = Image.open(logo_path)
                # Mantiene proporcion para evitar que el logo se vea estirado.
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img.thumbnail((330, 190), resample)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(content, image=self.logo_img, bg="#f5f5f5").pack(pady=(0, 8))
            except Exception:
                tk.Label(
                    content,
                    text="JossFarm SiembraTEC",
                    font=("Segoe UI", 28, "bold"),
                    fg=heading_color,
                    bg="#f5f5f5",
                ).pack(pady=(10, 22))
        else:
            tk.Label(
                content,
                text="JossFarm SiembraTEC",
                font=("Segoe UI", 28, "bold"),
                fg=heading_color,
                bg="#f5f5f5",
            ).pack(pady=(10, 22))

        tk.Label(
            content,
            text="Bienvenida a tu granja virtual",
            font=("Segoe UI", 16, "bold"),
            fg=heading_color,
            bg="#f5f5f5",
        ).pack(pady=(0, 4))

        tk.Label(
            content,
            text="Administra cultivos y animales, produce recursos\ny expande tus terrenos.",
            font=("Segoe UI", 10),
            fg=heading_color,
            bg="#f5f5f5",
            justify="center",
        ).pack(pady=(0, 10))

        style = {
            "font": ("Segoe UI", 15, "bold"),
            "fg": "#ffffff",
            "bg": "#447428",
            "activebackground": "#365d20",
            "activeforeground": "#ffffff",
            "bd": 0,
            "cursor": "hand2",
            "relief": "flat",
            "width": 17,
            "padx": 6,
            "pady": 6,
        }

        tk.Button(content, text="Iniciar Partida", command=self.app.new_game, **style).pack(pady=3)
        tk.Button(content, text="Continuar Partida", command=self.app.continue_game, **style).pack(pady=3)
        tk.Button(content, text="Ver Estadisticas", command=self.app.show_menu_stats, **style).pack(pady=3)
        tk.Button(content, text="Salir", command=self.app.close_app, **style).pack(pady=3)

        tk.Label(
            footer,
            text="Hecho por Joselyn Melissa Hidalgo Torres",
            font=("Segoe UI", 9),
            fg=heading_color,
            bg="#f5f5f5",
        ).pack()

        tk.Label(
            footer,
            text="Version 1.0.0",
            font=("Segoe UI", 9),
            fg=heading_color,
            bg="#f5f5f5",
        ).pack(pady=(2, 0))


class ShopWindow(tk.Toplevel):
    def __init__(self, parent: "GameView") -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Tienda")
        self.geometry("860x480")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)
        self._build()

    def _build(self) -> None:
        columns = ("clave", "nombre", "categoria", "precio", "tiempo", "ganancia")
        tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        tree.pack(fill="both", expand=True, padx=12, pady=12)

        headers = {
            "clave": "Clave",
            "nombre": "Producto",
            "categoria": "Categoria",
            "precio": "Precio",
            "tiempo": "Tiempo (s)",
            "ganancia": "Ganancia",
        }
        for col, title in headers.items():
            tree.heading(col, text=title)

        for key, definition in PRODUCTS.items():
            tree.insert(
                "",
                "end",
                values=(
                    key,
                    definition.name,
                    definition.category,
                    definition.price,
                    definition.production_time,
                    definition.gain,
                ),
            )

        for key, data in CONSUMABLES.items():
            tree.insert("", "end", values=(key, data["name"], "consumible", data["price"], 0, 0))

        status = tk.Label(self, text=f"Monedas disponibles: {self.parent.engine.state.coins}", bg="#eef5e8")
        status.pack(pady=(0, 8))

        def buy_selected() -> None:
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Tienda", "Selecciona un producto.", parent=self)
                return
            vals = tree.item(selected[0], "values")
            key = vals[0]
            ok, msg = self.parent.engine.buy_product(key)
            if not ok:
                messagebox.showerror("Tienda", msg, parent=self)
                return
            status.config(text=f"Monedas disponibles: {self.parent.engine.state.coins}")
            if key in PRODUCTS:
                self.parent.set_pending_purchase(key)
            self.parent.refresh_ui()
            messagebox.showinfo("Tienda", msg, parent=self)

        tk.Button(
            self,
            text="Comprar seleccionado",
            font=("Segoe UI", 12, "bold"),
            bg="#3c9b2c",
            fg="white",
            bd=0,
            command=buy_selected,
        ).pack(pady=(0, 12))


class InventoryWindow(tk.Toplevel):
    def __init__(self, parent: "GameView") -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Inventario")
        self.geometry("520x430")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="Inventario actual", font=("Segoe UI", 18, "bold"), bg="#eef5e8").pack(pady=8)

        self.listbox = tk.Listbox(self, font=("Consolas", 12), height=14)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=10)

        self.entries: List[Tuple[str, int]] = []
        for key, count in sorted(self.parent.engine.state.inventory.items()):
            if count > 0:
                label = key
                if key in PRODUCTS:
                    label = PRODUCTS[key].name
                elif key in CONSUMABLES:
                    label = CONSUMABLES[key]["name"]
                self.entries.append((key, count))
                self.listbox.insert("end", f"{label:<22} x {count}")

        if not self.entries:
            self.listbox.insert("end", "Inventario vacio.")
            self.listbox.insert("end", "Compra en la tienda o retira elementos del terreno.")

        tk.Label(
            self,
            text="Para consumibles usa el boton Curar sobre una celda afectada.",
            bg="#eef5e8",
        ).pack(pady=6)

        def place_from_inventory() -> None:
            idx = self.listbox.curselection()
            if not idx:
                messagebox.showwarning("Inventario", "Selecciona un item.", parent=self)
                return
            key = self.entries[idx[0]][0]
            if key in CONSUMABLES:
                messagebox.showwarning("Inventario", "Los consumibles no se colocan en celdas.", parent=self)
                return
            self.parent.set_pending_inventory_item(key)
            messagebox.showinfo(
                "Inventario",
                "Producto seleccionado. Ahora haz clic en una celda vacia para colocarlo.",
                parent=self,
            )
            self.destroy()

        place_button = tk.Button(
            self,
            text="Colocar item seleccionado",
            font=("Segoe UI", 12, "bold"),
            bg="#3c9b2c",
            fg="white",
            bd=0,
            command=place_from_inventory,
        )
        place_button.pack(pady=10)

        if not self.entries:
            place_button.config(state="disabled", bg="#91b88a", fg="#eef5e8")


class StatsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, state: GameState) -> None:
        super().__init__(parent)
        self.title("Estadisticas")
        self.geometry("660x520")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)

        stats = state.statistics
        frame = tk.Frame(self, bg="#eef5e8")
        frame.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(frame, text="Resumen de partida", font=("Segoe UI", 20, "bold"), bg="#eef5e8").pack(anchor="w")
        tk.Label(frame, text=f"Jugador: {state.player_name}", bg="#eef5e8", font=("Segoe UI", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Monedas actuales: {state.coins}", bg="#eef5e8", font=("Segoe UI", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Terrenos comprados: {len(state.terrains)}", bg="#eef5e8", font=("Segoe UI", 12)).pack(anchor="w")
        tk.Label(
            frame,
            text=f"Tiempo jugado: {format_seconds(stats.total_play_seconds)}",
            bg="#eef5e8",
            font=("Segoe UI", 12),
        ).pack(anchor="w")
        tk.Label(frame, text=f"Monedas generadas: {stats.total_generated}", bg="#eef5e8", font=("Segoe UI", 12)).pack(anchor="w")
        tk.Label(
            frame,
            text=f"Total de compras realizadas: {stats.total_products_bought}",
            bg="#eef5e8",
            font=("Segoe UI", 12),
        ).pack(anchor="w")

        tk.Label(frame, text="Compras por producto:", font=("Segoe UI", 12, "bold"), bg="#eef5e8").pack(anchor="w", pady=(10, 2))
        buy_box = tk.Text(frame, height=8, width=72, font=("Consolas", 10))
        buy_box.pack(fill="x")
        if not stats.products_bought_by_type:
            buy_box.insert("end", "Sin compras registradas.\n")
        else:
            for key, count in sorted(stats.products_bought_by_type.items()):
                name = PRODUCTS[key].name if key in PRODUCTS else CONSUMABLES.get(key, {}).get("name", key)
                buy_box.insert("end", f"- {name}: {count}\n")
        buy_box.config(state="disabled")

        tk.Label(frame, text="Ganancias por producto:", font=("Segoe UI", 12, "bold"), bg="#eef5e8").pack(anchor="w", pady=(10, 2))
        gain_box = tk.Text(frame, height=8, width=72, font=("Consolas", 10))
        gain_box.pack(fill="x")
        if not stats.products_gain_by_type:
            gain_box.insert("end", "Sin ganancias registradas.\n")
        else:
            for key, amount in sorted(stats.products_gain_by_type.items()):
                name = PRODUCTS[key].name if key in PRODUCTS else key
                gain_box.insert("end", f"- {name}: {amount}\n")
        gain_box.config(state="disabled")


class GameView(tk.Toplevel):
    def __init__(self, app: "FarmApp", state: GameState) -> None:
        super().__init__(app.root)
        self.app = app
        self.state = state
        self.engine = GameEngine(state, logger=self.add_log_line)
        self.engine.start_all_threads()

        self.title("SiembraTEC - Juego")
        self.geometry("1340x860")
        self.minsize(1180, 720)
        self.configure(bg="#dcefd1")

        self.pending_shop_item: Optional[str] = None
        self.pending_inventory_item: Optional[str] = None
        self.selected_cell: Optional[Tuple[int, int]] = None

        self.photo_cache: Dict[str, tk.PhotoImage] = {}
        self.cell_buttons: List[List[tk.Button]] = []

        self.info_var = tk.StringVar(value="")
        self.selected_var = tk.StringVar(value="Selecciona una celda")
        self.pending_var = tk.StringVar(value="Sin producto pendiente")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_layout()
        self._load_images()
        self.refresh_ui()
        self._ui_loop()

    def _build_layout(self) -> None:
        top = tk.Frame(self, bg="#e7f4df")
        top.pack(fill="x", padx=8, pady=6)

        tk.Label(top, textvariable=self.info_var, font=("Segoe UI", 11, "bold"), bg="#e7f4df").pack(side="left", padx=8)
        tk.Label(top, textvariable=self.pending_var, font=("Segoe UI", 11), bg="#e7f4df").pack(side="right", padx=8)

        toolbar = tk.Frame(self, bg="#dcefd1")
        toolbar.pack(fill="x", padx=8, pady=(0, 6))

        row_top = tk.Frame(toolbar, bg="#dcefd1")
        row_top.pack(fill="x", pady=(0, 4))

        row_bottom = tk.Frame(toolbar, bg="#dcefd1")
        row_bottom.pack(fill="x")

        def btn(parent: tk.Widget, text: str, cmd: Callable[[], None], bg: str = "#2f8f2f") -> None:
            tk.Button(
            parent,
                text=text,
                command=cmd,
                font=("Segoe UI", 10, "bold"),
                bg=bg,
                fg="white",
                activebackground="#256f25",
                bd=0,
                padx=10,
                pady=6,
                cursor="hand2",
            ).pack(side="left", padx=3)

        btn(row_top, "Tienda", self.open_shop)
        btn(row_top, "Inventario", self.open_inventory)
        btn(row_top, "Guardar", self.save_now, bg="#3b7ea7")
        btn(row_top, "Estadisticas", self.open_stats, bg="#7a5ba6")
        btn(row_top, "Retirar -> Inventario", self.remove_selected_to_inventory, bg="#4b8c52")
        btn(row_top, "Cosechar", self.harvest_selected, bg="#996515")
        btn(row_top, "Curar", self.cure_selected, bg="#995a1b")
        btn(row_top, "Limpiar celda", self.clear_selected, bg="#7e3a3a")

        btn(row_bottom, "Terreno -", self.prev_terrain, bg="#40506b")
        btn(row_bottom, "Terreno +", self.next_terrain, bg="#40506b")
        btn(row_bottom, "Ir a terreno", self.goto_terrain_dialog, bg="#40506b")
        btn(row_bottom, "Comprar terreno (20000)", self.buy_terrain, bg="#3d5f28")

        self.auto_var = tk.BooleanVar(value=self.state.auto_harvest)
        tk.Checkbutton(
            row_bottom,
            text="Auto recoleccion",
            variable=self.auto_var,
            command=self.toggle_auto_harvest,
            font=("Segoe UI", 10, "bold"),
            bg="#dcefd1",
        ).pack(side="left", padx=14)

        body = tk.Frame(self, bg="#dcefd1")
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left = tk.Frame(body, bg="#dcefd1")
        left.pack(side="left", fill="both", expand=True)

        grid_frame = tk.Frame(left, bg="#98c787", bd=2, relief="ridge")
        grid_frame.pack(fill="both", expand=True)

        for r in range(GRID_SIZE):
            row_buttons = []
            for c in range(GRID_SIZE):
                b = tk.Button(
                    grid_frame,
                    text="",
                    width=10,
                    height=4,
                    bg="#f6fff1",
                    relief="groove",
                    command=lambda rr=r, cc=c: self.on_cell_click(rr, cc),
                )
                b.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                row_buttons.append(b)
            self.cell_buttons.append(row_buttons)

        for i in range(GRID_SIZE):
            grid_frame.grid_rowconfigure(i, weight=1)
            grid_frame.grid_columnconfigure(i, weight=1)

        bottom = tk.Frame(left, bg="#dcefd1")
        bottom.pack(fill="x", pady=6)
        tk.Label(bottom, textvariable=self.selected_var, bg="#dcefd1", font=("Consolas", 11)).pack(anchor="w")

        right = tk.Frame(body, bg="#edf7e6", width=360)
        right.pack(side="right", fill="y", padx=(8, 0))

        tk.Label(right, text="Bitacora", bg="#edf7e6", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=8, pady=6)

        self.log_text = tk.Text(right, height=34, width=44, font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.insert("end", "\n".join(self.state.log_entries[-80:]) + "\n")
        self.log_text.config(state="disabled")

    def _load_images(self) -> None:
        if not Image or not ImageTk:
            return
        for key, definition in PRODUCTS.items():
            path = IMAGES_DIR / definition.image_file
            if path.exists():
                try:
                    img = Image.open(path).resize((62, 62))
                    self.photo_cache[key] = ImageTk.PhotoImage(img)
                except Exception:
                    pass

        dead_path = IMAGES_DIR / "muerto.png"
        if dead_path.exists():
            try:
                img = Image.open(dead_path).resize((62, 62))
                self.photo_cache["__dead__"] = ImageTk.PhotoImage(img)
            except Exception:
                pass

    def add_log_line(self, line: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def set_pending_purchase(self, key: str) -> None:
        self.pending_shop_item = key
        self.pending_inventory_item = None
        self.pending_var.set(f"Pendiente por colocar (tienda): {PRODUCTS[key].name}")

    def set_pending_inventory_item(self, key: str) -> None:
        self.pending_inventory_item = key
        self.pending_shop_item = None
        self.pending_var.set(f"Pendiente por colocar (inventario): {PRODUCTS[key].name}")

    def clear_pending(self) -> None:
        self.pending_shop_item = None
        self.pending_inventory_item = None
        self.pending_var.set("Sin producto pendiente")

    def open_shop(self) -> None:
        ShopWindow(self)

    def open_inventory(self) -> None:
        InventoryWindow(self)

    def open_stats(self) -> None:
        StatsWindow(self, self.state)

    def save_now(self) -> None:
        save_game(self.state)
        self.add_log_line(f"[{time.strftime('%H:%M:%S')}] Partida guardada en JSON.")

    def toggle_auto_harvest(self) -> None:
        self.state.auto_harvest = bool(self.auto_var.get())
        self.engine.log(
            "Auto recoleccion activada."
            if self.state.auto_harvest
            else "Auto recoleccion desactivada."
        )
        if self.state.auto_harvest:
            harvested = self.engine.collect_ready_items()
            if harvested > 0:
                self.engine.log(f"Auto recoleccion aplicada a {harvested} producciones pendientes.")
                self.refresh_ui()

    def on_cell_click(self, row: int, col: int) -> None:
        self.selected_cell = (row, col)
        terrain_index = self.state.current_terrain_index

        if self.pending_shop_item:
            key = self.pending_shop_item
            animal_name = ""
            if PRODUCTS[key].category == "animal":
                animal_name = simpledialog.askstring(
                    "Nombre del animal",
                    "Escribe un nombre para este animal:",
                    parent=self,
                ) or ""
            ok, msg = self.engine.place_item(
                key,
                terrain_index,
                row,
                col,
                animal_name=animal_name,
                from_inventory=True,
            )
            if ok:
                self.clear_pending()
            messagebox.showinfo("Colocar", msg, parent=self)
            self.refresh_ui()
            return

        if self.pending_inventory_item:
            key = self.pending_inventory_item
            animal_name = ""
            if PRODUCTS[key].category == "animal":
                animal_name = simpledialog.askstring(
                    "Nombre del animal",
                    "Nombre para el animal que sale del inventario:",
                    parent=self,
                ) or ""
            ok, msg = self.engine.place_item(
                key,
                terrain_index,
                row,
                col,
                animal_name=animal_name,
                from_inventory=True,
            )
            if ok:
                self.clear_pending()
            messagebox.showinfo("Colocar", msg, parent=self)
            self.refresh_ui()
            return

        self.refresh_selected_info()

    def refresh_selected_info(self) -> None:
        if not self.selected_cell:
            self.selected_var.set("Selecciona una celda")
            return

        r, c = self.selected_cell
        terrain_idx = self.state.current_terrain_index
        item = self.engine.get_item_at(terrain_idx, r, c)
        if not item:
            self.selected_var.set(f"Terreno {terrain_idx + 1} - Celda ({r + 1},{c + 1}) vacia")
            return

        definition = PRODUCTS[item.product_key]
        animal = f" Nombre: {item.animal_name}." if item.animal_name else ""
        cond = f" Condicion: {item.condition} ({item.condition_remaining}s)." if item.condition else ""
        life = " Muerto." if item.dead else ""

        if definition.is_productive and not item.ready:
            timing = f" Tiempo restante: {format_seconds(item.remaining_seconds)}."
        elif item.ready:
            timing = f" Listo para recolectar. Se dana en {max(0, 90 - item.ready_wait_seconds)}s."
        else:
            timing = ""

        self.selected_var.set(
            f"Terreno {terrain_idx + 1} - Celda ({r + 1},{c + 1}): {definition.name}.{animal}{timing}{cond}{life}"
        )

    def remove_selected_to_inventory(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Inventario", "Selecciona una celda.", parent=self)
            return
        r, c = self.selected_cell
        ok, msg = self.engine.remove_to_inventory(self.state.current_terrain_index, r, c)
        messagebox.showinfo("Inventario", msg, parent=self)
        self.refresh_ui()

    def clear_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Limpiar", "Selecciona una celda.", parent=self)
            return
        r, c = self.selected_cell
        ok, msg = self.engine.clear_cell(self.state.current_terrain_index, r, c)
        messagebox.showinfo("Limpiar", msg, parent=self)
        self.refresh_ui()

    def harvest_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Cosechar", "Selecciona una celda.", parent=self)
            return
        r, c = self.selected_cell
        item = self.engine.get_item_at(self.state.current_terrain_index, r, c)
        if not item:
            messagebox.showwarning("Cosechar", "No hay elemento en la celda.", parent=self)
            return
        ok, msg = self.engine.harvest(item, automatic=False)
        messagebox.showinfo("Cosechar", msg, parent=self)
        self.refresh_ui()

    def cure_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Curar", "Selecciona una celda.", parent=self)
            return
        r, c = self.selected_cell
        ok, msg = self.engine.cure_item(self.state.current_terrain_index, r, c)
        messagebox.showinfo("Curar", msg, parent=self)
        self.refresh_ui()

    def buy_terrain(self) -> None:
        ok, msg = self.engine.buy_terrain()
        messagebox.showinfo("Terrenos", msg, parent=self)
        self.refresh_ui()

    def prev_terrain(self) -> None:
        idx = self.state.current_terrain_index - 1
        if self.engine.set_current_terrain(idx):
            self.engine.log(f"Navegaste al terreno {idx + 1}.")
            self.refresh_ui()
        else:
            messagebox.showwarning("Terrenos", "Ya estas en el primer terreno.", parent=self)

    def next_terrain(self) -> None:
        idx = self.state.current_terrain_index + 1
        if self.engine.set_current_terrain(idx):
            self.engine.log(f"Navegaste al terreno {idx + 1}.")
            self.refresh_ui()
        else:
            messagebox.showwarning("Terrenos", "No existe un terreno siguiente.", parent=self)

    def goto_terrain_dialog(self) -> None:
        total = len(self.state.terrains)
        value = simpledialog.askinteger(
            "Ir a terreno",
            f"A cual terreno quieres ir? (1 - {total})",
            parent=self,
            minvalue=1,
            maxvalue=total,
        )
        if value is None:
            return
        idx = value - 1
        if self.engine.set_current_terrain(idx):
            self.engine.log(f"Navegaste al terreno {value}.")
            self.refresh_ui()

    def refresh_ui(self) -> None:
        ready_count = sum(1 for item in self.state.items.values() if item.ready)
        used_cells = sum(1 for _ in self.state.items.values())

        self.info_var.set(
            f"Jugador: {self.state.player_name} | Monedas: {self.state.coins} | "
            f"Terreno: {self.state.current_terrain_index + 1}/{len(self.state.terrains)} | "
            f"Elementos: {used_cells} | Listos: {ready_count} | "
            f"Tiempo juego: {format_seconds(self.state.statistics.total_play_seconds)}"
        )

        terrain = self.state.terrains[self.state.current_terrain_index]

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                btn = self.cell_buttons[r][c]
                item_id = terrain.grid[r][c]
                if not item_id:
                    btn.config(text="", image="", bg="#f6fff1", fg="#244d24")
                    continue

                item = self.state.items.get(item_id)
                if not item:
                    btn.config(text="", image="", bg="#f6fff1", fg="#244d24")
                    continue

                definition = PRODUCTS[item.product_key]
                image_key = "__dead__" if item.dead and "__dead__" in self.photo_cache else item.product_key
                has_image = image_key in self.photo_cache

                if item.dead:
                    tail = "DEAD"
                elif item.condition:
                    tail = f"{item.condition[:3].upper()}:{item.condition_remaining:02d}"
                elif item.ready:
                    tail = f"OK:{max(0, 90 - item.ready_wait_seconds):02d}"
                elif definition.is_productive:
                    tail = format_seconds(item.remaining_seconds)
                else:
                    tail = ""

                caption = definition.short
                if definition.category == "animal" and item.animal_name:
                    caption = item.animal_name[:2].upper()

                if has_image:
                    btn.config(
                        image=self.photo_cache[image_key],
                        compound="top",
                        text=tail,
                        bg="#fffadf" if item.ready else "#f6fff1",
                        fg="#243924",
                    )
                else:
                    txt = f"{caption}\n{tail}" if tail else caption
                    btn.config(text=txt, image="", bg="#fffadf" if item.ready else "#f6fff1", fg="#243924")

        self.refresh_selected_info()

    def _ui_loop(self) -> None:
        # Contador general de juego. Corre solo cuando app esta activa.
        self.state.statistics.total_play_seconds += 1
        self.refresh_ui()

        # Guardado automatico cada 30 segundos.
        if self.state.statistics.total_play_seconds % 30 == 0:
            save_game(self.state)

        if self.engine.running:
            self.after(1000, self._ui_loop)

    def on_close(self) -> None:
        save_game(self.state)
        self.engine.stop_all_threads()
        self.destroy()
        self.app.on_game_closed()


class FarmApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SiembraTEC")
        # Proporcion 1920x1005 para que el fondo no se vea estirado.
        width = 1150
        height = 660
        self.root.geometry(f"{width}x{height}+0+0")
        self.root.configure(bg="#06a10d")
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.menu_view = MenuView(root, self)
        self.game_view: Optional[GameView] = None

    def new_game(self) -> None:
        if SAVE_FILE.exists():
            confirm = messagebox.askyesno(
                "Confirmacion muy importante",
                "Vas a iniciar una partida nueva y eliminar la anterior.\n"
                "Esta accion borra TODO el progreso guardado.\n\n"
                "Estas completamente seguro?",
                parent=self.root,
            )
            if not confirm:
                return
            delete_save()

        name = simpledialog.askstring("Nuevo juego", "Nombre del jugador:", parent=self.root)
        if not name:
            name = "Jugador"

        state = GameState.new(name.strip())
        save_game(state)
        self.start_game(state)

    def continue_game(self) -> None:
        state = load_game()
        if not state:
            messagebox.showwarning("Continuar", "No hay partida guardada.", parent=self.root)
            return
        self.start_game(state)

    def show_menu_stats(self) -> None:
        state = load_game()
        if not state:
            messagebox.showwarning("Estadisticas", "No hay partida guardada.", parent=self.root)
            return
        StatsWindow(self.root, state)

    def start_game(self, state: GameState) -> None:
        if self.game_view is not None:
            try:
                self.game_view.on_close()
            except Exception:
                pass
        self.menu_view.pack_forget()
        self.game_view = GameView(self, state)

    def on_game_closed(self) -> None:
        self.game_view = None
        self.menu_view = MenuView(self.root, self)

    def close_app(self) -> None:
        if self.game_view is not None:
            self.game_view.on_close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = FarmApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

