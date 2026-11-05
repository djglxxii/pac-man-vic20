
.section .zp.bss,"aw",@nobits
.global v_addr,v_save,v_data,v_flags,v_shift,v_flip,v_lo,v_hi
v_addr: .zero 2
v_save: .zero 2
v_data: .zero 2
v_flags: .zero 1
v_shift: .zero 1
v_flip: .zero 1
.global v_right,v_saved_right,v_row
v_right: .zero 2
v_saved_right: .zero 2
v_lo: .zero 1
v_hi: .zero 1
v_row: .zero 1
.section .text.bitmap,"ax",@progbits
.global arcade_prepare_outputs
arcade_prepare_outputs:
 ldx #15
prepare_sound:
 lda $0e8c,x
 sta $0350,x
 dex
 bpl prepare_sound
 ldx #27
prepare_sprites:
 lda $0c02,x
 sta $0c22,x
 dex
 bpl prepare_sprites
 rts
.section .rodata.bit_reverse,"a",@progbits
.global bit_reverse
.p2align 8
bit_reverse:
.byte 0,128,64,192,32,160,96,224,16,144,80,208,48,176,112,240
.byte 8,136,72,200,40,168,104,232,24,152,88,216,56,184,120,248
.byte 4,132,68,196,36,164,100,228,20,148,84,212,52,180,116,244
.byte 12,140,76,204,44,172,108,236,28,156,92,220,60,188,124,252
.byte 2,130,66,194,34,162,98,226,18,146,82,210,50,178,114,242
.byte 10,138,74,202,42,170,106,234,26,154,90,218,58,186,122,250
.byte 6,134,70,198,38,166,102,230,22,150,86,214,54,182,118,246
.byte 14,142,78,206,46,174,110,238,30,158,94,222,62,190,126,254
.byte 1,129,65,193,33,161,97,225,17,145,81,209,49,177,113,241
.byte 9,137,73,201,41,169,105,233,25,153,89,217,57,185,121,249
.byte 5,133,69,197,37,165,101,229,21,149,85,213,53,181,117,245
.byte 13,141,77,205,45,173,109,237,29,157,93,221,61,189,125,253
.byte 3,131,67,195,35,163,99,227,19,147,83,211,51,179,115,243
.byte 11,139,75,203,43,171,107,235,27,155,91,219,59,187,123,251
.byte 7,135,71,199,39,167,103,231,23,151,87,215,55,183,119,247
.byte 15,143,79,207,47,175,111,239,31,159,95,223,63,191,127,255
.section .text.bitmap_tile,"ax",@progbits
.global bitmap_tile
bitmap_tile:
 lda v_save
 and #31
 sta v_saved_right+1
 lda v_save
 lsr
 lsr
 lsr
 lsr
 lsr
 sta v_saved_right
 lda v_save+1
 asl
 asl
 asl
 ora v_saved_right
 cmp #2
 bcc tile_side
 cmp #30
 bcs tile_side
 sta v_saved_right
 lda #29
 sec
 sbc v_saved_right
 sta v_saved_right
 lda v_saved_right+1
 clc
 adc #2
 jmp tile_xy
tile_side:
 tax
 lda v_saved_right+1
 cmp #2
 bcc tile_early_done
 cmp #30
 bcs tile_early_done
 lda #29
 sec
 sbc v_saved_right+1
 sta v_saved_right
 txa
 cmp #30
 bcc tile_bottom
 sec
 sbc #30
 jmp tile_xy
tile_early_done:
 rts
tile_bottom:
 clc
 adc #34
tile_xy:
 asl
 sta v_lo
 asl
 clc
 adc v_lo
 sta v_lo
 lda v_save
 sta v_addr
 lda v_save+1
 clc
 adc #4
 sta v_addr+1
 ldy #0
 lda (v_addr),y
 sta v_hi
 inc v_addr+1
 inc v_addr+1
 inc v_addr+1
 inc v_addr+1
 lda (v_addr),y
 and #31
 sta v_flags
 lda v_hi
 asl
 sta v_data
 lda #0
 rol
 sta v_data+1
 lda v_data
 clc
 adc v_hi
 sta v_data
 lda v_data+1
 adc #0
 sta v_data+1
 lda v_data
 clc
 adc #<arcade_tiles
 sta v_data
 lda v_data+1
 adc #>arcade_tiles
 sta v_data+1
 lda v_flags
 bne tile_shape_ready
 lda #<(arcade_tiles+192)
 sta v_data
 lda #>(arcade_tiles+192)
 sta v_data+1
tile_shape_ready:
 lda v_saved_right
 lsr
 tax
 lda column_lo,x
 clc
 adc v_lo
 sta v_addr
 lda column_hi,x
 adc #0
 sta v_addr+1
 stx v_saved_right+1
 lda v_lo
 lsr
 lsr
 lsr
 lsr
 tax
 lda row_times_14,x
 clc
 adc v_saved_right+1
 sta v_right
 lda #>0x9400
 sta v_right+1
 ldx v_flags
 beq tile_color_done
 lda v_hi
 cmp #$c0
 bcc tile_nonwall
 jsr bitmap_wall_colour
 jmp tile_color_ready
tile_nonwall:
 sec
 sbc #$10
 cmp #5
 bcs tile_not_dot
 lsr
 bcc tile_dot
tile_not_dot:
 lda v_hi
 and #3
 asl
 sta v_shift
 lda v_hi
 lsr
 lsr
 tax
 lda arcade_tile_class,x
 ldx v_shift
 beq tile_class_ready
tile_class_shift:
 lsr
 dex
 bne tile_class_shift
tile_class_ready:
 and #3
 sta v_shift
 lda v_flags
 asl
 asl
 ora v_shift
 tax
 lda arcade_colors,x
 jmp tile_color_ready
tile_dot:
 lda #1
tile_color_ready:
 sta v_shift
 ldy #0
 lda (v_data),y
 iny
 ora (v_data),y
 iny
 ora (v_data),y
 beq tile_color_done
 lda v_shift
 ldy #0
 jsr bitmap_cell_colour
 lda v_lo
 and #15
 cmp #11
 bcc tile_color_done
 ldy #14
 lda v_shift
 jsr bitmap_cell_colour
tile_color_done:
 lda v_saved_right
 and #1
 sta v_flip
 lda #15
 ldx v_flip
 beq tile_mask
 lda #240
tile_mask:
 sta v_flags
 lda v_data
 sta tile_fetch+1
 lda v_data+1
 sta tile_fetch+2
 ldx #0
 ldy #0
tile_pair:
tile_fetch:
 lda $ffff,x
 sta v_hi
 and #240
 bit v_flags
 bpl tile_upper
 lsr
 lsr
 lsr
 lsr
tile_upper:
 sta v_lo
 lda (v_addr),y
 and v_flags
 ora v_lo
 sta (v_addr),y
 iny
 lda v_hi
 and #15
 bit v_flags
 bmi tile_lower
 asl
 asl
 asl
 asl
tile_lower:
 sta v_lo
 lda (v_addr),y
 and v_flags
 ora v_lo
 sta (v_addr),y
 iny
 inx
 cpx #3
 bne tile_pair
tile_done:
 rts
.section .maze_cells,"aw",@nobits
.global maze_cells
maze_cells: .zero 25
.section .cold,"ax",@progbits
.global mazeColours_24d7
mazeColours_24d7:
 cmp #1
 beq maze_palette_full
 ldx $0e04
 cpx #15
 bcc maze_palette_full
 cpx #30
 bcc video_flash_palette
maze_palette_full:
 jmp mazeColours_full
.global video_flash_palette
video_flash_palette:
 cmp #2
 bne maze_palette_blue
 lda #31
 bne maze_palette_value
maze_palette_blue:
 lda #16
maze_palette_value:
 ldx #0
maze_palette_pages:
 sta $0840,x
 sta $0940,x
 sta $0a40,x
 inx
 bne maze_palette_pages
 ldx #127
maze_palette_tail:
 sta $0b40,x
 dex
 bpl maze_palette_tail
 lda #15
 ldx #63
maze_palette_hud:
 sta $0bc0,x
 dex
 bpl maze_palette_hud
 lda #1
 sta maze_flash
 rts
.section .text.bitmap_cell_colour,"ax",@progbits
bitmap_cell_colour:
 sta (v_right),y
 tya
 clc
 adc v_right
 tax
 and #7
 tay
 lda bit_masks,y
 sta v_row
 txa
 lsr
 lsr
 lsr
 tay
 lda v_hi
 cmp #$c0
 bcc cell_colour_shared
 lda maze_cells,y
 ora v_row
 sta maze_cells,y
 jmp cell_colour_done
cell_colour_shared:
 lda maze_cells,y
 and v_row
 beq cell_colour_done
 jsr bitmap_wall_colour
 sta 0x9400,x
cell_colour_done:
 lda $0200,x
 cmp #196
 bcs pool_background_colour_done
 lda $9400,x
 sta $9600,x
pool_background_colour_done:
 rts
.section .text.bitmap_wall_colour,"ax",@progbits
bitmap_wall_colour:
 lda #1
 ldy $0e04
 cpy #15
 bcc wall_colour_done
 cpy #30
 bcs wall_colour_done
 ldy $0840
 cpy #31
 bne wall_colour_done
 lda #6
wall_colour_done:
 rts
.section .arcade_data,"a",@progbits
.global bit_masks
bit_masks:
.byte 1,2,4,8,16,32,64,128
.section .text.bitmap_maze_flash,"ax",@progbits
.global bitmap_maze_flash
bitmap_maze_flash:
 lda $0840
 cmp #31
 beq maze_colour_blue
 lda #1
 bne maze_colour_ready
maze_colour_blue:
 lda #6
maze_colour_ready:
 sta v_flags
 ldx #199
 ldy #24
maze_colour_byte:
 lda maze_cells,y
 sta v_row
 lda #8
 sta v_lo
 lda v_flags
maze_colour_cell:
 asl v_row
 bcc maze_colour_next
 sta 0x9400,x
 pha
 lda $0200,x
 cmp #196
 bcs pool_flash_occupied
 pla
 sta $9600,x
 jmp maze_colour_next
pool_flash_occupied:
 pla
maze_colour_next:
 dex
 dec v_lo
 bne maze_colour_cell
 dey
 bpl maze_colour_byte
maze_colour_done:
 rts
.section .rodata.bitmap_columns,"a",@progbits
.global column_lo,column_hi,row_times_14
column_lo:
.byte 0,224,192,160,128,96,64,32,0,224,192,160,128,96
column_hi:
.byte 16,16,17,18,19,20,21,22,23,23,24,25,26,27
row_times_14:
.byte 0,14,28,42,56,70,84,98,112,126,140,154,168,182
.section .text.add_score_bcd,"ax",@progbits
.global add_score_bcd
add_score_bcd:
 sta v_lo
 stx v_hi
 lda #$80
 ldx $0e09
 beq score_player
 lda #$84
score_player:
 sta v_data
 lda #$0e
 sta v_data+1
 ldy #0
 sed
 clc
 lda (v_data),y
 adc v_lo
 sta (v_data),y
 iny
 lda (v_data),y
 adc v_hi
 sta (v_data),y
 iny
 lda (v_data),y
 adc #0
 sta (v_data),y
 cld
 rts
.section .text.spend_credit_bcd,"ax",@progbits
.global spend_credit_bcd
spend_credit_bcd:
 sta v_lo
 sed
 sec
 lda $0e6e
 sbc v_lo
 sta $0e6e
 cld
 rts
