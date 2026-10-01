# -*- coding: utf-8 -*-
"""
EC2 - BIM Management
Rutina Dynamo + CPython3 para Civil 3D 2025

OBJETIVO
--------
Recibir desde Dynamo la información de cada tubería de una Pipe Network,
calcular profundidades de excavación y consultar las estructuras (buzones)
conectadas para obtener nombre, estilo de etiqueta y tipo de buzón.

ENTORNO VALIDADO
----------------
- Autodesk Civil 3D 2025.2.1
- Dynamo 3.3.1.7726
- Motor Python: CPython3

ENTRADAS DEL NODO PYTHON
------------------------
IN[0] = Nombre de la tubería
IN[1] = Part Size / dimensión de la tubería
IN[2] = Longitud 2D de la tubería
IN[3] = Pendiente de la tubería
IN[4] = Cota de terreno al inicio
IN[5] = Cota de fondo de tubería al inicio
IN[6] = Cota de terreno al final
IN[7] = Cota de fondo de tubería al final
IN[8] = Estructura / buzón conectado al inicio
IN[9] = Estructura / buzón conectado al final

SALIDA
------
OUT = Lista de filas. Cada fila contiene 19 campos, en este orden:

01 Nombre de tubería
02 Part Size
03 Longitud 2D
04 Pendiente
05 Cota terreno inicio
06 Cota fondo tubería inicio
07 Excavación inicio
08 Cota terreno final
09 Cota fondo tubería final
10 Excavación final
11 Excavación promedio
12 Buzón inicio
13 Estilo de etiqueta inicio
14 Tipo de buzón inicio
15 Rango de altura inicio
16 Buzón final
17 Estilo de etiqueta final
18 Tipo de buzón final
19 Rango de altura final

NOTA
----
El tipo de buzón se infiere a partir de la nomenclatura del estilo de
etiqueta o del nombre de la estructura. Por ello, la rutina depende de que
esa convención se mantenga en el modelo.
"""

import re
import clr

# ---------------------------------------------------------------------------
# 1. CARGA DE API AUTOCAD / CIVIL 3D
# ---------------------------------------------------------------------------

clr.AddReference("AcMgd")
clr.AddReference("AcDbMgd")
clr.AddReference("AeccDbMgd")

from Autodesk.AutoCAD.ApplicationServices import Application
from Autodesk.AutoCAD.DatabaseServices import OpenMode
from Autodesk.Civil.DatabaseServices import StructureLabel


# ---------------------------------------------------------------------------
# 2. FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def to_list(value):
    """Convierte una entrada de Dynamo en una lista Python."""
    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        return list(value)

    try:
        if hasattr(value, "__iter__") and not isinstance(value, str):
            return list(value)
    except Exception:
        pass

    return [value]


def clean(value):
    """Reemplaza None por texto vacío para evitar celdas problemáticas."""
    return "" if value is None else value


def as_float(value):
    """Convierte un valor a float; devuelve None si no es numérico."""
    try:
        return float(value)
    except Exception:
        return None


def difference(a, b):
    """Calcula a - b cuando ambos valores son numéricos."""
    aa = as_float(a)
    bb = as_float(b)

    if aa is None or bb is None:
        return ""

    return aa - bb


def average(a, b):
    """Calcula el promedio de dos valores numéricos."""
    aa = as_float(a)
    bb = as_float(b)

    if aa is None or bb is None:
        return ""

    return (aa + bb) / 2.0


def depth_range(depth):
    """
    Clasifica la profundidad de excavación en rangos de 0.50 m.
    """
    value = as_float(depth)

    if value is None:
        return "SIN ALTURA"

    if value < 0:
        return "REVISAR COTA"

    if value < 1.50:
        return "0.00-1.50 m"
    if value < 2.00:
        return "1.50-2.00 m"
    if value < 2.50:
        return "2.00-2.50 m"
    if value < 3.00:
        return "2.50-3.00 m"
    if value < 3.50:
        return "3.00-3.50 m"
    if value < 4.00:
        return "3.50-4.00 m"

    return ">= 4.00 m"


def parse_structure_type(text):
    """
    Interpreta el tipo de buzón a partir de una convención de nomenclatura.

    Reconoce, entre otros:
    TIPO I ... TIPO VIII
    TI ... TVIII
    T1 ... T8
    """
    text_upper = (text or "").upper()

    roman_types = [
        ("VIII", "TIPO VIII"),
        ("VII", "TIPO VII"),
        ("VI", "TIPO VI"),
        ("V", "TIPO V"),
        ("IV", "TIPO IV"),
        ("III", "TIPO III"),
        ("II", "TIPO II"),
        ("I", "TIPO I"),
    ]

    # Caso explícito: "TIPO III", "TIPOIII", etc.
    for roman, label in roman_types:
        if ("TIPO " + roman) in text_upper or ("TIPO" + roman) in text_upper:
            return label

    # Caso abreviado: TIII, T3, etc.
    tokens = re.split(r"[^A-Z0-9]+", text_upper.replace("-", "_"))

    abbreviations = [
        ("TVIII", "TIPO VIII"), ("T8", "TIPO VIII"),
        ("TVII", "TIPO VII"), ("T7", "TIPO VII"),
        ("TVI", "TIPO VI"), ("T6", "TIPO VI"),
        ("TV", "TIPO V"), ("T5", "TIPO V"),
        ("TIV", "TIPO IV"), ("T4", "TIPO IV"),
        ("TIII", "TIPO III"), ("T3", "TIPO III"),
        ("TII", "TIPO II"), ("T2", "TIPO II"),
        ("TI", "TIPO I"), ("T1", "TIPO I"),
    ]

    for token, label in abbreviations:
        if token in tokens:
            return label

    return "SIN TIPO EN ETIQUETA"


def object_id_from_wrapper(obj):
    """
    Obtiene el ObjectId nativo de AutoCAD/Civil 3D desde el wrapper de Dynamo.
    """
    if obj is None:
        return None

    try:
        return obj.InternalObjectId
    except Exception:
        pass

    try:
        return obj.InternalDBObject.ObjectId
    except Exception:
        return None


def structure_info(obj, transaction):
    """
    Devuelve:
        (nombre_estructura, estilo_etiqueta, tipo_buzon)

    La función consulta el objeto nativo de Civil 3D y las etiquetas
    disponibles asociadas a la estructura.
    """
    if obj is None:
        return ("NO CONECTADO", "SIN ETIQUETA", "NO CONECTADO")

    object_id = object_id_from_wrapper(obj)

    if object_id is None:
        return ("ID NO DISPONIBLE", "SIN ETIQUETA", "REVISAR ESTRUCTURA")

    structure_name = ""
    style_names = []

    # Nombre de la estructura
    try:
        db_object = transaction.GetObject(object_id, OpenMode.ForRead)
        try:
            structure_name = str(db_object.Name)
        except Exception:
            pass
    except Exception:
        try:
            structure_name = str(obj.Name)
        except Exception:
            structure_name = ""

    # Estilos de etiqueta asociados
    try:
        label_ids = StructureLabel.GetAvailableLabelIds(object_id)

        for label_id in label_ids:
            try:
                label = transaction.GetObject(label_id, OpenMode.ForRead)
                style_name = str(label.StyleName)

                if style_name:
                    style_names.append(style_name)

            except Exception:
                pass

    except Exception:
        pass

    # Prioriza la etiqueta de planta usada para buzones
    selected_style = ""

    for style_name in style_names:
        style_upper = style_name.upper()

        if (
            "ETIQ_BUZONES_PLANTA" in style_upper
            or "BUZONES_PLANTA" in style_upper
            or "PLANTA" in style_upper
        ):
            selected_style = style_name
            break

    # Si existe alguna etiqueta pero no coincide con la convención anterior,
    # utiliza la primera disponible.
    if not selected_style and style_names:
        selected_style = style_names[0]

    if not selected_style:
        selected_style = "SIN ETIQUETA"

    structure_type = parse_structure_type(
        selected_style + " " + structure_name
    )

    return (
        structure_name if structure_name else "SIN NOMBRE",
        selected_style,
        structure_type,
    )


def normalize_input_lengths(input_lists):
    """
    Valida las listas recibidas desde Dynamo.

    Regla:
    - Las listas principales deben tener la misma cantidad de elementos.
    - Se permite una lista de un solo elemento como valor constante.
    - Una lista vacía se completa con None.
    - Una longitud intermedia inconsistente genera un error explícito.

    Esto evita repetir silenciosamente el último elemento de una lista.
    """
    max_count = max([len(values) for values in input_lists] + [0])

    if max_count == 0:
        raise ValueError(
            "El nodo Python no recibió elementos. "
            "Revise la Pipe Network y las conexiones de entrada."
        )

    normalized = []

    for index, values in enumerate(input_lists):
        current_length = len(values)

        if current_length == max_count:
            normalized.append(values)

        elif current_length == 1:
            normalized.append(values * max_count)

        elif current_length == 0:
            normalized.append([None] * max_count)

        else:
            raise ValueError(
                "Longitud inconsistente en IN[{0}]: {1} elementos. "
                "Se esperaban {2}, 1 o 0.".format(
                    index, current_length, max_count
                )
            )

    return normalized, max_count


# ---------------------------------------------------------------------------
# 3. RECEPCIÓN Y VALIDACIÓN DE INPUTS DE DYNAMO
# ---------------------------------------------------------------------------

if len(IN) < 10:
    raise ValueError(
        "El script requiere 10 entradas IN[0]...IN[9]. "
        "Actualmente recibe {0}.".format(len(IN))
    )

input_lists = [to_list(value) for value in IN[:10]]
input_lists, pipe_count = normalize_input_lengths(input_lists)

(
    pipe_names,
    part_sizes,
    lengths_2d,
    slopes,
    start_terrain_elevations,
    start_bottom_elevations,
    end_terrain_elevations,
    end_bottom_elevations,
    start_structures,
    end_structures,
) = input_lists


# ---------------------------------------------------------------------------
# 4. PROCESAMIENTO DE CADA TUBERÍA
# ---------------------------------------------------------------------------

rows = []

active_document = Application.DocumentManager.MdiActiveDocument

if active_document is None:
    raise RuntimeError(
        "No existe un documento activo de Civil 3D."
    )

transaction = active_document.Database.TransactionManager.StartTransaction()

try:
    for index in range(pipe_count):

        # ---------------------------
        # Datos directos de la tubería
        # ---------------------------
        pipe_name = clean(pipe_names[index])
        part_size = clean(part_sizes[index])
        length_2d = clean(lengths_2d[index])
        slope = clean(slopes[index])

        # ---------------------------
        # Cotas inicio / final
        # ---------------------------
        start_terrain = clean(start_terrain_elevations[index])
        start_bottom = clean(start_bottom_elevations[index])

        end_terrain = clean(end_terrain_elevations[index])
        end_bottom = clean(end_bottom_elevations[index])

        # Excavación = cota terreno - cota fondo exterior de tubería
        start_excavation = difference(start_terrain, start_bottom)
        end_excavation = difference(end_terrain, end_bottom)

        average_excavation = average(
            start_excavation,
            end_excavation
        )

        # ---------------------------
        # Estructuras conectadas
        # ---------------------------
        start_name, start_style, start_type = structure_info(
            start_structures[index],
            transaction
        )

        end_name, end_style, end_type = structure_info(
            end_structures[index],
            transaction
        )

        # ---------------------------
        # Fila de salida
        # ---------------------------
        rows.append([
            pipe_name,
            part_size,
            length_2d,
            slope,

            start_terrain,
            start_bottom,
            start_excavation,

            end_terrain,
            end_bottom,
            end_excavation,

            average_excavation,

            start_name,
            start_style,
            start_type,
            depth_range(start_excavation),

            end_name,
            end_style,
            end_type,
            depth_range(end_excavation),
        ])

finally:
    # La transacción es solo de lectura; no se requiere Commit().
    transaction.Dispose()


# ---------------------------------------------------------------------------
# 5. SALIDA HACIA DYNAMO
# ---------------------------------------------------------------------------

OUT = rows
