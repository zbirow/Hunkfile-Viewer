# Hunkfile-Viewer
Actual tested on Monster High: NGS on PC/Wii , Barbie PC

Can dispaly Texture

In progress.....

Hunkfile Viewer (.hnk) Torus Games

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

| Game | Width | Height | Endian | Exp. bytes | Out |
| ----- | ----- | ----- | ------ | -------- | ------:|
| PC | 0x0C | 0x0E | Little Endian | 0x00 0x02 | 512 |
| Wii | 0x0C | 0x0E | Big Endian | 0x02 0x00 | 512 |

[Tool](https://www.save-editor.com/tools/wse_hex.html "Tool")


### Tables for Monster High

| Item      | Value PC | Value Wii |
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
| RenderModelTemplate data | 0x40054 |
| RenderModelTemplate data table | 0x20055 |
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

# How To Use
- download repo
- run hunkfile_viewer.py 

# Credits
<https://github.com/desuex/hunkfile> - HNK Structure/Table
