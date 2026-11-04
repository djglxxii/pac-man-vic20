/* Whole-frame pool transaction. Six 8x12 slots occupy at most 24 cells.
   Two disjoint banks of 24 retain displayed and pending compositions. The
   final twelve glyphs are unused, except code 255 as a clipped-column sink.
   No dynamic allocation, deferral or logical-clock change is required. */
#include <stdint.h>
#include <string.h>
#define MATRIX ((uint8_t *)0x0200)
#define HOME_COLOURS ((uint8_t *)0x9400)
#define LIVE_COLOURS ((uint8_t *)0x9600)
uint8_t pool_cells[48] __attribute__((section(".pool_lists")));
uint8_t pool_colours[48] __attribute__((section(".pool_lists")));
uint8_t pool_count[2] __attribute__((section(".pool_state")));
uint8_t pool_bank __attribute__((section(".pool_state")));
uint8_t pool_epoch __attribute__((section(".pool_state")));
uint8_t pool_failed __attribute__((section(".pool_state")));
extern uint8_t v_cell, v_color, v_flags, v_shift, v_sy;
extern uint8_t *v_addr, *v_right, *v_save, *v_saved_right;
extern uint8_t full_dirty, rebuild_phase, maze_flash;
void pool_actors(void), pool_reuse_guard(void), bitmap_maze_flash(void);
void video_background(void);

__attribute__((section(".boot.text"))) void pool_init(void) {
    pool_count[0] = pool_count[1] = pool_bank = pool_failed = pool_epoch = 0;
    memset((void *)0x96c4, 0, 196);
}

#ifdef POOL_ADDRESS_FAST
#define HOME(code) ((uint8_t)(((code) << 4) | ((code) >> 4)))
#else
#define HOME(code) (code)
#endif
const uint8_t home_codes[196] = {
    HOME(0),HOME(14),HOME(28),HOME(42),HOME(56),HOME(70),HOME(84),HOME(98),HOME(112),HOME(126),HOME(140),HOME(154),HOME(168),HOME(182),
    HOME(1),HOME(15),HOME(29),HOME(43),HOME(57),HOME(71),HOME(85),HOME(99),HOME(113),HOME(127),HOME(141),HOME(155),HOME(169),HOME(183),
    HOME(2),HOME(16),HOME(30),HOME(44),HOME(58),HOME(72),HOME(86),HOME(100),HOME(114),HOME(128),HOME(142),HOME(156),HOME(170),HOME(184),
    HOME(3),HOME(17),HOME(31),HOME(45),HOME(59),HOME(73),HOME(87),HOME(101),HOME(115),HOME(129),HOME(143),HOME(157),HOME(171),HOME(185),
    HOME(4),HOME(18),HOME(32),HOME(46),HOME(60),HOME(74),HOME(88),HOME(102),HOME(116),HOME(130),HOME(144),HOME(158),HOME(172),HOME(186),
    HOME(5),HOME(19),HOME(33),HOME(47),HOME(61),HOME(75),HOME(89),HOME(103),HOME(117),HOME(131),HOME(145),HOME(159),HOME(173),HOME(187),
    HOME(6),HOME(20),HOME(34),HOME(48),HOME(62),HOME(76),HOME(90),HOME(104),HOME(118),HOME(132),HOME(146),HOME(160),HOME(174),HOME(188),
    HOME(7),HOME(21),HOME(35),HOME(49),HOME(63),HOME(77),HOME(91),HOME(105),HOME(119),HOME(133),HOME(147),HOME(161),HOME(175),HOME(189),
    HOME(8),HOME(22),HOME(36),HOME(50),HOME(64),HOME(78),HOME(92),HOME(106),HOME(120),HOME(134),HOME(148),HOME(162),HOME(176),HOME(190),
    HOME(9),HOME(23),HOME(37),HOME(51),HOME(65),HOME(79),HOME(93),HOME(107),HOME(121),HOME(135),HOME(149),HOME(163),HOME(177),HOME(191),
    HOME(10),HOME(24),HOME(38),HOME(52),HOME(66),HOME(80),HOME(94),HOME(108),HOME(122),HOME(136),HOME(150),HOME(164),HOME(178),HOME(192),
    HOME(11),HOME(25),HOME(39),HOME(53),HOME(67),HOME(81),HOME(95),HOME(109),HOME(123),HOME(137),HOME(151),HOME(165),HOME(179),HOME(193),
    HOME(12),HOME(26),HOME(40),HOME(54),HOME(68),HOME(82),HOME(96),HOME(110),HOME(124),HOME(138),HOME(152),HOME(166),HOME(180),HOME(194),
    HOME(13),HOME(27),HOME(41),HOME(55),HOME(69),HOME(83),HOME(97),HOME(111),HOME(125),HOME(139),HOME(153),HOME(167),HOME(181),HOME(195)
};
#define home_code(cell) home_codes[cell]

/* Assembly owns bounded allocation, copying, stamping and publication. */
void video_restore(void), video_update_begin(void), video_update_end(void);
void video_sprites(void);
uint8_t pool_start __attribute__((section(".pool_state")));
uint8_t pool_limit __attribute__((section(".pool_state")));
uint8_t pool_code_base __attribute__((section(".pool_state")));
uint8_t pool_code_end __attribute__((section(".pool_state")));
/* Separate entry/exit symbols preserve host-only capture/profile hooks. */
__attribute__((noinline)) void video_frame_end(void) { __asm__ volatile(""); }
__attribute__((noinline)) void video_frame_begin(void) {
    video_sprites();
    video_frame_end();
}
void video_refresh(void) {
    if (full_dirty) video_restore();
    video_background();
    if (full_dirty) return;
    video_frame_begin();
}
