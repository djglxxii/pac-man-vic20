/*
 * Copyright (c) 2024 Mark Burkley.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "memmap.h"
#include "protos.h"
#include "data.h"
#include "consts.h"
#include "structs.h"
#include "cpu.h"
#include "../video.h"
void reset_0000(void) {
    interruptDisable();
    initSelfTest_230b();
}
void setMemory_0008(uint8_t *hl, uint8_t b, uint8_t a) { memset(hl, a, b); }
void nothing_000c(void) {}
void nothingParam_000c(uint16_t unused) {}
void nothingSound_000c(SOUND_EFFECT *effect, uint8_t *frequency) {}
void setupGhostTimers_000d(uint8_t param) { setupGhostTimers_070e(param); }
uint8_t fetchOffset_0010(uint8_t **hl, uint8_t b) {
    (*hl) += b;
    return **hl;
}
uint16_t tableLookup_0018(uint8_t *hl, uint8_t b) {
    int e = fetchOffset_0010(&hl, b * 2);
    hl++;
    int d = *hl;
    return e | (d << 8);
}
void tableCall_0020(void (*const func[])(), uint8_t a) { func[a](); }
void schedTask(uint8_t b, uint8_t c) { addTask_0042(b, c); }
void schedISRTask(uint8_t time, uint8_t routine, uint8_t param) {
    TASK task;
    task.timer = time;
    task.func = routine;
    task.param = param;
    addISRTask_0051(ISR_TASKS, 0x10, (uint8_t *)&task);
}
void waitForever_0038(void) {
    while (1) {
        INTENABLE = 0;
        COINCOUNTER = 0;
    }
}
void addTask_0042(uint8_t task, uint8_t param) {
    arcade_byte(TASK_LIST_END++) = task;
    arcade_byte(TASK_LIST_END++) = param;
    if (TASK_LIST_END == 0x4d00)
        TASK_LIST_END = 0x4cc0;
}
void addISRTask_0051(uint8_t *ptr, int count, uint8_t *data) {
    int i;
    for (i = 0; i < count; i++) {
        if (*ptr == 0)
            break;
        ptr += 3;
    }
    if (i == count)
        return;
    for (i = 0; i < 3; i++) {
        *ptr++ = *data++;
    }
}
uint16_t getScreenOffset_0065(XYPOS pos) { return getScreenOffset_202d(pos); }
void isr_008d(void) {
    kickWatchdog();
    INTENABLE = 0;
    interruptDisable();
#ifdef VIC20
    extern void arcade_prepare_outputs(void);
    arcade_prepare_outputs();
#else
    memcpy(&SOUND[0x10], &CH1_FREQ0, 0x10);
#endif
    int a;
    if (CH1_SOUND_WAVE->mask != 0)
        a = CH1_SOUND_WAVE->selected;
    else
        a = CH1_SOUND_EFFECT->selected;
    SOUND[5] = a;
    if (CH2_SOUND_WAVE->mask != 0)
        a = CH2_SOUND_WAVE->selected;
    else
        a = CH2_SOUND_EFFECT->selected;
    SOUND[0xa] = a;
    if (CH3_SOUND_WAVE->mask != 0)
        a = CH3_SOUND_WAVE->selected;
    else
        a = CH3_SOUND_EFFECT->selected;
    SOUND[0xf] = a;
    ((void)0);
#ifndef VIC20
    memcpy(SPRITE_POS, &BLINKY_SPRITE, 0x1c);
#endif
    rotate8(&SPRITE_POS[0], 2);
    rotate8(&SPRITE_POS[2], 2);
    rotate8(&SPRITE_POS[4], 2);
    rotate8(&SPRITE_POS[6], 2);
    rotate8(&SPRITE_POS[8], 2);
    rotate8(&SPRITE_POS[10], 2);
    if (KILLED_STATE == 1) {
        swap16(&SPRITE_POS[2], &SPRITE_POS[(KILLED_GHOST_INDEX - 1) * 2]);
        swap16(&SPRITE_DATA[2], &SPRITE_POS[(KILLED_GHOST_INDEX - 1) * 2 + 0x10]);
    }
    if (PACMAN_POWEREDUP != 0) {
        swap16(SPRITE_POS, &SPRITE_POS[8]);
        swap16(SPRITE_DATA, &SPRITE_DATA[8]);
    }
#ifndef VIC20
    memcpy(SPRITEATTRIB + 2, SPRITE_POS, 0xc);
    memcpy(SPRITECOORDS + 2, SPRITE_DATA, 0xc);
#endif
    updateCounters_01dc();
    dispatchISRTasks_0221();
    mainStateMachine_03c8();
    if (MAIN_STATE != MAIN_STATE_INIT) {
        func_039d();
        spriteAnimationCocktail_1490();
        spriteAnimationUpright_141f();
        checkCoinInput_0267();
        checkCoinCounterTimeout_02ad();
        showStartNumPlayers_02fd();
    }
    if (MAIN_STATE == MAIN_STATE_DEMO) {
        CH2_SOUND_EFFECT->mask = 0;
        CH3_SOUND_EFFECT->mask = 0;
    }
    soundEffectsAllChannels_2d0c();
    playSongsAllChannels_2cc1();
    if (MAIN_STATE != MAIN_STATE_INIT && IN0_RACKADV == 0) {
        ((void)0);
#ifdef VIC20
        for (;;) {
        }
#else
        exit(1);
#endif
    }
    INTENABLE = 1;
    interruptEnable();
}
void updateCounters_01dc(void) {
    uint8_t *counter = SOUND_COUNTER;
    ((void)0);
    counter[0]++;
    counter[1]--;
    counter = TIMER_SIXTIETHS;
    uint8_t *limit = DATA_0219;
    int c = 1;
    for (int b = 0; b < 4; b++) {
        counter[b]++;
        ((void)0);
        if ((counter[b] & 0x0f) != *limit)
            break;
        c++;
        counter[b] = (counter[b] + 0x10) & 0xf0;
        limit++;
        ((void)0);
        if ((counter[b] & 0xf0) != *limit)
            break;
        c++;
        counter[b] = 0;
        limit++;
    }
    ((void)0);
    COUNTER_LIMITS_CHANGES = c;
    RND_NUM_GEN1 = RND_NUM_GEN1 * 5 + 1;
    RND_NUM_GEN2 = RND_NUM_GEN2 * 13 + 1;
}
void dispatchISRTasks_0221(void) {
    for (uint8_t offset = 0; offset < 0x30; offset += 3) {
        uint8_t timer = ISR_TASKS[offset];
        if (timer != 0) {
            if ((timer >> 6) < COUNTER_LIMITS_CHANGES) {
                ((void)0);
                ISR_TASKS[offset] = --timer;
                if ((timer & 0x3f) == 0) {
                    ISR_TASKS[offset] = 0;
                    ((void)0);
                    ASSERT(ISR_TASKS[offset + 1] < 10);
                    static void (*const func[])() = {incLevelStateSubr_0894, incMainSub2_06a3,
                                                     incMainStateIntro_058e, incKilledState_1272,
                                                     resetFruit_1000,        func_100b,
                                                     displayReady_0263,      incScene1State_212b,
                                                     incScene2State_21f0,    incScene3State_22b9};
                    tableCall_0020(func, ISR_TASKS[offset + 1]);
                }
            }
        }
    }
}
void displayReady_0263(void) { schedTask(TASK_DISPLAY_MSG, 0x80 | MSG_READY); }
void checkCoinInput_0267(void) {
    COINLOCKOUT = CREDITS << 1;
    if (CREDITS >= 0x99)
        return;
    SERVICE1_DEBOUNCE = ((SERVICE1_DEBOUNCE << 1) & 0x0f) | (IN0_CREDIT ? 1 : 0);
    if (SERVICE1_DEBOUNCE == 12)
        checkCoinCredit_02df();
    COIN2_DEBOUNCE = ((COIN2_DEBOUNCE << 1) & 0x0f) | (IN0_COIN2 ? 1 : 0);
    if (COIN2_DEBOUNCE == 0xc)
        COIN_COUNTER++;
    COIN1_DEBOUNCE = ((COIN1_DEBOUNCE << 1) & 0x0f) | (IN0_COIN1 ? 1 : 0);
    if (COIN1_DEBOUNCE != 0xc)
        return;
    ((void)0);
    COIN_COUNTER++;
}
void checkCoinCounterTimeout_02ad(void) {
    if (COIN_COUNTER == 0)
        return;
    if (COIN_COUNTER_TIMEOUT == 0) {
        COINCOUNTER = 1;
        checkCoinCredit_02df();
    }
    if (COIN_COUNTER_TIMEOUT == 8) {
        COINCOUNTER = 0;
    }
    COIN_COUNTER_TIMEOUT++;
    if (COIN_COUNTER_TIMEOUT != 0x10)
        return;
    COIN_COUNTER_TIMEOUT -= 0x10;
    COIN_COUNTER--;
}
void checkCoinCredit_02df(void) {
    if (++PARTIAL_CREDIT < COINS_PER_CREDIT)
        return;
    PARTIAL_CREDIT -= COINS_PER_CREDIT;
    CREDITS += CREDITS_PER_COIN;
    bcdAdjust(&CREDITS);
    if (CREDITS > 0x99)
        CREDITS = 0x99;
    CH1_SOUND_EFFECT->mask |= 2;
}
void showStartNumPlayers_02fd(void) {
    int a = COIN_TIMER++;
    if ((a & 0xf) == 0) {
        int b = (a >> 4) | ((a & 0xf) << 4);
        b |= ~WAIT_START_BUTTON;
        int c = b;
        if (CREDITS < 1) {
            a = c = 0;
        } else if (CREDITS != 1) {
            a = c;
        }
        P1START = a;
        P2START = c;
    }
    uint8_t *ix = &SCREEN[0x3d8];
    uint8_t *iy = &SCREEN[0x3c5];
    if (MAIN_STATE != MAIN_STATE_PLAY) {
        if (CREDIT_STATE < CREDIT_STATE_PLAYER1_READY) {
            oneUp_0369(ix);
            twoUp_0376(iy);
            return;
        }
    }
    if (PLAYER == 0) {
        if ((COIN_TIMER & 0x10) == 0)
            oneUp_0369(ix);
        else
            oneBlank_0383(ix);
    } else {
        if ((COIN_TIMER & 0x10) == 0)
            twoUp_0376(iy);
        else
            twoBlank_0390(iy);
    }
    if (!TWO_PLAYERS)
        twoBlank_0390(iy);
}
void oneUp_0369(uint8_t *ix) {
    video_store(ix, 0x50);
    video_store(ix + 1, 0x55);
    video_store(ix + 2, 0x31);
}
void twoUp_0376(uint8_t *iy) {
    video_store(iy, 0x50);
    video_store(iy + 1, 0x55);
    video_store(iy + 2, 0x32);
}
void oneBlank_0383(uint8_t *ix) {
    video_store(ix, 0x40);
    video_store(ix + 1, 0x40);
    video_store(ix + 2, 0x40);
}
void twoBlank_0390(uint8_t *iy) {
    video_store(iy, 0x40);
    video_store(iy + 1, 0x40);
    video_store(iy + 2, 0x40);
}
void func_039d(void) {
    if (SCENE1_STATE < 5)
        return;
    CLYDE_POS.y = FRUIT_POS.y = PACMAN_POS.y;
    PINKY_POS.y = INKY_POS.y = PACMAN_POS.y - 16;
    PINKY_POS.x = CLYDE_POS.x = PACMAN_POS.x + 8;
    INKY_POS.x = FRUIT_POS.x = PACMAN_POS.x - 8;
}
void mainStateMachine_03c8(void) {
    static void (*const func[])() = {resetStateMachine_03d4, introStateMachine_03fe,
                                     coinInsertedStateMachine_05e5, playGameStateMachine_06be};
    tableCall_0020(func, MAIN_STATE);
}
void resetStateMachine_03d4(void) {
    static void (*const func[])() = {initResetGame_03dc, nothing_000c};
    tableCall_0020(func, RESET_STATE);
}
void initResetGame_03dc(void) {
    schedTask(TASK_CLEAR_SCREEN, 0);
    schedTask(TASK_CLEAR_COLOUR, 0);
    schedTask(TASK_MAZE_COLOURS, 0);
    schedTask(TASK_CONFIGURE_GAME, 0);
    schedTask(TASK_CLEAR_SCORES, 0);
    schedTask(TASK_INIT_POSITIONS, 0);
    schedTask(TASK_RESET_POSITIONS, 0);
    schedTask(TASK_RESET_GAME_STATE, 0);
    RESET_STATE++;
    SOUNDENABLE = 1;
}
void introStateMachine_03fe(void) {
    displayCredits_2ba1();
    if (CREDITS != 0) {
        INTRO_STATE = LEVEL_STATE = 0;
        MAIN_STATE++;
        return;
    }
    static void (*const func[])() = {introStart_045f,
                                     nothing_000c,
                                     introduceBlinky_0471,
                                     nothing_000c,
                                     introduceShadow_047f,
                                     nothing_000c,
                                     introduceBlinkyNickname_0485,
                                     nothing_000c,
                                     introducePinky_048b,
                                     nothing_000c,
                                     introduceSpeedy_0499,
                                     nothing_000c,
                                     introducePinkyNickname_049f,
                                     nothing_000c,
                                     introduceInky_04a5,
                                     nothing_000c,
                                     introduceBashful_04b3,
                                     nothing_000c,
                                     introduceInkyNickname_04b9,
                                     nothing_000c,
                                     introduceClyde_04bf,
                                     nothing_000c,
                                     introducePokey_04cd,
                                     nothing_000c,
                                     introduceClydeNickname_04d3,
                                     nothing_000c,
                                     introducePoints_04d8,
                                     nothing_000c,
                                     introSceneSetup_04e0,
                                     nothing_000c,
                                     introStartMoveBlinky_051c,
                                     introStartMovePinky_054b,
                                     introStartMoveInky_0556,
                                     introStartMoveClyde_0561,
                                     introCheckAllGhostsEaten_056c,
                                     introPlayGame_057c};
    tableCall_0020(func, INTRO_STATE);
}
void introStart_045f(void) {
    schedTask(TASK_CLEAR_SCREEN, 1);
    schedTask(TASK_MAZE_COLOURS, 0);
    schedTask(TASK_INIT_POSITIONS, 0);
    schedTask(TASK_RESET_POSITIONS, 0);
    displayIntroMsg_0585(MSG_NICKNAME);
}
void introduceBlinky_0471(void) {
    drawGhost_05bf(0x304, 1);
    displayIntroMsg_0585(MSG_NICKNAME);
}
void introduceShadow_047f(void) { introduceGhost_0593(0x14); }
void introduceBlinkyNickname_0485(void) { introduceGhost_0593(0xd); }
void introducePinky_048b(void) {
    drawGhost_05bf(0x307, 3);
    displayIntroMsg_0585(MSG_NICKNAME);
}
void introduceSpeedy_0499(void) { introduceGhost_0593(0x16); }
void introducePinkyNickname_049f(void) { introduceGhost_0593(0xf); }
void introduceInky_04a5(void) {
    drawGhost_05bf(0x30a, 5);
    displayIntroMsg_0585(MSG_NICKNAME);
}
void introduceBashful_04b3(void) { introduceGhost_0593(0x33); }
void introduceInkyNickname_04b9(void) { introduceGhost_0593(0x2f); }
void introduceClyde_04bf(void) {
    drawGhost_05bf(0x30d, 7);
    displayIntroMsg_0585(MSG_NICKNAME);
}
void introducePokey_04cd(void) { introduceGhost_0593(0x35); }
void introduceClydeNickname_04d3(void) { selectDisplayGhostName_0580(0x31); }
void introducePoints_04d8(void) {
    schedTask(TASK_DISPLAY_MSG, MSG_10PTS);
    displayIntroMsg_0585(MSG_50PTS);
}
void introSceneSetup_04e0(void) {
    displayIntroMsg_0585(MSG_COPYRIGHT2);
    resetPlayerParams_0879();
    LEVEL_STATE--;
    schedTask(TASK_CLEAR_GHOST_STATE, 0);
    schedTask(TASK_BLINKY_SUBSTATE, SUBSTATE_CHASE);
    schedTask(TASK_SETUP_GHOST_TIMERS, 20);
    schedTask(TASK_INIT_POSITIONS, 1);
    P1_REAL_LIVES = 1;
    TWO_PLAYERS = 0;
    P1_DISPLAY_LIVES = 0;
    video_store(&SCREEN[0x332], CHAR_POWERUP);
    demoMazeHorizontal_0506();
}
void demoMazeHorizontal_0506(void) {
    int ix = 0x40;
    for (int b = 0; b < 0x1c; b++) {
        video_store(&SCREEN[ix + 0x11], 0xfc);
        video_store(&SCREEN[ix + 0x13], 0xfc);
        ix += 0x20;
    }
}
void introStartMoveBlinky_051c(void) {
    introAdvanceState_0524(&BLINKY_SUBSTATE, 0x21, PACMAN_TILE2.x);
}
void introAdvanceState_0524(uint8_t *ghostSubstate, uint8_t target, uint8_t tile) {
    if (tile != target) {
        introMain_052c();
        return;
    }
    *ghostSubstate = SUBSTATE_CHASE;
    incMainStateIntro_058e();
    return;
}
void introMain_052c(void) {
    updateGhostStates_1017();
    updateGhostStates_1017();
    toggleGhostAnimation_0e23();
    flashPowerups_0c0d();
    setGhostColour_0bd6();
    pacmanReverse_05a5();
    blinkyCheckReverse_1efe();
    pinkyCheckReverse_1f25();
    inkyCheckReverse_1f4c();
    clydeCheckReverse_1f73();
}
void introStartMovePinky_054b(void) {
    introAdvanceState_0524(&PINKY_SUBSTATE, 0x20, BLINKY_TILE2.x);
}
void introStartMoveInky_0556(void) { introAdvanceState_0524(&INKY_SUBSTATE, 0x22, BLINKY_TILE2.x); }
void introStartMoveClyde_0561(void) {
    introAdvanceState_0524(&CLYDE_SUBSTATE, 0x24, BLINKY_TILE2.x);
}
void introCheckAllGhostsEaten_056c(void) {
    if (KILLED_COUNT + KILLED_STATE == 6) {
        incMainStateIntro_058e();
        return;
    }
    introMain_052c();
}
void introPlayGame_057c(void) { playGameStateMachine_06be(); }
void selectDisplayGhostName_0580(uint8_t c) {
    c += GHOST_NAMES_MODE;
    displayIntroMsg_0585(c);
}
void displayIntroMsg_0585(uint8_t c) {
    addTask_0042(TASK_DISPLAY_MSG, c);
    schedISRTask(0x4a, ISRTASK_INC_INTRO_STATE, 0x00);
    incMainStateIntro_058e();
}
void incMainStateIntro_058e(void) { INTRO_STATE++; }
void introduceGhost_0593(uint8_t c) {
    addTask_0042(TASK_DISPLAY_MSG, c + GHOST_NAMES_MODE);
    schedISRTask(0x45, ISRTASK_INC_INTRO_STATE, 0x00);
    incMainStateIntro_058e();
}
XYPOS pacmanReverse_05a5(void) {
    XYPOS vector = {0, 0};
    if (PACMAN_ORIENT_CHG_FLAG == 0)
        return vector;
    PACMAN_ORIENT_CHG_FLAG = 0;
    PACMAN_DESIRED_ORIENTATION = PACMAN_ORIENTATION ^ 2;
    vector = MOVE_VECTOR_DATA[PACMAN_DESIRED_ORIENTATION];
    PACMAN_VECTOR2 = vector;
    return vector;
}
void drawGhost_05bf(int hl, uint8_t a) {
    video_store(&SCREEN[hl++], 0xb1);
    video_store(&SCREEN[hl++], 0xb3);
    video_store(&SCREEN[hl], 0xb5);
    hl += 0x1e;
    video_store(&SCREEN[hl++], 0xb0);
    video_store(&SCREEN[hl++], 0xb2);
    video_store(&SCREEN[hl], 0xb4);
    video_store(&COLOUR[hl--], a);
    video_store(&COLOUR[hl--], a);
    video_store(&COLOUR[hl], a);
    hl -= 0x1e;
    video_store(&COLOUR[hl--], a);
    video_store(&COLOUR[hl--], a);
    video_store(&COLOUR[hl], a);
}
void coinInsertedStateMachine_05e5(void) {
    static void (*const func[])() = {pushStartMsg_05f3, checkStartButtons_061b,
                                     player1ReadyMsg_0674, nothing_000c, creditStateReset_06a8};
    tableCall_0020(func, CREDIT_STATE);
}
void pushStartMsg_05f3(void) {
    displayCredits_2ba1();
    schedTask(TASK_CLEAR_SCREEN, 1);
    schedTask(TASK_MAZE_COLOURS, 0);
    schedTask(TASK_DISPLAY_MSG, MSG_PUSHSTART);
    schedTask(TASK_DISPLAY_MSG, MSG_COPYRIGHT1);
    schedTask(TASK_RESET_POSITIONS, 0);
    CREDIT_STATE++;
    WAIT_START_BUTTON = 1;
    if (BONUS_LIFE == 0xff)
        return;
    schedTask(TASK_DISPLAY_MSG, MSG_BONUS_PACMAN);
    schedTask(TASK_SHOW_BONUS_LIFE_SCORE, 0x00);
}
void checkStartButtons_061b(void) {
    displayCredits_2ba1();
    if (CREDITS == 1)
        displayMsg_2c5e(MSG_ONEPLAYER);
    else
        displayMsg_2c5e(MSG_ONEORTWOPLAYER);
    if (CREDITS != 1 && !IN1_START2)
        TWO_PLAYERS = 1;
    else if (IN1_START1)
        return;
    else
        TWO_PLAYERS = 0;
    if (COINS_PER_CREDIT != 0) {
        uint8_t amount = 1 + TWO_PLAYERS;
#ifdef VIC20
        extern void spend_credit_bcd(uint8_t amount);
        spend_credit_bcd(amount);
#else
        uint8_t correction = (CREDITS & 15) < amount ? 6 : 0;
        CREDITS -= amount + correction;
#endif
        displayCredits_2ba1();
    }
    CREDIT_STATE++;
    WAIT_START_BUTTON = 0;
    CH1_SOUND_WAVE->mask = CH2_SOUND_WAVE->mask = 1;
}
void player1ReadyMsg_0674(void) {
    schedTask(TASK_CLEAR_SCREEN, 1);
    schedTask(TASK_MAZE_COLOURS, 1);
    schedTask(TASK_DRAW_MAZE, 0);
    schedTask(TASK_CLEAR_PILLS, 0);
    schedTask(TASK_DRAW_PILLS, 0);
    schedTask(TASK_DISPLAY_MSG, MSG_PLAYER1);
    schedTask(TASK_DISPLAY_MSG, MSG_READY);
    schedTask(TASK_CLEAR_SCORES, 0);
    schedTask(TASK_FRUIT_HISTORY, 0);
    P1_LEVEL = 0;
    P1_REAL_LIVES = P1_DISPLAY_LIVES = LIVES_PER_GAME;
    schedTask(TASK_BOTTOM_COLOUR, 0x00);
    schedISRTask(0x57, ISRTASK_INC_MAIN_SUB2, 0x00);
    incMainSub2_06a3();
}
void incMainSub2_06a3(void) { CREDIT_STATE++; }
void creditStateReset_06a8(void) {
    P1_DISPLAY_LIVES--;
    bottomTextColourAndDisplayLives_2b6a(0);
    INTRO_STATE = CREDIT_STATE = LEVEL_STATE = 0;
    MAIN_STATE++;
}
void playGameStateMachine_06be(void) {
    static void (*const func[])() = {resetPlayerParams_0879,
                                     levelStatePlayerReady_0899,
                                     nothing_000c,
                                     playGameMain_08cd,
                                     playerDied_090d,
                                     nothing_000c,
                                     switchPlayers_0940,
                                     nothing_000c,
                                     switchModeDemo_0972,
                                     gameOverOrNextPlayer_0988,
                                     nothing_000c,
                                     advanceToLevelStatePlayGame_09d2,
                                     playGameSoundOff_09d8,
                                     nothing_000c,
                                     mazeColourWhite_09e8,
                                     nothing_000c,
                                     mazeColourBlue_09fe,
                                     nothing_000c,
                                     mazeColourWhite_0a02,
                                     nothing_000c,
                                     mazeColourBlue_0a04,
                                     nothing_000c,
                                     mazeColourWhite_0a06,
                                     nothing_000c,
                                     mazeColourBlue_0a08,
                                     nothing_000c,
                                     mazeColourWhite_0a0a,
                                     nothing_000c,
                                     mazeColourBlue_0a0c,
                                     nothing_000c,
                                     mazeReset_0a0e,
                                     nothing_000c,
                                     nextLevelStateMachine_0a2c,
                                     nothing_000c,
                                     nextLevel_0a7c,
                                     gameOverOrNextPlayer_0aa0,
                                     nothing_000c,
                                     advanceToLevelStatePlayGame_0aa3};
    tableCall_0020(func, LEVEL_STATE);
}
void setupGhostTimers_070e(uint8_t b) {
    if (b == 0) {
        b = rom_low_read(P1_CURR_DIFFICULTY);
        ((void)0);
    }
    uint8_t *ix = DATA_0796 + b * 6;
    ((void)0);
    uint8_t a = ix[0] * 0x2a;
    uint8_t *hl = MOVE_DATA_330f + a;
    ((void)0);
    setupMovePat_0814(hl);
    REL_DIFF = ix[1];
    ((void)0);
    hl = DATA_0843 + 3 * ix[2];
    ((void)0);
    initLeaveHouseCounters_083a(hl);
    uint8_t *iy = DATA_084f + 2 * ix[3];
    ((void)0);
    PILLS_REM_DIFF_1 = iy[0];
    PILLS_REM_DIFF_2 = iy[1];
    iy = DATA_0861 + 2 * ix[4];
    ((void)0);
    GHOST_EDIBLE_TIME = *(uint16_t *)iy;
    iy = DATA_0873 + 2 * ix[5];
    ((void)0);
    ((void)0);
    UNITS_B4_GHOST_LEAVES_HOME = *(uint16_t *)iy;
    fruitHistoryLevelCheck_2bea(b);
}
void setupMovePat_0814(uint8_t *hl) {
    memcpy(&PACMAN_MOVE_PAT_NORMAL, hl, 0x1c);
    memcpy(&PINKY_MOVE_PAT_NORMAL, &hl[0x10], 0xc);
    memcpy(&INKY_MOVE_PAT_NORMAL, &hl[0x10], 0xc);
    memcpy(&CLYDE_MOVE_PAT_NORMAL, &hl[0x10], 0xc);
    memcpy(DIFFICULTY_TABLE, &hl[0x1c], 0xe);
}
void initLeaveHouseCounters_083a(uint8_t *hl) { memcpy(&PINKY_LEAVE_HOME_COUNTER, hl, 3); }
void resetPlayerParams_0879(void) {
    memset(&PLAYER, 0, 11);
    clearPillArrays_24c9();
    P1_CURR_DIFFICULTY = DIFFICULTY_PTR;
    ((void)0);
    memcpy(&P2_CURR_DIFFICULTY, &P1_CURR_DIFFICULTY, 0x2e);
    incLevelStateSubr_0894();
}
void incLevelStateSubr_0894(void) { LEVEL_STATE++; }
void levelStatePlayerReady_0899(void) {
    if (MAIN_STATE == MAIN_STATE_DEMO) {
        LEVEL_STATE = LEVEL_STATE_GAME_OVER;
        return;
    }
    schedTask(TASK_CLEAR_GHOST_STATE, 0);
    schedTask(TASK_DISPLAY_MSG, 0x80 | MSG_PLAYER1);
    schedTask(TASK_INIT_POSITIONS, 0);
    schedTask(TASK_BLINKY_SUBSTATE, SUBSTATE_IN_HOUSE);
    schedTask(TASK_SETUP_GHOST_TIMERS, 0);
    schedTask(TASK_BOTTOM_COLOUR, 0);
    schedISRTask(0x54, ISRTASK_INC_LEVEL_STATE, 0x00);
    schedISRTask(0x54, ISRTASK_DISPLAY_READY, 0x00);
    FLIPSCREEN = (COCKTAIL_MODE & PLAYER);
    incLevelStateSubr_0894();
}
void playGameMain_08cd(void) {
    if (IN0_RACKADV == 0) {
        LEVEL_STATE = 0x0e;
        schedTask(TASK_CLEAR_PILLS_SCREEN, 0x00);
        return;
    }
    if (P1_PILLS_EATEN_LEVEL == 0xf4) {
        LEVEL_STATE = 0x0c;
        return;
    }
    updateGhostStates_1017();
    updateGhostStates_1017();
    checkInactivityCounter_13dd();
    ghostsLeaveHouse_0c42();
    toggleGhostAnimation_0e23();
    ghostsChangeOrientation_0e36();
    ghostsFlashBecomingInedible_0ac3();
    setGhostColour_0bd6();
    flashPowerups_0c0d();
    updatePillsEatenSoundEffect_0e6c();
    selectFruit_0ead();
}
void playerDied_090d(void) {
    P1_DIED_IN_LEVEL = 1;
    updatePillsFromScreen_2487(0);
    LEVEL_STATE++;
    if (P1_REAL_LIVES == 0) {
        if (TWO_PLAYERS) {
            if (P2_REAL_LIVES != 0) {
                addTask_0042(TASK_DISPLAY_MSG, PLAYER + 3);
                schedTask(TASK_DISPLAY_MSG, MSG_GAMEOVER);
                schedISRTask(0x54, ISRTASK_INC_LEVEL_STATE, 0x00);
                return;
            }
        }
    }
    LEVEL_STATE++;
}
void switchPlayers_0940(void) {
    if (TWO_PLAYERS == 0 || P2_REAL_LIVES == 0) {
        if (P1_REAL_LIVES == 0) {
            displayCredits_2ba1();
            schedTask(TASK_DISPLAY_MSG, MSG_GAMEOVER);
            schedISRTask(0x54, ISRTASK_INC_LEVEL_STATE, 0x00);
            LEVEL_STATE++;
            return;
        }
    } else {
        swapP1P2Difficulty_0aa6();
        PLAYER ^= 1;
    }
    LEVEL_STATE = LEVEL_STATE_GAME_OVER;
}
void switchModeDemo_0972(void) {
    INTRO_STATE = LEVEL_STATE = TWO_PLAYERS = PLAYER = 0;
    FLIPSCREEN = 0;
    MAIN_STATE = MAIN_STATE_DEMO;
}
void gameOverOrNextPlayer_0988(void) {
    schedTask(TASK_CLEAR_SCREEN, 1);
    schedTask(TASK_MAZE_COLOURS, 1);
    schedTask(TASK_DRAW_MAZE, 0);
    schedTask(TASK_CLEAR_GHOST_STATE, 0);
    schedTask(TASK_CLEAR_PILLS_SCREEN, 0);
    schedTask(TASK_DRAW_PILLS, 0);
    schedTask(TASK_INIT_POSITIONS, 0);
    schedTask(TASK_BLINKY_SUBSTATE, SUBSTATE_IN_HOUSE);
    schedTask(TASK_SETUP_GHOST_TIMERS, 0);
    schedTask(TASK_BOTTOM_COLOUR, 0);
    schedTask(TASK_DISPLAY_MSG, MSG_READY);
    if (MAIN_STATE != MAIN_STATE_PLAY) {
        schedTask(TASK_DISPLAY_MSG, MSG_GAMEOVER);
        schedTask(TASK_DISPLAY_CREDITS, 0);
    }
    schedISRTask(0x54, ISRTASK_INC_LEVEL_STATE, 0);
    if (MAIN_STATE != MAIN_STATE_DEMO) {
        schedISRTask(0x54, ISRTASK_DISPLAY_READY, 0);
    }
    FLIPSCREEN = (COCKTAIL_MODE & PLAYER);
    incLevelStateSubr_0894();
}
void advanceToLevelStatePlayGame_09d2(void) { LEVEL_STATE = LEVEL_STATE_PLAY_GAME; }
void playGameSoundOff_09d8(void) {
    schedISRTask(0x54, ISRTASK_INC_LEVEL_STATE, 0x00);
    LEVEL_STATE++;
    CH2_SOUND_EFFECT->mask = 0;
    CH3_SOUND_EFFECT->mask = 0;
}
void mazeColourWhite_09e8(void) { mazeColour_09ea(2); }
void mazeColour_09ea(uint8_t param) {
    addTask_0042(TASK_MAZE_COLOURS, param);
    schedISRTask(0x42, ISRTASK_INC_LEVEL_STATE, 0x00);
    setGhostPosition_267e(0, 0);
    LEVEL_STATE++;
}
void mazeColourBlue_09fe(void) { mazeColour_09ea(0); }
void mazeColourWhite_0a02(void) { mazeColourWhite_09e8(); }
void mazeColourBlue_0a04(void) { mazeColourBlue_09fe(); }
void mazeColourWhite_0a06(void) { mazeColourWhite_09e8(); }
void mazeColourBlue_0a08(void) { mazeColourBlue_09fe(); }
void mazeColourWhite_0a0a(void) { mazeColourWhite_09e8(); }
void mazeColourBlue_0a0c(void) { mazeColourBlue_09fe(); }
void mazeReset_0a0e(void) {
    schedTask(TASK_CLEAR_SCREEN, 1);
    schedTask(TASK_CLEAR_COLOUR, 0);
    schedTask(TASK_CLEAR_GHOST_STATE, 0);
    schedTask(TASK_CLEAR_PILLS_SCREEN, 0);
    schedTask(TASK_INIT_POSITIONS, 1);
    schedTask(TASK_BLINKY_SUBSTATE, SUBSTATE_CHASE);
    schedTask(TASK_SETUP_GHOST_TIMERS, 19);
    schedISRTask(0x43, ISRTASK_INC_LEVEL_STATE, 0);
    LEVEL_STATE++;
}
void nextLevelStateMachine_0a2c(void) {
    CH2_SOUND_EFFECT->mask = 0;
    CH3_SOUND_EFFECT->mask = 0;
    CH1_SOUND_WAVE->mask = CH2_SOUND_WAVE->mask = 2;
    int a = P1_LEVEL;
    if (a >= 20)
        a = 20;
    static void (*const func[])() = {
        incLevelState_0a6f,      scene1StateMachine_2108, incLevelState_0a6f, incLevelState_0a6f,
        scene2StateMachine_219e, incLevelState_0a6f,      incLevelState_0a6f, incLevelState_0a6f,
        scene3StateMachine_2297, incLevelState_0a6f,      incLevelState_0a6f, incLevelState_0a6f,
        scene3StateMachine_2297, incLevelState_0a6f,      incLevelState_0a6f, incLevelState_0a6f,
        scene3StateMachine_2297, incLevelState_0a6f,      incLevelState_0a6f, incLevelState_0a6f,
        incLevelState_0a6f};
    tableCall_0020(func, a);
}
void incLevelState_0a6f(void) {
    LEVEL_STATE += 2;
    CH1_SOUND_WAVE->mask = CH2_SOUND_WAVE->mask = 0;
}
void nextLevel_0a7c(void) {
    clearPillArrays_24c9();
    CH1_SOUND_WAVE->mask = CH2_SOUND_WAVE->mask = 0;
    memset(&P1_FIRST_FRUIT, 0, 7);
    clearPillArrays_24c9();
    LEVEL_STATE++;
    P1_LEVEL++;
    if (rom_low_read(P1_CURR_DIFFICULTY) == 0x14)
        return;
    P1_CURR_DIFFICULTY++;
}
void gameOverOrNextPlayer_0aa0(void) { gameOverOrNextPlayer_0988(); }
void advanceToLevelStatePlayGame_0aa3(void) { advanceToLevelStatePlayGame_09d2(); }
void swapP1P2Difficulty_0aa6(void) {
    uint8_t *ix = (uint8_t *)&P1_CURR_DIFFICULTY;
    uint8_t *iy = (uint8_t *)&P2_CURR_DIFFICULTY;
    for (int i = 0; i < 0x2e; i++) {
        uint8_t d = *ix;
        uint8_t e = *iy;
        *iy++ = d;
        *ix++ = e;
    }
}
void ghostsFlashBecomingInedible_0ac3(void) {
    if (KILLED_GHOST_INDEX != 0)
        return;
    if (GHOST_COL_POWERUP_COUNTER == 0) {
        GHOST_COL_POWERUP_COUNTER = 0xe;
        if (PACMAN_POWEREDUP != 0) {
            if (EDIBLE_REMAIN_COUNT < 0x100) {
                CH2_SOUND_EFFECT->mask |= 0x80;
                if (PACMAN_COLOUR == 9) {
                    CH2_SOUND_EFFECT->mask &= ~0x80;
                }
                PACMAN_COLOUR = 9;
            }
        }
        if (BLINKY_EDIBLE) {
            if (EDIBLE_REMAIN_COUNT < 0x100) {
                if (BLINKY_COLOUR != 0x11) {
                    BLINKY_COLOUR = 0x11;
                } else {
                    BLINKY_COLOUR = 0x12;
                }
            }
        } else {
            if (BLINKY_COLOUR != 1) {
                BLINKY_COLOUR = 1;
            } else {
                BLINKY_COLOUR = 1;
            }
        }
        if (PINKY_EDIBLE != 0) {
            if (EDIBLE_REMAIN_COUNT < 0x100) {
                if (PINKY_COLOUR != 0x11) {
                    PINKY_COLOUR = 0x11;
                } else {
                    PINKY_COLOUR = 0x12;
                }
            }
        } else {
            if (PINKY_COLOUR != 3) {
                PINKY_COLOUR = 3;
            } else {
                PINKY_COLOUR = 3;
            }
        }
        if (INKY_EDIBLE) {
            if (EDIBLE_REMAIN_COUNT < 0x100) {
                if (INKY_COLOUR != 0x11) {
                    INKY_COLOUR = 0x11;
                } else {
                    INKY_COLOUR = 0x12;
                }
            }
        } else {
            if (INKY_COLOUR != 5) {
                INKY_COLOUR = 5;
            } else {
                INKY_COLOUR = 5;
            }
        }
        if (CLYDE_EDIBLE != 0) {
            if (EDIBLE_REMAIN_COUNT < 0x100) {
                if (CLYDE_COLOUR != 0x11) {
                    CLYDE_COLOUR = 0x11;
                } else {
                    CLYDE_COLOUR = 0x12;
                }
            }
        } else {
            if (CLYDE_COLOUR != 7) {
                CLYDE_COLOUR = 7;
            } else {
                CLYDE_COLOUR = 7;
            }
        }
    }
    GHOST_COL_POWERUP_COUNTER--;
}
void setGhostColour_0bd6(void) {
    int b = 0x19;
    if (INTRO_STATE == 0x22) {
        b = 0;
    }
    if (BLINKY_STATE) {
        BLINKY_COLOUR = b;
    }
    if (PINKY_STATE) {
        PINKY_COLOUR = b;
    }
    if (INKY_STATE) {
        INKY_COLOUR = b;
    }
    if (CLYDE_STATE) {
        CLYDE_COLOUR = b;
    }
}
void flashPowerups_0c0d(void) {
    if (++PILL_CHANGE_COUNTER != 0xa)
        return;
    PILL_CHANGE_COUNTER = 0;
    if (LEVEL_STATE == LEVEL_STATE_PLAY_GAME) {
        int a = 0x10;
        if (COLOUR[0x64] == a)
            a = 0;
        video_store(&COLOUR[0x64], a);
        video_store(&COLOUR[0x78], a);
        video_store(&COLOUR[0x384], a);
        video_store(&COLOUR[0x398], a);
        return;
    } else {
        int a = 0x10;
        if (COLOUR[0x332] == 0x10)
            a = 0;
        video_store(&COLOUR[0x332], a);
        video_store(&COLOUR[0x278], a);
    }
}
void ghostsLeaveHouse_0c42(void) {
    if (KILLED_GHOST_INDEX != 0)
        return;
    rotate8(&GHOST_HOUSE_MOVE_COUNT, 1);
    if ((GHOST_HOUSE_MOVE_COUNT & 0x01) == 0)
        return;
    if (BLINKY_SUBSTATE == SUBSTATE_IN_HOUSE) {
        BLINKY_POS = addXYOffset_2000(*MOVE_VECTOR_UP, BLINKY_POS);
        BLINKY_ORIENTATION = BLINKY_PREV_ORIENTATION = ORIENT_UP;
        if (BLINKY_POS.y == 0x64) {
            BLINKY_TILE.y = 0x2c;
            BLINKY_TILE.x = 0x2e;
            BLINKY_VECTOR.y = BLINKY_VECTOR2.y = 0x00;
            BLINKY_VECTOR.x = BLINKY_VECTOR2.x = 0x01;
            BLINKY_ORIENTATION = BLINKY_PREV_ORIENTATION = ORIENT_LEFT;
            BLINKY_SUBSTATE = SUBSTATE_CHASE;
        }
    }
    if (PINKY_SUBSTATE != SUBSTATE_CHASE) {
        if (PINKY_SUBSTATE == SUBSTATE_IN_HOUSE) {
            if (PINKY_POS.y == 0x78 || PINKY_POS.y == 0x80)
                pinkyReverse_1f2e();
            PINKY_PREV_ORIENTATION = PINKY_ORIENTATION;
            PINKY_POS = addXYOffset_2000(PINKY_VECTOR2, PINKY_POS);
        } else {
            PINKY_POS = addXYOffset_2000(*MOVE_VECTOR_UP, PINKY_POS);
            PINKY_PREV_ORIENTATION = PINKY_ORIENTATION = ORIENT_UP;
            if (PINKY_POS.y == 0x64) {
                PINKY_TILE.y = 0x2c;
                PINKY_TILE.x = 0x2e;
                PINKY_VECTOR.y = PINKY_VECTOR2.y = 0x00;
                PINKY_VECTOR.x = PINKY_VECTOR2.x = 0x01;
                PINKY_PREV_ORIENTATION = PINKY_ORIENTATION = ORIENT_LEFT;
                PINKY_SUBSTATE = SUBSTATE_CHASE;
            }
        }
    }
    if (INKY_SUBSTATE != SUBSTATE_CHASE) {
        if (INKY_SUBSTATE == SUBSTATE_IN_HOUSE) {
            if (INKY_POS.y == 0x78 || INKY_POS.y == 0x80)
                inkyReverse_1f55();
            INKY_PREV_ORIENTATION = INKY_ORIENTATION;
            INKY_POS = addXYOffset_2000(INKY_VECTOR2, INKY_POS);
        } else {
            if (INKY_SUBSTATE == SUBSTATE_HOUSE_MOVE) {
                INKY_POS = addXYOffset_2000(*MOVE_VECTOR_RIGHT, INKY_POS);
                INKY_PREV_ORIENTATION = INKY_ORIENTATION = ORIENT_RIGHT;
                if (INKY_POS.x == 0x80) {
                    INKY_SUBSTATE = SUBSTATE_LEAVING_HOUSE;
                }
            } else {
                INKY_POS = addXYOffset_2000(*MOVE_VECTOR_UP, INKY_POS);
                INKY_PREV_ORIENTATION = INKY_ORIENTATION = ORIENT_UP;
                if (INKY_POS.y == 0x64) {
                    INKY_TILE.y = 0x2c;
                    INKY_TILE.x = 0x2e;
                    INKY_VECTOR.y = INKY_VECTOR2.y = 0x00;
                    INKY_VECTOR.x = INKY_VECTOR2.x = 0x01;
                    INKY_PREV_ORIENTATION = INKY_ORIENTATION = ORIENT_LEFT;
                    INKY_SUBSTATE = SUBSTATE_CHASE;
                }
            }
        }
    }
    if (CLYDE_SUBSTATE == SUBSTATE_CHASE)
        return;
    if (CLYDE_SUBSTATE == SUBSTATE_IN_HOUSE) {
        if (CLYDE_POS.y == 0x78 || CLYDE_POS.y == 0x80)
            clydeReverse_1f7c();
        CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION;
        CLYDE_POS = addXYOffset_2000(CLYDE_VECTOR2, CLYDE_POS);
        return;
    }
    if (CLYDE_SUBSTATE == GHOST_STATE_HOUSE_MOVE) {
        CLYDE_POS = addXYOffset_2000(*MOVE_VECTOR_LEFT, CLYDE_POS);
        CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION = ORIENT_LEFT;
        if (CLYDE_POS.x != 0x80)
            return;
        CLYDE_SUBSTATE = SUBSTATE_LEAVING_HOUSE;
        return;
    }
    CLYDE_POS = addXYOffset_2000(*MOVE_VECTOR_UP, CLYDE_POS);
    CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION = ORIENT_UP;
    if (CLYDE_POS.y != 0x64)
        return;
    CLYDE_TILE.y = 0x2c;
    CLYDE_TILE.x = 0x2e;
    CLYDE_VECTOR.y = CLYDE_VECTOR2.y = 0x00;
    CLYDE_VECTOR.x = CLYDE_VECTOR2.x = 0x01;
    CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION = ORIENT_LEFT;
    CLYDE_SUBSTATE = SUBSTATE_CHASE;
}
void toggleGhostAnimation_0e23(void) {
    if (++GHOST_ANIMATION_COUNTER != 8)
        return;
    GHOST_ANIMATION_COUNTER = 0;
    GHOST_ANIMATION ^= 1;
}
void ghostsChangeOrientation_0e36(void) {
    if (PACMAN_POWEREDUP)
        return;
    if (NONRANDOM_MOVEMENT == 7)
        return;
    ORIENTATION_CHANGE_COUNT++;
    if (ORIENTATION_CHANGE_COUNT != DIFFICULTY_TABLE[NONRANDOM_MOVEMENT])
        return;
    NONRANDOM_MOVEMENT++;
    BLINKY_ORIENT_CHG_FLAG = PINKY_ORIENT_CHG_FLAG = INKY_ORIENT_CHG_FLAG = CLYDE_ORIENT_CHG_FLAG =
        1;
}
void updatePillsEatenSoundEffect_0e6c(void) {
    if (PAC_DEAD_ANIM_STATE != 0) {
        CH2_SOUND_EFFECT->mask = 0;
        return;
    }
    if (P1_PILLS_EATEN_LEVEL >= 0xe4) {
        CH2_SOUND_EFFECT->mask = (CH2_SOUND_EFFECT->mask & 0xe0) | 0x10;
        return;
    }
    if (P1_PILLS_EATEN_LEVEL >= 0xd4) {
        CH2_SOUND_EFFECT->mask = (CH2_SOUND_EFFECT->mask & 0xe0) | 0x08;
        return;
    }
    if (P1_PILLS_EATEN_LEVEL >= 0xb4) {
        CH2_SOUND_EFFECT->mask = (CH2_SOUND_EFFECT->mask & 0xe0) | 0x04;
        return;
    }
    if (P1_PILLS_EATEN_LEVEL >= 0x74) {
        CH2_SOUND_EFFECT->mask = (CH2_SOUND_EFFECT->mask & 0xe0) | 0x02;
        return;
    }
    CH2_SOUND_EFFECT->mask = (CH2_SOUND_EFFECT->mask & 0xe0) | 0x01;
}
void selectFruit_0ead(void) {
    if (PAC_DEAD_ANIM_STATE != 0)
        return;
    if (FRUIT_POINTS != 0)
        return;
    if (P1_PILLS_EATEN_LEVEL != 0x46) {
        if (P1_PILLS_EATEN_LEVEL != 0xaa)
            return;
        if (P1_SECOND_FRUIT != 0)
            return;
        P1_SECOND_FRUIT++;
    } else {
        if (P1_FIRST_FRUIT != 0)
            return;
        P1_FIRST_FRUIT++;
    }
    FRUIT_POS.x = 0x80;
    FRUIT_POS.y = 0x94;
    int a = P1_LEVEL;
    if (a >= 20)
        a = 20;
    a *= 3;
    uint8_t *hl = FRUIT_DATA_0efd;
    FRUIT_SPRITE = fetchOffset_0010(&hl, a);
    FRUIT_COLOUR = hl[1];
    FRUIT_POINTS = hl[2];
    schedISRTask(0x8a, ISRTASK_RESET_FRUIT, 0);
}
void resetFruit_1000(void) {
    FRUIT_POINTS = 0;
    resetFruitState_1004();
}
void resetFruitState_1004(void) { FRUIT_POS.y = FRUIT_POS.x = 0; }
void func_100b(void) {
    schedTask(TASK_DISPLAY_MSG, 0x80 | MSG_100PTS);
    if (MAIN_STATE == MAIN_STATE_DEMO)
        return;
    schedTask(TASK_DISPLAY_MSG, 0x80 | MSG_5000PTS);
}
void updateGhostStates_1017(void) {
    pacmanDeadAnimState_1291();
    ((void)0);
    if (PAC_DEAD_ANIM_STATE != 0)
        return;
    selectGhostState_1066();
    if (BLINKY_STATE)
        blinkyStateMachine_1094();
    if (PINKY_STATE)
        pinkyStateMachine_109e();
    if (INKY_STATE)
        inkyStateMachine_10a8();
    if (CLYDE_STATE)
        clydeStateMachine_10b4();
    if (KILLED_GHOST_INDEX != 0) {
        ghostKilledState_1235();
        return;
    }
    pacmanCheckGhostCoincidence_171d();
    pacmanCheckEatGhost_1789();
    if (KILLED_GHOST_INDEX != 0)
        return;
    pacmanUpdateMovePat_1806();
    blinkyUpdateMovePat_1b36();
    pinkyUpdateMovePat_1c4b();
    inkyUpdateMovePat_1d22();
    clydeUpdateMovePat_1df9();
    if (LEVEL_STATE != LEVEL_STATE_PLAY_GAME)
        return;
    powerupOver_1376();
    pinkyCheckLeaveHouse_2069();
    inkyCheckLeaveHouse_208c();
    clydeCheckLeaveHouse_20af();
}
void selectGhostState_1066(void) {
    if (GHOST_STATE == 0)
        return;
    ((void)0);
    if (GHOST_STATE == GHOST_BLINKY) {
        GHOST_STATE = 0;
        BLINKY_STATE = GHOST_STATE_DEAD;
        return;
    }
    if (GHOST_STATE == GHOST_PINKY) {
        GHOST_STATE = 0;
        PINKY_STATE = GHOST_STATE_DEAD;
        return;
    }
    if (GHOST_STATE == GHOST_INKY) {
        GHOST_STATE = 0;
        INKY_STATE = GHOST_STATE_DEAD;
        return;
    }
    CLYDE_STATE = GHOST_STATE_DEAD;
    GHOST_STATE = 0;
}
void blinkyStateMachine_1094(void) {
    ((void)0);
    static void (*const func[])() = {nothing_000c, blinkyStateDead_10c0,
                                     blinkyStateEnterHouse_10d2};
    tableCall_0020(func, BLINKY_STATE);
}
void pinkyStateMachine_109e(void) {
    static void (*const func[])() = {nothing_000c, pinkyStateDead_1118, pinkyStateEnterHouse_112a};
    tableCall_0020(func, PINKY_STATE);
}
void inkyStateMachine_10a8(void) {
    static void (*const func[])() = {nothing_000c, inkyStateDead_115c, inkyStateEnterHouse_116e,
                                     inkyStateHouseMoveAside_118f};
    tableCall_0020(func, INKY_STATE);
}
void clydeStateMachine_10b4(void) {
    static void (*const func[])() = {nothing_000c, clydeStateDead_11c9, clydeStateEnterHouse_11db,
                                     clydeStateHouseMoveAside_11fc};
    tableCall_0020(func, CLYDE_STATE);
}
void blinkyStateDead_10c0(void) {
    blinkyUpdatePosition_1bd8();
    if (BLINKY_POS.x != 0x80 || BLINKY_POS.y != 0x64)
        return;
    BLINKY_STATE++;
}
void blinkyStateEnterHouse_10d2(void) {
    BLINKY_POS = addXYOffset_2000(*MOVE_VECTOR_DOWN, BLINKY_POS);
    BLINKY_PREV_ORIENTATION = BLINKY_ORIENTATION = ORIENT_DOWN;
    if (BLINKY_POS.y != 0x80)
        return;
    BLINKY_TILE.y = BLINKY_TILE2.y = 0x2f;
    BLINKY_TILE.x = BLINKY_TILE2.x = 0x2e;
    BLINKY_SUBSTATE = SUBSTATE_IN_HOUSE;
    BLINKY_STATE = GHOST_STATE_ALIVE;
    BLINKY_EDIBLE = 0;
    ghostsAnyDeadSoundOff_1101();
}
void ghostsAnyDeadSoundOff_1101(void) {
    if (BLINKY_STATE | PINKY_STATE | INKY_STATE | CLYDE_STATE)
        return;
    CH2_SOUND_EFFECT->mask &= ~0x40;
}
void pinkyStateDead_1118(void) {
    pinkyUpdatePosition_1caf();
    if (PINKY_POS.x != 0x80 || PINKY_POS.y != 0x64)
        return;
    PINKY_STATE++;
}
void pinkyStateEnterHouse_112a(void) {
    PINKY_POS = addXYOffset_2000(*MOVE_VECTOR_DOWN, PINKY_POS);
    PINKY_ORIENTATION = PINKY_PREV_ORIENTATION = ORIENT_DOWN;
    if (PINKY_POS.y != 0x80)
        return;
    PINKY_TILE.y = PINKY_TILE2.y = 0x2f;
    PINKY_TILE.x = PINKY_TILE2.x = 0x2e;
    PINKY_SUBSTATE = SUBSTATE_IN_HOUSE;
    PINKY_STATE = GHOST_STATE_ALIVE;
    PINKY_EDIBLE = 0;
    ghostsAnyDeadSoundOff_1101();
}
void inkyStateDead_115c(void) {
    inkyUpdatePosition_1d86();
    if (INKY_POS.x != 0x80 || INKY_POS.y != 0x64)
        return;
    INKY_STATE++;
}
void inkyStateEnterHouse_116e(void) {
    INKY_POS = addXYOffset_2000(*MOVE_VECTOR_DOWN, INKY_POS);
    INKY_ORIENTATION = INKY_PREV_ORIENTATION = ORIENT_DOWN;
    if (INKY_POS.y != 0x80)
        return;
    INKY_STATE++;
}
void inkyStateHouseMoveAside_118f(void) {
    INKY_POS = addXYOffset_2000(*MOVE_VECTOR_LEFT, INKY_POS);
    INKY_ORIENTATION = INKY_PREV_ORIENTATION = ORIENT_LEFT;
    if (INKY_POS.x != 0x90)
        return;
    INKY_TILE.y = INKY_TILE2.y = 0x2f;
    INKY_TILE.x = INKY_TILE2.x = 0x30;
    INKY_ORIENTATION = INKY_PREV_ORIENTATION = ORIENT_DOWN;
    INKY_SUBSTATE = SUBSTATE_IN_HOUSE;
    INKY_STATE = GHOST_STATE_ALIVE;
    INKY_EDIBLE = 0;
    ghostsAnyDeadSoundOff_1101();
}
void clydeStateDead_11c9(void) {
    clydeUpdatePosition_1e5d();
    if (CLYDE_POS.x != 0x80 || CLYDE_POS.y != 0x64)
        return;
    CLYDE_STATE++;
}
void clydeStateEnterHouse_11db(void) {
    CLYDE_POS = addXYOffset_2000(*MOVE_VECTOR_DOWN, CLYDE_POS);
    CLYDE_ORIENTATION = CLYDE_PREV_ORIENTATION = ORIENT_DOWN;
    if (CLYDE_POS.y != 0x80)
        return;
    CLYDE_STATE++;
}
void clydeStateHouseMoveAside_11fc(void) {
    CLYDE_POS = addXYOffset_2000(*MOVE_VECTOR_RIGHT, CLYDE_POS);
    CLYDE_ORIENTATION = CLYDE_PREV_ORIENTATION = ORIENT_RIGHT;
    if (CLYDE_POS.x != 0x70)
        return;
    CLYDE_TILE.y = CLYDE_TILE2.y = 0x2f;
    CLYDE_TILE.x = CLYDE_TILE2.x = 0x2c;
    CLYDE_ORIENTATION = CLYDE_PREV_ORIENTATION = ORIENT_DOWN;
    CLYDE_SUBSTATE = SUBSTATE_IN_HOUSE;
    CLYDE_STATE = GHOST_STATE_ALIVE;
    CLYDE_EDIBLE = 0;
    ghostsAnyDeadSoundOff_1101();
}
void ghostKilledState_1235(void) {
    static void (*const func[])() = {showKillPoints_123f, nothing_000c, showKillPoints_123f};
    tableCall_0020(func, KILLED_STATE);
}
void showKillPoints_123f(void) {
    uint8_t *hl = &BLINKY_SPRITE + KILLED_GHOST_INDEX * 2 - 2;
    ((void)0);
    if (KILLED_STATE == 0) {
        uint8_t b = KILLED_COUNT + 0x27;
        if ((COCKTAIL_MODE & PLAYER) != 0) {
            b |= (IMG_MIRROR | IMG_INVERT);
        }
        hl[0] = b;
        hl[1] = 0x18;
        PACMAN_COLOUR = 0;
        schedISRTask(0x4a, ISRTASK_INC_KILLED_STATE, 0x00);
        KILLED_STATE++;
        return;
    }
    hl[0] = 0x20;
    PACMAN_COLOUR = 9;
    GHOST_STATE = KILLED_GHOST_INDEX;
    ((void)0);
    KILLED_GHOST_INDEX = KILLED_STATE = 0;
    CH2_SOUND_EFFECT->mask |= 0x40;
}
void pacmanDeadAnimState_1291(void) {
    static void (*const func[])() = {nothing_000c,
                                     pacmanDeadAnimState1To4_12b7,
                                     pacmanDeadAnimState1To4_12b7,
                                     pacmanDeadAnimState1To4_12b7,
                                     pacmanDeadAnimState1To4_12b7,
                                     pacmanDeadAnimState5_12cb,
                                     pacmanDeadAnimState6_12f9,
                                     pacmanDeadAnimState7_1306,
                                     pacmanDeadAnimState8_130e,
                                     pacmanDeadAnimState9_1316,
                                     pacmanDeadAnimState10_131e,
                                     pacmanDeadAnimState11_1326,
                                     pacmanDeadAnimState12_132e,
                                     pacmanDeadAnimState13_1336,
                                     pacmanDeadAnimState14_133e,
                                     pacmanDeadAnimState15_1346,
                                     decrementLives_1353};
    tableCall_0020(func, PAC_DEAD_ANIM_STATE);
}
void incKilledState_1272(void) { KILLED_STATE++; }
void pacmanDeadAnimState1To4_12b7(void) {
    COUNT_SINCE_PAC_KILLED++;
    if (COUNT_SINCE_PAC_KILLED != 0x78)
        return;
    PAC_DEAD_ANIM_STATE = 5;
}
void pacmanDeadAnimState5_12cb(void) {
    setGhostPosition_267e(0, 0);
    pacmanDeadAnimation_12d6(0x34, 0xb4);
}
void pacmanDeadAnimation_12d6(uint8_t ch, int count) {
    if (COCKTAIL_MODE & PLAYER) {
        ch |= 0xc0;
    }
    PACMAN_SPRITE = ch;
    if (++COUNT_SINCE_PAC_KILLED != count)
        return;
    PAC_DEAD_ANIM_STATE++;
}
void pacmanDeadAnimState6_12f9(void) {
    CH3_SOUND_EFFECT->mask |= 0x10;
    pacmanDeadAnimation_12d6(0x35, 0xc3);
}
void pacmanDeadAnimState7_1306(void) { pacmanDeadAnimation_12d6(0x36, 0xd2); }
void pacmanDeadAnimState8_130e(void) { pacmanDeadAnimation_12d6(0x37, 0xe1); }
void pacmanDeadAnimState9_1316(void) { pacmanDeadAnimation_12d6(0x38, 0xf0); }
void pacmanDeadAnimState10_131e(void) { pacmanDeadAnimation_12d6(0x39, 0xff); }
void pacmanDeadAnimState11_1326(void) { pacmanDeadAnimation_12d6(0x3a, 0x10e); }
void pacmanDeadAnimState12_132e(void) { pacmanDeadAnimation_12d6(0x3b, 0x11d); }
void pacmanDeadAnimState13_1336(void) { pacmanDeadAnimation_12d6(0x3c, 0x12c); }
void pacmanDeadAnimState14_133e(void) { pacmanDeadAnimation_12d6(0x3d, 0x13b); }
void pacmanDeadAnimState15_1346(void) {
    CH3_SOUND_EFFECT->mask = 0x20;
    pacmanDeadAnimation_12d6(0x3e, 0x159);
}
void decrementLives_1353(void) {
    PACMAN_SPRITE = 0x3f;
    if (++COUNT_SINCE_PAC_KILLED != 0x1b8)
        return;
    P1_REAL_LIVES--;
    P1_DISPLAY_LIVES--;
    resetPositions_2675();
    LEVEL_STATE++;
}
void powerupOver_1376(void) {
    if (PACMAN_POWEREDUP == 0)
        return;
    if ((*(uint32_t *)&BLINKY_EDIBLE) != 0) {
        if (--EDIBLE_REMAIN_COUNT != 0)
            return;
    }
    PACMAN_COLOUR = 9;
    if (BLINKY_STATE == GHOST_STATE_ALIVE) {
        BLINKY_EDIBLE = 0;
    }
    if (PINKY_STATE == GHOST_STATE_ALIVE) {
        PINKY_EDIBLE = 0;
    }
    if (INKY_STATE == GHOST_STATE_ALIVE) {
        INKY_EDIBLE = 0;
    }
    if (CLYDE_STATE == GHOST_STATE_ALIVE) {
        CLYDE_EDIBLE = 0;
    }
    EDIBLE_REMAIN_COUNT = 0;
    PACMAN_POWEREDUP = 0;
    GHOST_COL_POWERUP_COUNTER = 0;
    KILLED_COUNT = 0;
    CH2_SOUND_EFFECT->mask &= 0x5f;
}
void checkInactivityCounter_13dd(void) {
    if (P1_PILLS_EATEN_LEVEL != EATEN_SINCE_MOVE) {
        UNITS_INACTIVITY_COUNTER = 0;
        return;
    }
    UNITS_INACTIVITY_COUNTER++;
    ((void)0);
    if (UNITS_INACTIVITY_COUNTER != UNITS_B4_GHOST_LEAVES_HOME)
        return;
    UNITS_INACTIVITY_COUNTER = 0;
    if (PINKY_SUBSTATE == SUBSTATE_IN_HOUSE) {
        PINKY_SUBSTATE = SUBSTATE_LEAVING_HOUSE;
        return;
    }
    if (INKY_SUBSTATE == SUBSTATE_IN_HOUSE) {
        INKY_SUBSTATE = SUBSTATE_HOUSE_MOVE;
        return;
    }
    if (CLYDE_SUBSTATE == SUBSTATE_IN_HOUSE)
        CLYDE_SUBSTATE = SUBSTATE_HOUSE_MOVE;
}
void spriteAnimationUpright_141f(void) {
    if ((COCKTAIL_MODE & PLAYER) == 0)
        return;
    arcade_byte(0x4c13) = BLINKY_POS.y + 8;
    arcade_byte(0x4c12) = 6 - BLINKY_POS.x;
    arcade_byte(0x4c15) = PINKY_POS.y + 8;
    arcade_byte(0x4c14) = 6 - PINKY_POS.x;
    arcade_byte(0x4c17) = INKY_POS.y + 8;
    arcade_byte(0x4c16) = 7 - INKY_POS.x;
    arcade_byte(0x4c19) = CLYDE_POS.y + 8;
    arcade_byte(0x4c18) = 7 - CLYDE_POS.x;
    arcade_byte(0x4c1b) = PACMAN_POS.y + 8;
    arcade_byte(0x4c1a) = 7 - PACMAN_POS.x;
    arcade_byte(0x4c1d) = FRUIT_POS.y + 8;
    arcade_byte(0x4c1c) = 7 - FRUIT_POS.x;
    spriteAnimation_14fe(true);
}
void spriteAnimationCocktail_1490(void) {
    if ((COCKTAIL_MODE & PLAYER) != 0)
        return;
    arcade_byte(0x4c13) = 8 - BLINKY_POS.y;
    arcade_byte(0x4c12) = BLINKY_POS.x + 6;
    arcade_byte(0x4c15) = 8 - PINKY_POS.y;
    arcade_byte(0x4c14) = PINKY_POS.x + 6;
    arcade_byte(0x4c17) = 8 - INKY_POS.y;
    arcade_byte(0x4c16) = INKY_POS.x + 7;
    arcade_byte(0x4c19) = 8 - CLYDE_POS.y;
    arcade_byte(0x4c18) = CLYDE_POS.x + 7;
    arcade_byte(0x4c1b) = 8 - PACMAN_POS.y;
    arcade_byte(0x4c1a) = PACMAN_POS.x + 7;
    arcade_byte(0x4c1d) = 8 - FRUIT_POS.y;
    arcade_byte(0x4c1c) = FRUIT_POS.x + 7;
    spriteAnimation_14fe(false);
}
void spriteAnimation_14fe(bool invert) {
    if (PAC_DEAD_ANIM_STATE == 0) {
        if (KILLED_GHOST_INDEX != 0) {
            ghostsCocktailMode_15b4(invert);
            return;
        }
        static void (*const func[])() = {selectPacmanLeftSprite_168c, selectPacmanDownSprite_16b1,
                                         selectPacmanRightSprite_16d6, selectPacmanUpSprite_16f7};
        tableCall_0020(func, PACMAN_ORIENTATION);
        ((void)0);
        if (invert) {
            if ((PACMAN_SPRITE & 0xc0) == 0) {
                PACMAN_SPRITE |= 0xc0;
            } else {
                if (PACMAN_ORIENTATION == ORIENT_LEFT) {
                    if (PACMAN_SPRITE & 0x80) {
                        PACMAN_SPRITE ^= 0xc0;
                    }
                } else if (PACMAN_ORIENTATION == ORIENT_UP) {
                    if ((PACMAN_SPRITE & 0x40) != 0) {
                        PACMAN_SPRITE ^= 0xc0;
                    }
                }
            }
        }
    }
    BLINKY_SPRITE = PINKY_SPRITE = INKY_SPRITE = CLYDE_SPRITE = GHOST_ANIMATION + 0x1c;
    if (BLINKY_STATE != 0 || BLINKY_EDIBLE == 0) {
        BLINKY_SPRITE = BLINKY_ORIENTATION * 2 + GHOST_ANIMATION + 0x20;
    }
    if (PINKY_STATE != 0 || PINKY_EDIBLE == 0) {
        PINKY_SPRITE = PINKY_ORIENTATION * 2 + GHOST_ANIMATION + 0x20;
    }
    if (INKY_STATE != 0 || INKY_EDIBLE == 0) {
        INKY_SPRITE = INKY_ORIENTATION * 2 + GHOST_ANIMATION + 0x20;
    }
    if (CLYDE_STATE != 0 || CLYDE_EDIBLE == 0) {
        CLYDE_SPRITE = CLYDE_ORIENTATION * 2 + GHOST_ANIMATION + 0x20;
    }
    ghostsCocktailMode_15b4(invert);
}
void ghostsCocktailMode_15b4(bool invert) {
    scene1Animation_15e6();
    scene2Animation_162d();
    scene3Animation_1652();
    if (!invert)
        return;
    BLINKY_SPRITE |= 0xc0;
    PINKY_SPRITE |= 0xc0;
    INKY_SPRITE |= 0xc0;
    CLYDE_SPRITE |= 0xc0;
    FRUIT_SPRITE |= 0xc0;
}
__attribute__((section(".cold"))) void scene1Animation_15e6(void) {
    if (SCENE1_STATE < 5)
        return;
    int a = PACMAN_POS.x & 0xf;
    int d;
    if (a >= 0xc) {
        d = 0x18;
    } else if (a >= 8) {
        d = 0x14;
    } else if (a >= 4) {
        d = 0x10;
    } else {
        d = 0x14;
    }
    PINKY_SPRITE = d++;
    INKY_SPRITE = d++;
    CLYDE_SPRITE = d++;
    FRUIT_SPRITE = d++;
    PACMAN_SPRITE = 0x3f;
    PINKY_COLOUR = INKY_COLOUR = CLYDE_COLOUR = FRUIT_COLOUR = 0x16;
}
__attribute__((section(".cold"))) void scene2Animation_162d(void) {
    if (SCENE2_STATE == 0)
        return;
    if (PACMAN_TILE2.x == 0x3d) {
        PACMAN_COLOUR = 0;
    }
    if (SCENE2_STATE < 0xa)
        return;
    BLINKY_SPRITE = 0x32;
    BLINKY_COLOUR = 0x1d;
    if (SCENE2_STATE < 0xc)
        return;
    BLINKY_SPRITE = 0x33;
}
__attribute__((section(".cold"))) void scene3Animation_1652(void) {
    if (SCENE3_STATE == 0)
        return;
    if (PACMAN_TILE2.x == 0x3d) {
        PACMAN_COLOUR = 0;
    }
    if (SCENE3_STATE < 0x1)
        return;
    BLINKY_SPRITE = GHOST_ANIMATION + 8;
    if (SCENE3_STATE < 0x3)
        return;
    FRUIT_SPRITE = ((BLINKY_POS.x & 8) >> 3) + 0xa;
    BLINKY_SPRITE = FRUIT_SPRITE + 2;
    FRUIT_COLOUR = 0x1e;
}
void selectPacmanLeftSprite_168c(void) {
    int a = PACMAN_POS.x & 7;
    if (a >= 6) {
        PACMAN_SPRITE = 0x30;
        return;
    }
    if (a >= 4) {
        PACMAN_SPRITE = 0x2e;
        return;
    }
    if (a >= 2) {
        PACMAN_SPRITE = 0x2c;
        return;
    }
    PACMAN_SPRITE = 0x2e;
    return;
}
void selectPacmanDownSprite_16b1(void) {
    int a = PACMAN_POS.y & 7;
    if (a >= 6) {
        PACMAN_SPRITE = 0x2f;
        return;
    }
    if (a >= 4) {
        PACMAN_SPRITE = 0x2d;
        return;
    }
    if (a >= 2) {
        PACMAN_SPRITE = 0x2f;
        return;
    }
    PACMAN_SPRITE = 0x30;
}
void selectPacmanRightSprite_16d6(void) {
    int a = PACMAN_POS.x & 7;
    if (a >= 6) {
        PACMAN_SPRITE = 0x2e | 0x80;
        return;
    }
    if (a >= 4) {
        PACMAN_SPRITE = 0x2c | 0x80;
        return;
    }
    PACMAN_SPRITE = (a < 2 ? 0x30 : 0x2e) | 0x80;
}
void selectPacmanUpSprite_16f7(void) {
    int a = PACMAN_POS.y & 7;
    if (a >= 6) {
        PACMAN_SPRITE = 0x30;
        return;
    }
    if (a >= 4) {
        PACMAN_SPRITE = 0x2f | 0x40;
        return;
    }
    if (a >= 2) {
        PACMAN_SPRITE = 0x2d | 0x40;
        return;
    }
    PACMAN_SPRITE = 0x2f | 0x40;
}
void pacmanCheckGhostCoincidence_171d(void) {
    if (CLYDE_STATE == GHOST_STATE_ALIVE && CLYDE_TILE2.y == PACMAN_TILE2.y &&
        CLYDE_TILE2.x == PACMAN_TILE2.x) {
        pacmanGhostCoincide_1763(GHOST_CLYDE);
        return;
    }
    if (INKY_STATE == GHOST_STATE_ALIVE && INKY_TILE2.y == PACMAN_TILE2.y &&
        INKY_TILE2.x == PACMAN_TILE2.x) {
        pacmanGhostCoincide_1763(GHOST_INKY);
        return;
    }
    if (PINKY_STATE == GHOST_STATE_ALIVE && PINKY_TILE2.y == PACMAN_TILE2.y &&
        PINKY_TILE2.x == PACMAN_TILE2.x) {
        pacmanGhostCoincide_1763(GHOST_PINKY);
        return;
    }
    if (BLINKY_STATE == GHOST_STATE_ALIVE && BLINKY_TILE2.y == PACMAN_TILE2.y &&
        BLINKY_TILE2.x == PACMAN_TILE2.x) {
        pacmanGhostCoincide_1763(GHOST_BLINKY);
        return;
    }
    pacmanGhostCoincide_1763(0);
}
void pacmanGhostCoincide_1763(uint8_t b) {
    KILLED_GHOST_INDEX = PAC_DEAD_ANIM_STATE = b;
    if (b == 0)
        return;
    ((void)0);
    uint8_t edible = (&BLINKY_EDIBLE)[b - 1];
    ((void)0);
    if (edible == 0)
        return;
    PAC_DEAD_ANIM_STATE = 0;
    KILLED_COUNT++;
    addToScore_2a5a(KILLED_COUNT + 1);
    CH3_SOUND_EFFECT->mask |= 0x8;
}
void pacmanCheckEatGhost_1789(void) {
    if (KILLED_GHOST_INDEX != 0)
        return;
    if (PACMAN_POWEREDUP == 0)
        return;
    uint8_t dx = CLYDE_POS.x - PACMAN_POS.x;
    uint8_t dy = CLYDE_POS.y - PACMAN_POS.y;
    if (CLYDE_STATE == GHOST_STATE_ALIVE && dx >= 0 && dx < 4 && dy >= 0 && dy < 4) {
        ((void)0);
        pacmanGhostCoincide_1763(GHOST_CLYDE);
        return;
    }
    dx = INKY_POS.x - PACMAN_POS.x;
    dy = INKY_POS.y - PACMAN_POS.y;
    if (INKY_STATE == GHOST_STATE_ALIVE && dx >= 0 && dx < 4 && dy >= 0 && dy < 4) {
        ((void)0);
        pacmanGhostCoincide_1763(GHOST_INKY);
        return;
    }
    dx = PINKY_POS.x - PACMAN_POS.x;
    dy = PINKY_POS.y - PACMAN_POS.y;
    if (PINKY_STATE == GHOST_STATE_ALIVE && dx >= 0 && dx < 4 && dy >= 0 && dy < 4) {
        ((void)0);
        pacmanGhostCoincide_1763(GHOST_PINKY);
        return;
    }
    dx = BLINKY_POS.x - PACMAN_POS.x;
    dy = BLINKY_POS.y - PACMAN_POS.y;
    if (BLINKY_STATE == GHOST_STATE_ALIVE && dx >= 0 && dx < 4 && dy >= 0 && dy < 4) {
        ((void)0);
        pacmanGhostCoincide_1763(GHOST_BLINKY);
        return;
    }
    pacmanGhostCoincide_1763(0);
}
void pacmanUpdateMovePat_1806(void) {
    if (PACMAN_MOVE_DELAY != 0xff) {
        PACMAN_MOVE_DELAY--;
        return;
    }
    if (PACMAN_POWEREDUP != 0) {
        rotate32(&PACMAN_MOVE_PAT_POWERUP, 1);
        if ((PACMAN_MOVE_PAT_POWERUP & 0x10000) == 0)
            return;
    } else {
        rotate32(&PACMAN_MOVE_PAT_NORMAL, 1);
        if ((PACMAN_MOVE_PAT_NORMAL & 0x10000) == 0)
            return;
    }
    EATEN_SINCE_MOVE = P1_PILLS_EATEN_LEVEL;
    int inverted = (COCKTAIL_MODE & PLAYER);
    if (PACMAN_TILE2.x < 0x21 || PACMAN_TILE2.x >= 0x3b) {
        PACMAN_IN_TUNNEL = 1;
        if (MAIN_STATE == MAIN_STATE_DEMO) {
            pacmanDemoMoveTile_1a19();
            return;
        }
        if (LEVEL_STATE >= 0x10) {
            pacmanDemoMoveTile_1a19();
            return;
        }
        int input;
        if (inverted) {
            input = IO_INPUT1;
        } else {
            input = IO_INPUT0;
        }
        if (~input & INPUT_LEFT) {
            PACMAN_ORIENTATION = ORIENT_LEFT;
            PACMAN_VECTOR = *MOVE_VECTOR_LEFT;
            pacmanMove_1950();
            return;
        } else if (~input & INPUT_RIGHT) {
            PACMAN_ORIENTATION = ORIENT_RIGHT;
            PACMAN_VECTOR = *MOVE_VECTOR_RIGHT;
        }
        pacmanMove_1950();
        return;
    }
    if (MAIN_STATE == MAIN_STATE_DEMO) {
        pacmanDemoMoveTile_1a19();
        return;
    }
    if (LEVEL_STATE >= 0x10) {
        pacmanDemoMoveTile_1a19();
        return;
    }
    int input;
    if (inverted) {
        input = IO_INPUT1;
    } else {
        input = IO_INPUT0;
    }
    if (~input & INPUT_LEFT) {
        pacmanOrientLeft_1ac9();
        return;
    }
    if (~input & INPUT_RIGHT) {
        pacmanOrientRight_1ad9();
        return;
    }
    if (~input & INPUT_UP) {
        pacmanOrientUp_1ae8();
        return;
    }
    if (~input & INPUT_DOWN) {
        pacmanOrientDown_1af8();
        return;
    }
    PACMAN_VECTOR2 = PACMAN_VECTOR;
    pacmanCheckMoveClear_18e4(1);
}
void pacmanCheckMoveClear_18e4(uint8_t noInput) {
    ((void)0);
    int a = getScreenCharPosOffset_200f(PACMAN_VECTOR2, PACMAN_TILE2);
    if ((a & CHAR_MAZE_MASK) != CHAR_MAZE_MASK) {
        pacmanHitMazeWall_1940(noInput);
        return;
    }
    if (noInput == 1) {
        if ((PACMAN_ORIENTATION & ORIENT_VERTICAL) == 0) {
            if ((PACMAN_POS.x & 7) == 4)
                return;
            pacmanHitMazeWall_1940(1);
            return;
        } else {
            if ((PACMAN_POS.y & 7) == 4)
                return;
            pacmanHitMazeWall_1940(1);
            return;
        }
    }
    a = getScreenCharPosOffset_200f(PACMAN_VECTOR, PACMAN_TILE2);
    if ((a & CHAR_MAZE_MASK) != CHAR_MAZE_MASK) {
        pacmanMove_1950();
        return;
    }
    if ((PACMAN_ORIENTATION & ORIENT_VERTICAL) == 0) {
        if ((PACMAN_POS.x & 7) == 4)
            return;
        pacmanMove_1950();
        return;
    }
    if ((PACMAN_POS.y & 7) == 4)
        return;
    pacmanMove_1950();
}
void pacmanHitMazeWall_1940(uint8_t noInput) {
    PACMAN_VECTOR = PACMAN_VECTOR2;
    if (noInput != 1)
        PACMAN_ORIENTATION = PACMAN_DESIRED_ORIENTATION;
    pacmanMove_1950();
}
void pacmanMove_1950(void) {
    ((void)0);
    XYPOS pacmanXY = addXYOffset_2000(PACMAN_VECTOR, PACMAN_POS);
    ((void)0);
    if ((PACMAN_ORIENTATION & ORIENT_VERTICAL) == 0) {
        if ((pacmanXY.y & 7) != 4) {
            if ((pacmanXY.y & 7) < 4)
                pacmanXY.y++;
            else
                pacmanXY.y--;
        }
    } else {
        if ((pacmanXY.x & 7) != 4) {
            if ((pacmanXY.x & 7) < 4)
                pacmanXY.x++;
            else
                pacmanXY.x--;
        }
    }
    pacmanUpdatePos_1985(pacmanXY);
}
void pacmanUpdatePos_1985(XYPOS pos) {
    ((void)0);
    PACMAN_POS = pos;
    PACMAN_TILE2 = pixelToTile_2018(pos);
    ((void)0);
    if (PACMAN_IN_TUNNEL) {
        PACMAN_IN_TUNNEL = 0;
        return;
    }
    if (FRUIT_POS.y != 0) {
        if (FRUIT_POINTS != 0) {
            if (PACMAN_POS.x == 0x80 && PACMAN_POS.y == 0x94) {
                addTask_0042(0x19, FRUIT_POINTS);
                addTask_0042(TASK_DISPLAY_MSG, FRUIT_POINTS + 0x15);
                resetFruitState_1004();
                schedISRTask(0x54, 0x05, 0x00);
                CH3_SOUND_EFFECT->mask |= 0x4;
            }
        }
    }
    PACMAN_MOVE_DELAY = 0xff;
    uint16_t addr = getScreenOffset_0065(PACMAN_TILE2);
    if (SCREEN[addr] != CHAR_PILL && SCREEN[addr] != CHAR_POWERUP)
        return;
    P1_PILLS_EATEN_LEVEL++;
    int a = (SCREEN[addr] & 0xf) >> 1;
    video_store(&SCREEN[addr], 0x40);
    addTask_0042(TASK_ADD_TO_SCORE, a >> 1);
    a++;
    if (a != 1) {
        a *= 2;
    }
    PACMAN_MOVE_DELAY = a;
    updateLeaveHouseCounters_1b08();
    checkGhostsBecomeEdible_1a6a();
    if ((P1_PILLS_EATEN_LEVEL & 1) == 0) {
        CH3_SOUND_EFFECT->mask |= 1;
        CH3_SOUND_EFFECT->mask &= 0xfd;
        return;
    } else {
        CH3_SOUND_EFFECT->mask &= 0xfe;
        CH3_SOUND_EFFECT->mask |= 2;
        return;
    }
}
void pacmanDemoMoveTile_1a19(void) {
    ((void)0);
    if (PACMAN_VECTOR.y != 0) {
        if ((PACMAN_POS.y & 7) != 4) {
            pacmanMove_1a5c();
            return;
        }
    } else {
        if ((PACMAN_POS.x & 7) != 4) {
            pacmanMove_1a5c();
            return;
        }
    }
    if (!checkTunnelWrap_1ed0(DEMO_PACMAN)) {
        schedTask(TASK_PACMAN_ORIENT, 0);
    }
    PACMAN_TILE = addXYOffset_2000(PACMAN_VECTOR2, PACMAN_TILE);
    PACMAN_VECTOR = PACMAN_VECTOR2;
    PACMAN_ORIENTATION = PACMAN_DESIRED_ORIENTATION;
    pacmanMove_1a5c();
}
void pacmanMove_1a5c(void) {
    XYPOS pos = addXYOffset_2000(PACMAN_VECTOR, PACMAN_POS);
    pacmanUpdatePos_1985(pos);
}
void checkGhostsBecomeEdible_1a6a(void) {
    ((void)0);
    if (PACMAN_MOVE_DELAY != 0x6)
        return;
    ghostsBecomeEdible_1a70();
}
void ghostsBecomeEdible_1a70(void) {
    EDIBLE_REMAIN_COUNT = GHOST_EDIBLE_TIME;
    PACMAN_POWEREDUP = BLINKY_EDIBLE = PINKY_EDIBLE = INKY_EDIBLE = CLYDE_EDIBLE =
        BLINKY_ORIENT_CHG_FLAG = PINKY_ORIENT_CHG_FLAG = INKY_ORIENT_CHG_FLAG =
            CLYDE_ORIENT_CHG_FLAG = PACMAN_ORIENT_CHG_FLAG = 1;
    GHOST_COL_POWERUP_COUNTER = KILLED_COUNT = 0;
    BLINKY_SPRITE = PINKY_SPRITE = INKY_SPRITE = CLYDE_SPRITE = 0x1c;
    BLINKY_COLOUR = PINKY_COLOUR = INKY_COLOUR = CLYDE_COLOUR = 0x11;
    CH2_SOUND_EFFECT->mask |= 0x20;
    CH2_SOUND_EFFECT->mask &= ~0x80;
}
void pacmanOrientLeft_1ac9(void) {
    PACMAN_DESIRED_ORIENTATION = ORIENT_LEFT;
    PACMAN_VECTOR2 = *MOVE_VECTOR_LEFT;
    pacmanCheckMoveClear_18e4(0);
}
void pacmanOrientRight_1ad9(void) {
    PACMAN_DESIRED_ORIENTATION = ORIENT_RIGHT;
    PACMAN_VECTOR2 = *MOVE_VECTOR_RIGHT;
    pacmanCheckMoveClear_18e4(0);
}
void pacmanOrientUp_1ae8(void) {
    PACMAN_DESIRED_ORIENTATION = ORIENT_UP;
    PACMAN_VECTOR2 = *MOVE_VECTOR_UP;
    pacmanCheckMoveClear_18e4(0);
}
void pacmanOrientDown_1af8(void) {
    PACMAN_DESIRED_ORIENTATION = ORIENT_DOWN;
    PACMAN_VECTOR2 = *MOVE_VECTOR_DOWN;
    pacmanCheckMoveClear_18e4(0);
}
void updateLeaveHouseCounters_1b08(void) {
    if (P1_DIED_IN_LEVEL != 0) {
        EATEN_PILLS_COUNT++;
    }
    if (CLYDE_SUBSTATE != SUBSTATE_IN_HOUSE)
        return;
    if (INKY_SUBSTATE != SUBSTATE_IN_HOUSE) {
        P1_CLYDE_LEAVE_HOME_COUNTER++;
        return;
    }
    if (PINKY_SUBSTATE != SUBSTATE_IN_HOUSE) {
        P1_INKY_LEAVE_HOME_COUNTER++;
        return;
    }
    P1_PINKY_LEAVE_HOME_COUNTER++;
}
void blinkyUpdateMovePat_1b36(void) {
    ((void)0);
    if (BLINKY_SUBSTATE == SUBSTATE_IN_HOUSE)
        return;
    if (BLINKY_STATE != 0)
        return;
    cruiseElroyMode_20d7();
    checkGhostEnterTunnel_205a(BLINKY_TILE2, &BLINKY_IN_TUNNEL);
    ((void)0);
    if (BLINKY_IN_TUNNEL != 0) {
        rotate32(&BLINKY_MOVE_PAT_TUNNEL, 1);
        if ((BLINKY_MOVE_PAT_TUNNEL & 0x10000) == 0)
            return;
    } else if (BLINKY_EDIBLE != 0) {
        rotate32(&BLINKY_MOVE_PAT_EDIBLE, 1);
        if ((BLINKY_MOVE_PAT_EDIBLE & 0x10000) == 0)
            return;
    } else if (CRUISE_ELROY_MODE_2 != 0) {
        rotate32(&BLINKY_MOVE_PAT_DIFF2, 1);
        if ((BLINKY_MOVE_PAT_DIFF2 & 0x10000) == 0)
            return;
    } else {
        if (CRUISE_ELROY_MODE_1 != 0) {
            rotate32(&BLINKY_MOVE_PAT_DIFF1, 1);
            if ((BLINKY_MOVE_PAT_DIFF1 & 0x10000) == 0)
                return;
        } else {
            rotate32(&BLINKY_MOVE_PAT_NORMAL, 1);
            if ((BLINKY_MOVE_PAT_NORMAL & 0x10000) == 0)
                return;
        }
    }
    blinkyUpdatePosition_1bd8();
}
void blinkyUpdatePosition_1bd8(void) {
    if (BLINKY_VECTOR.y != 0) {
        if ((BLINKY_POS.y & 7) != 4)
            goto jump_1c36;
    } else {
        if ((BLINKY_POS.x & 7) != 4)
            goto jump_1c36;
    }
    if (!checkTunnelWrap_1ed0(GHOST_BLINKY)) {
        if (BLINKY_EDIBLE != 0) {
            schedTask(TASK_HOME_RANDOM_BLINKY, 0x00);
        } else {
            uint16_t addr = getColourOffset_2052(BLINKY_TILE);
            if (COLOUR[addr] != 0x1a) {
                schedTask(TASK_SCATTER_CHASE_BLINKY, 0x00);
            } else
                ((void)0);
        }
    } else
        ((void)0);
    blinkyCheckReverse_1efe();
    BLINKY_TILE = addXYOffset_2000(BLINKY_VECTOR2, BLINKY_TILE);
    BLINKY_VECTOR = BLINKY_VECTOR2;
    BLINKY_PREV_ORIENTATION = BLINKY_ORIENTATION;
jump_1c36:
    BLINKY_POS = addXYOffset_2000(BLINKY_VECTOR, BLINKY_POS);
    BLINKY_TILE2 = pixelToTile_2018(BLINKY_POS);
    ((void)0);
}
void pinkyUpdateMovePat_1c4b(void) {
    if (PINKY_SUBSTATE != SUBSTATE_CHASE)
        return;
    if (PINKY_STATE != GHOST_STATE_ALIVE)
        return;
    checkGhostEnterTunnel_205a(PINKY_TILE2, &PINKY_IN_TUNNEL);
    if (PINKY_IN_TUNNEL != 0) {
        rotate32(&PINKY_MOVE_PAT_TUNNEL, 1);
        if ((PINKY_MOVE_PAT_TUNNEL & 0x10000) == 0)
            return;
    } else {
        if (PINKY_EDIBLE != 0) {
            rotate32(&PINKY_MOVE_PAT_EDIBLE, 1);
            if ((PINKY_MOVE_PAT_EDIBLE & 0x10000) == 0)
                return;
        } else {
            rotate32(&PINKY_MOVE_PAT_NORMAL, 1);
            if ((PINKY_MOVE_PAT_NORMAL & 0x10000) == 0)
                return;
        }
    }
    pinkyUpdatePosition_1caf();
}
void pinkyUpdatePosition_1caf(void) {
    if (PINKY_VECTOR.y != 0) {
        if ((PINKY_POS.y & 7) != 4)
            goto jump_1d0d;
    } else {
        if ((PINKY_POS.x & 7) != 4)
            goto jump_1d0d;
    }
    if (!checkTunnelWrap_1ed0(GHOST_PINKY)) {
        if (PINKY_EDIBLE != 0) {
            schedTask(TASK_HOME_RANDOM_PINKY, 0x00);
        } else {
            uint16_t addr = getColourOffset_2052(PINKY_TILE);
            if (COLOUR[addr] != 0x1a) {
                schedTask(TASK_SCATTER_CHASE_PINKY, 0x00);
            }
        }
    }
    pinkyCheckReverse_1f25();
    PINKY_TILE = addXYOffset_2000(PINKY_VECTOR2, PINKY_TILE);
    PINKY_VECTOR = PINKY_VECTOR2;
    PINKY_PREV_ORIENTATION = PINKY_ORIENTATION;
jump_1d0d:
    PINKY_POS = addXYOffset_2000(PINKY_VECTOR, PINKY_POS);
    PINKY_TILE2 = pixelToTile_2018(PINKY_POS);
}
void inkyUpdateMovePat_1d22(void) {
    if (INKY_SUBSTATE != SUBSTATE_CHASE)
        return;
    if (INKY_STATE != GHOST_STATE_ALIVE)
        return;
    checkGhostEnterTunnel_205a(INKY_TILE2, &INKY_IN_TUNNEL);
    if (INKY_IN_TUNNEL != 0) {
        rotate32(&INKY_MOVE_PAT_TUNNEL, 1);
        if ((INKY_MOVE_PAT_TUNNEL & 0x10000) == 0)
            return;
    } else {
        if (INKY_EDIBLE != 0) {
            rotate32(&INKY_MOVE_PAT_EDIBLE, 1);
            if ((INKY_MOVE_PAT_EDIBLE & 0x10000) == 0)
                return;
        } else {
            rotate32(&INKY_MOVE_PAT_NORMAL, 1);
            if ((INKY_MOVE_PAT_NORMAL & 0x10000) == 0)
                return;
        }
    }
    inkyUpdatePosition_1d86();
}
void inkyUpdatePosition_1d86(void) {
    if (INKY_VECTOR.y != 0) {
        if ((INKY_POS.y & 7) != 4)
            goto jump_1de4;
    } else {
        if ((INKY_POS.x & 7) != 4)
            goto jump_1de4;
    }
    if (!checkTunnelWrap_1ed0(GHOST_INKY)) {
        if (INKY_EDIBLE != 0) {
            schedTask(TASK_HOME_RANDOM_INKY, 0x00);
        } else {
            uint16_t addr = getColourOffset_2052(INKY_TILE);
            if (COLOUR[addr] != 0x1a) {
                schedTask(TASK_SCATTER_CHASE_INKY, 0x00);
            }
        }
    }
    inkyCheckReverse_1f4c();
    INKY_TILE = addXYOffset_2000(INKY_VECTOR2, INKY_TILE);
    INKY_VECTOR = INKY_VECTOR2;
    INKY_PREV_ORIENTATION = INKY_ORIENTATION;
jump_1de4:
    INKY_POS = addXYOffset_2000(INKY_VECTOR, INKY_POS);
    INKY_TILE2 = pixelToTile_2018(INKY_POS);
}
void clydeUpdateMovePat_1df9(void) {
    if (CLYDE_SUBSTATE != SUBSTATE_CHASE)
        return;
    if (CLYDE_STATE != GHOST_STATE_ALIVE)
        return;
    checkGhostEnterTunnel_205a(CLYDE_TILE2, &CLYDE_IN_TUNNEL);
    if (CLYDE_IN_TUNNEL != 0) {
        rotate32(&CLYDE_MOVE_PAT_TUNNEL, 1);
        if ((CLYDE_MOVE_PAT_TUNNEL & 0x10000) == 0)
            return;
    } else {
        if (CLYDE_EDIBLE != 0) {
            rotate32(&CLYDE_MOVE_PAT_EDIBLE, 1);
            if ((CLYDE_MOVE_PAT_EDIBLE & 0x10000) == 0)
                return;
        } else {
            rotate32(&CLYDE_MOVE_PAT_NORMAL, 1);
            if ((CLYDE_MOVE_PAT_NORMAL & 0x10000) == 0)
                return;
        }
    }
    clydeUpdatePosition_1e5d();
}
void clydeUpdatePosition_1e5d(void) {
    if (CLYDE_VECTOR.y != 0) {
        if ((CLYDE_POS.y & 7) != 4)
            goto jump_1ebb;
    } else {
        if ((CLYDE_POS.x & 7) != 4)
            goto jump_1ebb;
    }
    if (!checkTunnelWrap_1ed0(GHOST_CLYDE)) {
        if (CLYDE_EDIBLE != 0) {
            schedTask(TASK_HOME_RANDOM_CLYDE, 0x00);
        } else {
            uint16_t addr = getColourOffset_2052(CLYDE_TILE);
            if (COLOUR[addr] != 0x1a) {
                schedTask(TASK_SCATTER_CHASE_CLYDE, 0x00);
            }
        }
    }
    clydeCheckReverse_1f73();
    CLYDE_TILE = addXYOffset_2000(CLYDE_VECTOR2, CLYDE_TILE);
    CLYDE_VECTOR = CLYDE_VECTOR2;
    CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION;
jump_1ebb:
    CLYDE_POS = addXYOffset_2000(CLYDE_VECTOR, CLYDE_POS);
    CLYDE_TILE2 = pixelToTile_2018(CLYDE_POS);
}
bool checkTunnelWrap_1ed0(int ghost) {
    XYPOS *tile = &BLINKY_TILE + ghost - 1;
    ((void)0);
    if (tile->x == 0x1d) {
        tile->x = 0x3d;
    } else if (tile->x == 0x3e) {
        tile->x = 0x1e;
    } else {
        if (tile->x >= 0x21 && tile->x < 0x3b)
            return false;
    }
    return true;
}
void blinkyCheckReverse_1efe(void) {
    if (BLINKY_ORIENT_CHG_FLAG == 0)
        return;
    BLINKY_ORIENT_CHG_FLAG = 0;
    BLINKY_ORIENTATION = BLINKY_PREV_ORIENTATION ^ 2;
    BLINKY_VECTOR2 = MOVE_VECTOR_DATA[BLINKY_ORIENTATION];
    if (INTRO_STATE != 0x22)
        return;
    BLINKY_VECTOR = BLINKY_VECTOR2;
    BLINKY_PREV_ORIENTATION = BLINKY_ORIENTATION;
}
void pinkyCheckReverse_1f25(void) {
    if (PINKY_ORIENT_CHG_FLAG == 0)
        return;
    PINKY_ORIENT_CHG_FLAG = 0;
    pinkyReverse_1f2e();
}
void pinkyReverse_1f2e(void) {
    PINKY_ORIENTATION = PINKY_PREV_ORIENTATION ^ 2;
    PINKY_VECTOR2 = MOVE_VECTOR_DATA[PINKY_ORIENTATION];
    if (INTRO_STATE != 0x22)
        return;
    PINKY_VECTOR = PINKY_VECTOR2;
    PINKY_PREV_ORIENTATION = PINKY_ORIENTATION;
}
void inkyCheckReverse_1f4c(void) {
    if (INKY_ORIENT_CHG_FLAG == 0)
        return;
    INKY_ORIENT_CHG_FLAG = 0;
    inkyReverse_1f55();
}
void inkyReverse_1f55(void) {
    ((void)0);
    INKY_ORIENTATION = INKY_PREV_ORIENTATION ^ 2;
    INKY_VECTOR2 = MOVE_VECTOR_DATA[INKY_ORIENTATION];
    if (INTRO_STATE != 0x22)
        return;
    INKY_VECTOR = INKY_VECTOR2;
    INKY_PREV_ORIENTATION = INKY_ORIENTATION;
}
void clydeCheckReverse_1f73(void) {
    if (CLYDE_ORIENT_CHG_FLAG == 0)
        return;
    CLYDE_ORIENT_CHG_FLAG = 0;
    clydeReverse_1f7c();
}
void clydeReverse_1f7c(void) {
    CLYDE_ORIENTATION = CLYDE_PREV_ORIENTATION ^ 2;
    CLYDE_VECTOR2 = MOVE_VECTOR_DATA[CLYDE_ORIENTATION];
    if (INTRO_STATE != 0x22)
        return;
    CLYDE_VECTOR = CLYDE_VECTOR2;
    CLYDE_PREV_ORIENTATION = CLYDE_ORIENTATION;
}
XYPOS addXYOffset_2000(XYPOS ix, XYPOS iy) {
    ix.x += iy.x;
    ix.y += iy.y;
    return ix;
}
uint8_t getScreenCharPosOffset_200f(XYPOS offset, XYPOS pos) {
    pos = addXYOffset_2000(offset, pos);
    uint16_t addr = getScreenOffset_0065(pos);
    return SCREEN[addr];
}
XYPOS pixelToTile_2018(XYPOS pos) {
    pos.y = (pos.y >> 3) + 0x20;
    pos.x = (pos.x >> 3) + 0x1e;
    return pos;
}
uint16_t getScreenOffset_202d(XYPOS hl) {
    ((void)0);
    hl.y -= 0x20;
    hl.x -= 0x20;
    int result = (hl.x << 5) + hl.y + 0x40;
    result &= 0x3ff;
    ((void)0);
    return result;
}
uint16_t getColourOffset_2052(XYPOS pos) { return getScreenOffset_0065(pos); }
void checkGhostEnterTunnel_205a(XYPOS pos, uint8_t *aux) {
    uint16_t addr = getColourOffset_2052(pos);
    if (COLOUR[addr] == 0x1b) {
        *aux = 1;
    } else {
        *aux = 0;
    }
}
void pinkyCheckLeaveHouse_2069(void) {
    if (PINKY_SUBSTATE != SUBSTATE_IN_HOUSE)
        return;
    if (P1_DIED_IN_LEVEL) {
        if (EATEN_PILLS_COUNT != 7)
            return;
    } else {
        ((void)0);
        if (P1_PINKY_LEAVE_HOME_COUNTER < PINKY_LEAVE_HOME_COUNTER)
            return;
    }
    PINKY_SUBSTATE = SUBSTATE_LEAVING_HOUSE;
}
void inkyCheckLeaveHouse_208c(void) {
    if (INKY_SUBSTATE != SUBSTATE_IN_HOUSE)
        return;
    if (P1_DIED_IN_LEVEL) {
        if (EATEN_PILLS_COUNT != 0x11)
            return;
    } else {
        ((void)0);
        if (P1_INKY_LEAVE_HOME_COUNTER < INKY_LEAVE_HOME_COUNTER)
            return;
    }
    INKY_SUBSTATE = SUBSTATE_HOUSE_MOVE;
}
void clydeCheckLeaveHouse_20af(void) {
    if (CLYDE_SUBSTATE != SUBSTATE_IN_HOUSE)
        return;
    if (P1_DIED_IN_LEVEL) {
        if (EATEN_PILLS_COUNT != 0x20)
            return;
        P1_DIED_IN_LEVEL = EATEN_PILLS_COUNT = 0;
        return;
    }
    if (P1_CLYDE_LEAVE_HOME_COUNTER < CLYDE_LEAVE_HOME_COUNTER)
        return;
    CLYDE_SUBSTATE = SUBSTATE_HOUSE_MOVE;
}
void cruiseElroyMode_20d7(void) {
    if (CLYDE_SUBSTATE == SUBSTATE_IN_HOUSE)
        return;
    if (CRUISE_ELROY_MODE_1 == 0) {
        if (PILLS_REM_DIFF_1 < 0xf4 - P1_PILLS_EATEN_LEVEL)
            return;
        CRUISE_ELROY_MODE_1 = 1;
    }
    if (CRUISE_ELROY_MODE_2 != 0)
        return;
    if (PILLS_REM_DIFF_2 < 0xf4 - P1_PILLS_EATEN_LEVEL)
        return;
    CRUISE_ELROY_MODE_2 = 1;
}
__attribute__((section(".cold"))) void scene1StateMachine_2108(void) {
    static void (*const func[])() = {scene1State0_211a, scene1State1_2140, scene1State2_214b,
                                     nothing_000c,      scene1State4_2170, scene1State5_217b,
                                     scene1State6_2186};
    tableCall_0020(func, SCENE1_STATE);
}
__attribute__((section(".cold"))) void scene1State0_211a(void) {
    if (PACMAN_TILE2.x != 0x21) {
        updateMoveVectorPacmanBlinky_2130();
        return;
    }
    BLINKY_SUBSTATE = SUBSTATE_CHASE;
    CRUISE_ELROY_MODE_2 = 1;
    demoMazeHorizontal_0506();
    incScene1State_212b();
}
void incScene1State_212b(void) { SCENE1_STATE++; }
void updateMoveVectorPacmanBlinky_2130(void) {
    pacmanUpdateMovePat_1806();
    pacmanUpdateMovePat_1806();
    updateMoveVectorBlinky_2136();
}
void updateMoveVectorBlinky_2136(void) {
    blinkyUpdateMovePat_1b36();
    blinkyUpdateMovePat_1b36();
    toggleGhostAnimation_0e23();
}
__attribute__((section(".cold"))) void scene1State1_2140(void) {
    if (PACMAN_TILE2.x != 0x1e)
        updateMoveVectorPacmanBlinky_2130();
    else
        SCENE1_STATE++;
}
__attribute__((section(".cold"))) void scene1State2_214b(void) {
    if (BLINKY_TILE2.x != 0x1e) {
        updateMoveVectorBlinky_2136();
        return;
    }
    ghostsBecomeEdible_1a70();
    CH2_SOUND_EFFECT->mask = CH3_SOUND_EFFECT->mask = 0;
    XYPOS vector = pacmanReverse_05a5();
    PACMAN_VECTOR = vector;
    PACMAN_ORIENTATION = PACMAN_DESIRED_ORIENTATION;
    schedISRTask(0x45, ISRTASK_INC_SCENE1_STATE, 0x00);
    SCENE1_STATE++;
}
__attribute__((section(".cold"))) void scene1State4_2170(void) {
    if (BLINKY_TILE2.x != 0x2f) {
        updateMoveVectorBlinky_2136();
        return;
    }
    SCENE1_STATE++;
}
__attribute__((section(".cold"))) void scene1State5_217b(void) {
    if (BLINKY_TILE2.x != 0x3d) {
        updateMoveVectorPacmanBlinky_2130();
        return;
    }
    SCENE1_STATE++;
}
__attribute__((section(".cold"))) void scene1State6_2186(void) {
    pacmanUpdateMovePat_1806();
    pacmanUpdateMovePat_1806();
    if (PACMAN_TILE2.x != 0x3d)
        return;
    SCENE1_STATE = 0;
    schedISRTask(0x45, ISRTASK_INC_LEVEL_STATE, 0x00);
    LEVEL_STATE++;
}
__attribute__((section(".cold"))) void scene2StateMachine_219e(void) {
    static void (*const func[])(uint16_t param) = {
        scene2State0_21c2, nothingParam_000c, scene2State2_21e1, scene2State3_21f5,
        scene2State4_220c, scene2State5_221e, scene2State6_2244, scene2State7_225d,
        nothingParam_000c, scene2State9_226a, nothingParam_000c, scene2State11_2286,
        nothingParam_000c, scene2State13_228d};
    func[SCENE2_STATE](0x41d2);
}
__attribute__((section(".cold"))) void scene2State0_21c2(uint16_t iy) {
    video_store(&COLOUR[0x1d2], 1);
    video_store(&COLOUR[0x1d3], 1);
    video_store(&COLOUR[0x1f2], 1);
    video_store(&COLOUR[0x1f3], 1);
    demoMazeHorizontal_0506();
    video_store(arcade_ptr(iy), 0x60);
    video_store(arcade_ptr(iy + 1), 0x61);
    schedISRTask(0x43, ISRTASK_INC_SCENE2_STATE, 0x00);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State2_21e1(uint16_t iy) {
    if (PACMAN_TILE2.x != 0x2c) {
        updateMoveVectorPacmanBlinky_2130();
        return;
    }
    BLINKY_SUBSTATE = CRUISE_ELROY_MODE_2 = 1;
    incScene2State_21f0();
}
void incScene2State_21f0(void) { SCENE2_STATE++; }
__attribute__((section(".cold"))) void scene2State3_21f5(uint16_t iy) {
    if (BLINKY_POS.x != 0x77) {
        if (BLINKY_POS.x != 0x78) {
            updateMoveVectorPacmanBlinky_2130();
            return;
        }
    }
    BLINKY_MOVE_PAT_DIFF2 = 0x20842084;
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State4_220c(uint16_t iy) {
    if (BLINKY_POS.x != 0x78) {
        updateMoveVector_2237();
        return;
    }
    video_store(arcade_ptr(iy), 0x62);
    video_store(arcade_ptr(iy + 1), 0x63);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State5_221e(uint16_t iy) {
    if (BLINKY_POS.x != 0x7b) {
        updateMoveVector_2237();
        return;
    }
    video_store(arcade_ptr(iy), 0x64);
    video_store(arcade_ptr(iy + 1), 0x65);
    video_store(arcade_ptr(iy + 0x20), 0x66);
    video_store(arcade_ptr(iy + 0x21), 0x67);
    incScene2State_21f0();
}
void updateMoveVector_2237(void) {
    pacmanUpdateMovePat_1806();
    pacmanUpdateMovePat_1806();
    blinkyUpdateMovePat_1b36();
    toggleGhostAnimation_0e23();
}
__attribute__((section(".cold"))) void scene2State6_2244(uint16_t iy) {
    if (BLINKY_POS.x != 0x7e) {
        updateMoveVector_2237();
        return;
    }
    video_store(arcade_ptr(iy), 0x68);
    video_store(arcade_ptr(iy + 1), 0x69);
    video_store(arcade_ptr(iy + 0x20), 0x6a);
    video_store(arcade_ptr(iy + 0x21), 0x6b);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State7_225d(uint16_t iy) {
    if (BLINKY_POS.x != 0x80) {
        updateMoveVector_2237();
        return;
    }
    schedISRTask(0x4f, ISRTASK_INC_SCENE2_STATE, 0x00);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State9_226a(uint16_t iy) {
    BLINKY_POS.x += 2;
    video_store(arcade_ptr(iy), 0x6c);
    video_store(arcade_ptr(iy + 1), 0x6d);
    video_store(arcade_ptr(iy + 0x20), 0x40);
    video_store(arcade_ptr(iy + 0x21), 0x40);
    schedISRTask(0x4a, ISRTASK_INC_SCENE2_STATE, 0x00);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State11_2286(uint16_t iy) {
    schedISRTask(0x54, ISRTASK_INC_SCENE2_STATE, 0x00);
    incScene2State_21f0();
}
__attribute__((section(".cold"))) void scene2State13_228d(uint16_t iy) {
    SCENE2_STATE = 0;
    LEVEL_STATE += 2;
}
__attribute__((section(".cold"))) void scene3StateMachine_2297(void) {
    static void (*const func[])() = {scene3State0_22a7, scene3State1_22be, nothing_000c,
                                     scene3State3_22dd, scene3State4_22f5, scene3State5_22fe};
    tableCall_0020(func, SCENE3_STATE);
}
__attribute__((section(".cold"))) void scene3State0_22a7(void) {
    if (PACMAN_TILE2.x != 0x25) {
        updateMoveVectorPacmanBlinky_2130();
        return;
    }
    BLINKY_SUBSTATE = CRUISE_ELROY_MODE_2 = 1;
    demoMazeHorizontal_0506();
    incScene3State_22b9();
}
void incScene3State_22b9(void) { SCENE3_STATE++; }
__attribute__((section(".cold"))) void scene3State1_22be(void) {
    if (BLINKY_POS.x != 0xff && BLINKY_POS.x != 0xfe) {
        updateMoveVectorPacmanBlinky_2130();
        return;
    }
    BLINKY_POS.x += 2;
    BLINKY_ORIENT_CHG_FLAG = 1;
    blinkyCheckReverse_1efe();
    schedISRTask(0x4a, ISRTASK_INC_SCENE3_STATE, 0x00);
    incScene3State_22b9();
}
__attribute__((section(".cold"))) void scene3State3_22dd(void) {
    if (BLINKY_TILE2.x == 0x2d) {
        incScene3State_22b9();
        return;
    }
    scene3FruitPos_22e4();
}
__attribute__((section(".cold"))) void scene3FruitPos_22e4(void) {
    FRUIT_POS.y = BLINKY_POS.y;
    FRUIT_POS.x = BLINKY_POS.x - 8;
    updateMoveVectorPacmanBlinky_2130();
}
__attribute__((section(".cold"))) void scene3State4_22f5(void) {
    if (BLINKY_TILE2.x == 0x1e) {
        incScene3State_22b9();
        return;
    }
    scene3FruitPos_22e4();
}
__attribute__((section(".cold"))) void scene3State5_22fe(void) {
    SCENE3_STATE = 0;
    schedISRTask(0x45, ISRTASK_INC_LEVEL_STATE, 0x00);
    LEVEL_STATE++;
}
void initSelfTest_230b(void) {
    INTENABLE = SOUNDENABLE = AUXENABLE = FLIPSCREEN = P1START = P2START = COINLOCKOUT =
        COINCOUNTER = 0;
    int hl = 0;
    for (int b = 0; b <= 4; b++) {
        kickWatchdog();
        COINCOUNTER = 0;
        for (int l = 0; l < 0x100; l++)
            video_store(&SCREEN[hl++], 0x40);
    }
    hl = 0;
    for (int b = 0; b <= 4; b++) {
        kickWatchdog();
        COINCOUNTER = 0;
        for (int i = 0; i < 0x100; i++)
            video_store(&COLOUR[hl++], 0x0f);
    }
    interruptMode(2);
    interruptVector(isr_3000);
    COINCOUNTER = 0;
    INTENABLE = 1;
    interruptEnable();
    interruptHalt();
    mainTaskLoop_234b();
}
void mainTaskLoop_234b(void) {
    kickWatchdog();
    memset(&REGSWRITE, 0, 8);
    memset(&arcade_byte(0x4c00), 0, 4 * 0xbe);
#ifdef VIC20
    memset((void *)0xa0, 0, 0x60);
#endif
    memset(&SOUND[0], 0, 0x40);
    kickWatchdog();
    clearColour_240d(0);
    kickWatchdog();
    jumpClearScreen_23ed(0);
    kickWatchdog();
    TASK_LIST_BEGIN = TASK_LIST_END = 0x4cc0;
    memset(&arcade_byte(0x4cc0), 0xff, 0x40);
    INTENABLE = 1;
    interruptEnable();
    return;
}

void arcade_tasks(void) {
    while (arcade_byte(TASK_LIST_BEGIN) < 0x80) {
        while (arcade_byte(TASK_LIST_BEGIN) > 0x80) {
            ((void)0);
            interruptHalt();
        }
        int task = arcade_byte(TASK_LIST_BEGIN);
        int param = arcade_byte(TASK_LIST_BEGIN + 1);
        arcade_byte(TASK_LIST_BEGIN) = 0xff;
        arcade_byte(TASK_LIST_BEGIN + 1) = 0xff;
        TASK_LIST_BEGIN += 2;
        ((void)0);
        if ((TASK_LIST_BEGIN & 0xff) == 0)
            TASK_LIST_BEGIN = 0x4cc0;
        static void (*const func[])(uint8_t param) = {jumpClearScreen_23ed,
                                                      mazeColours_24d7,
                                                      drawMaze_2419,
                                                      drawPills_2448,
                                                      initialisePositions_25d3,
                                                      blinkySubstateTBD_268b,
                                                      clearColour_240d,
                                                      resetGameState_2698,
                                                      blinkyScatterOrChase_2730,
                                                      pinkyScatterOrChase_276c,
                                                      inkyScatterOrChase_27a9,
                                                      clydeScatterOrChase_27f1,
                                                      homeOrRandomBlinky_283b,
                                                      homeOrRandomPinky_2865,
                                                      homeOrRandomInky_288f,
                                                      homeOrRandomClyde_28b9,
                                                      setupGhostTimers_000d,
                                                      clearGhostState_26a2,
                                                      clearPillArrays_24c9,
                                                      clearPillsScreen_2a35,
                                                      configureGame_26d0,
                                                      updatePillsFromScreen_2487,
                                                      advanceLevelState_23e8,
                                                      pacmanOrientationDemo_28e3,
                                                      clearScores_2ae0,
                                                      addToScore_2a5a,
                                                      bottomTextColourAndDisplayLives_2b6a,
                                                      fruitHistoryLevelCheck_2bea,
                                                      displayMsg_2c5e,
                                                      displayCredits_2ba1,
                                                      resetPositions_2675,
                                                      showBonusLifeScore_26b2};
        ((void)0);
        func[task](param);
    }
}
void advanceLevelState_23e8(uint8_t param) { LEVEL_STATE++; }
void jumpClearScreen_23ed(uint8_t param) {
    static void (*const func[])() = {clearScreen_23f3, clearScreenMazeOnly_2400};
    tableCall_0020(func, param);
}
void clearScreen_23f3(void) {
    video_fill(SCREEN, 0x40, 0x400);
    ((void)0);
}
void clearScreenMazeOnly_2400(void) {
    video_fill(SCREEN + 0x40, 0x40, 0x380);
    ((void)0);
}
void clearColour_240d(uint8_t param) {
    video_fill(COLOUR, 0, 0x400);
    ((void)0);
}
void drawMaze_2419(uint8_t param) {
    ((void)0);
    uint16_t hl = 0;
    uint8_t *bc = DATA_3435;
    while (1) {
        uint8_t a = *bc;
        if (a == 0)
            return;
        ((void)0);
        if (a < 0x80) {
            hl += a - 1;
            a = *++bc;
            ((void)0);
        }
        hl++;
        video_store(&SCREEN[hl], a);
        ((void)0);
        uint16_t tmp = 0x3e0 + (hl & 0x1f) * 2 - hl;
        ((void)0);
        video_store(&SCREEN[tmp], a ^ 1);
        bc++;
    }
}
void drawPills_2448(uint8_t param) {
    uint8_t *hl = SCREEN;
    uint8_t *ix = P1_PILL_ARRAY;
    uint8_t *iy = DATA_35b5;
    for (int b = 0; b < 0x1e; b++) {
        for (int c = 0; c < 8; c++) {
            hl += *iy;
            if (*ix & (0x80 >> c))
                video_store(hl, CHAR_PILL);
            iy++;
        }
        ix++;
    }
    video_store(&SCREEN[0x64], P1_POWERUP_ARRAY[0]);
    video_store(&SCREEN[0x78], P1_POWERUP_ARRAY[1]);
    video_store(&SCREEN[0x384], P1_POWERUP_ARRAY[2]);
    video_store(&SCREEN[0x398], P1_POWERUP_ARRAY[3]);
}
void updatePillsFromScreen_2487(uint8_t param) {
    int hl = 0;
    uint8_t *ix = P1_PILL_ARRAY;
    uint8_t *iy = DATA_35b5;
    for (int b = 0; b < 0x1e; b++) {
        for (int c = 0; c < 8; c++) {
            hl += *iy;
            *ix <<= 1;
            if (SCREEN[hl] == 0x10)
                *ix |= 1;
            iy++;
        }
        ix++;
    }
    P1_POWERUP_ARRAY[0] = SCREEN[0x64];
    P1_POWERUP_ARRAY[1] = SCREEN[0x78];
    P1_POWERUP_ARRAY[2] = SCREEN[0x384];
    P1_POWERUP_ARRAY[3] = SCREEN[0x398];
}
void clearPillArrays_24c9() {
    memset(P1_PILL_ARRAY, 0xff, 0x1e);
    memset(P1_POWERUP_ARRAY, 0x14, 0x4);
}
#ifdef VIC20
/* The native entry dispatches flash-only updates before this full path. */
void mazeColours_full(uint8_t param) {
#else
void mazeColours_24d7(uint8_t param) {
#endif
    int a;
    if (param == 2)
        a = 0x1f;
    else
        a = 0x10;
    video_fill(COLOUR + 0x40, a, 0x380);
    video_fill(COLOUR + 0x3c0, 0xf, 0x40);
    if (param != 1)
        return;
    uint8_t *ix = &COLOUR[0x1a0];
    for (int b = 0; b < 6; b++) {
        video_store(ix + (0xc), 0x1a);
        video_store(ix + (0x18), 0x1a);
        ix += 0x20;
        ((void)0);
    }
    ix = COLOUR + 0x40;
    for (int b = 0; b < 5; b++) {
        video_store(ix + (0xe), 0x1b);
        video_store(ix + (0xf), 0x1b);
        video_store(ix + (0x10), 0x1b);
        ix += 0x20;
    }
    ix = COLOUR + 0x320;
    for (int b = 0; b < 5; b++) {
        video_store(ix + (0xe), 0x1b);
        video_store(ix + (0xf), 0x1b);
        video_store(ix + (0x10), 0x1b);
        ix += 0x20;
    }
    video_store(&COLOUR[0x1ed], 0x18);
    video_store(&COLOUR[0x20d], 0x18);
}
void initialisePositions_25d3(uint8_t intro) {
    BLINKY_SPRITE = 0x20;
    PINKY_SPRITE = 0x20;
    INKY_SPRITE = 0x20;
    CLYDE_SPRITE = 0x20;
    PACMAN_SPRITE = 0x2c;
    FRUIT_SPRITE = 0x3f;
    BLINKY_COLOUR = 0x01;
    PINKY_COLOUR = 0x03;
    INKY_COLOUR = 0x05;
    CLYDE_COLOUR = 0x07;
    PACMAN_COLOUR = 0x09;
    FRUIT_COLOUR = 0x00;
    if (intro == 0) {
        BLINKY_POS.y = 0x64;
        BLINKY_POS.x = 0x80;
        PINKY_POS.y = 0x7c;
        PINKY_POS.x = 0x80;
        INKY_POS.y = 0x7c;
        INKY_POS.x = 0x90;
        CLYDE_POS.y = 0x7c;
        CLYDE_POS.x = 0x70;
        PACMAN_POS.y = 0xc4;
        PACMAN_POS.x = 0x80;
        BLINKY_TILE.y = BLINKY_TILE2.y = 0x2c;
        BLINKY_TILE.x = BLINKY_TILE2.x = 0x2e;
        PINKY_TILE.y = PINKY_TILE2.y = 0x2f;
        PINKY_TILE.x = PINKY_TILE2.x = 0x2e;
        INKY_TILE.y = INKY_TILE2.y = 0x2f;
        INKY_TILE.x = INKY_TILE2.x = 0x30;
        CLYDE_TILE.y = CLYDE_TILE2.y = 0x2f;
        CLYDE_TILE.x = CLYDE_TILE2.x = 0x2c;
        PACMAN_TILE.y = PACMAN_TILE2.y = 0x38;
        PACMAN_TILE.x = PACMAN_TILE2.x = 0x2e;
        BLINKY_VECTOR.y = BLINKY_VECTOR2.y = 0x00;
        BLINKY_VECTOR.x = BLINKY_VECTOR2.x = 0x01;
        PINKY_VECTOR.y = PINKY_VECTOR2.y = 0x01;
        PINKY_VECTOR.x = PINKY_VECTOR2.x = 0x00;
        INKY_VECTOR.y = INKY_VECTOR2.y = 0xff;
        INKY_VECTOR.x = INKY_VECTOR2.x = 0x00;
        CLYDE_VECTOR.y = CLYDE_VECTOR2.y = 0xff;
        CLYDE_VECTOR.x = CLYDE_VECTOR2.x = 0x00;
        PACMAN_VECTOR.y = PACMAN_VECTOR2.y = 0x00;
        PACMAN_VECTOR.x = PACMAN_VECTOR2.x = 0x01;
        BLINKY_ORIENTATION = BLINKY_PREV_ORIENTATION = ORIENT_LEFT;
        PINKY_ORIENTATION = PINKY_PREV_ORIENTATION = ORIENT_DOWN;
        INKY_ORIENTATION = INKY_PREV_ORIENTATION = ORIENT_UP;
        CLYDE_ORIENTATION = CLYDE_PREV_ORIENTATION = ORIENT_UP;
        PACMAN_ORIENTATION = PACMAN_DESIRED_ORIENTATION = ORIENT_LEFT;
        FRUIT_POS.y = FRUIT_POS.x = 0;
    } else {
        BLINKY_POS.y = PINKY_POS.y = INKY_POS.y = CLYDE_POS.y = 0x94;
        BLINKY_POS.x = PINKY_POS.x = INKY_POS.x = CLYDE_POS.x = 0x00;
        BLINKY_TILE.y = BLINKY_TILE2.y = PINKY_TILE.y = PINKY_TILE2.y = INKY_TILE.y = INKY_TILE2.y =
            CLYDE_TILE.y = CLYDE_TILE2.y = 0x32;
        BLINKY_TILE.x = BLINKY_TILE2.x = PINKY_TILE.x = PINKY_TILE2.x = INKY_TILE.x = INKY_TILE2.x =
            CLYDE_TILE.x = CLYDE_TILE2.x = 0x1e;
        BLINKY_VECTOR.y = BLINKY_VECTOR2.y = PINKY_VECTOR.y = PINKY_VECTOR2.y = INKY_VECTOR.y =
            INKY_VECTOR2.y = CLYDE_VECTOR.y = CLYDE_VECTOR2.y = PACMAN_VECTOR.y = PACMAN_VECTOR2.y =
                0x00;
        BLINKY_VECTOR.x = BLINKY_VECTOR2.x = PINKY_VECTOR.x = PINKY_VECTOR2.x = INKY_VECTOR.x =
            INKY_VECTOR2.x = CLYDE_VECTOR.x = CLYDE_VECTOR2.x = PACMAN_VECTOR.x = PACMAN_VECTOR2.x =
                0x01;
        memset(&BLINKY_PREV_ORIENTATION, ORIENT_LEFT, 9);
        PACMAN_DESIRED_ORIENTATION = ORIENT_LEFT;
        PACMAN_POS.y = 0x94;
        PACMAN_POS.x = 0x08;
        PACMAN_TILE.y = PACMAN_TILE2.y = 0x32;
        PACMAN_TILE.x = PACMAN_TILE2.x = 0x1f;
        ((void)0);
    }
}
void resetPositions_2675() {
    FRUIT_POS.y = FRUIT_POS.x = 0;
    PACMAN_POS.y = PACMAN_POS.x = 0;
    setGhostPosition_267e(0, 0);
}
void setGhostPosition_267e(int y, int x) {
    BLINKY_POS.x = x;
    PINKY_POS.x = x;
    INKY_POS.x = x;
    CLYDE_POS.x = x;
    BLINKY_POS.y = y;
    PINKY_POS.y = y;
    INKY_POS.y = y;
    CLYDE_POS.y = y;
}
void blinkySubstateTBD_268b(uint8_t param) {
    GHOST_HOUSE_MOVE_COUNT = 0x55;
    if (--param == 0)
        return;
    BLINKY_SUBSTATE = SUBSTATE_CHASE;
}
void resetGameState_2698() {
    MAIN_STATE = MAIN_STATE_DEMO;
    RESET_STATE = RESET_STATE_RESET;
}
void clearGhostState_26a2() {
    for (int i = 0x4d00; i < 0x4e00; i++)
        arcade_byte(i) = 0;
}
void showBonusLifeScore_26b2() {
    int digit = BONUS_LIFE;
    video_store(&SCREEN[0x136], (digit & 0xf) + 0x30);
    digit >>= 4;
    if ((digit & 0xf) == 0)
        return;
    video_store(&SCREEN[0x156], digit + 0x30);
}
void configureGame_26d0(uint8_t unused) {
    int a = DIP_SWITCH_COINS;
    if (a == 0) {
        CREDITS = 0xff;
    }
    COINS_PER_CREDIT = (a & 1) + (a >> 1);
    CREDITS_PER_COIN = (COINS_PER_CREDIT & 2) ^ a;
    LIVES_PER_GAME = DIP_SWITCH_LIVES + 1;
    if (LIVES_PER_GAME == 4)
        LIVES_PER_GAME++;
    BONUS_LIFE = BONUS_LIFE_DATA[DIP_SWITCH_BONUS];
    GHOST_NAMES_MODE = DIP_SWITCH_NAMES ^ 1;
    ((void)0);
    DIFFICULTY_PTR = DIFFICULTY_DATA[DIP_SWITCH_DIFFICULTY ^ 1];
    COCKTAIL_MODE = IN1_CABINET ? 0 : 1;
}
void blinkyScatterOrChase_2730(uint8_t param) {
    ((void)0);
    if ((NONRANDOM_MOVEMENT & 1) == 0) {
        if (CRUISE_ELROY_MODE_1 == 0) {
            if (LEVEL_STATE == LEVEL_STATE_PLAY_GAME) {
                ((void)0);
                XYPOS target = {0x1d, 0x22};
                BLINKY_VECTOR2 = findBestOrientation_2966(BLINKY_TILE, target, &BLINKY_ORIENTATION);
                showTarget(BLINKY_TILE, target, GHOST_BLINKY);
                return;
            }
        }
    }
    ((void)0);
    BLINKY_VECTOR2 = findBestOrientation_2966(BLINKY_TILE, PACMAN_TILE2, &BLINKY_ORIENTATION);
    showTarget(BLINKY_TILE, PACMAN_TILE2, GHOST_BLINKY);
}
void pinkyScatterOrChase_276c(uint8_t param) {
    if ((NONRANDOM_MOVEMENT & 1) == 0) {
        if (LEVEL_STATE == LEVEL_STATE_PLAY_GAME) {
            XYPOS target = {0x1d, 0x39};
            PINKY_VECTOR2 = findBestOrientation_2966(PINKY_TILE, target, &PINKY_ORIENTATION);
            showTarget(PINKY_TILE, target, GHOST_PINKY);
            return;
        }
    }
    XYPOS target;
    /* Preserve the original 16-bit ADD HL,HL carry (the Pinky up bug). */
    uint16_t ahead = ((uint16_t)PACMAN_VECTOR.x << 8) | PACMAN_VECTOR.y;
    ahead = ahead * 4 + (((uint16_t)PACMAN_TILE2.x << 8) | PACMAN_TILE2.y);
    target.x = ahead >> 8;
    target.y = ahead;
    PINKY_VECTOR2 = findBestOrientation_2966(PINKY_TILE, target, &PINKY_ORIENTATION);
    showTarget(PINKY_TILE, target, GHOST_PINKY);
}
void inkyScatterOrChase_27a9(uint8_t param) {
    if ((NONRANDOM_MOVEMENT & 1) == 0) {
        if (LEVEL_STATE == LEVEL_STATE_PLAY_GAME) {
            XYPOS target = {0x40, 0x20};
            INKY_VECTOR2 = findBestOrientation_2966(INKY_TILE, target, &INKY_ORIENTATION);
            showTarget(INKY_TILE, target, GHOST_INKY);
            return;
        }
    }
    XYPOS target;
    uint16_t ahead = ((uint16_t)PACMAN_VECTOR.x << 8) | PACMAN_VECTOR.y;
    ahead = ahead * 2 + (((uint16_t)PACMAN_TILE2.x << 8) | PACMAN_TILE2.y);
    target.y = ahead;
    target.x = ahead >> 8;
    target.y = target.y * 2 - BLINKY_TILE.y;
    target.x = target.x * 2 - BLINKY_TILE.x;
    INKY_VECTOR2 = findBestOrientation_2966(INKY_TILE, target, &INKY_ORIENTATION);
    showTarget(INKY_TILE, target, GHOST_INKY);
}
void clydeScatterOrChase_27f1(uint8_t param) {
    if ((NONRANDOM_MOVEMENT & 1) == 0) {
        if (LEVEL_STATE == LEVEL_STATE_PLAY_GAME) {
        random:
            XYPOS target = {0x40, 0x3b};
            CLYDE_VECTOR2 = findBestOrientation_2966(CLYDE_TILE, target, &CLYDE_ORIENTATION);
            showTarget(CLYDE_TILE, target, GHOST_CLYDE);
            return;
        }
    }
    uint16_t dist = computeDistance_29ea(PACMAN_TILE2, CLYDE_TILE);
    if (dist < 0x40)
        goto random;
    CLYDE_VECTOR2 = findBestOrientation_2966(CLYDE_TILE, PACMAN_TILE2, &CLYDE_ORIENTATION);
    showTarget(CLYDE_TILE, PACMAN_TILE2, GHOST_CLYDE);
}
void homeOrRandomBlinky_283b() {
    if (BLINKY_STATE != GHOST_STATE_ALIVE) {
        XYPOS target = {0x2c, 0x2e};
        BLINKY_VECTOR2 = findBestOrientation_2966(BLINKY_TILE, target, &BLINKY_ORIENTATION);
        showTarget(BLINKY_TILE, target, GHOST_BLINKY);
        return;
    }
    BLINKY_VECTOR2 = randomDirection_291e(BLINKY_TILE, &BLINKY_ORIENTATION);
    showTarget(BLINKY_TILE, BLINKY_TILE, GHOST_BLINKY);
}
void homeOrRandomPinky_2865() {
    if (PINKY_STATE != GHOST_STATE_ALIVE) {
        XYPOS target = {0x2c, 0x2e};
        PINKY_VECTOR2 = findBestOrientation_2966(PINKY_TILE, target, &PINKY_ORIENTATION);
        showTarget(PINKY_TILE, target, GHOST_PINKY);
        return;
    }
    PINKY_VECTOR2 = randomDirection_291e(PINKY_TILE, &PINKY_ORIENTATION);
    showTarget(PINKY_TILE, PINKY_TILE, GHOST_PINKY);
}
void homeOrRandomInky_288f() {
    if (INKY_STATE) {
        XYPOS target = {0x2c, 0x2e};
        INKY_VECTOR2 = findBestOrientation_2966(INKY_TILE, target, &INKY_ORIENTATION);
        showTarget(INKY_TILE, target, GHOST_INKY);
        return;
    }
    INKY_VECTOR2 = randomDirection_291e(INKY_TILE, &INKY_ORIENTATION);
    showTarget(INKY_TILE, INKY_TILE, GHOST_INKY);
}
void homeOrRandomClyde_28b9() {
    if (CLYDE_STATE) {
        XYPOS target = {0x2c, 0x2e};
        CLYDE_VECTOR2 = findBestOrientation_2966(CLYDE_TILE, target, &CLYDE_ORIENTATION);
        showTarget(CLYDE_TILE, target, GHOST_CLYDE);
        return;
    }
    CLYDE_VECTOR2 = randomDirection_291e(CLYDE_TILE, &CLYDE_ORIENTATION);
    showTarget(CLYDE_TILE, CLYDE_TILE, GHOST_CLYDE);
}
void pacmanOrientationDemo_28e3() {
    if (BLINKY_EDIBLE) {
        ((void)0);
        PACMAN_VECTOR2 =
            findBestOrientation_2966(PACMAN_TILE, PINKY_TILE, &PACMAN_DESIRED_ORIENTATION);
        showTarget(PACMAN_TILE, PINKY_TILE, 5);
        return;
    }
    XYPOS target;
    target.y = PACMAN_TILE2.y * 2 - PINKY_TILE.y;
    target.x = PACMAN_TILE2.x * 2 - PINKY_TILE.x;
    ((void)0);
    ((void)0);
    ((void)0);
    ((void)0);
    PACMAN_VECTOR2 = findBestOrientation_2966(PACMAN_TILE, target, &PACMAN_DESIRED_ORIENTATION);
    showTarget(PACMAN_TILE, target, 5);
}
XYPOS randomDirection_291e(XYPOS hl, uint8_t *orientation) {
    CURRENT_TILE_POS = hl;
    OPPOSITE_ORIENTATION = *orientation ^ 2;
    BEST_ORIENTATION_FOUND = random_2a23() & 3;
    XYPOS *ix = &MOVE_VECTOR_DATA[BEST_ORIENTATION_FOUND];
    XYPOS iy = CURRENT_TILE_POS;
    while (1) {
        if (OPPOSITE_ORIENTATION != BEST_ORIENTATION_FOUND) {
            int a = getScreenCharPosOffset_200f(*ix, iy);
            if ((a & CHAR_MAZE_MASK) != CHAR_MAZE_MASK) {
                *orientation = BEST_ORIENTATION_FOUND;
                return *(XYPOS *)ix;
            }
        }
        ix++;
        BEST_ORIENTATION_FOUND = (BEST_ORIENTATION_FOUND + 1) & 3;
    }
    return hl;
}
XYPOS findBestOrientation_2966(XYPOS hl, XYPOS de, uint8_t *a) {
    ((void)0);
    CURRENT_TILE_POS = hl;
    DEST_TILE_POS = de;
    BEST_ORIENTATION_FOUND = *a;
    OPPOSITE_ORIENTATION = *a ^ 2;
    ((void)0);
    MIN_DISTANCE_FOUND = 0xffff;
    TRIAL_ORIENTATION = 0;
    XYPOS *ix = MOVE_VECTOR_DATA;
    do {
        if (OPPOSITE_ORIENTATION != TRIAL_ORIENTATION) {
            TMP_RESULT_POS = addXYOffset_2000(*ix, CURRENT_TILE_POS);
            int offset = getScreenOffset_0065(TMP_RESULT_POS);
            ((void)0);
            if ((SCREEN[offset] & CHAR_MAZE_MASK) != CHAR_MAZE_MASK) {
                ((void)0);
                uint16_t dist = computeDistance_29ea(DEST_TILE_POS, TMP_RESULT_POS);
                ((void)0);
                if (MIN_DISTANCE_FOUND >= dist) {
                    MIN_DISTANCE_FOUND = dist;
                    BEST_ORIENTATION_FOUND = TRIAL_ORIENTATION;
                }
            }
        }
        ix++;
    } while (++TRIAL_ORIENTATION < 4);
    ((void)0);
    *a = BEST_ORIENTATION_FOUND;
    return ix[BEST_ORIENTATION_FOUND];
}
uint16_t computeDistance_29ea(XYPOS ix, XYPOS iy) {
    int b = ix.y - iy.y;
    if (b < 0) {
        b = iy.y - ix.y;
    }
    uint16_t hl = calcSquare_2a12(b);
    b = ix.x - iy.x;
    if (b < 0) {
        b = iy.x - ix.x;
    }
    hl += calcSquare_2a12(b);
    return hl;
}
uint16_t calcSquare_2a12(uint8_t a) {
#ifdef VIC20
    extern const uint16_t arcade_squares[128];
    uint8_t n = a & 127;
    uint16_t square = arcade_squares[n];
    return (a & 128) ? square + ((uint16_t)n << 8) + 0x4000u : square;
#else
    return (uint16_t)a * a;
#endif
}
uint8_t random_2a23(void) {
#ifdef VIC20
    /* An exact ROM-backed sequence for every reachable frightened decision.
       The 1536-call bound exceeds four energizers * six seconds * four ghosts
       * two pixel steps/tick / eight pixels, plus initial center decisions. */
    static uint16_t random_index __attribute__((section(".work")));
    if (!RND_VAL_PTR)
        random_index = 0;
    RND_VAL_PTR = (RND_VAL_PTR * 5 + 1) & 0x1fff;
    ASSERT(random_index < 1536);
    uint16_t i = random_index++;
    return (rom_random[i >> 2] >> ((i & 3) * 2)) & 3;
#else
    RND_VAL_PTR = (RND_VAL_PTR * 5 + 1) & 0x1fff;
    return arcade_byte(RND_VAL_PTR);
#endif
}
void clearPillsScreen_2a35() {
    int de = 0x40;
    while (de != 0x3c0) {
        int a = SCREEN[de];
        if (a != 0x10 && a != 0x12 && a != 0x14) {
            de++;
        } else {
            video_store(&SCREEN[de++], 0x40);
        }
    }
}
void addToScore_2a5a(uint8_t b) {
    if (MAIN_STATE == MAIN_STATE_DEMO)
        return;
    uint16_t add = scoreTable_2b17[b];
    ((void)0);
    uint8_t *score = getPlayerScorePtr_2b0b();
#ifdef VIC20
    extern void add_score_bcd(uint16_t amount);
    add_score_bcd(add);
#else
    uint8_t carry = 0;
    for (uint8_t i = 0; i < 3; i++) {
        uint8_t digit = i == 0 ? add : i == 1 ? add >> 8 : 0;
        uint16_t sum = score[i] + digit + carry;
        if ((score[i] & 15) + (digit & 15) + carry > 9)
            sum += 6;
        if (sum > 0x99)
            sum += 0x60;
        score[i] = sum;
        carry = sum > 255;
    }
#endif
    uint16_t hl = (score[2] << 8) + score[1];
    hl *= 16;
    if (hl >> 8 > BONUS_LIFE - 1)
        extraLife_2b33(&score[2]);
    drawPlayerScore_2aaf(&score[2]);
    uint8_t *highScore = HIGH_SCORE;
    int index;
    for (index = 2; index >= 0; index--) {
        if (score[index] < highScore[index])
            return;
        if (score[index] > highScore[index])
            break;
    }
    if (index < 0)
        return;
    score = getPlayerScorePtr_2b0b();
    highScore = HIGH_SCORE;
    memcpy(highScore, score, 3);
    drawScore_2abe(0x3f2, &highScore[2], 4);
}
void drawPlayerScore_2aaf(uint8_t *score) {
    uint16_t screenLoc;
    if (PLAYER == 0)
        screenLoc = 0x3fc;
    else
        screenLoc = 0x3e9;
    drawScore_2abe(screenLoc, score, 4);
}
void drawScore_2abe(uint16_t screenLoc, uint8_t *score, int blanks) {
    for (int b = 0; b < 3; b++) {
        ((void)0);
        blanks = drawDigit_2ace(&screenLoc, *score >> 4, blanks);
        blanks = drawDigit_2ace(&screenLoc, *score, blanks);
        score--;
    }
}
int drawDigit_2ace(uint16_t *screenLoc, uint8_t digit, int blanks) {
    digit &= 0xf;
    ((void)0);
    if (digit != 0) {
        blanks = 0;
    } else {
        if (blanks != 0) {
            digit = 0x40;
            blanks--;
        }
    }
    ((void)0);
    video_store(&SCREEN[(*screenLoc)--], digit);
    return blanks;
}
void clearScores_2ae0() {
    displayMsg_2c5e(MSG_HIGHSCORE);
    memset(P1_SCORE, 0, 8);
    drawScore_2abe(0x3fc, &P1_SCORE[2], 4);
    int blanks = 4;
    if (TWO_PLAYERS)
        blanks = 6;
    drawScore_2abe(0x3e9, &P2_SCORE[2], blanks);
}
uint8_t *getPlayerScorePtr_2b0b(void) {
    if (PLAYER == 0)
        return P1_SCORE;
    return P2_SCORE;
}
uint16_t scoreTable_2b17[] = {0x0010, 0x0050, 0x0200, 0x0400, 0x0800, 0x1600, 0x0100,
                              0x0300, 0x0500, 0x0700, 0x1000, 0x2000, 0x3000, 0x5000};
void extraLife_2b33(uint8_t *score) {
    if ((score[1] & 1) != 0)
        return;
    score[1] |= 1;
    CH1_SOUND_EFFECT->mask |= 1;
    P1_REAL_LIVES++;
    P1_DISPLAY_LIVES++;
    displayLives_2b4a(P1_DISPLAY_LIVES);
}
uint16_t displayLives_2b4a(int lives) {
    int hl = 0x1a;
    int c = 5;
    if (lives != 0) {
        if (lives < 6) {
            for (int i = 0; i < lives; i++) {
                drawFruit_2b8f(&SCREEN[hl], 0x20);
                hl -= 2;
                c--;
            }
        }
    }
    while (c-- > 0) {
        drawBlankSquare_2b7e(&SCREEN[hl]);
        hl -= 2;
    }
    return hl;
}
void bottomTextColourAndDisplayLives_2b6a(uint8_t unused) {
    if (MAIN_STATE == MAIN_STATE_DEMO)
        return;
    fillScreenArea_2bcd(0x4412, 0x09, 0x0a, 0x02);
    displayLives_2b4a(P1_DISPLAY_LIVES);
}
void drawBlankSquare_2b7e(uint8_t *hl) { drawCharSquare_2b80(hl, 0x40); }
void drawCharSquare_2b80(uint8_t *hl, uint8_t a) {
    video_store(hl + (0), a);
    video_store(hl + (1), a);
    video_store(hl + (0x20), a);
    video_store(hl + (0x21), a);
}
void drawFruit_2b8f(uint8_t *hl, uint8_t a) {
    ((void)0);
    video_store(hl + (0), a++);
    video_store(hl + (1), a++);
    video_store(hl + (0x20), a++);
    video_store(hl + (0x21), a);
}
void displayCredits_2ba1() {
    if (CREDITS == 0xff) {
        displayMsg_2c5e(MSG_FREEPLAY);
        return;
    }
    displayMsg_2c5e(MSG_CREDIT);
    int digit = CREDITS & 0xf0;
    if (digit != 0) {
        video_store(&SCREEN[0x34], (digit >> 4) + 0x30);
    }
    digit = CREDITS & 0x0f;
    video_store(&SCREEN[0x33], digit + 0x30);
}
void fillScreenArea_2bcd(int addr, uint8_t ch, uint8_t cols, uint8_t rows) {
    ((void)0);
    while (rows--) {
        for (int x = 0; x < cols; x++) {
            video_store(arcade_ptr(addr + x), ch);
            ((void)0);
        }
        addr += 0x20;
    }
}
void fruitHistoryLevelCheck_2bea(uint8_t param) {
    if (MAIN_STATE == MAIN_STATE_DEMO)
        return;
    uint8_t level = P1_LEVEL + 1;
    if (level >= 8) {
        fruitHistoryLevelHigherThan8_2c2e(level);
        return;
    }
    displayFruitHistory_2bfd(FRUIT_TABLE, level);
}
void displayFruitHistory_2bfd(uint8_t *table, int level) {
    uint8_t c = 7;
    uint16_t hl = 0x4;
    /* The original DJNZ with B=0 runs 256 times: the board-256 split screen. */
    uint8_t count = level;
    do {
        drawFruit_2b8f(&SCREEN[hl], table[0]);
        drawCharSquare_2b80(&COLOUR[hl], table[1]);
        table += 2;
        hl += 2;
        c--;
    } while (--count);
    while (c-- > 0) {
        drawBlankSquare_2b7e(&SCREEN[hl]);
        drawCharSquare_2b80(&COLOUR[hl], 0);
        hl += 2;
    }
}
void fruitHistoryLevelHigherThan8_2c2e(int level) {
    if (level >= 0x13)
        level = 0x13;
    displayFruitHistory_2bfd(&FRUIT_TABLE[(level - 7) * 2], 7);
}
void func_2c44(uint8_t a) {
    uint8_t b = a & 0xf;
    bcdAdjust(&b);
    if ((a & 0xf0) != 0) {
        a >>= 4;
        for (int b = 0; b < a; b++) {
            a += 0x16;
            bcdAdjust(&a);
        }
    }
    bcdAdjust(&a);
}
void displayMsg_2c5e(uint8_t msg) {
    uint16_t msgDataAddr = tableLookup_0018(DATA_MSG_TABLE_36a5, msg);
    int16_t screenLoc = *(int16_t *)(rom_long_ptr(msgDataAddr));
    uint8_t *chr = rom_long_ptr(msgDataAddr + 1);
    screenLoc &= 0x7fff;
    uint8_t *colour = &COLOUR[screenLoc];
    uint8_t *video = &SCREEN[screenLoc];
    int posDelta = -1;
    if ((*chr & 0x80) == 0) {
        posDelta = -0x20;
    }
    chr++;
    uint16_t byteCount = 0;
    if (msg < 0x80) {
        while (*chr != 0x2f) {
            video_store(video, *chr++);
            video += posDelta;
            byteCount++;
        }
        chr++;
    jump_2c93:
        if (*chr < 0x80) {
            while (byteCount--) {
                video_store(colour, *chr++);
                colour += posDelta;
            }
            return;
        } else {
            while (byteCount--) {
                video_store(colour, *chr);
                colour += posDelta;
            }
            return;
        }
    } else {
        while (*chr != 0x2f) {
            video_store(video, 0x40);
            chr++;
            video += posDelta;
            byteCount++;
        }
        chr++;
        byteCount++;
        while (*chr != 0x2f && byteCount > 0) {
            chr++;
            byteCount--;
        }
        chr++;
        goto jump_2c93;
    }
}
void playSongsAllChannels_2cc1(void) {
    if (CH1_SOUND_WAVE->mask || CH1_SOUND_WAVE->current) {
        uint8_t volume = playSongOneChannel_2d44(CH1_SOUND_WAVE, &CH1_FREQ0, SONG_TABLE_CH1_3bc8);
        if (CH1_SOUND_WAVE->mask != 0)
            CH1_VOL = volume;
    }
    if (CH2_SOUND_WAVE->mask || CH2_SOUND_WAVE->current) {
        uint8_t volume = playSongOneChannel_2d44(CH2_SOUND_WAVE, &CH2_FREQ0, SONG_TABLE_CH2_3bcc);
        if (CH2_SOUND_WAVE->mask != 0)
            CH2_VOL = volume;
    }
    if (CH3_SOUND_WAVE->mask || CH3_SOUND_WAVE->current) {
        uint8_t volume = playSongOneChannel_2d44(CH3_SOUND_WAVE, &CH3_FREQ0, SONG_TABLE_CH3_3bd0);
        if (CH3_SOUND_WAVE->mask != 0)
            CH3_VOL = volume;
    }
}
void soundEffectsAllChannels_2d0c(void) {
    CH1_VOL =
        (CH1_SOUND_EFFECT->mask || CH1_SOUND_EFFECT->current)
            ? soundEffectOneChannel_2dee(CH1_SOUND_EFFECT, &CH1_FREQ0, EFFECT_TABLE_CH1_3b30, 1)
            : 0;
    CH2_VOL =
        (CH2_SOUND_EFFECT->mask || CH2_SOUND_EFFECT->current)
            ? soundEffectOneChannel_2dee(CH2_SOUND_EFFECT, &CH2_FREQ0, EFFECT_TABLE_CH2_3b40, 2)
            : 0;
    CH3_VOL =
        (CH3_SOUND_EFFECT->mask || CH3_SOUND_EFFECT->current)
            ? soundEffectOneChannel_2dee(CH3_SOUND_EFFECT, &CH3_FREQ0, EFFECT_TABLE_CH3_3b80, 3)
            : 0;
    CH1_FREQ4 = 0;
}
static uint8_t highestSoundBit(uint8_t flags) {
    static const uint8_t bits[16] = {0, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4};
    uint8_t high = bits[flags >> 4];
    return high ? high + 4 : bits[flags & 15];
}
uint8_t playSongOneChannel_2d44(SOUND_EFFECT *effect, uint8_t *frequency, uint8_t *table) {
    if (effect->mask == 0)
        return soundEffectClear_2df4(effect, frequency);
    ((void)0);
    uint8_t bit = highestSoundBit(effect->mask);
    uint8_t mask = POWER_OF_2_3bb0[bit - 1];
    if (bit == 0)
        return 0;
    uint16_t addr;
    if ((effect->current & mask) == 0) {
        effect->current = mask;
        ((void)0);
        bit--;
        addr = tableLookup_0018(table, bit);
        ((void)0);
    } else {
        ((void)0);
        if (--effect->duration)
            goto jump_2dd7;
    jump_2d6c:
        addr = effect->offset;
    }
    int a = rom_long_read(addr++);
    effect->offset = addr;
    ((void)0);
    if (a >= 0xf0) {
        ((void)0);
        a &= 0xf;
        static void (*const func[])(SOUND_EFFECT *, uint8_t *)
            __attribute__((section(".song_dispatch"))) = {soundEffectIndirect_2f55,
                                                          soundEffectSelect_2f65,
                                                          soundEffectInitialFrequency_2f77,
                                                          soundEffectInitialVolume_2f89,
                                                          soundEffectType_2f9b,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          nothingSound_000c,
                                                          soundEffectMarkDone_2fad};
        func[a](effect, frequency);
        goto jump_2d6c;
    }
    if ((a & 0x1f) != 0) {
        effect->dir = a;
    }
    int c = effect->volumeInitial;
    if ((effect->type & 8) != 0) {
        c = 0;
    }
    effect->volume = c;
    effect->duration = POWER_OF_2_3bb0[(a >> 5) & 7];
    if ((a & 0x1f) != 0) {
        effect->frequency = FREQ_TABLE_3bb8[a & 0x0f];
    }
jump_2dd7:
    a = effect->dir & 0x10;
    if (a != 0) {
        a = 1;
    }
    a += effect->frequencyInitial;
    ((void)0);
    if (a == 0)
        return frequencyWithVolume_2ee8(effect, frequency, effect->frequency);
    else
        return frequencyScaledWithVolume_2ee4(effect, frequency, effect->frequency, a);
}
uint8_t soundEffectOneChannel_2dee(SOUND_EFFECT *effect, uint8_t *frequency, uint8_t *table,
                                   int chan) {
    if (effect->mask != 0)
        return soundEffectProcess_2e1b(effect, frequency, table, chan);
    else
        return soundEffectClear_2df4(effect, frequency);
}
uint8_t soundEffectClear_2df4(SOUND_EFFECT *effect, uint8_t *frequency) {
    if (effect->current == 0)
        return 0;
    effect->current = effect->dir = effect->frequency = effect->volume = 0;
    frequency[0] = frequency[1] = frequency[2] = frequency[3] = 0;
    return 0;
}
uint8_t soundEffectProcess_2e1b(SOUND_EFFECT *effect, uint8_t *frequency, uint8_t *table,
                                int chan) {
process_next:
    if (!effect->mask)
        return soundEffectClear_2df4(effect, frequency);
    ((void)0);
    uint8_t bit = highestSoundBit(effect->mask);
    uint8_t mask = POWER_OF_2_3bb0[bit - 1];
    if (bit == 0)
        return 0;
    if ((effect->current & mask) == 0) {
        effect->current = mask;
        ((void)0);
        table += (bit - 1) * 8;
        memcpy(&effect->selected, table, 8);
        ((void)0);
        effect->duration = effect->offset & 0x7f;
        effect->frequency = effect->frequencyInitial;
        effect->type = effect->volumeInitial >> 4;
        ((void)0);
        if ((effect->type & 8) == 0) {
            effect->volume = effect->volumeInitial;
            effect->dir = 0;
        }
    }
    ((void)0);
    if (--effect->duration != 0)
        goto jump_2ecd;
    if (effect->repeat != 0 && --effect->repeat == 0) {
        ((void)0);
        effect->mask &= ~mask;
        goto process_next;
    } else {
        ((void)0);
        effect->duration = effect->offset & 0x7f;
        if ((effect->offset & 0x80) != 0) {
            effect->frequencyDelta = -effect->frequencyDelta;
            ((void)0);
            effect->dir ^= 1;
            if ((effect->dir & 1) != 0)
                goto jump_2ecd;
        }
        ((void)0);
        effect->frequencyInitial += effect->offset >> 8;
        effect->frequency = effect->frequencyInitial;
        effect->volumeInitial += effect->volumeDelta;
        if ((effect->type & 8) == 0)
            effect->volume = effect->volumeInitial;
    }
jump_2ecd:
    effect->frequency += effect->frequencyDelta;
    if ((effect->selected & 0x70) == 0)
        return frequencyWithVolume_2ee8(effect, frequency, effect->frequency);
    else
        return frequencyScaledWithVolume_2ee4(effect, frequency, effect->frequency,
                                              (effect->selected & 0x70) >> 4);
}
uint8_t frequencyScaledWithVolume_2ee4(SOUND_EFFECT *effect, uint8_t *frequency,
                                       uint16_t frequencyValue, uint8_t scale) {
    ((void)0);
    frequencyValue <<= scale;
    return frequencyWithVolume_2ee8(effect, frequency, frequencyValue);
}
uint8_t frequencyWithVolume_2ee8(SOUND_EFFECT *effect, uint8_t *frequency,
                                 uint16_t frequencyValue) {
    frequency[0] = frequencyValue & 0xff;
    frequency[1] = (frequencyValue >> 4) & 0xf;
    frequency[2] = (frequencyValue >> 8) & 0xff;
    frequency[3] = (frequencyValue >> 12) & 0xf;
    static uint8_t (*const func[])(SOUND_EFFECT *) = {
        volumeDecayNone_2f22,        volumeDecay_2f26,           volumeDecayHalfTime_2f2b,
        volumeDecayQuarterTime_2f3c, volumeDecayEighthTime_2f43, soundEffectDoNothing_2f4a,
        soundEffectDoNothing_2f4a,   soundEffectDoNothing_2f4a,  soundEffectDoNothing_2f4a,
        soundEffectDoNothing_2f4a,   soundEffectDoNothing_2f4a,  soundEffectDoNothing_2f4a,
        soundEffectDoNothing_2f4a,   soundEffectDoNothing_2f4a,  soundEffectDoNothing_2f4a,
        soundEffectDoNothing_2f4a};
    int vol = func[effect->type](effect);
    ((void)0);
    return vol;
}
uint8_t volumeDecayNone_2f22(SOUND_EFFECT *effect) { return effect->volume; }
uint8_t volumeDecay_2f26(SOUND_EFFECT *effect) {
    return volumeDecrease_2f34(effect, effect->volume);
}
uint8_t volumeDecayHalfTime_2f2b(SOUND_EFFECT *effect) {
    return volumeDecreaseConditional_2f30(effect, *SOUND_COUNTER & 1);
}
uint8_t volumeDecreaseConditional_2f30(SOUND_EFFECT *effect, uint8_t condition) {
    if (condition != 0)
        return effect->volume;
    return volumeDecrease_2f34(effect, effect->volume);
}
uint8_t volumeDecrease_2f34(SOUND_EFFECT *effect, uint8_t volume) {
    volume &= 0xf;
    if (volume == 0)
        return 0;
    effect->volume = --volume;
    return volume;
}
uint8_t volumeDecayQuarterTime_2f3c(SOUND_EFFECT *effect) {
    return volumeDecreaseConditional_2f30(effect, *SOUND_COUNTER & 3);
}
uint8_t volumeDecayEighthTime_2f43(SOUND_EFFECT *effect) {
    return volumeDecreaseConditional_2f30(effect, *SOUND_COUNTER & 7);
}
uint8_t soundEffectDoNothing_2f4a(SOUND_EFFECT *effect) { return 0; }
void soundEffectIndirect_2f55(SOUND_EFFECT *effect, uint8_t *frequency) {
    ((void)0);
    effect->offset = *((uint16_t *)rom_long_ptr(effect->offset));
}
void soundEffectSelect_2f65(SOUND_EFFECT *effect, uint8_t *frequency) {
    effect->selected = rom_long_read(effect->offset++);
    ((void)0);
}
void soundEffectInitialFrequency_2f77(SOUND_EFFECT *effect, uint8_t *frequency) {
    effect->frequencyInitial = rom_long_read(effect->offset++);
    ((void)0);
}
void soundEffectInitialVolume_2f89(SOUND_EFFECT *effect, uint8_t *frequency) {
    effect->volumeInitial = rom_long_read(effect->offset++);
    ((void)0);
}
void soundEffectType_2f9b(SOUND_EFFECT *effect, uint8_t *frequency) {
    effect->type = rom_long_read(effect->offset++);
    ((void)0);
}
void soundEffectMarkDone_2fad(SOUND_EFFECT *effect, uint8_t *frequency) {
    effect->mask &= ~effect->current;
    ((void)0);
    soundEffectClear_2df4(effect, frequency);
}
void isr_3000(void) {
    uint8_t h = 0;
    uint8_t l = 0;
    do {
        do {
            uint8_t c = 0;
            for (uint8_t b = 0; b < 0x10; b++) {
                kickWatchdog();
                do {
                    c += rom_read((h << 8) | l);
                    l += 2;
                } while (l >= 2);
                h++;
            }
            if (c != 0) {
                romChecksumBad_3031(h, c);
                return;
            }
            COINCOUNTER = 0;
        } while (h != 0x30);
        h = 0;
        l++;
    } while (l < 2);
    ramTest_3042();
}
void romChecksumBad_3031(uint8_t h, uint8_t checksum) {
    h--;
    COINCOUNTER = h & 0xf0;
    ((void)0);
    testResultRamRom_30bd(h >> 4, checksum, 0);
}
void ramTest_3042(void) {
    uint16_t *stackData = DATA_3154;
    uint8_t a = 0;
    uint16_t de = 0;
    uint8_t testValue = 0;
    do {
        ((void)0);
        for (uint8_t b = 0xff; b != 0; b--) {
            uint16_t hl = *stackData++;
            de = *stackData++;
            testValue = b;
            do {
                kickWatchdog();
                do {
                    do {
                        testValue &= de;
                        arcade_byte(hl) = testValue;
                        testValue += 0x33;
                        hl++;
                    } while ((hl & 0x0f) != 0);
                    testValue = testValue * 5 + 0x31;
                } while ((hl & 0xff) != 0);
                de -= 0x100;
            } while ((de & 0xff00) != 0);
            stackData -= 2;
            hl = *stackData++;
            de = *stackData++;
            testValue = b;
            do {
                kickWatchdog();
                do {
                    do {
                        testValue &= de;
                        if (testValue != (arcade_byte(hl) & de)) {
                            ((void)0);
                            badRam_30b5(de & 0xff, testValue);
                            return;
                        }
                        testValue += 0x33;
                    } while ((++hl & 0x0f) != 0);
                    testValue = testValue * 5 + 0x31;
                } while ((hl & 0xff) != 0);
                de -= 0x100;
            } while ((de & 0xff00) != 0);
            stackData -= 2;
            b -= 0x10;
        }
        a = *stackData++ >> 8;
        de = *stackData++;
    } while ((a != 0x44) || ((de & 0xff) ^ 0xf0) != 0);
    ((void)0);
    testResultRamRom_30bd((de & 0xff), testValue, 1);
}
void badRam_30b5(uint8_t e, uint8_t c) {
    ((void)0);
    testResultRamRom_30bd((e & 1) ^ 1, c, 0);
}
void testResultRamRom_30bd(int e, uint8_t checksum, uint8_t pass) {
    ((void)0);
    kickWatchdog();
    for (int i = 0; i < 0x400; i++) {
        arcade_byte(0x4c00 + i) = 0;
    }
    kickWatchdog();
    for (int i = 0; i < 0x400; i++) {
        video_store(&SCREEN[i], 0x40);
    }
    kickWatchdog();
    for (int i = 0; i < 0x400; i++) {
        video_store(&COLOUR[i], 0x0f);
    }
    if (pass == 0) {
        badRomOrRamMessage_30fb(e, 4, checksum);
        return;
    }
    displayMsg_2c5e(MSG_FREEPLAY);
    serviceModeOrStartGame_3174();
}
void badRomOrRamMessage_30fb(int e, int h, uint8_t checksum) {
    video_store(&SCREEN[0x184], e + 0x30);
    displayMsg_2c5e(MSG_BADROMRAM);
    uint8_t *hl = BAD_ROM_316c;
    if (h >= 0x40) {
        hl = BAD_W_RAM_316e;
        if (h < 0x4c) {
            hl = BAD_V_RAM_3170;
            if (h >= 0x44) {
                hl = BAD_C_RAM_3172;
            }
        }
    }
    video_store(&SCREEN[0x204], hl[0]);
    video_store(&SCREEN[0x264], hl[1]);
    if ((IN0_UP & IN1_UP) == 0) {
        video_store(&SCREEN[0x185], checksum & 0xf);
        video_store(&SCREEN[0x186], checksum >> 4);
    }
    do {
        kickWatchdog();
    } while (IN1_SERVICE == 0);
    initSelfTest_230b();
}
void serviceModeOrStartGame_3174(void) {
    INTENABLE = SOUNDENABLE = AUXENABLE = FLIPSCREEN = P1START = P2START = COINLOCKOUT = 1;
    FLIPSCREEN = 0;
    interruptVector(isr_008d);
    do {
        ((void)0);
        kickWatchdog();
        MAIN_STATE = MAIN_STATE_INIT;
        RESET_STATE = RESET_STATE_DONE;
        INTENABLE = 1;
        interruptEnable();
        if ((~IO_INPUT0 & INPUT_ANYCOIN) != 0) {
            ((void)0);
            CH1_SOUND_EFFECT->mask = 2;
        }
        if ((~IO_INPUT1 & INPUT_ANYSTART) != 0) {
            ((void)0);
            CH1_SOUND_EFFECT->mask = 1;
        }
        if (IN0_UP == 0 || IN1_UP == 0) {
            ((void)0);
            CH3_SOUND_EFFECT->mask = 8;
        }
        if (IN0_LEFT == 0 || IN1_LEFT == 0) {
            ((void)0);
            CH3_SOUND_EFFECT->mask = 4;
        }
        if (IN0_RIGHT == 0 || IN1_RIGHT == 0) {
            ((void)0);
            CH3_SOUND_EFFECT->mask = 0x10;
        }
        if (IN0_DOWN == 0 || IN1_DOWN == 0) {
            ((void)0);
            CH3_SOUND_EFFECT->mask = 0x20;
        }
        displayMsg_2c5e(MSG_NOCOINS + DIP_SWITCH_COINS);
        if (DIP_SWITCH_BONUS == 3) {
            displayMsg_2c5e(MSG_BONUS_NONE);
        } else {
            displayMsg_2c5e(MSG_BONUS);
            displayMsg_2c5e(MSG_000);
            video_store(&SCREEN[0x22a], DATA_32f9[DIP_SWITCH_BONUS]);
            video_store(&SCREEN[0x24a], DATA_32f9[DIP_SWITCH_BONUS + 1]);
        }
        uint8_t a = (DIP_SWITCH_LIVES) + 0x31;
        if (a == 0x34)
            a++;
        video_store(&SCREEN[0x20c], a);
        displayMsg_2c5e(MSG_PACMAN);
        displayMsg_2c5e(((IN1_CABINET == 0) ? 0 : 1) + MSG_TABLE);
        interruptHalt();
    } while (IN1_SERVICE == 0);
    INTENABLE = 0;
    interruptDisable();
    INTENABLE = SOUNDENABLE = AUXENABLE = FLIPSCREEN = P1START = P2START = COINLOCKOUT =
        COINCOUNTER = 0;
    uint16_t *stackData = DATA_3ae2;
    for (uint8_t b = 0; b < 3; b++) {
        uint16_t hl = *stackData++ - 0x4000;
        uint16_t de = *stackData++;
        do {
            kickWatchdog();
            uint16_t bc = *stackData++;
            ((void)0);
            for (int i = 0; i < 0x10; i++) {
                video_store(&SCREEN[hl++], 0x3c);
                video_store(&SCREEN[hl++], de >> 8);
            }
            for (int i = 0; i < 0x10; i++) {
                video_store(&SCREEN[hl++], bc & 0xff);
                video_store(&SCREEN[hl++], 0x3f);
            }
            stackData--;
            de--;
        } while ((de & 0xff) > 0);
        stackData++;
    }
    for (uint8_t b = 0; b < 8; b++) {
        delay_32ed();
    }
    do {
        kickWatchdog();
    } while (!IN1_SERVICE);
    if (P1START || P2START) {
        mainTaskLoop_234b();
        return;
    }
    for (uint8_t b = 0; b < 8; b++) {
        delay_32ed();
    }
    if (IN1_SERVICE != 0) {
        mainTaskLoop_234b();
        return;
    }
    uint8_t e = 1;
    do {
        for (uint8_t b = 0; b < 4; b++) {
            do {
                kickWatchdog();
                delay_32ed();
            } while ((IO_INPUT0 & e) != 0);
            do {
                delay_32ed();
                kickWatchdog();
            } while (IO_INPUT0 == 0);
        }
        e <<= 1;
    } while (e < 0x10);
    for (uint16_t hl = 0; hl < 0x400; hl++) {
        video_store(&SCREEN[hl], 0x40);
    }
    madeByNamco_3af4();
    while (IN1_SERVICE == 0) {
        kickWatchdog();
    }
    mainTaskLoop_234b();
}
void delay_32ed(void) {
    kickWatchdog();
    for (int hl = 0x2800; hl > 0; hl--)
        ;
}
#if 0
    uint8_t *msgTable_36a5[] = 
    {
        {
            0xd4, 0x83,
            'H','I','G','H','@','S','C','O','R','E',
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x3b, 0x80
            'C','R','E','D','I','T','@','@','@',
            0x2f, 0x8f, 0x2f, 0x80
        },
        {
            0x3b, 0x80
            'F','R','E','E','@','P','L','A','Y', 
            0x2f, 0x8f, 0x2f, 0x80
        },
        {
            0x8c, 0x02
            'P','L','A','Y','E','R','@','O','N','E', 
            0x2f, 0x85, 
            0x2f, 0x10, 0x10, 0x1a, 0x1a, 0x1a, 0x1a, 0x1a, 0x1a, 0x10, 0x10
        },
        {
            0x8c, 0x02
            'P','L','A','Y','E','R','@','T','W','O',
            0x2f, 0x85, 0x2f, 0x80
        },
        {
            0x92, 0x02
            'G','A','M','E','@','@','O','V','E','R',
            0x2f, 0x81, 0x2f, 0x80
        },
        {
            0x52, 0x02
            'R','E','A','D','Y','?', 
            0x2f, 0x89, 0x2f, 0x90
        },
        {
            0xee, 0x02
            'P','U','S','H','@','S','T','A','R','T','@',
            'B','U','T','T','O','N',
            0x2f, 0x87, 0x2f, 0x80
        },
        {
            0xb2, 0x02
            "1@PLAYER@ONLY "
            0x2f, 0x85, 0x2f, 0x80
        },
        {
            0xb2, 0x02
            "1@OR@2@PLAYERS"
            0x2f, 0x85, 0x00, 0x2f 00 80
        },
        {
            0x00, 0x96 03
            "BONUS@PUCKMAN@FOR@@@000@]^_"
            0x2f, 0x8e, 0x2f, 0x80
        },
        {
            0xba, 0x02
            '\\','@','(',')','*','+',',','-','.','@','1','9','8','0', 
            0x2f, 0x83, 0x2f, 0x80
        },
        {
            0xc3, 0x02
            'C','H','A','R','A','C','T','E','R','@','/',
            '@','N','I','C','K','N','A','M','E',
            0x2f, 0x8f, 0x2f, 0x80
        },
        {
            0x65, 0x01 
            '&','A','K','A','B','E','I','&',
            0x2f, 0x81, 0x2f, 0x80
        },
        {
            0x45, 0x01 
            '&','M','A','C','K','Y','&',
            0x2f, 0x81, 0x2f, 0x80
        },
        {
            0x48, 0x01 
            '&','P','I','N','K','Y','&', 
            0x2f, 0x83, 0x2f, 0x80
        },
        {
            0x48, 0x01 
           '&','M','I','C','K','Y','&', 
            0x2f, 0x83, 0x2f, 0x80
        },
        {
            0x76, 0x02
            0x10, '@','1','0','@',']','^','_',
            0x2f, 0x9f, 0x2f, 0x80
        },
        {
            0x78, 0x02
            0x14, '@','5','0','@',']','^','_',
            0x2f, 0x9f, 0x2f, 0x80
        },
        {
            0x5d, 0x02
            '(',')','*','+',',','-','.', 
            0x2f, 0x83, 0x2f, 0x80 
        },
            '@','O','I','K','A','K','E',';',';',';',';', 
            0x2f, 0x81, 0x2f, 0x80 
        },
        {
            0xc5, 0x02 
            '@','U','R','C','H','I','N',';',';',';',';',';',
            0x2f, 0x81, 0x2f, 0x80
        },
            '@','M','A','C','H','I','B','U','S','E',';',';',
        {
            0xc8, 0x02
            '@','B','O','M','P',';',';',';',';',';',';',';',
            0x2f, 0x83, 0x2f, 0x80
        },
        {
            0x12, 0x02
            0x81, 0x85,
            0x2f, 0x83, 0x2f, 0x90
        },
        {
            0x32, 0x02
            '@', 0x82, 0x85, '@'
            0x2f, 0x83, 0x2f, 0x90
        },
        {
            0x32, 0x02				; OFFSET 
            '@', 0x83, 0x85, '@'
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x32, 0x02
            '@', 0x84, 0x85, '@'
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x32, 0x02
            '@', 0x86, 0x8d, '@'
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x32, 0x02
            0x87, 0x88, 0x8d, 0x8e 
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x32, 0x02
            0x89, 0x8a, 0x8d, 0x8e 
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x32, 0x02
            0x8b, 0x8c, 0x8d, 0x8e 
            0x2f, 0x83, 0x2f, 0x90 
        },
        {
            0x04, 0x03 
            'M','E','M','O','R','Y','@','@','O','K', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x04, 0x03 
            'B','A','D','@','@','@','@','R','@','M', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x08, 0x03 
            '1','@','C','O','I','N','@','@','1','@','C','R','E','D',
            'I','T','@', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x08, 0x03 
            '2','@','C','O','I','N','S','@','1','@','C','R','E','D',
            'I','T','@', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x08, 0x03 
            '1','@','C','O','I','N','@','@','2','@','C','R','E','D',
            'I','T','S', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x08, 0x03 
            'F','R','E','E','@','@','P','L','A','Y','@','@','@','@',
            '@','@','@', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0a, 0x03 
            'B','O','N','U','S','@','@','N','O','N','E', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0a, 0x03 
            'B','O','N','U','S','@', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0c, 0x03 
            'P','U','C','K','M','A','N', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0e, 0x03
            'T','A','B','L','E','@','@', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0e, 0x03
            'U','P','R','I','G','H','T', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x0a, 0x02 
            '0','0','0', 
            0x2f, 0x8f, 0x2f, 0x80 
        },
        {
            0x6b, 0x01 
            '&','A','O','S','U','K','E','&', 
            0x2f, 0x85, 0x2f, 0x80 
        },
        {
            0x4b, 0x01
            '&','M','U','C','K','Y','&', 
            0x2f, 0x85, 0x2f, 0x80 
        },
        {
            0x6e, 0x01
            '&','G','U','Z','U','T','A','&', 
            0x2f, 0x87, 0x2f, 0x80 
        },
        {
            0x4e, 0x01
            '&','M','O','C','K','Y','&', 
            0x2f, 0x87, 0x2f, 0x80 
        },
        {
            0xcb, 0x02
            '@','K','I','M','A','G','U','R','E',';',';', 
            0x2f, 0x85, 0x2f, 0x80 
        },
        {
            0xcb, 0x02
            '@','S','T','Y','L','I','S','T',';',';',';',';', 
            0x2f, 0x85, 0x2f, 0x80 
        },
        {
            0xce, 0x02
            '@','O','T','O','B','O','K','E',';',';',';', 
            0x2f, 0x87, 0x2f, 0x80 
        },
        {
            0xce, 0x02
            '@','C','R','Y','B','A','B','Y',';',';',';',';', 
            0x2f, 0x87, 0x2f, 0x80 
        },
#endif
void madeByNamco_3af4(void) {
    uint8_t *hl = &SCREEN[0xa2];
    uint8_t *de = rom_ptr(0x3a4f);
    while (1) {
        video_store(hl, 0x14);
        uint8_t a = *de;
        if (*de == 0)
            return;
        de++;
        hl += a;
    }
}
#if 0
    {
        0x96, 0x03
        'B','O','N','U','S','@','P','A','C',';','M','A','N','@','F',
        'O','R','@','@','@','0','0','0','@',']','^','_', 
        0x2f, 0x8e, 0x2f, 0x80
    },
    {
        0x3a, 0x03
        0x5c,'@','1','9','8','0','@','M','I','D','W','A','Y','@',
        'M','F','G','%','C','O','%', 
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0x3d, 0x03 
        0x5c,'@','1','9','8','0','@','M','I','D','W','A','Y','@',
        'M','F','G','%','C','O','%',
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0xc5, 0x02 
        ';','S','H','A','D','O','W','@','@','@',
        0x2f, 0x81, 0x2f, 0x80
    },
    {
        0x65, 0x01 
        '&','B','L','I','N','K','Y','&','@', 
        0x2f, 0x81, 0x2f, 0x80 
    },
    {
        0xc8, 0x02
        ';','S','P','E','E','D','Y','@','@','@', 
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0x68, 0x01 
        '&','P','I','N','K','Y','&','@','@', 
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0xcb, 0x02 
        ';','B','A','S','H','F','U','L','@','@', 
        0x2f, 0x85, 0x2f, 0x80
    },
    {
        0x6b, 0x01 
        '&','I','N','K','Y','&','@','@','@', 
        0x2f, 0x85, 0x2f, 0x80
    },
    {
        0xce, 0x02 
        ';','P','O','K','E','Y','@','@','@','@', 
        0x2f, 0x87, 0x2f, 0x80
    },
    {
        0x6e, 0x01
        '&','C','L','Y','D','E','&','@','@', 
        0x2f, 0x87, 0x2f, 0x80
    },
    {
        0xc5, 0x02
        ';','A','A','A','A','A','A','A','A',';', 
        0x2f, 0x81, 0x2f, 0x80
    },
    {
        0x65, 0x01
        '&','B','B','B','B','B','B','B','&', 
        0x2f, 0x81, 0x2f, 0x80
    },
    {
        0xc8, 0x02
        ';','C','C','C','C','C','C','C','C',';', 
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0x68, 0x01 
        '&','D','D','D','D','D','D','D','&', 
        0x2f, 0x83, 0x2f, 0x80
    },
    {
        0xcb, 0x02 
        ';','E','E','E','E','E','E','E','E',';', 
        0x2f, 0x85, 0x2f, 0x80
    },
    {
        0x6b, 0x01
        '&','F','F','F','F','F','F','F','&', 
        0x2f, 0x85, 0x2f, 0x80
    },
    {
        0xce, 0x02
        ';','G','G','G','G','G','G','G','G',';', 
        0x2f, 0x87, 0x2f, 0x80
    },
    {
        0x6e, 0x01
        '&','H','H','H','H','H','H','H','&', 
        0x2f, 0x87, 0x2f, 0x80
    },
    {
        0x0c, 0x03
        'P','A','C',';','M','A','N', 
        0x2f, 0x8f, 0x2f, 0x80
    },
#endif
