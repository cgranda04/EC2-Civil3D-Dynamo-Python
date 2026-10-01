# EC2 – Extracción de información de redes de tuberías Civil 3D con Dynamo + Python

## 1. Objetivo

Esta rutina automatiza la extracción de información de una red de tuberías modelada en **Autodesk Civil 3D 2025**, procesándola mediante **Dynamo + CPython3** para generar una tabla utilizable por el área de Costos.

El flujo evita que un usuario de Costos tenga que revisar manualmente cada perfil o manipular objetos especializados de Civil 3D para obtener datos de tuberías, excavaciones y buzones.

---

## 2. Entorno validado

- Autodesk Civil 3D **2025.2.1**
- Dynamo **3.3.1.7726**
- Motor Python: **CPython3**
- API utilizadas:
  - `AcMgd`
  - `AcDbMgd`
  - `AeccDbMgd`
- Paquetes externos de Dynamo requeridos: **ninguno para esta versión del grafo**

> La rutina fue desarrollada y validada en este entorno. No se garantiza su funcionamiento sin revisión en versiones anteriores de Civil 3D/Dynamo.

---

## 3. Inputs que debe configurar el usuario

Antes de ejecutar el grafo, el usuario debe revisar **cuatro entradas principales**.

| Input | Ejemplo actual | Qué debe ingresar el usuario |
|---|---|---|
| **Nombre de Pipe Network** | `RED 01` | Nombre exacto de la red de tuberías existente en el dibujo de Civil 3D. |
| **Nombre de superficie** | `XML_PAQUETE 33_TN` | Nombre exacto de la superficie utilizada como terreno para consultar cotas X-Y. |
| **Archivo Excel de salida** | `REPORTE_TUBERIAS_....xlsx` | Ruta donde se generará o actualizará el reporte. |
| **Nombre de hoja Excel** | `REPORTE` | Hoja en la que Dynamo escribirá la información. |

### Importante

Los nombres de la red y de la superficie deben coincidir exactamente con los objetos existentes en el dibujo activo de Civil 3D.

La ruta de Excel incluida originalmente en el grafo corresponde a una ruta local del equipo donde fue desarrollado. **Cada usuario debe seleccionar su propia ruta de salida antes de ejecutar.**

---

## 4. Inputs internos del nodo Python

El nodo **Python Script (CPython3)** recibe diez entradas provenientes de los nodos de Dynamo.

| Puerto | Variable | Procedencia / significado |
|---|---|---|
| `IN[0]` | Nombre de tubería | `CivilObject.Name` |
| `IN[1]` | Part Size | `Part.PartSize` |
| `IN[2]` | Longitud 2D | `Pipe.Length` |
| `IN[3]` | Pendiente | `Pipe.Slope` |
| `IN[4]` | Cota terreno inicio | Elevación de superficie en X-Y del punto inicial |
| `IN[5]` | Cota fondo inicio | Cota exterior inferior calculada para el inicio de la tubería |
| `IN[6]` | Cota terreno final | Elevación de superficie en X-Y del punto final |
| `IN[7]` | Cota fondo final | Cota exterior inferior calculada para el final de la tubería |
| `IN[8]` | Buzón/estructura inicial | `Pipe.StartStructure` |
| `IN[9]` | Buzón/estructura final | `Pipe.EndStructure` |

Estas entradas son generadas automáticamente por el grafo. El usuario final **no debe ingresarlas manualmente** si utiliza el `.dyn` completo.

---

## 5. Lógica de la rutina

El flujo general es:

```text
Civil 3D
   ↓
Seleccionar Pipe Network
   ↓
Obtener tuberías
   ↓
Extraer propiedades geométricas y alfanuméricas
   ↓
Consultar superficie en inicio y final
   ↓
Calcular cotas de fondo y excavaciones
   ↓
Consultar estructuras conectadas
   ↓
Python / Civil 3D API:
    - nombre de buzón
    - estilo de etiqueta
    - tipo de buzón
    - rango de profundidad
   ↓
Construir matriz de resultados
   ↓
Exportar a Excel
```

### Cálculos principales

**Excavación al inicio**

```text
Excavación_inicio = Cota_terreno_inicio - Cota_fondo_inicio
```

**Excavación al final**

```text
Excavación_final = Cota_terreno_final - Cota_fondo_final
```

**Excavación promedio**

```text
Excavación_promedio =
(Excavación_inicio + Excavación_final) / 2
```

---

## 6. Información generada

El reporte contiene 19 campos:

1. Nombre de tubería
2. Part Size
3. Longitud 2D
4. Pendiente
5. Cota de terreno inicial
6. Cota de fondo de tubería inicial
7. Excavación inicial
8. Cota de terreno final
9. Cota de fondo de tubería final
10. Excavación final
11. Excavación promedio
12. Buzón inicial
13. Estilo de etiqueta inicial
14. Tipo de buzón inicial
15. Rango de altura inicial
16. Buzón final
17. Estilo de etiqueta final
18. Tipo de buzón final
19. Rango de altura final

---

## 7. Clasificación de profundidad

La profundidad calculada se clasifica en los siguientes intervalos:

- `0.00–1.50 m`
- `1.50–2.00 m`
- `2.00–2.50 m`
- `2.50–3.00 m`
- `3.00–3.50 m`
- `3.50–4.00 m`
- `>= 4.00 m`

Si la profundidad es negativa, el script devuelve:

`REVISAR COTA`

---

## 8. Identificación del tipo de buzón

El nodo Python consulta mediante la API de Civil 3D las etiquetas asociadas a las estructuras.

Se priorizan estilos cuyo nombre contiene:

- `ETIQ_BUZONES_PLANTA`
- `BUZONES_PLANTA`
- `PLANTA`

Posteriormente se interpreta la nomenclatura para identificar tipos de buzón:

- TIPO I
- TIPO II
- TIPO III
- TIPO IV
- TIPO V
- TIPO VI
- TIPO VII
- TIPO VIII

También se reconocen abreviaturas como `TI`, `TII`, `TIII`, `T1`, `T2`, `T3`, etc.

---

## 9. Supuestos y limitaciones

1. La Pipe Network y la superficie deben existir en el dibujo activo.
2. La superficie debe cubrir las coordenadas X-Y de los extremos de las tuberías.
3. La identificación del tipo de buzón depende de la convención de nomenclatura de las etiquetas o del nombre de la estructura.
4. El resultado corresponde a información derivada del estado actual del modelo; si el modelo cambia, debe ejecutarse nuevamente la rutina.
5. La clasificación por rango utiliza la profundidad calculada entre terreno y fondo de tubería; no representa necesariamente una propiedad geométrica `Height` leída directamente de la estructura.
6. La ruta de Excel debe configurarse en cada equipo.
7. El script valida que las listas recibidas desde Dynamo sean consistentes y genera un error explícito si detecta longitudes incompatibles.

---

## 10. Resultado esperado

Al ejecutar el grafo, Dynamo genera una matriz de datos y la exporta a Excel para que pueda ser utilizada como input por Costos, metrados, presupuestos o controles posteriores.

La automatización busca reducir la revisión manual de perfiles y facilitar el acceso a información del modelo Civil 3D a usuarios que no requieren manipular directamente el modelo de diseño.
