/* Host build of exactly the C game core used by the VIC target. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "memmap.h"
#include "protos.h"
CPU_MEMMAP memmap;
uint8_t input0 = 255, input1 = 255, dipSwitches = 0xc9, charset[4096];
void interruptEnable(void) {}
void interruptDisable(void) {}
void interruptMode(int m) {}
void interruptVector(void (*f)(void)) {}
void interruptHalt(void) {}
void kickWatchdog(void) {}
void showTarget(XYPOS a, XYPOS b, int col) {}
void arcade_tasks(void);
static void call(unsigned addr, unsigned b, unsigned a, unsigned hl, unsigned de) {
    switch (addr) {
    case 0x01dc:
        updateCounters_01dc();
        break;
    case 0x0267:
        checkCoinInput_0267();
        break;
    case 0x02ad:
        checkCoinCounterTimeout_02ad();
        break;
    case 0x02df:
        checkCoinCredit_02df();
        break;
    case 0x05bf:
        drawGhost_05bf(hl - 0x4000, a);
        break;
    case 0x061b:
        checkStartButtons_061b();
        break;
    case 0x0940:
        switchPlayers_0940();
        break;
    case 0x070e:
        setupGhostTimers_070e(b);
        break;
    case 0x0a2c:
        nextLevelStateMachine_0a2c();
        break;
    case 0x0ead:
        selectFruit_0ead();
        break;
    case 0x20d7:
        cruiseElroyMode_20d7();
        break;
    case 0x2108:
        scene1StateMachine_2108();
        break;
    case 0x219e:
        scene2StateMachine_219e();
        break;
    case 0x2297:
        scene3StateMachine_2297();
        break;
    case 0x2675:
        resetPositions_2675();
        break;
    case 0x26a2:
        clearGhostState_26a2(b);
        break;
    case 0x26d0:
        configureGame_26d0(b);
        break;
    case 0x2730:
        blinkyScatterOrChase_2730(b);
        break;
    case 0x276c:
        pinkyScatterOrChase_276c(b);
        break;
    case 0x27a9:
        inkyScatterOrChase_27a9(b);
        break;
    case 0x27f1:
        clydeScatterOrChase_27f1(b);
        break;
    case 0x283b:
        homeOrRandomBlinky_283b();
        break;
    case 0x2865:
        homeOrRandomPinky_2865();
        break;
    case 0x288f:
        homeOrRandomInky_288f();
        break;
    case 0x28b9:
        homeOrRandomClyde_28b9();
        break;
    case 0x2a5a:
        addToScore_2a5a(b);
        break;
    case 0x2b4a:
        displayLives_2b4a(b);
        break;
    case 0x2bea:
        fruitHistoryLevelCheck_2bea(b);
        break;
    case 0x2cc1:
        playSongsAllChannels_2cc1();
        break;
    case 0x2d0c:
        soundEffectsAllChannels_2d0c();
        break;
    default:
        fprintf(stderr, "unknown native call %04x\n", addr);
        exit(3);
    }
}
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f)
        return 2;
    if (fread(ROM, 1, 16384, f) != 16384)
        return 2;
    fclose(f);
    mainTaskLoop_234b();
    char line[512], path[256];
    unsigned n, addr, val, frames = 0, b, a, hl, de;
    while (fgets(line, sizeof line, stdin)) {
        b = a = hl = de = 0;
        if (sscanf(line, "run %u", &n) == 1) {
            while (n--) {
                isr_008d();
                arcade_tasks();
                frames++;
            }
        } else if (sscanf(line, "call %x %x %x %x %x", &addr, &b, &a, &hl, &de) >= 1)
            call(addr, b, a, hl, de);
        else if (sscanf(line, "input %x %x", &addr, &val) == 2) {
            input0 = addr;
            input1 = val;
        } else if (sscanf(line, "poke %x %x", &addr, &val) == 2)
            MEM[addr] = val;
        else if (sscanf(line, "dump %255s", path) == 1) {
            f = fopen(path, "wb");
            if (!f)
                return 2;
            fwrite(MEM, 1, sizeof memmap, f);
            fclose(f);
        } else if (sscanf(line, "load %255s", path) == 1) {
            f = fopen(path, "rb");
            if (!f)
                return 2;
            if (fread(MEM, 1, sizeof memmap, f) != sizeof memmap)
                return 2;
            fclose(f);
        } else if (!strncmp(line, "quit", 4))
            break;
        printf("ok %u state=%u/%u/%u board=%u\n", frames, MAIN_STATE, INTRO_STATE, LEVEL_STATE,
               P1_LEVEL + 1);
        fflush(stdout);
    }
    return 0;
}
