typedef unsigned char u8;
typedef unsigned long u32;
u8 trial(void) {
    u8 *p=(u8 *)0xd62;
    u8 carry=p[3]>>7;
    p[3]=(p[3]<<1)|(p[2]>>7);
    p[2]=(p[2]<<1)|(p[1]>>7);
    p[1]=(p[1]<<1)|(p[0]>>7);
    p[0]=(p[0]<<1)|carry;
    return p[2]&1;
}
