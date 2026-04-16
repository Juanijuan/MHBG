# MHBG - Monster Hunter Board Game Custom Project

## Resumen

Proyecto personal para reconstruir y ampliar Monster Hunter World: The Board Game a partir de assets extraídos desde un mod de Tabletop Simulator.

Se trabaja principalmente con:
- cartas
- hojas de cartas
- imágenes
- modelos 3D
- organización por monstruo
- preparación de material para impresión posterior

---

## Estructura actual

```text
C:\Users\juani\Documents\MHBG\
├─ Imprimir\           # NO TOCAR
├─ Modelos 3d\         # salida de modelos 3D
├─ Scripts\            # scripts y proyecto principal
└─ TTS_Extract\        # salida de cartas e imágenes extraídas

## Scripts y archivos importantes

Ruta principal:

```text
C:\Users\juani\Documents\MHBG\Scripts\

Contenido actual detectado:

Scripts\
├─ .codex\
├─ extraer_cartas.py
├─ extraer_modelos_tts.py
├─ import re.py
├─ mods.json
├─ PillowCutter.py
└─ README-CODEX.md
Archivo: mods.json
C:\Users\juani\Documents\MHBG\Scripts\mods.json

Contiene el JSON completo exportado desde el mod de Tabletop Simulator.
Es la fuente principal para localizar:

FaceURL
BackURL
ImageURL
CustomMesh.MeshURL
CustomMesh.DiffuseURL
CustomMesh.ColliderURL
CustomMesh.NormalURL
Archivo: extraer_cartas.py

Script principal para extraer cartas e imágenes desde mods.json.

Debe ser capaz de:

Buscar por texto configurable (SEARCH_TERM)
Encontrar objetos relacionados con un monstruo, arma o carta
Generar:
<busqueda>_subset.json
<busqueda>_urls.txt
reporte_<busqueda>.txt
Copiar las imágenes desde la caché local de Tabletop Simulator a:
C:\Users\juani\Documents\MHBG\TTS_Extract\<busqueda>_assets\

Debe revisar principalmente:

FaceURL
BackURL
ImageURL
CustomDeck
CustomImage
Archivo: extraer_modelos_tts.py

Script principal para extraer modelos 3D desde mods.json.

Debe buscar objetos que contengan:

"CustomMesh": {
  "MeshURL": "...",
  "DiffuseURL": "...",
  "ColliderURL": "...",
  "NormalURL": "..."
}

La búsqueda debe funcionar por texto configurable (SEARCH_TERM) y revisar:

Nickname
Name
Description
GMNotes

La salida debe guardarse en:

C:\Users\juani\Documents\MHBG\Modelos 3d\<busqueda>\

y separarse automáticamente en:

<busqueda>\
├─ meshes\
├─ textures\
├─ colliders\
├─ normals\
├─ reporte_<busqueda>.txt
├─ objetos_<busqueda>.json
└─ urls_<busqueda>.txt

Debe ignorar objetos genéricos repetidos como:

Custom_Model_Bag
Custom_Model_Infinite_Bag
bolsas de nodos
bolsas de cartas de tiempo
otros contenedores sin nombre útil
Archivo: PillowCutter.py

Script auxiliar para cortar imágenes que contienen varias cartas en una sola hoja.

Casos típicos:

cartas de comportamiento 4x4
reversos de comportamiento
cartas de armadura
hojas de armas
physiology cards

Debe permitir configurar:

imagen de entrada
número de columnas
número de filas
carpeta de salida
Archivo: import re.py

Script temporal o de pruebas.

Actualmente no forma parte de la estructura principal del proyecto.

Se recomienda:

renombrarlo si acaba teniendo una función concreta
o eliminarlo si solo era una prueba

Porque el nombre import re.py puede dar problemas con Python al interferir con el módulo estándar re.

Carpeta .codex\

Contiene la configuración específica del proyecto para Codex:

Scripts\.codex\config.toml

Se usa para:

contexto persistente
rutas del proyecto
restricciones
instrucciones de trabajo