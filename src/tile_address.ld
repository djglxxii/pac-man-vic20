/* The trial changes compiler inlining in the intermission code. Keep BLK5
   within 8K by placing the existing 64-byte task dispatch table in BLK1-3.
   The base script still enforces the full stack and every pool RAM bound. */
SECTIONS {
 .tile_address_tables : { *(.rodata.arcade_tasks.func) } >ram
} INSERT BEFORE .arcade_data;
