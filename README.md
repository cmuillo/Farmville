# SiembraTEC - Proyecto 3

Juego tipo FarmVille en Python + Tkinter con:

- Terrenos 10x10 (matriz)
- Tienda de productos
- Produccion con hilos (1 hilo por elemento productivo)
- Plagas/enfermedades aleatorias
- Inventario (incluye retirar del tablero)
- Auto-recoleccion opcional
- Navegacion entre terrenos
- Persistencia JSON
- Bitacora de eventos
- Estadisticas por producto

## Ejecutar

1. Instalar dependencias (sin entorno virtual obligatorio):

```bash
pip install -r requirements.txt
```

2. Ejecutar:

```bash
python main.py
```

## Notas

- No es obligatorio usar entorno virtual para correr este proyecto.
- Si faltan imagenes, el juego usa etiquetas de texto en cada celda.
- El tiempo solo corre con la app abierta.
- La partida se guarda en `data/savegame.json`.

## Estructura del codigo (modular)

- `main.py`: punto de entrada de la aplicacion.
- `farmville/domain.py`: constantes, catalogo, entidades y dataclasses del estado.
- `farmville/persistence.py`: guardado/carga/eliminacion de partida en JSON.
- `farmville/engine.py`: reglas de negocio y temporizadores por item.
- `farmville/ui.py`: ventanas y flujo de interfaz Tkinter.
