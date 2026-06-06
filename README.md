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

1. Instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Ejecutar:

```bash
python main.py
```

## Notas

- Si falta `tkVideoPlayer`, el menu se muestra con fondo verde fijo.
- Si faltan imagenes, el juego usa etiquetas de texto en cada celda.
- El tiempo solo corre con la app abierta.
- La partida se guarda en `data/savegame.json`.
