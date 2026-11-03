/* Adapted from prototypes/multicolour-motion.S for the LLVM-MOS game.
   Only the main thread renders; the IRQ preserves A/X/Y. */
.include "build/multicolour-game/mc-assets.inc"
.section .zp.bss,"aw",@nobits
map_ptr: .zero 2
 /* The map is page-aligned, so its pointer and the cell index share a low byte. */
 /* Keep the raw index high byte separate from the pointer's absolute high byte. */
cell_low = map_ptr
old_lo: .zero 2
old_hi: .zero 2
new_lo: .zero 2
new_hi: .zero 2
new_color: .zero 2
left_ptr: .zero 2
middle_ptr: .zero 2
right_ptr: .zero 2
cell_high: .zero 1
color_pending: .zero 1

background_ptr: .zero 2
shared_ptr: .zero 2
.global v_addr,v_save,v_data,v_flags,v_lo,v_hi
.set v_addr,left_ptr
.set v_save,map_ptr
.set v_data,middle_ptr
.set v_flags,cell_high
.set v_lo,right_ptr
.set v_hi,color_pending

.section .mc_state,"aw",@nobits
.global cells_a_lo,cells_b_lo,cells_a_hi,cells_b_hi,colors_a,colors_b
cells_a_lo: .zero 54
cells_a_hi: .zero 54
cells_b_lo: .zero 54
cells_b_hi: .zero 54
 /* Colour indices are working character code minus 147, covering both banks. */
colors_a: .zero 54
colors_b: .zero 54
.global actors,mc_status,mc_pending,mc_new_count,mc_old_count,mc_new_base
actors: .zero 24                  /* Six records, painter priority: x,y,pose,accent. */
mc_status: .zero 1
mc_pending: .zero 1
mc_busy: .zero 1
mc_stage: .zero 1
mc_new_count: .zero 1
mc_old_count: .zero 1
actor_index: .zero 1
actor_col: .zero 1
actor_y: .zero 1
actor_shift: .zero 1
actor_columns: .zero 1
pixel_y: .zero 1
current_band: .zero 1
sprite_bottom: .zero 1
band_top: .zero 1
band_bottom: .zero 1
valid_columns: .zero 1
left_index: .zero 1               /* Colour slot = working character code - 147. */
middle_index: .zero 1
right_index: .zero 1
mc_hashes: .zero 147
/* Across 567 cells, at most two complete groups of 256 references exist.
   Store their owners rather than reserving a high byte for every glyph. */
mc_overflow0: .zero 1
mc_overflow1: .zero 1

.section .work,"aw",@nobits
mc_refs_lo: .zero 147
.section .mc_maps,"aw",@nobits
.p2align 8
cell_work: .zero 567
.section .mc_under,"aw",@nobits
mc_backgrounds: .zero 108

.global cell_work,mc_backgrounds,mc_refs_lo,mc_hashes,mc_overflow0,mc_overflow1,mc_prepare,mc_commit,mc_publish,mc_abort,mc_commit_end
.global resolve_row,clear_work_map,actor_col,current_band
.global mc_prepare_begin,mc_prepare_step,mc_busy,mc_stage
.set mc_new_base,publish_bank+1
.set background_map,$1800
/* Live front end for the retained hidden-character compositor. */
.section .text.mc_front,"ax",@progbits
.global video_refresh,video_frame_begin,video_frame_end,video_batch_begin,video_batch_end,video_rebuild
video_refresh:
video_batch_begin:
 lda full_dirty
 cmp #2
 beq mc_front_background
 lda rebuild_phase
 cmp #2
 beq mc_front_background
 lda mc_stage
 beq mc_front_background
 cmp #1
 bne mc_front_actor
video_frame_begin:
 jsr mc_update_hud
 jsr mc_live_actors
 jsr mc_prepare_begin
 inc mc_stage
 rts
mc_front_actor:
 jsr mc_prepare_step
 lda mc_busy
 beq mc_front_prepared
 /* Phased row tables make a pair of actors a bounded batch. Servicing two
    avoids spending a separate logic tick on every inexpensive actor. */
 jsr mc_prepare_step
mc_front_prepared:
 lda mc_busy
 bne video_batch_end
 lda #0
 sta mc_stage
 lda mc_status
 bne video_batch_end
 jsr mc_commit
video_frame_end:
 inc mc_frames
 bne video_batch_end
 inc mc_frames+1
video_batch_end:
 rts
mc_front_background:
 jsr video_background
 lda rebuild_phase
 cmp #2
 beq video_batch_end
 lda #1
 sta mc_stage
 rts
video_rebuild:
 jmp video_background
.section .text.mc_outputs,"ax",@progbits
.global arcade_prepare_outputs
arcade_prepare_outputs:
 ldx #15
mc_copy_sound:
 lda $0e8c,x
 sta $1c90,x
 dex
 bpl mc_copy_sound
 ldx #27
mc_copy_actors:
 lda $0c02,x
 sta $0c22,x
 dex
 bpl mc_copy_actors
 rts
.section .text.mc_init,"ax",@progbits
.global mc_init
mc_init:
 /* Boot only: publish_bank's assembled operand selects bank A initially. */
 lda #>cells_a_lo
 sta new_lo+1
 sta new_hi+1
 sta old_lo+1
 sta old_hi+1
 lda #>colors_a
 sta new_color+1
 lda #>mc_backgrounds
 sta restore_background+2
 lda #$ff
 sta restore_page+1
 sta publish_page+1
 jmp select_banks

.section .text.mc_compositor,"ax",@progbits
select_banks:
 lda mc_new_base
 cmp #147
 bne new_bank_b
 lda #<(mc_backgrounds+54)
 sta restore_background+1
 lda #<cells_a_lo
 sta new_lo
 lda #<cells_a_hi
 sta new_hi
 lda #<colors_a
 sta new_color
 lda #<cells_b_lo
 sta old_lo
 lda #<cells_b_hi
 sta old_hi
 rts
new_bank_b:
 lda #<mc_backgrounds
 sta restore_background+1
 lda #<cells_b_lo
 sta new_lo
 lda #<cells_b_hi
 sta new_hi
 lda #<colors_b
 sta new_color
 lda #<cells_a_lo
 sta old_lo
 lda #<cells_a_hi
 sta old_hi
 rts

mc_prepare:
 /* Synchronous entry retained for compositor tools and tests. The live front
    end uses begin/step, allowing logic and sound between complete actors. */
 jsr mc_prepare_begin
mc_prepare_all:
 jsr mc_prepare_step
 lda mc_busy
 bne mc_prepare_all
 rts
mc_prepare_begin:
 lda mc_pending
 ora mc_busy
 beq prepare_clean
 jsr mc_abort
prepare_clean:
 lda #0
 sta mc_status
 sta mc_new_count
 sta actor_index
 lda #1
 sta mc_busy
 rts
/* One actor per call. All actor coordinates were captured at begin; logical
   tile writes accumulate separately until this hidden picture is published.
   IRQ and game code do not touch the retained compositor state. */
mc_prepare_step:
 lda mc_busy
 bne prepare_actor
 rts
prepare_actor:
 ldx actor_index
 lda actors+2,x
 cmp #$ff
 bne actor_visible
 jmp next_actor
actor_visible:
 cmp #POSE_COUNT
 bcc actor_valid
 jmp prepare_failed
actor_valid:
 tay
 lda pose_has_accent,y
 sta reset_color_pending+1
 tya
 asl
 tay
 lda pose_addresses,y
 sta load_actor_row+1
 lda pose_addresses+1,y
 sta load_actor_row+2
 lda actors,x
 and #3
 sta actor_shift
 tay
 lda phase_offsets,y
 sta row_shift_index+1
 lda actor_shift
 cmp #3
 lda #2
 adc #0
 sta actor_columns
 lda actors,x
 cmp #$80
 ror
 cmp #$80
 ror
 sta actor_col
 lda actors+1,x
 sta actor_y
 lda actors+3,x
 and #7
 ora #8
 sta load_actor_accent+1
 lda actor_y
 cmp #208
 bcc actor_y_inside
 jmp next_actor
actor_y_inside:
 clc
 adc #14
 cmp #208
 bcc actor_bottom_ready
 lda #208
actor_bottom_ready:
 sta sprite_bottom
 lda actor_y
 cmp #16
 bcs actor_top_ready
 lda #16
actor_top_ready:
 cmp sprite_bottom
 bcc actor_rows_visible
 jmp next_actor
actor_rows_visible:
 sta pixel_y
  /* Clipping and the selected column painter stay constant for this actor. */
 lda #0
 sta valid_columns
 ldx #0
clip_actor_column:
 txa
 clc
 adc actor_col
 bmi clip_actor_next
 cmp #21
 bcs clip_actor_next
 lda valid_columns
 ora column_bits,x
 sta valid_columns
clip_actor_next:
 inx
 cpx actor_columns
 bcc clip_actor_column
 ldx valid_columns
 bne actor_columns_visible
 jmp next_actor
actor_columns_visible:
  /* Turn this pose's accent flag into its clipped mask once per actor. */
 lda reset_color_pending+1
 beq actor_colour_mask_ready
 txa
actor_colour_mask_ready:
 sta reset_color_pending+1
 txa
 asl
 tax
 lda resolve_addresses,x
 sta resolve_band_cells+1
 lda resolve_addresses+1,x
 sta resolve_band_cells+2
prepare_band:
 lda pixel_y
 and #$f8
 sta band_top
 lsr
 lsr
 lsr
 sta current_band
 lda band_top
 clc
 adc #8
 cmp sprite_bottom
 bcc band_bottom_ready
 lda sprite_bottom
band_bottom_ready:
 sta band_bottom
 sec
 sbc band_top
 sta row_limit+1
 jsr resolve_row
  /* Resolution reports allocation failure in carry as well as mc_status. */
 bcc band_ready
 jmp prepare_failed
band_ready:
 lda band_top
 sec
 sbc actor_y
 sta load_row_id+1
 lda pixel_y
 and #7
 tay
band_row:
 tya
 clc
load_row_id:
 adc #0
 tax
load_actor_row:
 lda pose_data,x
 clc
row_shift_index:
 adc #0
 tax
 lda valid_columns
 and #1
 beq mc_skip_left
 lda (left_ptr),y
 and row_mask0,x
 ora row_data0,x
 sta (left_ptr),y
mc_skip_left:
 lda valid_columns
 and #2
 beq mc_skip_middle
 lda (middle_ptr),y
 and row_mask1,x
 ora row_data1,x
 sta (middle_ptr),y
mc_skip_middle:
 /* Each pair of dictionary rows shares one byte of third-column/colour IDs.
    LSR retains the row parity in carry through TAX/LDA. */
 txa
 lsr
 tax
 lda shifted_tails,x
 bcc mc_tail_low
 lsr
 lsr
 lsr
 lsr
mc_tail_low:
 and #15
 tax
 lda valid_columns
 and #4
 beq row_colors
 lda (right_ptr),y
 and row_mask2,x
 ora row_data2,x
 sta (right_ptr),y
row_colors:
 lda color_pending
 beq row_advance
 and row_accent,x
 beq row_advance
  /* The source-row ID is no longer needed. X selects a colour-write path, */
  /* then the destination colour slots; Y remains the glyph scanline. */
 tax
 eor color_pending
 sta color_pending
load_actor_accent:
 lda #0
 jmp paint_colors
row_advance:
 iny
row_limit:
 cpy #0
 bcc band_row
band_done:
 lda band_bottom
 sta pixel_y
 cmp sprite_bottom
 bcs next_actor
 jmp prepare_band
next_actor:
 lda actor_index
 clc
 adc #4
 sta actor_index
 cmp #24
 bcs prepare_done
 rts
prepare_done:
 lda #1
 sta mc_pending
 lda #0
 sta mc_busy
mc_prepare_end:
 rts
prepare_failed:
 lda #1
 sta mc_status
 jsr clear_work_map
 lda #0
 sta mc_pending
 sta mc_busy
 rts

 /* The two colour banks are contiguous, so all seven combinations share fixed */
 /* absolute-X stores. Common two-column and single-column updates come first. */
paint_colors:
 cpx #3
 beq paint_left_middle
 cpx #2
 beq paint_middle
 cpx #1
 beq paint_left
 cpx #7
 beq paint_all
 cpx #5
 beq paint_left_right
 cpx #6
 beq paint_middle_right
paint_right:
 ldx right_index
 sta colors_a,x
 jmp row_advance
paint_all:
 ldx left_index
 sta colors_a,x
paint_middle_right:
 ldx middle_index
 sta colors_a,x
 jmp paint_right
paint_left_right:
 ldx left_index
 sta colors_a,x
 jmp paint_right
paint_left_middle:
 ldx left_index
 sta colors_a,x
paint_middle:
 ldx middle_index
 sta colors_a,x
 jmp row_advance
paint_left:
 ldx left_index
 sta colors_a,x
 jmp row_advance

 /* Resolve the clipped columns once per band. Advance the cell index directly; */
 /* all actors still share one map so overlaps use a single working character. */
resolve_row:
reset_color_pending:
 lda #0
 sta color_pending
 ldx current_band
 lda row_cell_lo,x
 clc
 adc actor_col
 sta cell_low
 lda row_cell_hi,x
 adc #0
 ldx actor_col
 bpl resolve_positive_column
 sec
 sbc #1
resolve_positive_column:
 sta cell_high
resolve_band_cells:
  /* Tail dispatch: each column routine returns to the preparation caller. */
 jmp resolve_cells_0

.macro NEXT_CELL

 inc cell_low
 bne no_carry\@
 inc cell_high
no_carry\@:
.endm
.macro CELL_MAP_POINTER
 lda cell_high
 clc
 adc #>cell_work
 sta map_ptr+1
.endm

 /* Resolve directly into each drawing pointer. Clipped column combinations */
 /* share these same three blocks, with separate entries for their first cell. */
 /* Each expansion owns its patched background read; the publication operand */
 /* remains the single bank selector. */
.macro RESOLVE_CELL_DIRECT PTR,INDEX
 jsr mc_get_cell
 bcc usable\@
 rts
usable\@:
 txa
 sec
 sbc #147
 sta \INDEX
 lda shared_ptr
 sta \PTR
 lda shared_ptr+1
 sta \PTR+1
.endm

/* Share the allocation/copy code. The compact live build trades a small
   per-cell call cost for room alongside the complete arcade program. */
mc_get_cell:
 CELL_MAP_POINTER
 ldy #0
 lda (map_ptr),y
 cmp #255
 beq mc_allocate_cell
 lda #0
 sta mc_copy_needed
 lda (map_ptr),y
 jmp mc_cell_pointer
mc_allocate_cell:
 ldy mc_new_count
 cpy #54
 bcc mc_cell_fits
 lda #1
 sta mc_status
 sec
 rts
mc_cell_fits:
 lda cell_low
 sta (new_lo),y
 lda cell_high
 sta (new_hi),y
 lda #14
 sta (new_color),y
 tya
 adc mc_new_base
 ldy #0
 sta (map_ptr),y
 inc mc_new_count
 pha
 lda #1
 sta mc_copy_needed
 pla
mc_cell_pointer:
 sta mc_current_code
 tax
 asl
 asl
 asl
 sta shared_ptr
 txa
 lsr
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta shared_ptr+1
 lda mc_copy_needed
 beq mc_cell_ready
 lda cell_high
 clc
 adc #$18
 sta mc_read_background+2
 ldx cell_low
mc_read_background:
 lda $1800,x
 cmp #147
 bcc mc_have_background
 tax
 lda mc_backgrounds-147,x
mc_have_background:
 ldx mc_current_code
 sta mc_backgrounds-147,x
 tax
 asl
 asl
 asl
 sta background_ptr
 txa
 lsr
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta background_ptr+1
 ldy #7
mc_copy_background:
 lda (background_ptr),y
 sta (shared_ptr),y
 dey
 bpl mc_copy_background
mc_cell_ready:
 ldx mc_current_code
resolve_cells_0:
 clc
 rts
resolve_cells_1:
resolve_cells_3:
resolve_cells_5:
resolve_cells_7:
 RESOLVE_CELL_DIRECT left_ptr,left_index
 lda valid_columns
 and #2
 bne resolve_cells_2
 lda valid_columns
 and #4
 bne resolve_left_and_right
 clc
 rts
resolve_left_and_right:
 jmp resolve_cells_4
resolve_cells_2:
resolve_cells_6:
 NEXT_CELL
 RESOLVE_CELL_DIRECT middle_ptr,middle_index
 lda valid_columns
 and #4
 bne resolve_third_column
 clc
 rts
resolve_cells_4:
 NEXT_CELL
resolve_third_column:
 NEXT_CELL
 RESOLVE_CELL_DIRECT right_ptr,right_index
 clc
 rts

 /* Abort/failure cleanup retains the shared map helper to limit code growth. */
make_map_ptr:
 CELL_MAP_POINTER
 rts

mc_commit:
 lda mc_pending
 bne commit_ready
 rts
commit_ready:
 jsr mc_publish
 lda mc_new_count
 sta mc_old_count
 lda #0
 sta mc_pending
 lda mc_new_base
 eor #$5a
 sta mc_new_base
 jmp select_banks

 /* Keep these lookup bytes off the executed path while placing the publisher's */
 /* common cached-page branch within a page, without adding padding. */
.section .rodata.mc_columns,"a",@progbits
column_bits: .byte 1,2,4
.section .text.mc_compositor,"ax",@progbits
resolve_addresses: .word resolve_cells_0,resolve_cells_1,resolve_cells_2,resolve_cells_3,resolve_cells_4,resolve_cells_5,resolve_cells_6,resolve_cells_7
mc_publish:
  /* Keep Y as the old-list cursor and X as the cell's low byte. Consecutive */
  /* old cells usually share a page; cache all four absolute-X operands. */
 ldy #0
restore_vacated:
 cpy mc_old_count
 bcs publish_start
 lda (old_lo),y
 tax
 lda (old_hi),y
restore_page:
 cmp #$ff
 beq restore_page_ready
 sta restore_page+1
 clc
 adc #>cell_work
 sta restore_map+2
 lda (old_hi),y
 clc
 adc #$18
 sta restore_code+2
 clc
 adc #$7c
 sta restore_color+2
restore_page_ready:
restore_map:
 lda cell_work,x
 cmp #$ff
 bne restore_skip
restore_background:
 lda mc_backgrounds,y
restore_code:
 sta $1800,x
 lda #14
restore_color:
 sta $9400,x
restore_skip:
 iny
 jmp restore_vacated
publish_start:
  /* Publication never changes Y except to advance this new-list cursor. */
 ldy #0
publish_cell:
 cpy mc_new_count
 bcs mc_commit_end
 lda (new_lo),y
 tax
 lda (new_hi),y
  /* Consecutive cells usually share a matrix/colour/map page. The patched */
  /* stores remain valid until this high byte changes, including across frames. */
publish_page:
 cmp #$ff
 beq publish_page_ready
 sta publish_page+1
 clc
 adc #$18
 sta publish_code+2
 clc
 adc #$7c
 sta publish_color+2
 lda (new_hi),y
 clc
 adc #>cell_work
 sta publish_clear+2
publish_page_ready:
 lda (new_color),y
publish_color:
 sta $9400,x
 tya
 clc
publish_bank:
 adc #147
publish_code:
 sta $1800,x
 lda #$ff
publish_clear:
 sta cell_work,x
 iny
 jmp publish_cell
mc_commit_end:
 rts

.section .text.mc_abort,"ax",@progbits
mc_abort:
 jsr clear_work_map
 lda #0
 sta mc_pending
 sta mc_busy
 rts
.section .text.mc_compositor,"ax",@progbits
clear_work_map:
  /* Abort/failure cleanup uses the same X-preserving map helper as restoration. */
 ldx #0
clear_map_cell:
 cpx mc_new_count
 bcs clear_map_done
 txa
 tay
 lda (new_lo),y
 sta cell_low
 lda (new_hi),y
 sta cell_high
 jsr make_map_ptr
 ldy #0
 lda #$ff
 sta (map_ptr),y
 inx
 jmp clear_map_cell
clear_map_done:
 rts

row_cell_lo:
.set N,0
.rept 27
 .byte (N*21)&255
.set N,N+1
.endr
row_cell_hi:
.set N,0
.rept 27
 .byte (N*21)>>8
.set N,N+1
.endr

.section .rodata.mc_art,"a",@progbits
pose_data: .incbin "build/multicolour-game/pose-rows.bin"
pose_addresses:
.set N,0
.rept POSE_COUNT
 .word pose_data+N*14
.set N,N+1
.endr
pose_has_accent: .incbin "build/multicolour-game/pose-accents.bin"
/* The 192 phased row IDs still fit in X. Only the tiny third-column/colour
   record needs an extra lookup; the two ordinary columns read packed rows
   directly. Runtime table images are copied before boot RAM is released. */
.section .mc_shift_tables,"a",@progbits
row_data0: .incbin "build/multicolour-game/shifted-data.bin",0,SHIFTED_ROWS
row_data1: .incbin "build/multicolour-game/shifted-data.bin",SHIFTED_ROWS,SHIFTED_ROWS
shifted_tails: .incbin "build/multicolour-game/shifted-tails.bin"
.section .rodata.mc_art,"a",@progbits
row_mask0: .incbin "build/multicolour-game/shifted-masks.bin",0,SHIFTED_ROWS
.section .text.mc_mask_table,"ax",@progbits
row_mask1: .incbin "build/multicolour-game/shifted-masks.bin",SHIFTED_ROWS,SHIFTED_ROWS
.section .mc_low_tables,"a",@progbits
row_data2: .incbin "build/multicolour-game/tail-records.bin",0,TAIL_RECORDS
row_mask2: .incbin "build/multicolour-game/tail-records.bin",TAIL_RECORDS,TAIL_RECORDS
row_accent: .incbin "build/multicolour-game/tail-records.bin",TAIL_RECORDS*2,TAIL_RECORDS
phase_offsets: .byte 0,ROW_RECORDS,ROW_RECORDS*2,ROW_RECORDS*3

.section .text.mc_store,"ax",@progbits
.zeropage __rc2,__rc3,full_dirty,dirty_count
.global video_store
/* LLVM-MOS: A is the byte, __rc2/__rc3 the pointer. This saves enough resident
   code for the continuation and keeps ordinary dirty writes inexpensive. */
video_store:
 ldy #0
 cmp (__rc2),y
 beq store_done
 sta (__rc2),y
 lda __rc3
 cmp #4
 bcc store_done
 cmp #12
 bcs store_done
 ldx full_dirty
 cpx #2
 beq store_done
 and #3
 sta v_save+1
 lda __rc2
 sta v_save
 and #7
 tax
 lda bit_masks,x
 sta v_lo
 lda v_save+1
 asl
 asl
 asl
 asl
 asl
 sta v_hi
 lda v_save
 lsr
 lsr
 lsr
 ora v_hi
 tax
 lda dirty_bits,x
 and v_lo
 bne store_done
 lda dirty_bits,x
 ora v_lo
 sta dirty_bits,x
 lda #1
 sta dirty_count
store_done:
 rts

.global bit_masks
bit_masks: .byte 1,2,4,8,16,32,64,128
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
 lda #14
 ldx $0840
 cpx #31
 bne mc_flash_done
 lda #9
mc_flash_done:
 sta $900f
 rts

/* LLVM-MOS passes a 16-bit amount in A/X. Decimal ADC also preserves the
   half-carry correction that the original Z80 DAA requires. */
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

.section .screen_work,"aw",@nobits
mc_copy_needed: .zero 1
mc_current_code: .zero 1

/* Read the score digits already formatted by the arcade. */
.section .text.mc_hud,"ax",@progbits
.global hud_glyph
hud_glyph:
 cmp #21
 bcs hud_score
 tax
 cpx #16
 bcc hud_label
 lda $0e70
 beq hud_score_blank
hud_label:
 lda hud_labels,x
 rts
hud_score:
 cmp #42
 bcs hud_bottom
 sec
 sbc #21
 tay
 eor #255
 tax
 cpy #6
 bcc hud_score_p1
 cpy #7
 beq hud_score_blank
 cpy #13
 bcc hud_score_high
 cpy #14
 beq hud_score_blank
 cpy #20
 bcs hud_score_blank
 lda $0e70
 beq hud_score_blank
 lda $06f8,x
 jmp hud_digit
hud_score_high:
 lda $06fa,x
 jmp hud_digit
hud_score_p1:
 lda $06fd,x
hud_digit:
 cmp #10
 bcs hud_score_blank
 clc
 adc #1
 rts
hud_score_blank:
 lda #0
 rts
hud_bottom:
 sec
 sbc #42
 tax
 cmp #1
 bcc hud_blank
 cmp #6
 bcs hud_status
 lda $0e15
 stx color_pending
 cmp color_pending
 bcc hud_blank
 lda #$f0
 rts
hud_status:
 cmp #10
 bne hud_fruit
 lda $0e13
 clc
 adc #1
 bcc hud_level_modulo
 lda #6
hud_level_modulo:
 cmp #10
 bcc hud_level_digit
 sec
 sbc #10
 bcs hud_level_modulo
hud_level_digit:
 clc
 adc #1
 rts
hud_fruit:
 cmp #19
 bne hud_blank
 lda $0e00
 cmp #3
 bne hud_blank
 lda #$51
 rts
hud_blank:
 lda #0
 rts
.section .rodata.mc_hud,"a",@progbits
hud_labels:
.byte 0,0,2,11,12,0,0,0,13,14,15,13,0,0,0,0,3,11,12,0,0

.section .text.mc_mark,"ax",@progbits
.global mark_tile
mark_tile:
 sta map_ptr
 stx map_ptr+1
 and #31
 sta left_ptr+1
 lda map_ptr
 lsr
 lsr
 lsr
 lsr
 lsr
 sta left_ptr
 txa
 asl
 asl
 asl
 ora left_ptr
 cmp #2
 bcc mc_mark_side
 cmp #30
 bcs mc_mark_side
 sta left_ptr
 lda #29
 sec
 sbc left_ptr
 sta left_ptr
 lda left_ptr+1
 clc
 adc #2
 jmp mc_mark_xy
mc_mark_side:
 tax
 lda left_ptr+1
 cmp #2
 bcs mc_mark_side_lower
 rts
mc_mark_side_lower:
 cmp #30
 bcc mc_mark_side_inside
 rts
mc_mark_side_inside:
 lda #29
 sec
 sbc left_ptr+1
 sta left_ptr
 txa
 cmp #30
 bcc mc_mark_bottom
 sec
 sbc #30
 jmp mc_mark_xy
mc_mark_bottom:
 clc
 adc #34
mc_mark_xy:
 asl
 sta shared_ptr
 asl
 clc
 adc shared_ptr
 sta shared_ptr
 lsr
 lsr
 lsr
 sta right_ptr
 lda shared_ptr
 clc
 adc #5
 lsr
 lsr
 lsr
 sta right_ptr+1
 lda left_ptr
 asl
 clc
 adc left_ptr
 sta shared_ptr
 lsr
 lsr
 sta middle_ptr
 lda shared_ptr
 clc
 adc #2
 lsr
 lsr
 sta middle_ptr+1
mc_mark_band:
 ldx right_ptr
 cpx #2
 bcc mc_mark_next_band
 cpx #26
 bcs mc_mark_done
 lda row_cell_lo,x
 clc
 adc middle_ptr
 sta background_ptr
 lda row_cell_hi,x
 adc #0
 sta background_ptr+1
 ldy middle_ptr
mc_mark_column:
 lda background_ptr
 and #7
 tax
 lda bit_masks,x
 sta shared_ptr
 lda background_ptr+1
 asl
 asl
 asl
 asl
 asl
 sta shared_ptr+1
 lda background_ptr
 lsr
 lsr
 lsr
 ora shared_ptr+1
 tax
 lda physical_dirty,x
 ora shared_ptr
 sta physical_dirty,x
 cpy middle_ptr+1
 beq mc_mark_next_band
 iny
 inc background_ptr
 bne mc_mark_column
 inc background_ptr+1
 jmp mc_mark_column
mc_mark_next_band:
 inc right_ptr
 lda right_ptr
 cmp right_ptr+1
 bcc mc_mark_band
 beq mc_mark_band
mc_mark_done:
 rts

.section .work,"aw",@nobits
.global previous_x,previous_y,facing
previous_x: .zero 1
previous_y: .zero 1
facing: .zero 1
.section .text.mc_live,"ax",@progbits
.global mc_live_actors
mc_live_actors:
 lda #12
 sta actor_index
 lda #0
 sta actor_y
mc_live_actor:
 ldy actor_y
 lda #255
 sta actors+2,y
 ldx actor_index
 lda $0c21,x
 and #31
 bne mc_live_visible
 jmp mc_live_next
mc_live_visible:
 sta middle_ptr
 lda $0c20,x
 sta right_ptr
 lsr
 lsr
 sta middle_ptr+1
 lda $0c30,x
 sta background_ptr
 and #7
 cpx #5
 bcs mc_live_fraction
 ora #8
mc_live_fraction:
 tay
 lda mc_x_fraction,y
 sta left_ptr
 lda background_ptr
 lsr
 lsr
 lsr
 sta shared_ptr
 asl
 clc
 adc shared_ptr
 sta shared_ptr
 lda #89
 sec
 sbc shared_ptr
 clc
 adc left_ptr
 sta left_ptr
 bmi mc_live_x_inside
 cmp #84
 bcc mc_live_x_inside
 jmp mc_live_next
mc_live_x_inside:
 lda $0c31,x
 sta background_ptr+1
 lsr
 lsr
 sta left_ptr+1
 lda #203
 sec
 sbc background_ptr+1
 clc
 adc left_ptr+1
 sta left_ptr+1
 lda middle_ptr+1
 cmp #32
 bcc mc_live_not_ghost
 cmp #40
 bcs mc_live_not_ghost
 sec
 sbc #32
 sta right_ptr+1
 and #2
 beq mc_live_horizontal_ghost
 lda right_ptr
 and #1
 jmp mc_live_ghost_flip
mc_live_horizontal_ghost:
 lda right_ptr
 and #2
mc_live_ghost_flip:
 beq mc_live_ghost_ready
 lda right_ptr+1
 eor #4
 sta right_ptr+1
mc_live_ghost_ready:
 lda middle_ptr
 cmp #25
 bne mc_live_ghost_pose
 lda right_ptr+1
 lsr
 clc
 adc #10
 jmp mc_live_pose
mc_live_ghost_pose:
 lda right_ptr+1
 jmp mc_live_pose
mc_live_not_ghost:
 cmp #30
 bcc mc_live_blue_frightened
 cmp #32
 bcs mc_live_not_frightened
 and #1
 clc
 adc #27
 jmp mc_live_pose
mc_live_blue_frightened:
 cmp #28
 beq mc_live_frightened
 cmp #29
 bne mc_live_not_frightened
mc_live_frightened:
 and #1
 ora #8
 jmp mc_live_pose
mc_live_not_frightened:
 lda middle_ptr
 cmp #9
 beq mc_live_pacman
 lda #26
 jmp mc_live_pose
mc_live_pacman:
 lda middle_ptr+1
 cmp #48
 beq mc_live_closed
 cmp #45
 beq mc_live_vertical_pacman
 cmp #47
 beq mc_live_vertical_pacman
 lda right_ptr
 and #2
 sta facing
 jmp mc_live_pacman_ready
mc_live_vertical_pacman:
 lda right_ptr
 and #1
 asl
 ora #1
 sta facing
 jmp mc_live_pacman_ready
mc_live_closed:
 lda previous_x
 sec
 sbc background_ptr
 sta shared_ptr
 lda previous_y
 sec
 sbc background_ptr+1
 sta shared_ptr+1
 beq mc_live_horizontal_motion
 lda shared_ptr
 bne mc_live_pacman_ready
 lda shared_ptr+1
 clc
 adc #15
 cmp #31
 bcs mc_live_pacman_ready
 lda #1
 bit shared_ptr+1
 bpl mc_live_store_facing
 lda #3
 bne mc_live_store_facing
mc_live_horizontal_motion:
 lda shared_ptr
 beq mc_live_pacman_ready
 clc
 adc #15
 cmp #31
 bcs mc_live_pacman_ready
 lda #0
 bit shared_ptr
 bpl mc_live_store_facing
 lda #2
mc_live_store_facing:
 sta facing
mc_live_pacman_ready:
 lda background_ptr
 sta previous_x
 lda background_ptr+1
 sta previous_y
 lda facing
 asl
 clc
 adc facing
 adc #14
 sta right_ptr+1
 lda middle_ptr+1
 cmp #48
 beq mc_live_pacman_pose
 inc right_ptr+1
 cmp #44
 beq mc_live_open_mouth
 cmp #45
 bne mc_live_pacman_pose
mc_live_open_mouth:
 inc right_ptr+1
mc_live_pacman_pose:
 lda right_ptr+1
mc_live_pose:
 ldy actor_y
 sta actors+2,y
 lda left_ptr
 sta actors,y
 lda left_ptr+1
 sta actors+1,y
 ldx middle_ptr
 lda mc_actor_accents,x
 sta actors+3,y
mc_live_next:
 lda actor_y
 clc
 adc #4
 sta actor_y
 dec actor_index
 dec actor_index
 beq mc_live_done
 jmp mc_live_actor
mc_live_done:
 rts
.section .rodata.mc_live,"a",@progbits
mc_x_fraction:
.byte 0,0,255,255,255,254,254,254,0,255,255,255,254,254,254,253
mc_actor_accents:
.byte 2,2,2,4,2,3,2,7,2,7,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2

.section .text.mc_cache,"ax",@progbits
.global mc_replace_cell
mc_replace_cell:
 sta left_ptr
 sta middle_ptr
 txa
 clc
 adc #$18
 sta left_ptr+1
 clc
 adc #$7c
 sta middle_ptr+1
 lda #0
 ldy #7
mc_cache_hash:
 asl
 adc #0
 eor mc_pattern,y
 dey
 bpl mc_cache_hash
 sta shared_ptr
 ldy #0
 lda (left_ptr),y
 cmp #147
 bcc mc_cache_old
 tax
 lda mc_backgrounds-147,x
mc_cache_old:
 sta right_ptr
 tax
 lda mc_hashes,x
 cmp shared_ptr
 bne mc_cache_change
 jsr mc_cache_matches
 bcs mc_cache_change
 jmp mc_cache_color
mc_cache_change:
 lda mc_refs_lo,x
 bne mc_cache_decrement
 cpx mc_overflow0
 bne mc_cache_release_second
 lda #255
 sta mc_overflow0
 jmp mc_cache_decrement
mc_cache_release_second:
 lda #255
 sta mc_overflow1
mc_cache_decrement:
 dec mc_refs_lo,x
 lda #255
 sta color_pending
 ldx #0
mc_cache_search:
 lda mc_refs_lo,x
 bne mc_cache_test
 cpx mc_overflow0
 beq mc_cache_test
 cpx mc_overflow1
 beq mc_cache_test
 lda color_pending
 cmp #255
 bne mc_cache_next
 stx color_pending
 jmp mc_cache_next
mc_cache_test:
 lda mc_hashes,x
 cmp shared_ptr
 bne mc_cache_next
 jsr mc_cache_matches
 bcc mc_cache_found
mc_cache_next:
 inx
 cpx #147
 bcc mc_cache_search
 ldx color_pending
 cpx #255
 bne mc_cache_load
 ldx right_ptr
 jsr mc_cache_increment
 inc mc_cache_errors
 rts
mc_cache_load:
 jsr mc_cache_pointer
 ldy #7
mc_cache_copy:
 lda mc_pattern,y
 sta (map_ptr),y
 dey
 bpl mc_cache_copy
 lda shared_ptr
 sta mc_hashes,x
mc_cache_found:
 stx right_ptr+1
 jsr mc_cache_increment
 ldy #0
 lda (left_ptr),y
 cmp #147
 bcc mc_cache_publish
 tax
 lda right_ptr+1
 sta mc_backgrounds-147,x
 rts
mc_cache_publish:
 lda right_ptr+1
 sta (left_ptr),y
mc_cache_color:
 ldy #0
 lda (left_ptr),y
 cmp #147
 bcs mc_cache_done
 lda v_flags
 sta (middle_ptr),y
mc_cache_done:
 rts
.section .text.mc_cache_increment,"ax",@progbits
mc_cache_increment:
 inc mc_refs_lo,x
 bne mc_cache_incremented
 lda mc_overflow0
 cmp #255
 bne mc_cache_increment_second
 stx mc_overflow0
 rts
mc_cache_increment_second:
 stx mc_overflow1
mc_cache_incremented:
 rts
.section .text.mc_cache,"ax",@progbits
mc_cache_matches:
 jsr mc_cache_pointer
 ldy #7
mc_cache_compare:
 lda (map_ptr),y
 cmp mc_pattern,y
 bne mc_cache_different
 dey
 bpl mc_cache_compare
 clc
 rts
mc_cache_different:
 sec
 rts
mc_cache_pointer:
 txa
 asl
 asl
 asl
 sta map_ptr
 txa
 lsr
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta map_ptr+1
 rts

/* Construct one 4x8-pixel background character from the live arcade tiles.
   Each scanline spans exactly two 3-pixel tiles. Resolve their patterns once
   per logical tile row, then combine complete rows instead of looking up all
   four pixels separately. Actor scratch is free before mc_live_actors.
   In: A/X = cell lo/hi. Out: cache entry updated. Clobbers: A/X/Y and the
   compositor pointers/counters; leaves the actor packet and live game intact. */
.section .text.mc_background_cell,"ax",@progbits
.global background_cell
background_cell:
 sta left_index
 stx middle_index
 sta background_ptr
 stx background_ptr+1
 ldy #0
mc_cell_divide_row:
 lda background_ptr+1
 bne mc_cell_subtract_row
 lda background_ptr
 cmp #21
 bcc mc_cell_column
mc_cell_subtract_row:
 lda background_ptr
 sec
 sbc #21
 sta background_ptr
 lda background_ptr+1
 sbc #0
 sta background_ptr+1
 iny
 bne mc_cell_divide_row
mc_cell_column:
 asl
 asl
 ldx #29
mc_cell_divide_x:
 cmp #3
 bcc mc_cell_x_ready
 sec
 sbc #3
 dex
 bcs mc_cell_divide_x
mc_cell_x_ready:
 sta actor_shift
 stx actor_col
 tya
 asl
 asl
 asl
 ldx #0
mc_cell_divide_y:
 cmp #6
 bcc mc_cell_y_ready
 sec
 sbc #6
 inx
 bcs mc_cell_divide_y
mc_cell_y_ready:
 sta actor_columns
 stx actor_index
 lda #0
 sta current_band
mc_cell_tile_pair:
 lda actor_index
 cmp #34
 bne mc_cell_main_source
 lda actor_col
 sta background_ptr
 lda #4
 bne mc_cell_source_high
mc_cell_main_source:
 lda actor_col
 asl
 asl
 asl
 asl
 asl
 sta background_ptr
 lda actor_col
 lsr
 lsr
 lsr
 clc
 adc #4
 sta background_ptr+1
 lda actor_index
 sec
 sbc #2
 clc
 adc background_ptr
 sta background_ptr
 lda background_ptr+1
 adc #0
mc_cell_source_high:
 sta background_ptr+1
 clc
 adc #4
 sta middle_ptr+1
 lda background_ptr
 sta middle_ptr
 jsr mc_cell_tile_pattern
 lda shared_ptr
 sta left_ptr
 lda shared_ptr+1
 sta left_ptr+1
 lda actor_index
 cmp #34
 bne mc_cell_right_main
 lda #1
 bne mc_cell_right_offset
mc_cell_right_main:
 lda #32
mc_cell_right_offset:
 sta band_top
 lda background_ptr
 sec
 sbc band_top
 sta background_ptr
 sta middle_ptr
 lda background_ptr+1
 sbc #0
 sta background_ptr+1
 clc
 adc #4
 sta middle_ptr+1
 jsr mc_cell_tile_pattern
 lda shared_ptr
 sta right_ptr
 lda shared_ptr+1
 sta right_ptr+1
mc_cell_row:
 ldy actor_columns
 lda (left_ptr),y
 ldx actor_shift
 beq mc_cell_phase0
 dex
 beq mc_cell_phase1
 /* Phase 2: one pixel from the left tile, three from the right. */
 asl
 asl
 asl
 asl
 asl
 asl
 sta band_top
 lda (right_ptr),y
 jmp mc_cell_join
mc_cell_phase1:
 asl
 asl
 asl
 asl
 sta band_top
 lda (right_ptr),y
 lsr
 lsr
 jmp mc_cell_join
mc_cell_phase0:
 asl
 asl
 sta band_top
 lda (right_ptr),y
 lsr
 lsr
 lsr
 lsr
mc_cell_join:
 ora band_top
 ldy current_band
 sta mc_pattern,y
 inc current_band
 lda current_band
 cmp #8
 beq mc_cell_pattern_ready
 inc actor_columns
 lda actor_columns
 cmp #6
 bcc mc_cell_row
 lda #0
 sta actor_columns
 inc actor_index
 jmp mc_cell_tile_pair

/* Resolve a live tile into its six packed rows. Colour zero makes it blank.
   In: background_ptr = code, middle_ptr = palette. Out: shared_ptr = rows.
   Clobbers A/X/Y; preserves the left/right pattern pointers. */
mc_cell_tile_pattern:
 ldy #0
 lda (middle_ptr),y
 and #31
 beq mc_cell_blank_tile
 lda (background_ptr),y
 jmp mc_cell_tile_id
mc_cell_blank_tile:
 lda #64
mc_cell_tile_id:
 tax
 lda mc_tile_ids,x
 sta shared_ptr
 asl
 sta map_ptr
 lda #0
 rol
 sta map_ptr+1
 lda map_ptr
 clc
 adc shared_ptr
 sta map_ptr
 lda map_ptr+1
 adc #0
 sta map_ptr+1
 asl map_ptr
 rol map_ptr+1
 lda map_ptr
 clc
 adc #<mc_tiles
 sta shared_ptr
 lda map_ptr+1
 adc #>mc_tiles
 sta shared_ptr+1
 rts
mc_cell_pattern_ready:
 lda #14
 sta v_flags
 lda left_index
 ldx middle_index
 jmp mc_replace_cell

.section .text.mc_background,"ax",@progbits
.global video_background
video_background:
 lda mc_busy
 beq mc_background_ready
 jsr mc_abort
 lda #0
 sta mc_stage
mc_background_ready:
 lda full_dirty
 cmp #2
 bne mc_background_collect
 jsr mc_reset_background
 lda #14
 sta $900f
 lda #255
 ldx #70
mc_background_reset_cells:
 sta physical_dirty,x
 dex
 bpl mc_background_reset_cells
 lda #0
 sta dirty_count
 sta rebuild_again
 sta rebuild_cursor+1
 ldx #127
mc_background_reset_tiles:
 sta dirty_bits,x
 dex
 bpl mc_background_reset_tiles
 lda #42
 sta rebuild_cursor
 lda #1
 sta full_dirty
 lda #2
 sta rebuild_phase
mc_background_collect:
 jsr mc_collect_writes
 lda rebuild_phase
 bne mc_background_scan
 rts
mc_background_scan:
 ldx rebuild_cursor+1
 cpx #2
 bcc mc_background_in_range
 lda rebuild_cursor
 cmp #34
 bcc mc_background_in_range
 lda rebuild_again
 bne mc_background_followup
 lda #0
 sta rebuild_phase
 sta full_dirty
 rts
mc_background_followup:
 lda #0
 sta rebuild_again
 sta rebuild_cursor+1
 lda #42
 sta rebuild_cursor
 /* Finish writes queued behind a full pass before adding HUD/actors. Keeping
    the full phase here also avoids pinning glyphs from two transitional scenes
    alongside the HUD. Ordinary passes retain phase 1. */
 jmp mc_background_scan
mc_background_in_range:
 lda rebuild_cursor
 lsr
 lsr
 lsr
 sta shared_ptr
 txa
 asl
 asl
 asl
 asl
 asl
 ora shared_ptr
 tax
 lda physical_dirty,x
 bne mc_background_nonempty
 lda rebuild_cursor
 ora #7
 clc
 adc #1
 sta rebuild_cursor
 bcc mc_background_scan
 inc rebuild_cursor+1
 jmp mc_background_scan
mc_background_nonempty:
 sta shared_ptr+1
 lda rebuild_cursor
 and #7
 tay
 lda bit_masks,y
 and shared_ptr+1
 beq mc_background_advance
 lda bit_masks,y
 eor #255
 and shared_ptr+1
 sta physical_dirty,x
 lda rebuild_cursor
 sta left_index
 lda rebuild_cursor+1
 sta middle_index
 inc rebuild_cursor
 bne mc_background_call
 inc rebuild_cursor+1
mc_background_call:
 lda left_index
 ldx middle_index
 jmp background_cell
mc_background_advance:
 inc rebuild_cursor
 bne mc_background_rescan
 inc rebuild_cursor+1
mc_background_rescan:
 jmp mc_background_scan

mc_collect_writes:
 lda dirty_count
 bne mc_collect_start
 rts
mc_collect_start:
 lda #0
 sta dirty_count
 ldx #127
mc_collect_group:
 lda dirty_bits,x
 beq mc_collect_next_group
 sta actor_col
 stx actor_index
 lda #0
 sta dirty_bits,x
 sta actor_y
mc_collect_bit:
 lsr actor_col
 bcc mc_collect_next_bit
 lda actor_index
 lsr
 lsr
 lsr
 lsr
 lsr
 tax
 lda actor_index
 asl
 asl
 asl
 ora actor_y
 jsr mark_tile
mc_collect_next_bit:
 inc actor_y
 lda actor_col
 bne mc_collect_bit
 ldx actor_index
mc_collect_next_group:
 dex
 bpl mc_collect_group
 lda rebuild_phase
 beq mc_collect_new_pass
 lda #1
 sta rebuild_again
 rts
mc_collect_new_pass:
 lda #1
 sta full_dirty
 sta rebuild_phase
mc_collect_cursor:
 lda #42
 sta rebuild_cursor
 lda #0
 sta rebuild_cursor+1
 rts
