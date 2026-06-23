# =============================================================================
# SiembraTEC - Farmville
# Archivo único principal: contiene todo el código del juego en un solo lugar.
# =============================================================================

# --- IMPORTACIONES -----------------------------------------------------------
# Cada librería tiene un propósito específico; se explica a continuación.

import json          # Leer y escribir archivos JSON → usado para guardar y cargar la partida
import random        # Generar números aleatorios → para simular plagas/enfermedades con probabilidad
import threading     # Crear y manejar hilos de ejecución → cada item productivo corre en su propio hilo
import time          # Funciones relacionadas con tiempo → para el temporizador de producción y timestamps
import uuid          # Generar identificadores únicos universales (UUID) → cada item colocado recibe un ID único

from dataclasses import dataclass, field  # Decoradores para crear clases de datos de forma concisa
from pathlib import Path                  # Manejo de rutas de archivos de manera multiplataforma
from typing import Callable, Dict, List, Optional, Tuple  # Anotaciones de tipo para mayor claridad

import tkinter as tk                      # Librería estándar de Python para interfaces gráficas (GUI)
from tkinter import messagebox, simpledialog, ttk  # Componentes adicionales de Tkinter:
                                          #   messagebox → cuadros de diálogo (información, error, pregunta)
                                          #   simpledialog → pedir texto o números al usuario
                                          #   ttk → widgets con estilos modernos (Treeview, Style, etc.)

try:
    # Pillow (PIL) → librería para abrir, redimensionar y mostrar imágenes
    # Se intenta importar; si no está instalada, el juego funciona igual sin imágenes
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


# =============================================================================
# SECCIÓN 1: CONSTANTES Y CONFIGURACIÓN GLOBAL
# =============================================================================

GRID_SIZE = 10           # Tamaño de la cuadrícula del terreno (10x10 celdas)
INITIAL_COINS = 100      # Monedas con las que empieza el jugador
NEW_TERRAIN_COST = 20000 # Costo para comprar un terreno adicional
SAVE_FILE = Path("data/savegame.json")  # Ruta del archivo de guardado
IMAGES_DIR = Path("assets/images")     # Carpeta de imágenes del juego

# Lista de rutas candidatas para la imagen de fondo del menú
MENU_BG_FILES = [
    Path("assets/images/menu.jpg"),
    Path("assets/images/menu.png"),
    Path("assets/images/menu_background.png"),
]


# =============================================================================
# SECCIÓN 2: CATÁLOGO DE PRODUCTOS
# Todos los productos que se pueden comprar en la tienda, con sus atributos.
# =============================================================================

# ★ PARA ESTUDIAR: @dataclass genera automáticamente __init__, __repr__ y __eq__
# evitando código repetitivo al definir clases de datos.
@dataclass
class ProductDefinition:
    """Define las características estáticas (fijas) de cada tipo de producto."""
    key: str              # Identificador interno único del producto
    name: str             # Nombre visible para el jugador
    category: str         # Categoría: "plantacion", "animal", "arbol", "decorativo"
    price: int            # Costo en monedas para comprarlo
    production_time: int = 0    # Segundos que tarda en producir (0 = no produce)
    gain: int = 0               # Monedas que genera al cosechar
    one_shot: bool = False      # True = se elimina tras la primera cosecha (plantas)
    image_file: str = ""        # Nombre del archivo de imagen en assets/images/
    short: str = ""             # Abreviatura de 2 letras para mostrar en celda sin imagen

    @property
    def is_productive(self) -> bool:
        """Retorna True si el producto genera ganancias (tiene tiempo y ganancia > 0)."""
        return self.production_time > 0 and self.gain > 0


# Diccionario con todos los productos disponibles en la tienda
PRODUCTS: Dict[str, "ProductDefinition"] = {
    # --- Plantaciones (one_shot=True: se cosechan y desaparecen) ---
    "trigo":     ProductDefinition("trigo",     "Trigo",     "plantacion",  20,   30,   35, True,  "trigo.png",     "TR"),
    "maiz":      ProductDefinition("maiz",      "Maiz",      "plantacion",  35,   60,   60, True,  "maiz.png",      "MZ"),
    "zanahoria": ProductDefinition("zanahoria", "Zanahoria", "plantacion",  50,   90,   90, True,  "zanahoria.png", "ZA"),
    "tomate":    ProductDefinition("tomate",    "Tomate",    "plantacion",  75,  120,  130, True,  "tomate.png",    "TO"),
    "papa":      ProductDefinition("papa",      "Papa",      "plantacion", 100,  180,  180, True,  "papa.png",      "PA"),
    # --- Animales (producen indefinidamente, reinician ciclo tras cosecha) ---
    "gallina":   ProductDefinition("gallina",   "Gallina",   "animal",     150,  120,  250, False, "gallina.png",   "GA"),
    "pato":      ProductDefinition("pato",      "Pato",      "animal",     250,  180,  400, False, "pato.png",      "PT"),
    "oveja":     ProductDefinition("oveja",     "Oveja",     "animal",     400,  300,  650, False, "oveja.png",     "OV"),
    "cerdo":     ProductDefinition("cerdo",     "Cerdo",     "animal",     700,  420, 1100, False, "cerdo.png",     "CE"),
    "vaca":      ProductDefinition("vaca",      "Vaca",      "animal",    1000,  600, 1700, False, "vaca.png",      "VA"),
    # --- Árboles frutales (producen indefinidamente) ---
    "manzano":   ProductDefinition("manzano",   "Manzano",   "arbol",      120,  180,  200, False, "manzano.png",   "MN"),
    "naranjo":   ProductDefinition("naranjo",   "Naranjo",   "arbol",      180,  240,  320, False, "naranjo.png",   "NR"),
    "limonero":  ProductDefinition("limonero",  "Limonero",  "arbol",      250,  300,  450, False, "limonero.png",  "LM"),
    "cacaotero": ProductDefinition("cacaotero", "Cacaotero", "arbol",      500,  480,  850, False, "cacaotero.png", "CC"),
    "cafetal":   ProductDefinition("cafetal",   "Cafetal",   "arbol",      800,  600, 1400, False, "cafetal.png",   "CF"),
    # --- Decorativos (no producen, solo embellecen) ---
    "cerca":     ProductDefinition("cerca",     "Cerca",     "decorativo",  50,    0,    0, False, "cerca.png",     "CR"),
    "banco":     ProductDefinition("banco",     "Banco",     "decorativo", 100,    0,    0, False, "banco.png",     "BC"),
    "fuente":    ProductDefinition("fuente",    "Fuente",    "decorativo", 250,    0,    0, False, "fuente.png",    "FT"),
    "estatua":   ProductDefinition("estatua",   "Estatua",   "decorativo", 500,    0,    0, False, "estatua.png",   "ES"),
    "molino_decorativo": ProductDefinition("molino_decorativo", "Molino Decorativo", "decorativo", 1000, 0, 0, False, "molino_decorativo.png", "MD"),
}

# Consumibles: no se colocan en celdas, se aplican directamente a items enfermos
CONSUMABLES = {
    "pesticida": {"name": "Pesticida", "price": 40,  "image": "pesticida.png"},  # Para plantas y árboles
    "medicina":  {"name": "Medicina",  "price": 60, "image": "medicina.png"},   # Para animales
}


# =============================================================================
# SECCIÓN 3: JERARQUÍA DE CLASES (HERENCIA Y POLIMORFISMO)
# ★ PARA ESTUDIAR: patrón de diseño Herencia + Polimorfismo + Factory Method
# =============================================================================

class FarmEntity:
    """
    Clase BASE de cualquier elemento que puede colocarse en la granja.
    Define la interfaz común que todas las subclases deben respetar.
    El método required_cure() es el punto de POLIMORFISMO: cada subclase
    responde diferente a la misma pregunta "¿qué cura necesitas?".
    """
    def __init__(self, definition: "ProductDefinition") -> None:
        self.definition = definition  # Guarda la definición del producto

    def required_cure(self) -> Optional[str]:
        """Retorna el nombre del consumible necesario para curar este elemento.
        None = no necesita cura (decorativos)."""
        return None

    def is_one_shot(self) -> bool:
        """True si el elemento desaparece tras la primera cosecha."""
        return self.definition.one_shot


class PlantEntity(FarmEntity):
    """Subclase para PLANTACIONES. Hereda de FarmEntity y sobreescribe required_cure."""
    def required_cure(self) -> Optional[str]:
        return "pesticida"   # Las plantas necesitan pesticida cuando tienen plaga


class TreeEntity(FarmEntity):
    """Subclase para ÁRBOLES. También usan pesticida (misma categoría de problema)."""
    def required_cure(self) -> Optional[str]:
        return "pesticida"


class AnimalEntity(FarmEntity):
    """Subclase para ANIMALES. Necesitan medicina cuando se enferman."""
    def required_cure(self) -> Optional[str]:
        return "medicina"


class DecorativeEntity(FarmEntity):
    """Subclase para DECORATIVOS. No sobreescribe required_cure → retorna None."""
    pass


# ★ PARA ESTUDIAR: patrón FACTORY METHOD
# En lugar de hacer "if" repartidos por el código, centralizamos la creación
# de objetos aquí. El motor solo llama create_entity() sin saber qué subclase usará.
def create_entity(definition: "ProductDefinition") -> FarmEntity:
    """Fábrica: elige la subclase correcta según la categoría del producto."""
    if definition.category == "plantacion":
        return PlantEntity(definition)
    if definition.category == "arbol":
        return TreeEntity(definition)
    if definition.category == "animal":
        return AnimalEntity(definition)
    return DecorativeEntity(definition)   # Fallback para decorativos


# =============================================================================
# SECCIÓN 4: MODELOS DE DATOS (DATACLASSES)
# Representan el estado del juego en memoria y saben serializarse a JSON.
# =============================================================================

@dataclass
class PlacedItem:
    """
    Representa UN elemento específico que fue colocado en una celda del terreno.
    Distinto de ProductDefinition (que es el "tipo"); este es la "instancia".
    """
    item_id: str             # UUID único generado al colocar
    product_key: str         # Referencia al tipo en PRODUCTS
    terrain_index: int       # En cuál terreno está
    row: int                 # Fila dentro de la cuadrícula
    col: int                 # Columna dentro de la cuadrícula
    animal_name: str = ""            # Nombre personalizado (solo animales)
    remaining_seconds: int = 0       # Segundos restantes para terminar producción
    ready: bool = False              # True cuando terminó de producir
    ready_wait_seconds: int = 0      # Segundos esperando cosecha (si no se cosecha, se pierde)
    condition: Optional[str] = None  # "plaga" o "enfermedad" si está afectado
    condition_remaining: int = 0     # Segundos restantes para curar antes de morir
    dead: bool = False               # True si murió por no curarse a tiempo

    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario para guardarlo en JSON."""
        return {
            "item_id": self.item_id, "product_key": self.product_key,
            "terrain_index": self.terrain_index, "row": self.row, "col": self.col,
            "animal_name": self.animal_name, "remaining_seconds": self.remaining_seconds,
            "ready": self.ready, "ready_wait_seconds": self.ready_wait_seconds,
            "condition": self.condition, "condition_remaining": self.condition_remaining,
            "dead": self.dead,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlacedItem":
        """Reconstruye un PlacedItem desde un diccionario leído del JSON."""
        return cls(
            item_id=data["item_id"], product_key=data["product_key"],
            terrain_index=data["terrain_index"], row=data["row"], col=data["col"],
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
    """Representa un terreno (parcela) de 10x10 celdas."""
    index: int  # Número de terreno (0, 1, 2...)
    # grid es una lista de listas: grid[fila][columna] = item_id o None si vacía
    # ★ field(default_factory=...) evita que todos los terrenos compartan la misma lista
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
    """Acumula métricas de la sesión del jugador."""
    total_generated: int = 0               # Total de monedas ganadas por producción
    total_products_bought: int = 0         # Cantidad total de compras realizadas
    products_bought_by_type: Dict[str, int] = field(default_factory=dict)  # Compras por tipo
    products_gain_by_type: Dict[str, int] = field(default_factory=dict)    # Ganancias por tipo
    total_play_seconds: int = 0            # Segundos totales jugados

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
    """
    Estado COMPLETO del juego en un momento dado.
    Es el objeto raíz que se serializa al guardar y se reconstruye al cargar.
    Contiene referencias a todos los demás modelos.
    """
    player_name: str
    coins: int
    terrains: List[Terrain]
    current_terrain_index: int
    items: Dict[str, PlacedItem]   # Mapa de item_id → PlacedItem
    inventory: Dict[str, int]      # Mapa de product_key → cantidad disponible
    auto_harvest: bool             # Si True, recolecta automáticamente al terminar
    statistics: Statistics
    log_entries: List[str]         # Bitácora de eventos del juego

    @classmethod
    def new(cls, player_name: str) -> "GameState":
        """Crea un estado inicial para una partida nueva."""
        return cls(
            player_name=player_name,
            coins=INITIAL_COINS,
            terrains=[Terrain(index=0)],          # Empieza con un solo terreno
            current_terrain_index=0,
            items={},
            inventory={"pesticida": 0, "medicina": 0},
            auto_harvest=False,
            statistics=Statistics(),
            log_entries=["Partida nueva creada."],
        )

    def to_dict(self) -> dict:
        return {
            "player_name": self.player_name, "coins": self.coins,
            "terrains": [t.to_dict() for t in self.terrains],
            "current_terrain_index": self.current_terrain_index,
            "items": {k: v.to_dict() for k, v in self.items.items()},
            "inventory": self.inventory, "auto_harvest": self.auto_harvest,
            "statistics": self.statistics.to_dict(),
            "log_entries": self.log_entries[-200:],   # Limita a 200 entradas
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        return cls(
            player_name=data["player_name"], coins=data["coins"],
            terrains=[Terrain.from_dict(t) for t in data["terrains"]],
            current_terrain_index=data.get("current_terrain_index", 0),
            items={k: PlacedItem.from_dict(v) for k, v in data.get("items", {}).items()},
            inventory=data.get("inventory", {"pesticida": 0, "medicina": 0}),
            auto_harvest=data.get("auto_harvest", False),
            statistics=Statistics.from_dict(data.get("statistics", {})),
            log_entries=data.get("log_entries", []),
        )


def format_seconds(seconds: int) -> str:
    """Convierte segundos enteros al formato 'MM:SS' para mostrar en la UI."""
    seconds = max(0, int(seconds))
    mm = seconds // 60
    ss = seconds % 60
    return f"{mm:02d}:{ss:02d}"


# =============================================================================
# SECCIÓN 5: PERSISTENCIA (GUARDAR / CARGAR / BORRAR PARTIDA)
# =============================================================================

def save_game(state: GameState) -> None:
    """Serializa el estado completo a JSON y lo escribe en disco."""
    SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)  # Crea carpeta data/ si no existe
    with SAVE_FILE.open("w", encoding="utf-8") as fp:
        json.dump(state.to_dict(), fp, ensure_ascii=False, indent=2)


def load_game() -> Optional[GameState]:
    """Carga la partida desde JSON. Retorna None si no hay archivo guardado."""
    if not SAVE_FILE.exists():
        return None
    with SAVE_FILE.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return GameState.from_dict(data)


def delete_save() -> None:
    """Elimina el archivo de guardado permanentemente (para nueva partida)."""
    if SAVE_FILE.exists():
        SAVE_FILE.unlink()


# =============================================================================
# SECCIÓN 6: HILO DE PRODUCCIÓN
# ★ PARA ESTUDIAR: Concurrencia con threading.Thread
# =============================================================================

class ProductionThread(threading.Thread):
    """
    Hilo daemon que avanza el tiempo de producción de UN item específico.
    Un hilo = un item productivo activo. Corren en paralelo al hilo principal (UI).

    IMPORTANTE: 'daemon=True' significa que el hilo muere automáticamente
    cuando el programa principal termina, sin necesidad de Join explícito.
    """

    def __init__(self, engine: "GameEngine", item_id: str) -> None:
        super().__init__(daemon=True)   # Hereda de threading.Thread, marca como daemon
        self.engine = engine            # Referencia al motor del juego
        self.item_id = item_id          # ID del item que este hilo controla
        self.stop_event = threading.Event()  # Evento para señalar parada segura

    def run(self) -> None:
        """Bucle principal del hilo: espera 1 segundo y llama tick_item()."""
        # ★ PARA ESTUDIAR: stop_event.is_set() permite terminar el hilo de forma
        # "cooperativa" (el hilo mismo decide cuándo parar) en lugar de forzar.
        while not self.stop_event.is_set() and self.engine.running:
            time.sleep(1)   # Pausa 1 segundo (el "tick" del reloj del juego)
            if self.stop_event.is_set() or not self.engine.running:
                break
            self.engine.tick_item(self.item_id)   # Avanza el estado del item

    def stop(self) -> None:
        """Señala al hilo que debe terminar en su próximo ciclo."""
        self.stop_event.set()


# =============================================================================
# SECCIÓN 7: MOTOR DEL JUEGO (GameEngine)
# ★ PARA ESTUDIAR: Separación de lógica de negocio de la interfaz gráfica
# =============================================================================

class GameEngine:
    """
    Núcleo central del juego. Contiene TODAS las reglas y operaciones.
    La UI solo llama métodos de GameEngine; no implementa lógica por sí misma.

    Ventajas de esta separación:
    - Se puede probar la lógica sin levantar ventanas
    - La UI puede cambiar sin tocar las reglas del juego
    - Código más mantenible y claro

    ★ PARA ESTUDIAR: threading.RLock() es un "Reentrant Lock": el mismo hilo
    puede adquirirlo varias veces sin bloquearse a sí mismo (a diferencia de Lock).
    Esto evita condiciones de carrera cuando múltiples hilos modifican el estado.
    """

    def __init__(self, state: GameState, logger: Optional[Callable[[str], None]] = None) -> None:
        self.state = state              # El estado completo del juego
        self.running = True             # Flag para detener todos los hilos
        self.lock = threading.RLock()   # Candado reentrante para acceso seguro al estado
        self.threads: Dict[str, "ProductionThread"] = {}  # Mapa item_id → hilo
        self.logger = logger            # Función opcional para mostrar logs en la UI

    def log(self, text: str) -> None:
        """Registra un evento en la bitácora con marca de tiempo."""
        with self.lock:  # Bloquea el estado para escritura segura desde cualquier hilo
            line = f"[{time.strftime('%H:%M:%S')}] {text}"
            self.state.log_entries.append(line)
            self.state.log_entries = self.state.log_entries[-200:]  # Mantiene máximo 200 entradas
        if self.logger:
            self.logger(line)   # Reenvía a la UI si hay función registrada

    def is_valid_position(self, row: int, col: int) -> bool:
        """Verifica que la posición está dentro de los límites de la cuadrícula."""
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def get_item_at(self, terrain_index: int, row: int, col: int) -> Optional[PlacedItem]:
        """Devuelve el PlacedItem en una celda, o None si está vacía."""
        terrain = self.state.terrains[terrain_index]
        item_id = terrain.grid[row][col]   # La cuadrícula almacena item_ids (no objetos directos)
        if not item_id:
            return None
        return self.state.items.get(item_id)

    def spend(self, amount: int) -> bool:
        """Descuenta monedas si hay suficientes. Retorna False si no alcanza."""
        if self.state.coins < amount:
            return False
        self.state.coins -= amount
        return True

    def buy_product(self, product_key: str) -> Tuple[bool, str]:
        """Proceso de compra: valida monedas, descuenta, agrega al inventario."""
        if product_key in CONSUMABLES:
            # Compra de consumibles (pesticida / medicina)
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

        # Compra de producto de la tienda
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
        self, product_key: str, terrain_index: int, row: int, col: int,
        animal_name: str = "", from_inventory: bool = False,
    ) -> Tuple[bool, str]:
        """
        ★ PARA ESTUDIAR: validación por etapas (Early Return Pattern).
        Cada condición inválida retorna inmediatamente con error,
        evitando estados inconsistentes si algo falla a mitad del proceso.
        """
        if not self.is_valid_position(row, col):
            return False, "Posicion invalida."
        terrain = self.state.terrains[terrain_index]
        if terrain.grid[row][col] is not None:
            return False, "La celda no esta libre."
        if from_inventory:
            if self.state.inventory.get(product_key, 0) <= 0:
                return False, "No hay unidades en inventario."
            self.state.inventory[product_key] -= 1   # Descuenta del inventario al colocar

        definition = PRODUCTS[product_key]
        item_id = str(uuid.uuid4())   # UUID único: garantiza que dos items nunca colisionan
        item = PlacedItem(
            item_id=item_id, product_key=product_key,
            terrain_index=terrain_index, row=row, col=col,
            animal_name=animal_name.strip(),
            remaining_seconds=definition.production_time,
        )
        self.state.items[item_id] = item    # Registra en el mapa global de items
        terrain.grid[row][col] = item_id    # Marca la celda con el ID

        if definition.is_productive:
            self.start_thread(item_id)      # Lanza el hilo de producción

        friendly = definition.name
        if definition.category == "animal" and item.animal_name:
            friendly = f"{friendly} ({item.animal_name})"
        self.log(f"Colocado: {friendly} en terreno {terrain_index + 1}, fila {row + 1}, columna {col + 1}.")
        return True, "Producto colocado correctamente."

    def remove_to_inventory(self, terrain_index: int, row: int, col: int) -> Tuple[bool, str]:
        """Retira un item del terreno y lo devuelve al inventario."""
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
        """Elimina un item del terreno sin devolver al inventario (limpieza definitiva)."""
        with self.lock:
            item = self.get_item_at(terrain_index, row, col)
            if not item:
                return False, "No hay nada para limpiar."
            self._remove_item(item)
            self.log("Celda limpiada manualmente.")
            return True, "Celda limpiada."

    def _remove_item(self, item: PlacedItem) -> None:
        """Método privado: quita el item de la cuadrícula, del mapa global y detiene su hilo."""
        terrain = self.state.terrains[item.terrain_index]
        terrain.grid[item.row][item.col] = None   # Libera la celda
        self.state.items.pop(item.item_id, None)  # Elimina del mapa global
        self.stop_thread(item.item_id)            # Detiene el hilo asociado

    def buy_terrain(self) -> Tuple[bool, str]:
        """Compra un terreno adicional si hay monedas suficientes."""
        with self.lock:
            if not self.spend(NEW_TERRAIN_COST):
                return False, "No tienes monedas suficientes para comprar terreno."
            idx = len(self.state.terrains)
            self.state.terrains.append(Terrain(index=idx))
            self.log(f"Compraste el terreno {idx + 1}.")
            return True, f"Terreno {idx + 1} comprado con exito."

    def set_current_terrain(self, idx: int) -> bool:
        """Cambia el terreno activo. Retorna False si el índice no existe."""
        if 0 <= idx < len(self.state.terrains):
            self.state.current_terrain_index = idx
            return True
        return False

    def start_thread(self, item_id: str) -> None:
        """Lanza un ProductionThread para el item dado, si no tiene uno activo."""
        item = self.state.items.get(item_id)
        if not item:
            return
        definition = PRODUCTS[item.product_key]
        if not definition.is_productive:
            return
        if item_id in self.threads and self.threads[item_id].is_alive():
            return   # Ya tiene un hilo corriendo, no duplicar
        th = ProductionThread(self, item_id)
        self.threads[item_id] = th
        th.start()

    def start_all_threads(self) -> None:
        """Al cargar una partida, reactiva los hilos de todos los items existentes."""
        for item_id in list(self.state.items.keys()):
            self.start_thread(item_id)

    def stop_thread(self, item_id: str) -> None:
        """Detiene y elimina el hilo de un item específico."""
        th = self.threads.pop(item_id, None)
        if th:
            th.stop()

    def stop_all_threads(self) -> None:
        """Detiene todos los hilos al cerrar el juego. Importante para cierre limpio."""
        self.running = False             # Señal global: ningún hilo debe continuar
        for th in list(self.threads.values()):
            th.stop()
        self.threads.clear()

    def cure_item(self, terrain_index: int, row: int, col: int) -> Tuple[bool, str]:
        """
        Aplica el consumible correcto a un item con plaga o enfermedad.
        Usa polimorfismo: create_entity() decide qué subclase verificar el tipo de cura.
        """
        with self.lock:
            item = self.get_item_at(terrain_index, row, col)
            if not item:
                return False, "No hay elemento en la celda."
            definition = PRODUCTS[item.product_key]
            entity = create_entity(definition)   # ★ POLIMORFISMO: obtiene subclase real
            needed = entity.required_cure()      # Pregunta polimórfica: cada clase responde distinto
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
        """
        ★ PARA ESTUDIAR: punto único de ganancia y reinicio del ciclo productivo.
        Tanto la cosecha manual (botón de UI) como la automática pasan por aquí,
        garantizando que las reglas sean siempre las mismas.
        """
        with self.lock:
            if item.item_id not in self.state.items:
                return False, "Elemento ya no existe."
            if item.dead:
                return False, "Elemento muerto."
            if not item.ready:
                return False, "Aun no esta listo."

            definition = PRODUCTS[item.product_key]
            # Acredita monedas y registra en estadísticas
            self.state.coins += definition.gain
            self.state.statistics.total_generated += definition.gain
            self.state.statistics.products_gain_by_type[item.product_key] = (
                self.state.statistics.products_gain_by_type.get(item.product_key, 0) + definition.gain
            )

            item.ready = False
            item.ready_wait_seconds = 0

            if definition.one_shot:
                # Plantación: se cosecha y desaparece de la celda
                self.log(
                    f"Cosecha {'automatica' if automatic else 'manual'} de {definition.name}: +{definition.gain} monedas."
                )
                self._remove_item(item)
                return True, "Cosechado. Como es plantacion de un solo uso, la celda queda libre."

            # Animal / árbol: reinicia el ciclo de producción
            item.remaining_seconds = definition.production_time
            self.log(
                f"Recoleccion {'automatica' if automatic else 'manual'} de {definition.name}: +{definition.gain} monedas."
            )
            return True, "Produccion recolectada."

    def collect_ready_items(self) -> int:
        """Recolecta automáticamente todos los items listos. Retorna cuántos se cosecharon."""
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
        """
        ★ PARA ESTUDIAR: MÁQUINA DE ESTADOS del ciclo productivo.
        Se llama cada segundo desde ProductionThread. Implementa la lógica de:
          1. Si tiene condición (plaga/enfermedad) → reducir contador → si llega a 0, muere
          2. Si no tiene condición → probabilidad de 0.3% de contraer una
          3. Si está produciendo → reducir remaining_seconds → marcar ready cuando llega a 0
          4. Si está listo y auto_harvest → cosechar automáticamente
          5. Si está listo sin auto_harvest → dar 90s de gracia → perder si no se cosecha
        """
        with self.lock:
            item = self.state.items.get(item_id)
            if not item or item.dead:
                return

            definition = PRODUCTS[item.product_key]
            entity = create_entity(definition)

            # ESTADO: tiene plaga o enfermedad → reducir tiempo de cura
            if item.condition:
                item.condition_remaining -= 1
                if item.condition_remaining <= 0:
                    item.dead = True
                    self.log(f"{definition.name} murio por no aplicar cura a tiempo.")
                return

            # ESTADO: produciendo → 0.3% de probabilidad de contraer condición
            if definition.is_productive and not item.ready and random.random() < 0.0015:
                cure = entity.required_cure()
                if cure:
                    item.condition = "plaga" if cure == "pesticida" else "enfermedad"
                    item.condition_remaining = 90
                    self.log(f"{definition.name} tiene {item.condition}. Aplica {cure} en 90s o morira.")
                    return

            # ESTADO: produciendo normalmente → avanzar temporizador
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

            # ESTADO: listo + auto recolección → cosechar inmediatamente
            if item.ready and self.state.auto_harvest:
                self.harvest(item, automatic=True)
                return

            # ESTADO: listo sin auto recolección → contar gracia de 90s
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


# =============================================================================
# SECCIÓN 8: INTERFAZ GRÁFICA - VISTAS Y VENTANAS
# ★ Tkinter: todo widget vive en el hilo principal; los hilos solo modifican estado.
# =============================================================================

class MenuView(tk.Frame):
    """
    Pantalla de inicio del juego (menú principal).
    Hereda de tk.Frame: es un contenedor de widgets Tkinter.
    Muestra imagen de fondo, logo y botones de acción.
    """

    def __init__(self, master: tk.Tk, app: "FarmApp") -> None:
        super().__init__(master, bg="#06a10d")
        self.app = app                  # Referencia a la aplicación principal
        self.bg_label = None            # Label que muestra la imagen de fondo
        self.bg_photo = None            # Objeto PhotoImage (debe mantenerse en memoria)
        self.bg_source_image = None     # Imagen PIL original para redimensionar
        self.logo_img = None            # Imagen del logo
        self.panel = None               # Panel blanco con los botones
        self._build()

    def _refresh_background(self) -> None:
        """Redimensiona la imagen de fondo al tamaño actual de la ventana (Pillow requerido)."""
        if not (self.bg_label and self.bg_source_image and Image and ImageTk):
            return
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        resized = self.bg_source_image.resize((w, h))
        self.bg_photo = ImageTk.PhotoImage(resized)
        self.bg_label.configure(image=self.bg_photo)

    def _on_resize(self, _event: tk.Event) -> None:
        """Callback que Tkinter llama cada vez que la ventana cambia de tamaño."""
        self._refresh_background()
        self._position_panel()

    def _position_panel(self) -> None:
        """Centra verticalmente el panel de botones según la altura disponible."""
        if not self.panel:
            return
        available_h = max(self.winfo_height(), 1)
        panel_h = min(max(available_h - 40, 520), 640)
        self.panel.place_configure(x=18, rely=0.5, anchor="w", width=470, height=panel_h)

    def _build(self) -> None:
        """Construye todos los widgets del menú."""
        self.pack(fill="both", expand=True)

        menu_bg = next((p for p in MENU_BG_FILES if p.exists()), None)
        if menu_bg:
            try:
                if Image and ImageTk:
                    self.bg_source_image = Image.open(menu_bg)
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
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img.thumbnail((330, 190), resample)
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(content, image=self.logo_img, bg="#f5f5f5").pack(pady=(0, 8))
            except Exception:
                tk.Label(content, text="JossFarm SiembraTEC", font=("Comic Sans MS", 28, "bold"),
                         fg=heading_color, bg="#f5f5f5").pack(pady=(10, 22))
        else:
            tk.Label(content, text="JossFarm SiembraTEC", font=("Comic Sans MS", 28, "bold"),
                     fg=heading_color, bg="#f5f5f5").pack(pady=(10, 22))

        tk.Label(content, text="Bienvenida a tu granja virtual",
                 font=("Comic Sans MS", 16, "bold"), fg=heading_color, bg="#f5f5f5").pack(pady=(0, 4))
        tk.Label(content, text="Administra cultivos y animales, produce recursos\ny expande tus terrenos.",
                 font=("Comic Sans MS", 10), fg=heading_color, bg="#f5f5f5", justify="center").pack(pady=(0, 10))

        style = {"font": ("Comic Sans MS", 15, "bold"), "fg": "#ffffff", "bg": "#447428",
                 "activebackground": "#365d20", "activeforeground": "#ffffff", "bd": 0,
                 "cursor": "hand2", "relief": "flat", "width": 17, "padx": 6, "pady": 6}

        tk.Button(content, text="Iniciar Partida",    command=self.app.new_game,        **style).pack(pady=3)
        tk.Button(content, text="Continuar Partida",  command=self.app.continue_game,   **style).pack(pady=3)
        tk.Button(content, text="Ver Estadisticas",   command=self.app.show_menu_stats, **style).pack(pady=3)
        tk.Button(content, text="Salir",              command=self.app.close_app,       **style).pack(pady=3)

        tk.Label(footer, text="Hecho por Joselyn Melissa Hidalgo Torres",
                 font=("Comic Sans MS", 9), fg=heading_color, bg="#f5f5f5").pack()
        tk.Label(footer, text="Version 1.0.0",
                 font=("Comic Sans MS", 9), fg=heading_color, bg="#f5f5f5").pack(pady=(2, 0))


class ShopWindow(tk.Toplevel):
    """Ventana flotante de la tienda. Muestra todos los productos y permite comprar."""

    def __init__(self, parent: "GameView") -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Tienda")
        self.geometry("860x480")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)
        self._build()

    def _build(self) -> None:
        # ttk.Treeview: tabla con columnas y filas, ideal para catálogos
        columns = ("clave", "nombre", "categoria", "precio", "tiempo", "ganancia")
        tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        tree.pack(fill="both", expand=True, padx=12, pady=12)

        headers = {"clave": "Clave", "nombre": "Producto", "categoria": "Categoria",
                   "precio": "Precio", "tiempo": "Tiempo (s)", "ganancia": "Ganancia"}
        for col, title in headers.items():
            tree.heading(col, text=title)

        for key, definition in PRODUCTS.items():
            tree.insert("", "end", values=(
                key, definition.name, definition.category,
                definition.price, definition.production_time, definition.gain))

        for key, data in CONSUMABLES.items():
            tree.insert("", "end", values=(key, data["name"], "consumible", data["price"], 0, 0))

        status = tk.Label(self, text=f"Monedas disponibles: {self.parent.engine.state.coins}", bg="#eef5e8")
        status.pack(pady=(0, 8))

        def buy_selected() -> None:
            """Función local: maneja el clic en 'Comprar'. Nótese que accede a variables del scope externo."""
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

        tk.Button(self, text="Comprar seleccionado", font=("Comic Sans MS", 12, "bold"),
                  bg="#3c9b2c", fg="white", bd=0, command=buy_selected).pack(pady=(0, 12))


class InventoryWindow(tk.Toplevel):
    """Ventana flotante que muestra el inventario y permite colocar items desde él."""

    def __init__(self, parent: "GameView") -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Inventario")
        self.geometry("520x400")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)
        self._build()

    def _build(self) -> None:
        # Título
        tk.Label(self, text="Inventario actual", font=("Comic Sans MS", 18, "bold"),
                 bg="#eef5e8").pack(pady=(10, 4))

        # Elementos inferiores fijos (se colocan primero para garantizar visibilidad)
        self.entries: List[Tuple[str, int]] = []

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
            messagebox.showinfo("Inventario",
                "Producto seleccionado. Ahora haz clic en una celda vacia para colocarlo.", parent=self)
            self.destroy()

        place_button = tk.Button(self, text="Colocar item seleccionado",
            font=("Comic Sans MS", 12, "bold"), bg="#3c9b2c", fg="white", bd=0,
            command=place_from_inventory)
        place_button.pack(side="bottom", pady=(6, 12))

        tk.Label(self, text="Para consumibles usa el boton Curar sobre una celda afectada.",
                 bg="#eef5e8").pack(side="bottom", pady=(0, 4))

        # Listbox ocupa el espacio restante
        self.listbox = tk.Listbox(self, font=("Comic Sans MS", 12), height=10)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=(4, 6))

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
            place_button.config(state="disabled", bg="#91b88a", fg="#eef5e8")


class StatsWindow(tk.Toplevel):
    """Ventana flotante de estadísticas: resumen de la sesión del jugador."""

    def __init__(self, parent: tk.Widget, state: GameState) -> None:
        super().__init__(parent)
        self.title("Estadisticas")
        self.geometry("660x520")
        self.configure(bg="#eef5e8")
        self.resizable(False, False)

        stats = state.statistics
        frame = tk.Frame(self, bg="#eef5e8")
        frame.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(frame, text="Resumen de partida", font=("Comic Sans MS", 20, "bold"), bg="#eef5e8").pack(anchor="w")
        tk.Label(frame, text=f"Jugador: {state.player_name}", bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Monedas actuales: {state.coins}", bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Terrenos comprados: {len(state.terrains)}", bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Tiempo jugado: {format_seconds(stats.total_play_seconds)}",
                 bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Monedas generadas: {stats.total_generated}", bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")
        tk.Label(frame, text=f"Total de compras realizadas: {stats.total_products_bought}",
                 bg="#eef5e8", font=("Comic Sans MS", 12)).pack(anchor="w")

        tk.Label(frame, text="Compras por producto:", font=("Comic Sans MS", 12, "bold"), bg="#eef5e8").pack(anchor="w", pady=(10, 2))
        buy_box = tk.Text(frame, height=8, width=72, font=("Comic Sans MS", 10))
        buy_box.pack(fill="x")
        if not stats.products_bought_by_type:
            buy_box.insert("end", "Sin compras registradas.\n")
        else:
            for key, count in sorted(stats.products_bought_by_type.items()):
                name = PRODUCTS[key].name if key in PRODUCTS else CONSUMABLES.get(key, {}).get("name", key)
                buy_box.insert("end", f"- {name}: {count}\n")
        buy_box.config(state="disabled")

        tk.Label(frame, text="Ganancias por producto:", font=("Comic Sans MS", 12, "bold"), bg="#eef5e8").pack(anchor="w", pady=(10, 2))
        gain_box = tk.Text(frame, height=8, width=72, font=("Comic Sans MS", 10))
        gain_box.pack(fill="x")
        if not stats.products_gain_by_type:
            gain_box.insert("end", "Sin ganancias registradas.\n")
        else:
            for key, amount in sorted(stats.products_gain_by_type.items()):
                name = PRODUCTS[key].name if key in PRODUCTS else key
                gain_box.insert("end", f"- {name}: {amount}\n")
        gain_box.config(state="disabled")


class GameView(tk.Toplevel):
    """
    Vista principal del juego: cuadrícula de terreno + barra de herramientas + bitácora.
    ★ PARA ESTUDIAR: esta clase SOLO llama métodos del motor (GameEngine).
    Nunca modifica el estado directamente, respetando la separación de responsabilidades.
    """

    def __init__(self, app: "FarmApp", state: GameState) -> None:
        super().__init__(app.root)
        self.app = app
        self.state = state
        # Crea el motor pasando la función add_log_line como callback de logging
        self.engine = GameEngine(state, logger=self.add_log_line)
        self.engine.start_all_threads()   # Reactiva hilos de items existentes

        self.title("SiembraTEC - Juego")
        self.geometry("1340x860")
        self.minsize(1180, 720)
        self.configure(bg="#dcefd1")

        # Estado de la UI (pendientes de colocación y selección activa)
        self.pending_shop_item: Optional[str] = None
        self.pending_inventory_item: Optional[str] = None
        self.selected_cell: Optional[Tuple[int, int]] = None

        # Caché de imágenes: mantiene PhotoImage en memoria para que Tkinter no las libere
        self.photo_cache: Dict[str, tk.PhotoImage] = {}
        self.cell_buttons: List[List[tk.Button]] = []   # Matriz de botones de la cuadrícula

        # StringVar: variables observables que la UI actualiza automáticamente
        self.info_var = tk.StringVar(value="")
        self.selected_var = tk.StringVar(value="Selecciona una celda")
        self.pending_var = tk.StringVar(value="Sin producto pendiente")

        # Intercepta el cierre de ventana para guardar antes de salir
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_layout()
        self._load_images()
        self.refresh_ui()
        self._ui_loop()   # Inicia el bucle de actualización cada 1 segundo

    def _build_layout(self) -> None:
        """Construye la estructura visual: barra superior, toolbar, grilla y panel de log."""
        top = tk.Frame(self, bg="#e7f4df")
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, textvariable=self.info_var,    font=("Comic Sans MS", 11, "bold"), bg="#e7f4df").pack(side="left",  padx=8)
        tk.Label(top, textvariable=self.pending_var, font=("Comic Sans MS", 11),         bg="#e7f4df").pack(side="right", padx=8)

        toolbar = tk.Frame(self, bg="#dcefd1")
        toolbar.pack(fill="x", padx=8, pady=(0, 6))
        row_top    = tk.Frame(toolbar, bg="#dcefd1")
        row_top.pack(fill="x", pady=(0, 4))
        row_bottom = tk.Frame(toolbar, bg="#dcefd1")
        row_bottom.pack(fill="x")

        def btn(parent: tk.Widget, text: str, cmd: Callable[[], None], bg: str = "#2f8f2f") -> None:
            """Función local auxiliar para crear botones de toolbar con estilo uniforme."""
            tk.Button(parent, text=text, command=cmd, font=("Comic Sans MS", 10, "bold"),
                      bg=bg, fg="white", activebackground="#256f25", bd=0,
                      padx=10, pady=6, cursor="hand2").pack(side="left", padx=3)

        btn(row_top, "Tienda",               self.open_shop)
        btn(row_top, "Inventario",           self.open_inventory)
        btn(row_top, "Guardar",              self.save_now,                          bg="#3b7ea7")
        btn(row_top, "Estadisticas",         self.open_stats,                        bg="#7a5ba6")
        btn(row_top, "Retirar -> Inventario",self.remove_selected_to_inventory,      bg="#4b8c52")
        btn(row_top, "Cosechar",             self.harvest_selected,                  bg="#996515")
        btn(row_top, "Curar",               self.cure_selected,                     bg="#995a1b")
        btn(row_top, "Limpiar celda",        self.clear_selected,                    bg="#7e3a3a")

        btn(row_bottom, "Terreno -",             self.prev_terrain,       bg="#40506b")
        btn(row_bottom, "Terreno +",             self.next_terrain,       bg="#40506b")
        btn(row_bottom, "Ir a terreno",          self.goto_terrain_dialog, bg="#40506b")
        btn(row_bottom, "Comprar terreno (20000)", self.buy_terrain,       bg="#3d5f28")

        self.auto_var = tk.BooleanVar(value=self.state.auto_harvest)
        tk.Checkbutton(row_bottom, text="Auto recoleccion", variable=self.auto_var,
                       command=self.toggle_auto_harvest, font=("Comic Sans MS", 10, "bold"),
                       bg="#dcefd1").pack(side="left", padx=14)

        body = tk.Frame(self, bg="#dcefd1")
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left = tk.Frame(body, bg="#dcefd1")
        left.pack(side="left", fill="both", expand=True)

        # Cuadrícula de botones 10x10 (cada celda = un tk.Button)
        grid_frame = tk.Frame(left, bg="#4a8c2a", bd=2, relief="ridge")
        grid_frame.pack(fill="both", expand=True)

        for r in range(GRID_SIZE):
            row_buttons = []
            for c in range(GRID_SIZE):
                # lambda con valores por defecto evita el problema de closure en bucles
                b = tk.Button(grid_frame, text="", width=10, height=4, bg="#6ab04c",
                              relief="groove", command=lambda rr=r, cc=c: self.on_cell_click(rr, cc))
                b.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                row_buttons.append(b)
            self.cell_buttons.append(row_buttons)

        for i in range(GRID_SIZE):
            grid_frame.grid_rowconfigure(i, weight=1)
            grid_frame.grid_columnconfigure(i, weight=1)

        bottom = tk.Frame(left, bg="#dcefd1")
        bottom.pack(fill="x", pady=6)
        tk.Label(bottom, textvariable=self.selected_var, bg="#dcefd1", font=("Comic Sans MS", 11)).pack(anchor="w")

        right = tk.Frame(body, bg="#edf7e6", width=360)
        right.pack(side="right", fill="y", padx=(8, 0))
        tk.Label(right, text="Bitacora", bg="#edf7e6", font=("Comic Sans MS", 14, "bold")).pack(anchor="w", padx=8, pady=6)

        self.log_text = tk.Text(right, height=34, width=44, font=("Comic Sans MS", 10))
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text.insert("end", "\n".join(self.state.log_entries[-80:]) + "\n")
        self.log_text.config(state="disabled")

    def _load_images(self) -> None:
        """Carga todas las imágenes en el caché. Sin Pillow, este método no hace nada."""
        if not Image or not ImageTk:
            return
        for key, definition in PRODUCTS.items():
            path = IMAGES_DIR / definition.image_file
            if path.exists():
                try:
                    img = Image.open(path).resize((70, 50))
                    self.photo_cache[key] = ImageTk.PhotoImage(img)
                except Exception:
                    pass
        dead_path = IMAGES_DIR / "muerto.png"
        if dead_path.exists():
            try:
                img = Image.open(dead_path).resize((70, 50))
                self.photo_cache["__dead__"] = ImageTk.PhotoImage(img)
            except Exception:
                pass

    def add_log_line(self, line: str) -> None:
        """Agrega una línea a la bitácora visual. Llamado como callback desde el motor."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")           # Auto-scroll al final
        self.log_text.config(state="disabled")

    def set_pending_purchase(self, key: str) -> None:
        """Indica que el jugador compró algo y debe colocarlo haciendo clic en una celda."""
        self.pending_shop_item = key
        self.pending_inventory_item = None
        self.pending_var.set(f"Pendiente por colocar (tienda): {PRODUCTS[key].name}")

    def set_pending_inventory_item(self, key: str) -> None:
        """Igual que set_pending_purchase pero el item viene del inventario."""
        self.pending_inventory_item = key
        self.pending_shop_item = None
        self.pending_var.set(f"Pendiente por colocar (inventario): {PRODUCTS[key].name}")

    def clear_pending(self) -> None:
        """Limpia el estado de "item pendiente por colocar"."""
        self.pending_shop_item = None
        self.pending_inventory_item = None
        self.pending_var.set("Sin producto pendiente")

    def open_shop(self) -> None:      ShopWindow(self)
    def open_inventory(self) -> None: InventoryWindow(self)
    def open_stats(self) -> None:     StatsWindow(self, self.state)

    def save_now(self) -> None:
        """Guarda manualmente la partida en JSON."""
        save_game(self.state)
        self.add_log_line(f"[{time.strftime('%H:%M:%S')}] Partida guardada en JSON.")

    def toggle_auto_harvest(self) -> None:
        """Activa/desactiva la recolección automática y procesa los items ya listos."""
        self.state.auto_harvest = bool(self.auto_var.get())
        self.engine.log("Auto recoleccion activada." if self.state.auto_harvest else "Auto recoleccion desactivada.")
        if self.state.auto_harvest:
            harvested = self.engine.collect_ready_items()
            if harvested > 0:
                self.engine.log(f"Auto recoleccion aplicada a {harvested} producciones pendientes.")
                self.refresh_ui()

    def on_cell_click(self, row: int, col: int) -> None:
        """
        ★ PARA ESTUDIAR: manejo de eventos de clic en cuadrícula.
        El comportamiento depende del estado actual (¿hay algo pendiente de colocar?).
        Patrón: verificar estado → actuar → limpiar estado.
        """
        self.selected_cell = (row, col)
        terrain_index = self.state.current_terrain_index

        if self.pending_shop_item:
            key = self.pending_shop_item
            animal_name = ""
            if PRODUCTS[key].category == "animal":
                animal_name = simpledialog.askstring(
                    "Nombre del animal", "Escribe un nombre para este animal:", parent=self) or ""
            ok, msg = self.engine.place_item(key, terrain_index, row, col,
                                             animal_name=animal_name, from_inventory=True)
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
                    "Nombre para el animal", "Nombre para el animal que sale del inventario:", parent=self) or ""
            ok, msg = self.engine.place_item(key, terrain_index, row, col,
                                             animal_name=animal_name, from_inventory=True)
            if ok:
                self.clear_pending()
            messagebox.showinfo("Colocar", msg, parent=self)
            self.refresh_ui()
            return

        self.refresh_selected_info()   # Sin pendiente: solo muestra info de la celda

    def refresh_selected_info(self) -> None:
        """Actualiza la barra inferior con información del item en la celda seleccionada."""
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
        cond   = f" Condicion: {item.condition} ({item.condition_remaining}s)." if item.condition else ""
        life   = " Muerto." if item.dead else ""

        if definition.is_productive and not item.ready:
            timing = f" Tiempo restante: {format_seconds(item.remaining_seconds)}."
        elif item.ready:
            timing = f" Listo para recolectar. Se dana en {max(0, 90 - item.ready_wait_seconds)}s."
        else:
            timing = ""

        self.selected_var.set(
            f"Terreno {terrain_idx + 1} - Celda ({r + 1},{c + 1}): {definition.name}.{animal}{timing}{cond}{life}")

    def remove_selected_to_inventory(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Inventario", "Selecciona una celda.", parent=self); return
        r, c = self.selected_cell
        ok, msg = self.engine.remove_to_inventory(self.state.current_terrain_index, r, c)
        messagebox.showinfo("Inventario", msg, parent=self)
        self.refresh_ui()

    def clear_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Limpiar", "Selecciona una celda.", parent=self); return
        r, c = self.selected_cell
        ok, msg = self.engine.clear_cell(self.state.current_terrain_index, r, c)
        messagebox.showinfo("Limpiar", msg, parent=self)
        self.refresh_ui()

    def harvest_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Cosechar", "Selecciona una celda.", parent=self); return
        r, c = self.selected_cell
        item = self.engine.get_item_at(self.state.current_terrain_index, r, c)
        if not item:
            messagebox.showwarning("Cosechar", "No hay elemento en la celda.", parent=self); return
        ok, msg = self.engine.harvest(item, automatic=False)
        messagebox.showinfo("Cosechar", msg, parent=self)
        self.refresh_ui()

    def cure_selected(self) -> None:
        if not self.selected_cell:
            messagebox.showwarning("Curar", "Selecciona una celda.", parent=self); return
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
        value = simpledialog.askinteger("Ir a terreno", f"A cual terreno quieres ir? (1 - {total})",
                                        parent=self, minvalue=1, maxvalue=total)
        if value is None:
            return
        idx = value - 1
        if self.engine.set_current_terrain(idx):
            self.engine.log(f"Navegaste al terreno {value}.")
            self.refresh_ui()

    def refresh_ui(self) -> None:
        """
        Actualiza todos los widgets visuales a partir del estado actual.
        ★ PARA ESTUDIAR: la UI es un REFLEJO del estado; no guarda datos propios.
        Esto significa que refresh_ui() siempre es idempotente (seguro de llamar N veces).
        """
        ready_count = sum(1 for item in self.state.items.values() if item.ready)
        used_cells  = len(self.state.items)

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
                    btn.config(text="", image="", bg="#6ab04c", fg="#1a3a0a")
                    continue

                item = self.state.items.get(item_id)
                if not item:
                    btn.config(text="", image="", bg="#6ab04c", fg="#1a3a0a")
                    continue

                definition = PRODUCTS[item.product_key]
                image_key = "__dead__" if item.dead and "__dead__" in self.photo_cache else item.product_key
                has_image = image_key in self.photo_cache

                # Texto de estado que aparece en cada celda
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
                    btn.config(image=self.photo_cache[image_key], compound="top",
                               text=tail, font=("Comic Sans MS", 9, "bold"),
                               bg="#fffadf" if item.ready else "#6ab04c", fg="#1a3a0a")
                else:
                    txt = f"{caption}\n{tail}" if tail else caption
                    btn.config(text=txt, image="", font=("Comic Sans MS", 9),
                               bg="#fffadf" if item.ready else "#6ab04c", fg="#1a3a0a")

        self.refresh_selected_info()

    def _ui_loop(self) -> None:
        """
        ★ PARA ESTUDIAR: bucle principal de la UI usando after() de Tkinter.
        after(1000, func) programa la ejecución de func 1 segundo después,
        en el hilo principal (sin bloquear la interfaz). Es la alternativa
        segura a time.sleep() en GUI, ya que no congela la ventana.
        """
        self.state.statistics.total_play_seconds += 1
        self.refresh_ui()
        if self.state.statistics.total_play_seconds % 30 == 0:
            save_game(self.state)   # Autoguardado cada 30 segundos
        if self.engine.running:
            self.after(1000, self._ui_loop)   # Reprograma para el próximo segundo

    def on_close(self) -> None:
        """Manejo seguro del cierre: guarda, detiene hilos y vuelve al menú."""
        save_game(self.state)
        self.engine.stop_all_threads()
        self.destroy()
        self.app.on_game_closed()


class FarmApp:
    """
    Controlador raíz de la aplicación.
    Gestiona la transición entre el menú y la vista de juego,
    y coordina el ciclo de vida de la ventana principal.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SiembraTEC")
        self.root.geometry("1150x660+0+0")
        self.root.configure(bg="#06a10d")
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.menu_view = MenuView(root, self)
        self.game_view: Optional[GameView] = None

    def new_game(self) -> None:
        """Inicia una partida nueva. Pide confirmación si ya existe una guardada."""
        if SAVE_FILE.exists():
            confirm = messagebox.askyesno(
                "Confirmacion muy importante",
                "Vas a iniciar una partida nueva y eliminar la anterior.\n"
                "Esta accion borra TODO el progreso guardado.\n\n"
                "Estas completamente seguro?", parent=self.root)
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
        """Carga la partida guardada. Muestra error si no hay archivo."""
        state = load_game()
        if not state:
            messagebox.showwarning("Continuar", "No hay partida guardada.", parent=self.root)
            return
        self.start_game(state)

    def show_menu_stats(self) -> None:
        """Muestra estadísticas desde el menú (sin abrir el juego)."""
        state = load_game()
        if not state:
            messagebox.showwarning("Estadisticas", "No hay partida guardada.", parent=self.root)
            return
        StatsWindow(self.root, state)

    def start_game(self, state: GameState) -> None:
        """Transición: oculta el menú y abre la vista de juego."""
        if self.game_view is not None:
            try:
                self.game_view.on_close()
            except Exception:
                pass
        self.menu_view.pack_forget()
        self.game_view = GameView(self, state)

    def on_game_closed(self) -> None:
        """Callback cuando el jugador cierra el juego: vuelve a mostrar el menú."""
        self.game_view = None
        self.menu_view = MenuView(self.root, self)

    def close_app(self) -> None:
        """Cierra toda la aplicación, guardando si había juego activo."""
        if self.game_view is not None:
            self.game_view.on_close()
        self.root.destroy()


# =============================================================================
# SECCIÓN 9: PUNTO DE ENTRADA
# =============================================================================

def main() -> None:
    """
    Función principal: crea la ventana raíz de Tkinter y arranca el juego.
    El bloque if __name__ == "__main__" garantiza que solo se ejecute
    cuando el archivo se corre directamente (no cuando se importa como módulo).
    """
    root = tk.Tk()                      # Ventana raíz del sistema de ventanas
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")         # Tema "clam": look más moderno en Windows
    app = FarmApp(root)
    root.mainloop()                     # Bucle de eventos de Tkinter (bloquea hasta cerrar)


if __name__ == "__main__":
    main()


