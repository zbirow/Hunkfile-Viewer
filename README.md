# Hunkfile-Viewer
Actual tested on Monster High: NGS on PC/Wii , Barbie PC, Falling Skies PC, Scooby-Doo 1/2 PC/Wii

Can dispaly Texture

3D model Viewer in progress.....

Hunkfile Viewer (.hnk) Torus Games

### Header Ident.

| offset 0x5 | Support Games |
| --- | ------------- |
| \x01\x00\x01\x00\x01 | MH(PC), Barbie(PC), Falling Skies(PC) |
| \xE5\x0A\x01\x00\x01 | MH(PC), Barbie(PC), Falling Skies(PC) |
| \x01\x04\x01\x00\x01 | Scooby Doo(PC) |
| Another | Wii games |

# Monster High: NGS / Barbie / Falling Skies
### Texture Info:
- Texture information is contained in the Texture Header [0x41150].

- The first two bytes correspond to the texture format.

### Texture Format
| Two First Bytes | Texture Format |
| --------------- | --------------:|
| 0xA1 0xBC | CMPR - Wii |
| 0xE9 0x78 | Unknown - Wii |
| 0xD3 0x3A | DXT5 - PC |
| 0xF9 0x3D | DXT1 - PC |
| 0x9F 0x5B | R8G8B8A8 - PC |

### Width/Height
 - Two bytes 

| Game | Width | Height | Endian | Example bytes | Out |
| ----- | ----- | ----- | ------ | -------- | ------:|
| PC | 0x0C | 0x0E | Little Endian | 0x00 0x02 | 512 |
| Wii | 0x0C | 0x0E | Big Endian | 0x02 0x00 | 512 |

[Tool](https://www.save-editor.com/tools/wse_hex.html "Tool")


### Tables for Monster High, Barbie, Falling Skies

| Type      | Value PC | Value Wii |
| --------- | -------- |----------:|
| File Name | 0x40071 | 0x40071 |
| ClankBodyTemplate main | 0x45100 |
| ClankBodyTemplate secondary| 0x402100 |
| ClankBodyTemplate name | 0x43100 |
| ClankBodyTemplate data | 0x44100 |
| ClankBodyTemplate data 2 | 0x404100 |
| LiteScript main | 0x4300c |
| LiteScript data | 0x4200c |
| LiteScript data 2 | 0x4100c |
| SqueakSample data | 0x204090 |
| TSETexture header | 0x41150 | 0x41150 |
| TSETexture data | 0x40151 | 0x202151 |
| TSETexture data 2 | 0x801151 |
| RenderModelTemplate header | 0x101050 |
| RenderModelTemplate data | 0x40054 | 0x202032 |
| RenderModelTemplate data table | 0x20055 | 0x202031 |
| Animation data | 0x42005 |
| Animation data 2 | 0x41005 |
| RenderSprite data | 0x41007 |
| EffectsParams data | 0x43112 |
| TSEFontDescriptor data | 0x43087 |
| TSEDataTable data 1 | 0x43083 |
| TSEDataTable data 2 | 0x4008a |
| StateFlowTemplate data | 0x43088 |
| StateFlowTemplate data 2 | 0x42088 |
| SqueakStream data | 0x204092 |
| SqueakStream data 2 | 0x201092 |
| EntityPlacement data | 0x42009 |
| EntityPlacement data 2 | 0x103009 |
| EntityPlacement BCC data | 0x101009 |
| EntityPlacement level data | 0x102009 |
| EntityTemplate data | 0x101008 |

# 3D Model Extraction Mechanism from HNK Format

`.hnk` files (used in games like *Monster High: New Ghoul in School*) are binary containers storing data records. This script processes these records to reconstruct a complete 3D model in `.obj` format.

## 1. Record Structure

The HNK format is based on data blocks of specific types:

- **Type `0x40054` (Vertex Buffer):** Stores raw vertex data (XYZ positions, UV coordinates, normals).
- **Type `0x20055` (Index Buffer):** Stores an index array defining how to connect vertices into triangles.

## 2. Challenge: Relative Indexing & Batches

The main difficulty in the HNK format is that the relationship between vertices and indices is not linear (1:1).

- **One large vertex buffer** may contain geometry for several model parts (e.g., head, torso, legs).
- **Indices inside a single record** do not grow indefinitely. Instead, for each new model part (sub-mesh), indices **reset to zero** (`0, 1, 2...`).

## 3. Reconstruction Algorithm (Step by Step)

### A. Part Detection (Batching)

The script scans index records for so-called **restarts**. Since each new section (e.g., hair after the face) starts indexing from zero, the script looks for sequences returning to low values (e.g., `..., 4881, 4882, 0, 1, 2`). Encountering such a sequence marks the beginning of a new sub-part (Batch).

### B. Dual Offset System (Key to Success)

The OBJ format requires absolute (global) indexing, while HNK uses local indexing. The script applies two levels of offsets:

1.  **Local Block Offset:** Used to navigate inside a single large vertex record. If Part 1 uses 1000 vertices, Part 2 (which starts indexing from 0) must have an offset of `+1000` added to point to the correct data within the same buffer.
2.  **Global OBJ Offset:** Used to combine multiple HNK records. If the first record (e.g., body) had 5000 vertices, indices from the second record (e.g., hair) must be shifted by `+5000` to point to unique line numbers in the OBJ file.

### C. Vertex Format Detection

HNK files do not have a fixed vertex size. The script dynamically detects the structure size (e.g., 32, 40, or 48 bytes) by analyzing separators and data patterns. This allows correct reading of XYZ positions and texture coordinates (UV) regardless of model complexity.

### D. Topology Building (Triangle List)

For each Batch, the script reads indices in groups of three, creating face definitions in the format:
`f v1/uv1 v2/uv2 v3/uv3`
UV coordinates are automatically flipped on the Y-axis (`1.0 - v`), which is standard when converting from Direct3D systems (used by the game) to the OpenGL/OBJ standard.

## 4. Technical Mapping Specification

- **Parser:** `struct.unpack("<H", ...)` for indices (16-bit unsigned short).
- **Vertex Data:** `struct.unpack("<3f", ...)` for positions (3x 32-bit float).
- **UV Data:** Offset by a variable `uv_offset` inside the vertex structure.
- **Part separators:** Pattern `[0, 1]` after values above a certain threshold, or optionally a `0xFFFF` separator.

## PC 3D Model

 [3D Model Extractor](https://github.com/zbirow/Hunkfile-Viewer/blob/main/dev/HNK_Test_Model.py)


Tested on Monster High NGiS PC, Barbie PC, Scooby Doo 1/2 PC.
 

# Scooby Doo -in progress
- Texture information is contained in the Texture Header PC [0x41056] , Wii [0x41033].
- 
### Texture Format

PC
| 0x34:0x40 | Texture Format |
| --------------- | --------------:|
| DXT5 | DXT5 - PC |
| DXT1 | DXT1 - PC |
| 0x15 | R8G8B8A8 - PC |


Wii
| 0x5:0x9 | Texture Format |
| --------------- | --------------:|
| 0x01 0x00 0x00 0x24 | CMPR - Wii |
| 0x01 0x00 0x00 0x28 | CMPR - Wii |
| 0x01 0x00 0x00 0x20 | CMPR - Wii |
| 0x01 0x00 0x00 0x2C | CMPR - Wii |
| 0x01 0x00 0x00 0x30 | CMPR - Wii |


### Width/Height
 - Two bytes 

| Game | Width | Height | Endian | Example bytes | Out | Format |
| ----- | ----- | ----- | ------ | -------- | -------- | ------:|
| PC | 0x30 | 0x32 | Little Endian | 0x00 0x02 | 512 | All |
| Wii | 0x58 | 0x5A | Big Endian | 0x00 0x02 | 512 | 0x01 0x00 0x00 0x24 |
| Wii | 0x5C | 0x5E | Big Endian | 0x00 0x02 | 512 | 0x01 0x00 0x00 0x28 |
| Wii | 0x54 | 0x56 | Big Endian | 0x00 0x02 | 512 | 0x01 0x00 0x00 0x20 |
| Wii | 0x60 | 0x62 | Big Endian | 0x00 0x02 | 512 | 0x01 0x00 0x00 0x2C |
| Wii | 0x64 | 0x66 | Big Endian | 0x00 0x02 | 512 | 0x01 0x00 0x00 0x30 |


### Wii First Frights

Format type = 0x18 0x00 0x00 0x00
offset: 15
4 bytes

Name count
offset: 6
2 bytes

size name block
offset 9
2 bytes

after name block
padding 00 - offset 2A
2 byte width
2 byte height
skip meta - offset 2D

after name block
padding 00 - offset 2A
2 byte width
2 byte height
skip meta - offset 2D

ect.

block texture data - 0x201034 / 0x201035



### Tables for Scooby Doo -in progress


| Type      | Value PC | Value Wii Spooky Swamp | Value Wii First Frights |
| --------- | -------- | ---------------------- |----------:|
| File Name         | 0x40071 | 0x40071  | 0x40071  |
| TSETexture header | 0x41056 | 0x41033  | 0x41033  |
| TSETexture data   | 0x40057 | 0x201035 |  |
| RenderModelTemplate header | 0x101050 |
| RenderModelTemplate data | 0x40054 |
| RenderModelTemplate data table | 0x20055 |


# How To Use
- download repo
- run hunkfile_viewer.py 

# Credits
<https://github.com/desuex/hunkfile> - HNK Structure/Table
