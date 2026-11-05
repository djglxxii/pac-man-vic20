/*
 * vicsim - minimal headless VIC-20 (NTSC) test harness.
 *
 * Emulates a 6502 with flat 64K RAM, the VIC raster counter, joystick
 * ports, and renders the VIC text display to PPM.  It has no ROMs: the
 * program is started directly at a given address.  Good enough to run
 * the native Pac-Man port and its VIA timer IRQ for automated tests.
 *
 * usage: vicsim PRG START_HEX SCRIPT [LABELS]
 * script commands (one per line, '#' comments):
 *   run N            run N frames
 *   joy STR          set joystick: any of U D L R F, or '-' for none
 *   shot FILE        write screen to PPM
 *   peek ADDR|LABEL [N]  print bytes
 *   poke ADDR VAL
 *   timing on|off    print per-frame busy cycles (needs label "frame_wait")
 *   sound on|off     print sound register writes per frame
 *   until LABEL N    run until PC hits label (max N frames)
 *   profile reset|off|FILE  collect instruction cycles and execution counts
 *   call LABEL [A X] execute a subroutine in isolation, retaining CPU state
 *   watch LABEL NAME trace a routine's entry and return without guest overhead
 *   stack reset      start measuring guest stack stores (host pokes excluded)
 *   stack            report lowest software/hardware stack stores as JSON
 *   boot             report startup entries and release status as JSON
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>

static uint8_t mem[65536];
static uint16_t pc;
static uint8_t a, x, y, sp, p;
static uint64_t cycles;
static uint64_t profile_cycles[65536], profile_hits[65536];
static int profiling;
static FILE *profile_trace;
static uint16_t render_begin_addr, render_end_addr, audio_addr;
static uint16_t flash_request_addr, flash_present_addr;
static uint16_t dirty_addr, rebuild_addr, bulk_active_addr, bulk_task_addr;
static uint16_t erase_addr, draw_addr, ghost_addr, sprite_save_addr, under_addr;
static uint16_t beam_begin_addr, beam_end_addr, beam_index_addr, beam_mask_addr;
static uint16_t beam_early_addr, beam_top_addr, beam_bottom_addr, beam_budget_addr;
static uint16_t c_stack_low = 0x2000, hw_stack_low = 0x0200;
static uint16_t c_stack_bottom = 0x1d40;
static int stack_tracking;
static uint16_t boot_addr, boot_limit, main_addr;
static unsigned boot_entries;
static int boot_released;
static struct {
    uint16_t entry, ret;
    uint8_t return_sp;
    int active;
    char name[64];
} watches[24];
static unsigned watch_count;
#define CYC_LINE 65
#define LINES 261
#define CYC_FRAME (CYC_LINE * LINES)

enum { FC = 1, FZ = 2, FI = 4, FD = 8, FB = 16, FU = 32, FV = 64, FN = 128 };
static uint8_t joy;       /* bit0 up 1 down 2 left 3 right 4 fire (1 = pressed) */
static uint8_t keys, via2_ier;
static uint16_t timer_latch;
static uint64_t timer_epoch, timer_ack;
static int timer_running;
static uint64_t timer_periods(void) {
    return timer_running ? (cycles - timer_epoch) / ((unsigned)timer_latch + 2) : 0;
}
static int timer_pending(void) { return timer_running && timer_periods() > timer_ack; }

static int nlabels;
static struct { char name[64]; uint16_t addr; } labels[8192];

static int find_label(const char *n, uint16_t *out) {
    for (int i = 0; i < nlabels; i++)
        if (!strcmp(labels[i].name, n)) { *out = labels[i].addr; return 1; }
    return 0;
}

static unsigned raster_line(void) { return (unsigned)((cycles / CYC_LINE) % LINES); }

static uint8_t rd(uint16_t addr) {
    if (addr >= 0x9000 && addr < 0x9010) {
        unsigned l = raster_line();
        if (addr == 0x9004) return (uint8_t)(l >> 1);
        if (addr == 0x9003) return (uint8_t)((mem[addr] & 0x7f) | ((l & 1) << 7));
        return mem[addr];
    }
    if (addr == 0x9111 || addr == 0x911f) {
        uint8_t v = 0xff;
        if (joy & 1) v &= ~0x04;
        if (joy & 2) v &= ~0x08;
        if (joy & 4) v &= ~0x10;
        if (joy & 16) v &= ~0x20;
        return v;
    }
    if (addr == 0x9120) {
        uint8_t v = 0xff;
        if ((joy & 8) && !(mem[0x9122] & 0x80)) v &= ~0x80;
        return v;
    }
    if (addr == 0x9121) {
        uint8_t v = 255;
        if (!(mem[0x9120] & 1)) { if (keys & 1) v &= ~1; if (keys & 2) v &= ~128; }
        if (!(mem[0x9120] & 4) && (keys & 4)) v &= ~1;
        return v;
    }
    if (addr == 0x9124 || addr == 0x9125) {
        unsigned elapsed = timer_running ? (cycles - timer_epoch) % ((unsigned)timer_latch + 2) : 0;
        uint16_t count = timer_latch - elapsed;
        if (addr == 0x9124) { timer_ack = timer_periods(); return count; }
        return count >> 8;
    }
    if (addr == 0x912d) return timer_pending() ? (0x40 | ((via2_ier & 0x40) ? 0x80 : 0)) : 0;
    if (addr == 0x912e) return via2_ier | 128;
    return mem[addr];
}

static int sound_log;
static uint8_t sndregs[16];
static void wr(uint16_t addr, uint8_t v) {
    /* Actual guest stores avoid torn software-SP values and loader pointers
       that temporarily occupy LLVM-MOS's software-SP zero-page addresses. */
    if (stack_tracking) {
        if (addr >= c_stack_bottom && addr < c_stack_low) c_stack_low = addr;
        if (addr >= 0x0100 && addr < hw_stack_low) hw_stack_low = addr;
    }
    if (profile_trace && dirty_addr && addr == dirty_addr && v == 2)
        fprintf(profile_trace, "%llu rebuild-request\n", (unsigned long long)cycles);
    if (profile_trace && rebuild_addr && addr == rebuild_addr && mem[addr] != v)
        fprintf(profile_trace, "%llu rebuild-phase-%u\n", (unsigned long long)cycles, v);
    if (profile_trace && bulk_active_addr && addr == bulk_active_addr && mem[addr] != v)
        fprintf(profile_trace, "%llu task-%u-%s\n", (unsigned long long)cycles, mem[bulk_task_addr], v ? "begin" : "end");
    if (addr >= 0x8000 && addr < 0x9000) return;     /* char ROM */
    if (addr >= 0xc000) return;                        /* BASIC/KERNAL ROM */
    if (addr >= 0x9400 && addr < 0x9800) v &= 0x0f;   /* colour nibbles */
    if (addr >= 0x900a && addr <= 0x900e) sndregs[addr - 0x9000] = v;
    if (addr == 0x9124 || addr == 0x9126) timer_latch = (timer_latch & 0xff00) | v;
    if (addr == 0x9125 || addr == 0x9127) {
        timer_latch = (timer_latch & 255) | ((unsigned)v << 8);
        if (addr == 0x9125) { timer_epoch = cycles; timer_ack = 0; timer_running = 1; }
    }
    if (addr == 0x912e) { if (v & 128) via2_ier |= v & 127; else via2_ier &= ~v; }
    mem[addr] = v;
}

static void push(uint8_t v) { wr(0x100 + sp--, v); }
static uint8_t pop(void) { return rd(0x100 + ++sp); }
static void setnz(uint8_t v) { p = (p & ~(FN | FZ)) | (v & FN) | (v ? 0 : FZ); }

static void adc(uint8_t v) {
    if (p & FD) {
        unsigned lo = (a & 0x0f) + (v & 0x0f) + (p & FC);
        unsigned hi = (a & 0xf0) + (v & 0xf0);
        if (lo > 9) { lo += 6; }
        if (lo > 0x0f) hi += 0x10;
        uint8_t bin = (uint8_t)(a + v + (p & FC));
        p &= ~(FZ | FN | FV | FC);
        if (!bin) p |= FZ;
        if (hi & 0x80) p |= FN;
        if (~(a ^ v) & (a ^ hi) & 0x80) p |= FV;
        if (hi > 0x90) hi += 0x60;
        if (hi > 0xff) p |= FC;
        a = (uint8_t)((lo & 0x0f) | (hi & 0xf0));
    } else {
        unsigned r = a + v + (p & FC);
        p &= ~(FC | FV);
        if (r > 0xff) p |= FC;
        if (~(a ^ v) & (a ^ r) & 0x80) p |= FV;
        a = (uint8_t)r;
        setnz(a);
    }
}
static void sbc(uint8_t v) {
    if (p & FD) {
        unsigned c = (p & FC) ? 0 : 1;
        unsigned r = a - v - c;
        int lo = (a & 0x0f) - (v & 0x0f) - (int)c;
        int hi = (a >> 4) - (v >> 4);
        if (lo < 0) { lo += 10; hi--; }
        if (hi < 0) hi += 10;
        p &= ~(FC | FV | FZ | FN);
        if (r < 0x100) p |= FC;
        if ((a ^ v) & (a ^ r) & 0x80) p |= FV;
        if (!(uint8_t)r) p |= FZ;
        if (r & 0x80) p |= FN;
        a = (uint8_t)(((hi & 0x0f) << 4) | (lo & 0x0f));
    } else {
        adc(v ^ 0xff);
    }
}
static void cmp(uint8_t r, uint8_t v) {
    unsigned t = r - v;
    p = (p & ~FC) | (r >= v ? FC : 0);
    setnz((uint8_t)t);
}

static uint16_t rd16(uint16_t ad) { return rd(ad) | (rd((uint16_t)(ad + 1)) << 8); }
static uint16_t rd16zp(uint8_t ad) { return rd(ad) | (rd((uint8_t)(ad + 1)) << 8); }

static int illegal;

static void step(void) {
    uint16_t instruction_pc = pc;
    if (profile_trace && beam_begin_addr && pc == beam_begin_addr) {
        unsigned group = mem[beam_index_addr];
        fprintf(profile_trace, "%llu beam-begin-%u-%u-%u-%u-%u\n",
                (unsigned long long)cycles, mem[beam_mask_addr],
                mem[beam_early_addr + group], mem[beam_top_addr + group],
                mem[beam_bottom_addr + group], mem[beam_budget_addr + group]);
    }
    if (profile_trace && beam_end_addr && pc == beam_end_addr)
        fprintf(profile_trace, "%llu beam-end\n", (unsigned long long)cycles);
    /* main takes over only after the temporary startup call has returned.
       Guard the released screen-RAM window for every native regression run. */
    if (boot_addr) {
        if (pc == boot_addr) boot_entries++;
        if (pc == main_addr) boot_released = 1;
        if (boot_released && pc >= boot_addr && pc < boot_limit) {
            fprintf(stderr, "Executed released startup RAM at $%04x\n", pc);
            illegal = 1;
            return;
        }
    }
    /* Host-only observation: identify each actor without adding guest cycles.
       Keep two-column trace records compatible with the other profilers. */
    if (profile_trace && sprite_save_addr && under_addr &&
        (pc == erase_addr || pc == draw_addr || pc == ghost_addr)) {
        int offset = (int)rd16(sprite_save_addr) - under_addr - 8;
        if (offset >= 0 && offset < 216 && offset % 36 == 0)
            fprintf(profile_trace, "%llu actor-%d-%s\n",
                    (unsigned long long)cycles, offset / 36,
                    pc == erase_addr ? "erase" : "paint");
    }
    if (profile_trace) for (unsigned i = 0; i < watch_count; i++) {
        if (watches[i].active && pc == watches[i].ret && sp == watches[i].return_sp) {
            fprintf(profile_trace, "%llu %s-end\n", (unsigned long long)cycles, watches[i].name);
            watches[i].active = 0;
        }
        if (!watches[i].active && pc == watches[i].entry) {
            watches[i].ret = (uint16_t)(mem[0x100 + (uint8_t)(sp + 1)] |
                                (mem[0x100 + (uint8_t)(sp + 2)] << 8)) + 1;
            watches[i].return_sp = sp + 2;
            watches[i].active = 1;
            fprintf(profile_trace, "%llu %s-begin\n", (unsigned long long)cycles, watches[i].name);
        }
    }
    if (profile_trace && flash_request_addr && pc == flash_request_addr)
        fprintf(profile_trace, "%llu flash-%s\n", (unsigned long long)cycles, a == 2 ? "blue" : "white");
    if (profile_trace && flash_present_addr && pc == flash_present_addr)
        fprintf(profile_trace, "%llu present-%s\n", (unsigned long long)cycles, (mem[0x960e] & 7) == 6 ? "blue" : "white");
    if (profile_trace && (pc == render_begin_addr || pc == render_end_addr || pc == audio_addr))
        fprintf(profile_trace, "%llu %s\n", (unsigned long long)cycles,
                pc == audio_addr ? "logic" : pc == render_begin_addr ? "begin" : "end");
    uint8_t op = rd(pc++);
    uint16_t ad = 0;
    uint8_t v;
    int c = 2;
#define IMM ad = pc++;
#define ZP  ad = rd(pc++);
#define ZPX ad = (uint8_t)(rd(pc++) + x);
#define ZPY ad = (uint8_t)(rd(pc++) + y);
#define ABS ad = rd16(pc); pc += 2;
#define ABX { uint16_t b = rd16(pc); pc += 2; ad = b + x; if ((b ^ ad) & 0xff00) c++; }
#define ABY { uint16_t b = rd16(pc); pc += 2; ad = b + y; if ((b ^ ad) & 0xff00) c++; }
#define ABXW { uint16_t b = rd16(pc); pc += 2; ad = b + x; }
#define ABYW { uint16_t b = rd16(pc); pc += 2; ad = b + y; }
#define IZX ad = rd16zp((uint8_t)(rd(pc++) + x));
#define IZY { uint16_t b = rd16zp(rd(pc++)); ad = b + y; if ((b ^ ad) & 0xff00) c++; }
#define IZYW { uint16_t b = rd16zp(rd(pc++)); ad = b + y; }
#define BR(cond) { int8_t o = (int8_t)rd(pc++); if (cond) { uint16_t n = pc + o; c += 1 + (((n ^ pc) & 0xff00) ? 1 : 0); pc = n; } }
    switch (op) {
    /* LDA */
    case 0xa9: IMM a = rd(ad); setnz(a); c = 2; break;
    case 0xa5: ZP  a = rd(ad); setnz(a); c = 3; break;
    case 0xb5: ZPX a = rd(ad); setnz(a); c = 4; break;
    case 0xad: ABS a = rd(ad); setnz(a); c = 4; break;
    case 0xbd: c = 4; ABX a = rd(ad); setnz(a); break;
    case 0xb9: c = 4; ABY a = rd(ad); setnz(a); break;
    case 0xa1: IZX a = rd(ad); setnz(a); c = 6; break;
    case 0xb1: c = 5; IZY a = rd(ad); setnz(a); break;
    /* LDX */
    case 0xa2: IMM x = rd(ad); setnz(x); c = 2; break;
    case 0xa6: ZP  x = rd(ad); setnz(x); c = 3; break;
    case 0xb6: ZPY x = rd(ad); setnz(x); c = 4; break;
    case 0xae: ABS x = rd(ad); setnz(x); c = 4; break;
    case 0xbe: c = 4; ABY x = rd(ad); setnz(x); break;
    /* LDY */
    case 0xa0: IMM y = rd(ad); setnz(y); c = 2; break;
    case 0xa4: ZP  y = rd(ad); setnz(y); c = 3; break;
    case 0xb4: ZPX y = rd(ad); setnz(y); c = 4; break;
    case 0xac: ABS y = rd(ad); setnz(y); c = 4; break;
    case 0xbc: c = 4; ABX y = rd(ad); setnz(y); break;
    /* STA */
    case 0x85: ZP  wr(ad, a); c = 3; break;
    case 0x95: ZPX wr(ad, a); c = 4; break;
    case 0x8d: ABS wr(ad, a); c = 4; break;
    case 0x9d: ABXW wr(ad, a); c = 5; break;
    case 0x99: ABYW wr(ad, a); c = 5; break;
    case 0x81: IZX wr(ad, a); c = 6; break;
    case 0x91: IZYW wr(ad, a); c = 6; break;
    /* STX/STY */
    case 0x86: ZP  wr(ad, x); c = 3; break;
    case 0x96: ZPY wr(ad, x); c = 4; break;
    case 0x8e: ABS wr(ad, x); c = 4; break;
    case 0x84: ZP  wr(ad, y); c = 3; break;
    case 0x94: ZPX wr(ad, y); c = 4; break;
    case 0x8c: ABS wr(ad, y); c = 4; break;
    /* transfers */
    case 0xaa: x = a; setnz(x); break;
    case 0xa8: y = a; setnz(y); break;
    case 0x8a: a = x; setnz(a); break;
    case 0x98: a = y; setnz(a); break;
    case 0xba: x = sp; setnz(x); break;
    case 0x9a: sp = x; break;
    /* stack */
    case 0x48: push(a); c = 3; break;
    case 0x08: push(p | FB | FU); c = 3; break;
    case 0x68: a = pop(); setnz(a); c = 4; break;
    case 0x28: p = pop() | FU; c = 4; break;
    /* logic */
#define LOGIC(base, OPX) \
    case base + 0x09: IMM a OPX rd(ad); setnz(a); c = 2; break; \
    case base + 0x05: ZP  a OPX rd(ad); setnz(a); c = 3; break; \
    case base + 0x15: ZPX a OPX rd(ad); setnz(a); c = 4; break; \
    case base + 0x0d: ABS a OPX rd(ad); setnz(a); c = 4; break; \
    case base + 0x1d: c = 4; ABX a OPX rd(ad); setnz(a); break; \
    case base + 0x19: c = 4; ABY a OPX rd(ad); setnz(a); break; \
    case base + 0x01: IZX a OPX rd(ad); setnz(a); c = 6; break; \
    case base + 0x11: c = 5; IZY a OPX rd(ad); setnz(a); break;
    LOGIC(0x00, |=)
    LOGIC(0x20, &=)
    LOGIC(0x40, ^=)
    /* ADC/SBC/CMP */
#define ARITH(base, FN_) \
    case base + 0x09: IMM FN_(rd(ad)); c = 2; break; \
    case base + 0x05: ZP  FN_(rd(ad)); c = 3; break; \
    case base + 0x15: ZPX FN_(rd(ad)); c = 4; break; \
    case base + 0x0d: ABS FN_(rd(ad)); c = 4; break; \
    case base + 0x1d: c = 4; ABX FN_(rd(ad)); break; \
    case base + 0x19: c = 4; ABY FN_(rd(ad)); break; \
    case base + 0x01: IZX FN_(rd(ad)); c = 6; break; \
    case base + 0x11: c = 5; IZY FN_(rd(ad)); break;
#define CMPA(v) cmp(a, v)
    ARITH(0x60, adc)
    ARITH(0xe0, sbc)
    ARITH(0xc0, CMPA)
    case 0xe0: IMM cmp(x, rd(ad)); c = 2; break;
    case 0xe4: ZP  cmp(x, rd(ad)); c = 3; break;
    case 0xec: ABS cmp(x, rd(ad)); c = 4; break;
    case 0xc0: IMM cmp(y, rd(ad)); c = 2; break;
    case 0xc4: ZP  cmp(y, rd(ad)); c = 3; break;
    case 0xcc: ABS cmp(y, rd(ad)); c = 4; break;
    /* BIT */
    case 0x24: ZP  v = rd(ad); p = (p & ~(FN | FV | FZ)) | (v & (FN | FV)) | ((a & v) ? 0 : FZ); c = 3; break;
    case 0x2c: ABS v = rd(ad); p = (p & ~(FN | FV | FZ)) | (v & (FN | FV)) | ((a & v) ? 0 : FZ); c = 4; break;
    /* INC/DEC */
#define RMW(opc_zp, opc_zpx, opc_abs, opc_abx, EXPR) \
    case opc_zp:  ZP  v = rd(ad); EXPR; wr(ad, v); c = 5; break; \
    case opc_zpx: ZPX v = rd(ad); EXPR; wr(ad, v); c = 6; break; \
    case opc_abs: ABS v = rd(ad); EXPR; wr(ad, v); c = 6; break; \
    case opc_abx: ABXW v = rd(ad); EXPR; wr(ad, v); c = 7; break;
    RMW(0xe6, 0xf6, 0xee, 0xfe, { v++; setnz(v); })
    RMW(0xc6, 0xd6, 0xce, 0xde, { v--; setnz(v); })
    RMW(0x06, 0x16, 0x0e, 0x1e, { p = (p & ~FC) | (v >> 7); v <<= 1; setnz(v); })
    RMW(0x46, 0x56, 0x4e, 0x5e, { p = (p & ~FC) | (v & 1); v >>= 1; setnz(v); })
    RMW(0x26, 0x36, 0x2e, 0x3e, { uint8_t ci = p & FC; p = (p & ~FC) | (v >> 7); v = (uint8_t)((v << 1) | ci); setnz(v); })
    RMW(0x66, 0x76, 0x6e, 0x7e, { uint8_t ci = p & FC; p = (p & ~FC) | (v & 1); v = (uint8_t)((v >> 1) | (ci << 7)); setnz(v); })
    case 0x0a: p = (p & ~FC) | (a >> 7); a <<= 1; setnz(a); break;
    case 0x4a: p = (p & ~FC) | (a & 1); a >>= 1; setnz(a); break;
    case 0x2a: { uint8_t ci = p & FC; p = (p & ~FC) | (a >> 7); a = (uint8_t)((a << 1) | ci); setnz(a); } break;
    case 0x6a: { uint8_t ci = p & FC; p = (p & ~FC) | (a & 1); a = (uint8_t)((a >> 1) | (ci << 7)); setnz(a); } break;
    case 0xe8: x++; setnz(x); break;
    case 0xca: x--; setnz(x); break;
    case 0xc8: y++; setnz(y); break;
    case 0x88: y--; setnz(y); break;
    /* flags */
    case 0x18: p &= ~FC; break;
    case 0x38: p |= FC; break;
    case 0x58: p &= ~FI; break;
    case 0x78: p |= FI; break;
    case 0xb8: p &= ~FV; break;
    case 0xd8: p &= ~FD; break;
    case 0xf8: p |= FD; break;
    /* branches */
    case 0x10: BR(!(p & FN)) break;
    case 0x30: BR(p & FN) break;
    case 0x50: BR(!(p & FV)) break;
    case 0x70: BR(p & FV) break;
    case 0x90: BR(!(p & FC)) break;
    case 0xb0: BR(p & FC) break;
    case 0xd0: BR(!(p & FZ)) break;
    case 0xf0: BR(p & FZ) break;
    /* jumps */
    case 0x4c: pc = rd16(pc); c = 3; break;
    case 0x6c: { uint16_t ia = rd16(pc); pc = rd(ia) | (rd((ia & 0xff00) | ((ia + 1) & 0xff)) << 8); c = 5; } break;
    case 0x20: { uint16_t t = rd16(pc); pc++; push(pc >> 8); push(pc & 0xff); pc = t; c = 6; } break;
    case 0x60: { uint16_t t = pop(); t |= pop() << 8; pc = t + 1; c = 6; } break;
    case 0x40: { p = pop() | FU; uint16_t t = pop(); t |= pop() << 8; pc = t; c = 6; } break;
    case 0xea: break;
    case 0x00: pc++; push(pc >> 8); push(pc & 0xff); push(p | FB | FU); p |= FI; pc = rd16(0xfffe); c = 7; break;
    default:
        illegal = 1;
        fprintf(stderr, "illegal opcode $%02X at $%04X\n", op, (uint16_t)(pc - 1));
        break;
    }
    cycles += c;
    if (profiling) { profile_cycles[instruction_pc] += c; profile_hits[instruction_pc]++; }
}

/* ---------------------------------------------------------------- render */
static const uint8_t palette[16][3] = {
    {0,0,0},{255,255,255},{182,31,33},{77,240,255},{180,63,255},{68,226,55},{26,52,255},{220,215,27},
    {202,84,0},{233,176,114},{231,146,147},{154,247,253},{224,159,255},{143,228,147},{130,144,255},{229,222,133}};

static void shot(const char *fn) {
    int cols = mem[0x9002] & 0x7f, rows = (mem[0x9003] >> 1) & 0x3f, tall = mem[0x9003] & 1;
    uint8_t r5 = mem[0x9005];
    uint16_t scr = ((r5 & 0x70) << 6) | ((~r5 & 0x80) << 8) | ((mem[0x9002] & 0x80) << 2);
    uint16_t chr = ((r5 & 0x07) << 10) | ((~r5 & 0x08) << 12);
    uint16_t colr = 0x9400 + ((mem[0x9002] & 0x80) ? 0x200 : 0);
    int bg = mem[0x900f] >> 4, border = mem[0x900f] & 7, aux = mem[0x900e] >> 4;
    int chh = tall ? 16 : 8;
    int B = 8, SX = 3, SY = 2;
    int w = (cols * 8 + 2 * B) * SX, h = (rows * chh + 2 * B) * SY;
    FILE *f = fopen(fn, "wb");
    if (!f) { perror(fn); return; }
    fprintf(f, "P6\n%d %d\n255\n", w, h);
    for (int py = 0; py < rows * chh + 2 * B; py++) {
        for (int sy = 0; sy < SY; sy++) {
            for (int px = 0; px < cols * 8 + 2 * B; px++) {
                int ci = border;
                int dx = px - B, dy = py - B;
                if (dx >= 0 && dy >= 0 && dx < cols * 8 && dy < rows * chh) {
                    int cell = (dy / chh) * cols + dx / 8;
                    uint8_t code = mem[(uint16_t)(scr + cell)];
                    uint8_t cc = mem[colr + cell] & 0x0f;
                    uint16_t ga = (uint16_t)(chr + code * chh + (dy % chh));
                    /* VIC address wrap: chars at $1C00+ beyond $1FFF wrap to $8000 */
                    if (ga >= 0x2000 && ga < 0x3000) ga = (uint16_t)(ga - 0x2000 + 0x8000);
                    uint8_t g = mem[ga];
                    int bit = dx & 7;
                    if (cc & 8) {
                        int pair = (g >> (6 - (bit & 6))) & 3;
                        ci = pair == 0 ? bg : pair == 1 ? border : pair == 2 ? (cc & 7) : aux;
                    } else {
                        ci = ((g >> (7 - bit)) & 1) ? (cc & 7) : bg;
                    }
                }
                for (int sx = 0; sx < SX; sx++) fwrite(palette[ci], 1, 3, f);
            }
        }
    }
    fclose(f);
}

/* ---------------------------------------------------------------- main */
static uint16_t parse_addr(const char *s) {
    uint16_t v;
    if (s[0] == '$') return (uint16_t)strtoul(s + 1, 0, 16);
    if (isdigit((unsigned char)s[0])) return (uint16_t)strtoul(s, 0, 0);
    if (find_label(s, &v)) return v;
    fprintf(stderr, "unknown label %s\n", s);
    exit(2);
}

static int timing;
static uint16_t wait_addr;
static int have_wait;
static uint16_t tick_addr;
static int have_tick;
static uint64_t frame_no;

static void run_frames(long n, int stop_at, uint16_t stop_pc) {
    uint64_t end = (cycles / CYC_FRAME + n) * CYC_FRAME;
    uint64_t fstart = cycles / CYC_FRAME;
    int marked = 0;
    while (cycles < end) {
        if (!(p & FI) && (via2_ier & 0x40) && timer_pending()) {
            push(pc >> 8); push(pc); push(p & ~FB); p |= FI;
            pc = rd16(0xfffe); cycles += 7;
        }
        if (have_wait && pc == wait_addr && !marked) {
            marked = 1;
            if (timing) {
                printf("frame %llu: busy until line %u (%llu cyc into frame)\n",
                       (unsigned long long)(cycles / CYC_FRAME), raster_line(),
                       (unsigned long long)(cycles % CYC_FRAME));
            }
        }
        if (stop_at == 1 && pc == stop_pc) { printf("hit $%04X at frame %llu\n", stop_pc, (unsigned long long)(cycles / CYC_FRAME)); return; }
        if (stop_at == 2 && rd16(tick_addr) == stop_pc) { printf("hit tick %u at frame %llu\n", stop_pc, (unsigned long long)(cycles / CYC_FRAME)); return; }
        uint16_t opc = pc;
        step();
        if (pc == opc && getenv("TRAPSTOP")) { printf("trap at $%04X\n", pc); exit(3); }
        if (illegal) { printf("CPU halted. A=%02X X=%02X Y=%02X SP=%02X P=%02X\n", a, x, y, sp, p); exit(1); }
        uint64_t f = cycles / CYC_FRAME;
        if (f != fstart) {
            fstart = f; marked = 0; frame_no++;
            if (sound_log) {
                printf("snd f%llu: %02X %02X %02X %02X vol %X\n", (unsigned long long)f,
                       sndregs[0xa], sndregs[0xb], sndregs[0xc], sndregs[0xd], sndregs[0xe] & 15);
            }
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: vicsim PRG START SCRIPT [LABELS]\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    int lo = fgetc(f), hi = fgetc(f);
    uint16_t la = (uint16_t)(lo | (hi << 8));
    size_t n = fread(mem + la, 1, 65536 - la, f);
    fclose(f);
    fprintf(stderr, "loaded $%04X-$%04X\n", la, (unsigned)(la + n - 1));
    if (argc > 4) {
        FILE *lf = fopen(argv[4], "r");
        char line[256];
        while (lf && fgets(line, sizeof line, lf)) {
            unsigned v; char nm[128];
            if (sscanf(line, "al %x .%127s", &v, nm) == 2 && nlabels < 8192) {
                snprintf(labels[nlabels].name, sizeof labels[nlabels].name, "%.63s", nm);
                labels[nlabels++].addr = (uint16_t)v;
            }
        }
        if (lf) fclose(lf);
        have_wait = find_label("frame_wait", &wait_addr);
        have_tick = find_label("arcade_ticks", &tick_addr);
        find_label("video_frame_begin", &render_begin_addr);
        find_label("video_frame_end", &render_end_addr);
        find_label("bitmap_erase", &erase_addr);
        find_label("bitmap_draw", &draw_addr);
        find_label("bitmap_draw_ghost", &ghost_addr);
        find_label("v_save", &sprite_save_addr);
        find_label("under", &under_addr);
        find_label("beam_group_begin", &beam_begin_addr);
        find_label("beam_group_end", &beam_end_addr);
        find_label("beam_group", &beam_index_addr);
        find_label("beam_mask", &beam_mask_addr);
        find_label("beam_early", &beam_early_addr);
        find_label("beam_tops", &beam_top_addr);
        find_label("beam_ends", &beam_bottom_addr);
        find_label("beam_budgets", &beam_budget_addr);
        find_label("boot_start", &boot_addr);
        find_label("__boot_limit", &boot_limit);
        find_label("main", &main_addr);
        find_label("__stack_bottom", &c_stack_bottom);
        find_label("audio_update", &audio_addr);
        find_label("video_flash_palette", &flash_request_addr);
        find_label("maze_colour_done", &flash_present_addr);
        find_label("full_dirty", &dirty_addr);
        find_label("rebuild_phase", &rebuild_addr);
        find_label("bulk_active", &bulk_active_addr);
        find_label("bulk_task", &bulk_task_addr);
    }
    mem[0x9002] = 0x96; mem[0x9003] = 0x2e; mem[0x9005] = 0xf0; mem[0x900f] = 0x1b;
    mem[0x9122] = 0xff;
    /* The VIC KERNAL saves A/X/Y before dispatching the RAM IRQ vector.
       Tests need this entry convention, rather than a complete KERNAL ROM. */
    const uint8_t irq_stub[] = {0x48,0x8a,0x48,0x98,0x48,0x6c,0x14,0x03};
    memcpy(mem + 0xff72, irq_stub, sizeof irq_stub);
    mem[0xfffe] = 0x72; mem[0xffff] = 0xff;
    pc = parse_addr(argv[2]);
    sp = 0xfd; p = FU | FI;
    FILE *sf = strcmp(argv[3], "-") ? fopen(argv[3], "r") : stdin;
    if (!sf) { perror(argv[3]); return 1; }
    char line[256];
    while (fgets(line, sizeof line, sf)) {
        char cmd[32], a1[128], a2[64];
        a1[0] = a2[0] = 0;
        int k = sscanf(line, "%31s %127s %63s", cmd, a1, a2);
        if (k < 1 || cmd[0] == '#') continue;
        if (!strcmp(cmd, "run")) run_frames(atol(a1), 0, 0);
        else if (!strcmp(cmd, "call")) {
            uint64_t call_cycles = cycles;
            uint16_t saved_pc = pc;
            uint8_t saved_a = a, saved_x = x, saved_y = y, saved_sp = sp, saved_p = p;
            unsigned av = 0, xv = 0;
            sscanf(line, "%*s %*s %u %u", &av, &xv);
            a = av; x = xv; p |= FI;
            push(0xff); push(0xef); pc = parse_addr(a1);
            unsigned count = 0;
            while (pc != 0xfff0 && !illegal && count++ < 1000000) step();
            if (pc != 0xfff0) { fprintf(stderr, "call did not return: %s", line); return 1; }
            printf("returned %02x %02x cycles=%llu\n", a, x, (unsigned long long)(cycles-call_cycles));
            pc = saved_pc; a = saved_a; x = saved_x; y = saved_y; sp = saved_sp; p = saved_p;
        }
        else if (!strcmp(cmd, "until")) run_frames(atol(a2), 1, parse_addr(a1));
        else if (!strcmp(cmd, "tick") && have_tick) run_frames(10000, 2, (uint16_t)strtoul(a1, 0, 0));
        else if (!strcmp(cmd, "joy")) {
            joy = 0;
            for (char *c = a1; *c; c++) {
                if (*c == 'U') joy |= 1; if (*c == 'D') joy |= 2;
                if (*c == 'L') joy |= 4; if (*c == 'R') joy |= 8; if (*c == 'F') joy |= 16;
            }
        } else if (!strcmp(cmd, "key")) {
            keys = 0;
            if (strchr(a1, '1')) keys |= 1;
            if (strchr(a1, '2')) keys |= 2;
            if (strchr(a1, '5')) keys |= 4;
        } else if (!strcmp(cmd, "shot")) shot(a1);
        else if (!strcmp(cmd, "load")) {
            FILE *lf = fopen(a2, "rb");
            if (!lf) { perror(a2); return 1; }
            uint16_t ad = parse_addr(a1);
            size_t loaded = fread(mem + ad, 1, 65536 - ad, lf);
            if (loaded < 65536 - ad && ferror(lf)) { perror(a2); fclose(lf); return 1; }
            fclose(lf);
        } else if (!strcmp(cmd, "dump")) {
            FILE *df = fopen(a1, "wb");
            if (!df) { perror(a1); return 1; }
            fwrite(mem, 1, sizeof mem, df);
            fclose(df);
        }
        else if (!strcmp(cmd, "peek")) {
            uint16_t ad = parse_addr(a1); int cnt = a2[0] ? atoi(a2) : 1;
            printf("%s:", a1);
            for (int i = 0; i < cnt; i++) printf(" %02X", mem[(uint16_t)(ad + i)]);
            printf("\n");
        } else if (!strcmp(cmd, "poke")) {
            int tracking = stack_tracking;
            stack_tracking = 0; /* Monitor fixtures/canaries are not guest stores. */
            wr(parse_addr(a1), (uint8_t)strtoul(a2, 0, 0));
            stack_tracking = tracking;
        }
        else if (!strcmp(cmd, "stack")) {
            if (!strcmp(a1, "reset")) {
                c_stack_low = 0x2000;
                hw_stack_low = 0x0200;
                stack_tracking = 1;
            } else printf("{\"software_lowest_write\":%u,\"software_bytes_written\":%u,"
                          "\"hardware_lowest_write\":%u,\"hardware_bytes_written\":%u}\n",
                          c_stack_low, 0x2000-c_stack_low,
                          hw_stack_low, 0x0200-hw_stack_low);
        }
        else if (!strcmp(cmd, "boot"))
            printf("{\"entries\":%u,\"released\":%s}\n",
                   boot_entries, boot_released ? "true" : "false");
        else if (!strcmp(cmd, "timing")) timing = !strcmp(a1, "on");
        else if (!strcmp(cmd, "sound")) sound_log = !strcmp(a1, "on");
        else if (!strcmp(cmd, "stats")) printf("cycles %llu\n", (unsigned long long)cycles);
        else if (!strcmp(cmd, "watch") && watch_count < 24 && a2[0]) {
            watches[watch_count].entry = parse_addr(a1);
            snprintf(watches[watch_count].name, sizeof watches[watch_count].name, "%s", a2);
            watch_count++;
        }
        else if (!strcmp(cmd, "trace")) {
            if (profile_trace) fclose(profile_trace);
            for (unsigned i = 0; i < watch_count; i++) watches[i].active = 0;
            profile_trace = strcmp(a1, "off") ? fopen(a1, "w") : NULL;
            if (strcmp(a1, "off") && !profile_trace) { perror(a1); return 1; }
        }
        else if (!strcmp(cmd, "profile")) {
            if (!strcmp(a1, "reset")) {
                memset(profile_cycles, 0, sizeof profile_cycles);
                memset(profile_hits, 0, sizeof profile_hits);
                profiling = 1;
            } else if (!strcmp(a1, "off")) profiling = 0;
            else {
                FILE *pf = fopen(a1, "w");
                if (!pf) { perror(a1); return 1; }
                for (unsigned i = 0; i < 65536; i++) if (profile_hits[i])
                    fprintf(pf, "%04x %llu %llu\n", i, (unsigned long long)profile_cycles[i], (unsigned long long)profile_hits[i]);
                fclose(pf);
            }
        }
        else if (!strcmp(cmd, "echo")) printf("%s", line + 5);
        else if (!strcmp(cmd, "sync")) printf("ok %llu\n", (unsigned long long)(cycles / CYC_FRAME));
        else if (!strcmp(cmd, "quit")) break;
        else fprintf(stderr, "bad command %s\n", cmd);
        fflush(stdout);
    }
    printf("end at frame %llu, PC=$%04X\n", (unsigned long long)(cycles / CYC_FRAME), pc);
    if (profile_trace) fclose(profile_trace);
    return 0;
}
