typedef unsigned char u8;
typedef unsigned long u32;
u8 trial(void) {
    u32 *p=(u32 *)0xd62;
    *p=(*p<<1)|(*p>>31);
    __asm__ volatile("" : : : "memory");
    return (*p & 0x10000) != 0;
}
