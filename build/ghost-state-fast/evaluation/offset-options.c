typedef unsigned char u8; typedef unsigned short u16;
typedef struct {u8 y,x;} XY;
u16 original(XY p) {p.y-=32;p.x-=32;return ((p.x<<5)+p.y+64)&1023;}
u16 reduced(XY p) {return (((u16)p.x<<5)+(u8)(p.y-32)+64)&1023;}
u16 split(XY p) {u16 a=(u8)(p.y-32)+64; a+=(u8)(p.x<<5);u8 hi=(p.x>>3)+(a>>8);return (u8)a|((u16)(hi&3)<<8);}
u16 byte_add(XY p) {u8 a=p.y-32; u8 lo=(p.x<<5); u8 hi=p.x>>3;u8 sum=a+64;hi+=sum<a;lo+=sum;hi+=lo<sum;return lo|((u16)(hi&3)<<8);}
