typedef unsigned char u8;
typedef unsigned long u32;
static inline void rot(u32 *v) {
    __asm__ volatile("lda %1+3\n\tasl\n\trol %1\n\trol %1+1\n\trol %1+2\n\trol %1+3" : "+m" (*v) : "i" ((unsigned short)v) : "a", "cc");
}
u8 trial(void) { u32 *v=(u32 *)0xd62; rot(v); return (*v & 0x10000) != 0; }
