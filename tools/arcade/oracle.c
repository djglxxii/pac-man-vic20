/* Local reference runner for unmodified Midway Pac-Man program ROMs.
 * The original Z80 executes here; none of the port's game routines are used. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#define CHIPS_IMPL
#include "z80.h"
static z80_t cpu;
static uint64_t pins;
static uint8_t ram[65536], in0 = 255, in1 = 255, dsw = 0xc9, vector = 255;
static bool irq, enabled, last_fetch;
static unsigned long frames;
static unsigned profile[16384];
static void cycle(void) {
    if (irq)
        pins |= Z80_INT;
    else
        pins &= ~Z80_INT;
    pins = z80_tick(&cpu, pins);
    if (pins & Z80_MREQ) {
        unsigned a = Z80_GET_ADDR(pins) & 0x7fff;
        if (pins & Z80_RD) {
            uint8_t v = a >= 0x5000 && a < 0x5040   ? in0
                        : a >= 0x5040 && a < 0x5080 ? in1
                        : a >= 0x5080 && a < 0x50c0 ? dsw
                                                    : ram[a];
            Z80_SET_DATA(pins, v);
            if ((pins & Z80_M1) && !(pins & Z80_RFSH) && !last_fetch && a < 16384)
                profile[a]++;
        } else if (pins & Z80_WR) {
            uint8_t v = Z80_GET_DATA(pins);
            if (a >= 0x4000 && a < 0x5000)
                ram[a] = v;
            else if (a >= 0x5040 && a < 0x5060)
                ram[a] = v & 15;
            else if (a >= 0x5060 && a < 0x5070)
                ram[a] = v;
            else if (a == 0x5000)
                enabled = v & 1;
        }
    } else if (pins & Z80_IORQ) {
        if (pins & Z80_M1) {
            Z80_SET_DATA(pins, vector);
            irq = false;
        } else if ((pins & Z80_WR) && !(Z80_GET_ADDR(pins) & 255))
            vector = Z80_GET_DATA(pins);
    }
    last_fetch = (pins & (Z80_MREQ | Z80_M1 | Z80_RD)) == (Z80_MREQ | Z80_M1 | Z80_RD);
}
static void run(unsigned n) {
    while (n--) {
        irq = enabled;
        for (unsigned c = 0; c < 50688; c++)
            cycle();
        frames++;
    }
}
static void call(unsigned addr, unsigned b, unsigned a, unsigned hl, unsigned de) {
    bool was_enabled = enabled, was_iff1 = cpu.iff1, was_iff2 = cpu.iff2;
    enabled = irq = false;
    cpu.iff1 = cpu.iff2 = false;
    cpu.b = b;
    cpu.a = a;
    cpu.hl = hl;
    cpu.de = de;
    cpu.sp -= 2;
    ram[cpu.sp] = 0x8d;
    ram[cpu.sp + 1] = 0x23;
    pins = z80_prefetch(&cpu, addr);
    for (unsigned c = 0; c < 4000000; c++) {
        cycle();
        if ((pins & (Z80_MREQ | Z80_RD | Z80_M1)) == (Z80_MREQ | Z80_RD | Z80_M1) &&
            Z80_GET_ADDR(pins) == 0x238d) {
            enabled = was_enabled;
            cpu.iff1 = was_iff1;
            cpu.iff2 = was_iff2;
            return;
        }
    }
    fprintf(stderr, "reference call $%04x timed out at $%04x\n", addr, cpu.pc);
    exit(3);
}
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f)
        return 2;
    if (fread(ram, 1, 16384, f) != 16384)
        return 2;
    fclose(f);
    pins = z80_init(&cpu);
    char line[512], path[256];
    unsigned n, addr, val, b, a, hl, de;
    while (fgets(line, sizeof line, stdin)) {
        n = 1;
        b = a = hl = de = 0;
        if (sscanf(line, "run %u", &n) == 1)
            run(n);
        else if (sscanf(line, "call %x %x %x %x %x", &addr, &b, &a, &hl, &de) >= 1)
            call(addr, b, a, hl, de);
        else if (sscanf(line, "input %x %x", &addr, &val) == 2) {
            in0 = addr;
            in1 = val;
        } else if (sscanf(line, "poke %x %x", &addr, &val) == 2)
            ram[addr & 65535] = val;
        else if (sscanf(line, "peek %x %u", &addr, &n) >= 1) {
            printf("%04x:", addr);
            for (unsigned i = 0; i < n; i++)
                printf(" %02x", ram[(addr + i) & 65535]);
            puts("");
        } else if (sscanf(line, "dump %255s", path) == 1) {
            f = fopen(path, "wb");
            if (!f)
                return 2;
            fwrite(ram, 1, sizeof ram, f);
            fclose(f);
        } else if (sscanf(line, "load %255s", path) == 1) {
            f = fopen(path, "rb");
            if (!f)
                return 2;
            if (fread(ram, 1, sizeof ram, f) < 0x5100)
                return 2;
            fclose(f);
        } else if (!strncmp(line, "profile", 7)) {
            for (unsigned i = 0; i < 16384; i++)
                if (profile[i])
                    printf("%04x %u\n", i, profile[i]);
            memset(profile, 0, sizeof profile);
        } else if (!strncmp(line, "quit", 4))
            break;
        printf("ok %lu pc=%04x state=%u/%u/%u board=%u\n", frames, cpu.pc, ram[0x4e00], ram[0x4e02],
               ram[0x4e04], ram[0x4e13] + 1);
        fflush(stdout);
    }
    return 0;
}
