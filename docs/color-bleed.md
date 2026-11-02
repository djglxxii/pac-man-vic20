Yes. On the VIC-20, "colour bleeding" (attribute clash) comes from one rule: each 8×8 cell has only one colour of its own. You can't remove that rule, but you can design around it.

**1. Split the palette between globals and cells**
- In a multicolour cell, three of the four colours are global: background, border and aux. Only one comes from colour RAM.
- Put the colours that appear everywhere into the globals, such as black outlines, a shadow shade or a sky colour. Use the per-cell colour as the accent.
- Done this way, most tiles look right in any cell, and clash only shows where two accent colours meet.

**2. Draw sprites in global colours only**
This is the most useful trick for games:
- Background tiles use only background plus the cell's own colour.
- Sprites use only the border and aux bit pairs.

A sprite can then cross any cell without touching colour RAM, so it never bleeds. The catch is that every sprite shares the same two colours. Simpler versions are one-colour sprites drawn in the background colour (a "cut-out" look) or in a global outline colour.

**3. Mix hires and multicolour cells**
Bit 3 of colour RAM is set per cell. Use hires cells for text, thin lines and fine detail, and multicolour cells for colourful areas. A cell boundary is a natural place for the colour to change, so design tiles with that edge in mind.

**4. Line up colour edges with the 8×8 grid**
- Draw the background art on a grid. Put colour changes exactly on cell edges, and keep each cell to background plus one colour.
- Use a gap of plain background cells between differently coloured objects.
- Make movement lanes, such as a corridor, sky or playfield, one colour-RAM value throughout. Sprites can then move freely within them.

**5. Accept the clash, but control it**
If a sprite must have its own colour:
- Write its colour into the cells it covers, and restore those cells after it moves.
- Change colour RAM in the same page flip as the screen. Flipping $9002 bit 7 switches both, so colour and shape never get out of step, which would look like flicker or tearing.
- Make the sprite's colour also work on the background tiles it usually crosses.

**6. Change the global colours partway down the screen**
A raster split, which can be a simple $9004 poll or a stable VIA-timer interrupt, can change background, border and aux in different bands of the screen, such as a status bar, sky, ground or water. This gives you more global colours per zone without touching colour RAM. With a fully stable raster you can even change them every line, as Robotic Liberation does.

**7. Avoid NTSC artifact colours too**
On an NTSC machine over composite or RF video, single-pixel-wide vertical hires lines can pick up false colour fringes. Two-pixel-wide strokes or multicolour (double-wide) pixels avoid this. Check this on real hardware or an emulator with CRT/NTSC filtering, because a sharp emulator display won't show it.

**Workflow tips**
- Mock up a screen and its tile set as an image with a visible 8×8 grid, and allow each cell only its legal colours. MINIPAINT on the VIC itself, or a VIC-20-aware character editor, enforces this for you.
- Choose the global colours before you draw any tiles. Changing them later breaks every tile.
- Test the exact multicolour bit-pair mapping in your emulator first. As noted in the report, sources disagree about which of `01`/`10` is border and which is cell colour.
