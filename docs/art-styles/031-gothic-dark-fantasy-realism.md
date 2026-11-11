# Gothic dark-fantasy realism

Reference works: Bloodborne.

## References

- *Bloodborne* (2015), FromSoftware, video game. https://en.wikipedia.org/wiki/Bloodborne
- *Dark Souls* (2011), FromSoftware, video game. https://en.wikipedia.org/wiki/Dark_Souls_(video_game)
- *Elden Ring* (2022), FromSoftware, video game. https://en.wikipedia.org/wiki/Elden_Ring
- *Demon's Souls* (2020), Bluepoint Games, video game. https://en.wikipedia.org/wiki/Demon's_Souls_(2020_video_game)
- *Sleepy Hollow* (1999), Tim Burton, live-action film. https://en.wikipedia.org/wiki/Sleepy_Hollow_(film)

## Visual definition

- **Shape language and proportions:** Tall, narrow, vertical: spires, pointed arches, flying buttresses, iron fences, statues and gravestones packed tightly. Characters wear long coats and layered cloth.
- **Line and outline:** No outline.
- **Shading model:** Physically based and smooth, with low-key contrast and wet specular highlights on cobbles and metal.
- **Palette:** `#0e1116` `#2b3038` `#4d5560` `#7c7466` `#5c1a1a` `#a8a08c` `#1f2a33`. Blue-black night, cold grey stone, tarnished iron, with dark blood red and weak candle yellow.
- **Lighting:** Moonlight through fog as a cold rim, plus small warm lanterns. Sky is overcast or a pale moon disc.
- **Texture and surface:** Ornate carved stone, worn cobbles, wrought-iron filigree, heavy cloth weave; all weathered and damp.
- **Atmosphere and post-processing:** Thick layered fog, blue-teal grade, mild bloom on lanterns and moon, grain and vignette.
- **Camera and framing:** Third-person behind the character, 28 to 35 mm equivalent, streets framed by tall facades.
- **UI and typography:** Thin tarnished-iron frames with engraved gothic filigree around dark parchment panels; icons are etched line drawings in pale bone `#a8a08c` on blue-black `#0e1116`. Type is a high-contrast old-style serif with small capitals. Counters use the same serif, and damage numbers are small and pale, with dark blood red `#5c1a1a` for health and critical hits.
- **VFX and motion:** Dark blood sprays in arcs and stains cloth, sparks jump where steel hits stone, embers drift from lanterns and fog curls around moving figures. Motion is weighty and realistic: long wind-ups, committed swings and quick sidesteps.

## Fits

- **Genres:** `soulslike`, `hack-and-slash`, `action-adventure`, `rpg`, `survival-horror`, `exploration`
- **Moods:** oppressive, dreadful, melancholic
- **Settings:** plague-ridden Victorian city, gothic cathedral district, moonlit graveyard, ruined castle

## Unity recipe

### Assets

Gothic and Victorian-city packs: spires, pointed arches, buttresses, iron fences, statues, gravestones, cobbled streets. Keep full PBR detail (carved stone, filigree, cloth weave) at 2048 px or more. Make everything damp: raise smoothness on cobbles and metal with a wetness mask. Stretch facades vertically and pack props tightly so streets feel narrow and tall. Characters wear long coats with cloth simulation.

### Materials

`Universal Render Pipeline/Lit` with the full map set. Wet cobbles: smoothness 0.75 to 0.9 in the joints through an edited mask map. Iron is dark metal with tarnish in the albedo. Cloth uses Lit with low smoothness and a detail weave normal. Fog cards are a custom transparent unlit shader with depth fade (sample `_CameraDepthTexture` through `SampleSceneDepth`) and a scrolling noise, placed in layers down each street. No outline, no stylised ramp.

### Lighting and atmosphere

Night. A cold blue-grey directional moon light at low intensity, placed behind the scene as a rim, with soft shadows. Small warm lantern point lights with shadows on the nearest. Bake Adaptive Probe Volumes with a dim blue sky so shadows hold shape. Thick fog is the key element: exponential-squared fog in `#1f2a33`, plus the layered fog cards. A night skybox with heavy cloud or a pale moon disc. Reflection probes for wet streets. SSAO on.

### Post-processing

ACES tonemapping. Blue-teal grade through Shadows Midtones Highlights and a cool White Balance, saturation -25 but protect the red accent. Mild Bloom on lanterns and the moon, Film Grain low, Vignette 0.35. TAA. No Chromatic Aberration.

### UI and effects

Thin tarnished-iron frames with engraved filigree around dark parchment panels; icons are etched line drawings in `#a8a08c` on `#0e1116`. Font asset from a high-contrast old-style serif such as Cormorant SC or EB Garamond with small capitals; small pale damage numbers, `#5c1a1a` for health and critical hits. Effects: dark blood in arcs with cloth-staining decals, short spark showers where steel hits stone, embers rising from lanterns, and fog particles that curl around moving figures using a force field.

## Do / Do not

Do:

- Build tall pointed vertical forms.
- Backlight with cold moonlight through fog.
- Carve ornament into stone as normal relief.
- Add a few small warm lanterns.

Do not:

- Do not use modern interiors lit by a flashlight; that reads as `029`.
- Do not use daylight and bulky military forms; that reads as `030`.
- Do not reduce the scene to flat black silhouettes; that reads as `070`.
- Do not use organic ribbed machine forms; that reads as `094`.

## Nearest styles

- `029` Survival-horror dark photoreal: this style shows outdoor streets of ornate carved stone under cold moonlight and fog, in blue-black and grey; `029` shows plain, cluttered modern interiors in dirty browns, lit by a flashlight cone.
- `030` Gritty desaturated war realism: this style is a night scene with a moonlit rim, small warm lanterns and tall thin spires; `030` is overcast daylight on bulky armour and broken classical columns, almost without colour.
- `094` Biomechanical monochrome: this style is built from stone, iron and cloth with warm lantern and blood-red accents; `094` covers everything in bone-grey ribs and tubes that fuse anatomy with machinery, with no warm colour.
