/* Compose colours separately from live colour RAM in the isolated trial. */
#ifdef GLYPH_POOL
#define VIDEO_COLOURS 0x9400
#elif defined(STABLE_COLOURS)
#define VIDEO_COLOURS colour_work
#else
#define VIDEO_COLOURS 0x9600
#endif
