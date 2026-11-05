typedef unsigned char u8;
typedef unsigned long u32;
u8 trial(void) {
    u32 *p=(u32 *)0xd62;
    *p=(*p<<1)|(*p>>31);
    return ((volatile u8 *)p)[2]&1;
}
