# SiembraTEC - Proyecto 3

Juego tipo FarmVille en Python + Tkinter con:

- Terrenos 10x10 (matriz)
- Tienda de productos
- Produccion con hilos (1 hilo por elemento productivo)
- Plagas/enfermedades aleatorias (0.15% de probabilidad por segundo)
- Inventario (incluye retirar del tablero)
- Auto-recoleccion opcional
- Navegacion entre terrenos
- Persistencia JSON
- Bitacora de eventos
- Estadisticas por producto
- Fuente Comic Sans MS en toda la interfaz

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
- Los consumibles (Pesticida y Medicina) cuestan 40 y 60 monedas respectivamente.

## Estructura del codigo

- `main.py`: punto de entrada de la aplicacion. Contiene todo el codigo del juego en un solo archivo (constantes, modelos, motor, UI).
