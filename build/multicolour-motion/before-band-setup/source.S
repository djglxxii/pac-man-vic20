; Isolated VIC-I character compositor. No game logic or arcade clock changes.
; Background codes 0..146; two 54-character work banks 147..200 / 201..254.
; mc_prepare writes only hidden work glyphs. mc_commit publishes screen codes.
.setcpu "6502"
.include "motion.inc"

.segment "LOADADDR"
.word $1201
.segment "BASIC"
.word basic_end
.word 10
.byte $9e,"4621",0
basic_end: .word 0
jmp entry

.segment "ZEROPAGE"
map_ptr: .res 2
; The map is page-aligned, so its pointer and the cell index share a low byte.
; Keep the raw index high byte separate from the pointer's absolute high byte.
cell_low = map_ptr
src_ptr: .res 2
dst_ptr: .res 2
old_lo: .res 2
old_hi: .res 2
new_lo: .res 2
new_hi: .res 2
new_color: .res 2
screen_ptr: .res 2
color_ptr: .res 2
left_ptr: .res 2
middle_ptr: .res 2
right_ptr: .res 2
cell_high: .res 1
color_pending: .res 1

.segment "STATE"
cells_a_lo: .res 54
cells_a_hi: .res 54
cells_b_lo: .res 54
cells_b_hi: .res 54
; Colour indices are working character code minus 147, covering both banks.
colors_a: .res 54
colors_b: .res 54
.assert colors_b-colors_a = 54, error, "Work colour banks must remain adjacent"
.export actors,mc_status,mc_pending,mc_new_count,mc_old_count,mc_new_base
actors: .res 24                 ; Six records, painter priority: x,y,pose,accent.
mc_status: .res 1
mc_pending: .res 1
mc_new_count: .res 1
mc_old_count: .res 1
actor_index: .res 1
actor_col: .res 1
actor_y: .res 1
actor_shift: .res 1
actor_columns: .res 1
actor_has_accent: .res 1
pixel_y: .res 1
current_band: .res 1
sprite_bottom: .res 1
band_top: .res 1
band_bottom: .res 1
valid_columns: .res 1
left_index: .res 1              ; Colour slot = working character code - 147.
middle_index: .res 1
right_index: .res 1
current_code: .res 1
list_index: .res 1
column_index: .res 1
replay_pointer: .res 2
replay_remaining: .res 2
replay_deadline: .res 1
replay_tick: .res 1
.export demo_frame
demo_frame: .res 2

.segment "BSS"
.export cell_work
cell_work: .res 567
.assert <cell_work = 0, lderror, "Shared cell/map low byte requires page alignment"

.segment "CODE"
.export entry,loader_start,mc_init,mc_prepare,mc_prepare_end,mc_commit,mc_commit_end,mc_publish,mc_abort,demo_ready,demo_presented
.export resolve_row,get_work_cell,clear_work_map
.export actor_col,current_band
; The bank selector is also the allocation instruction's immediate operand.
mc_new_base = allocate_code+1
loader_start = entry
entry:
 sei
 cld
 ldx #$ff
 txs
 lda #$7f
 sta $911e
 sta $912e
 lda #0
 sta $9002
 sta $900a
 sta $900b
 sta $900c
 sta $900d
 lda #$10
 sta $900e
 lda #$0e
 sta $900f
 jsr mc_init
 lda #12
 sta $9000
 lda #18
 sta $9001
 lda #$ec
 sta $9005
 lda #54
 sta $9003
 lda #21
 sta $9002
 lda #$40
 sta $912b
 lda #$e9
 sta $9124
 lda #$41
 sta $9125
 lda #<replay_irq
 sta $0314
 lda #>replay_irq
 sta $0315
 lda #0
 sta replay_tick
 sta replay_deadline
 lda #$c0
 sta $912e
 jsr reset_replay
 cli
demo_ready:
 lda replay_tick
 sec
 sbc replay_deadline
 bmi demo_ready
 lda replay_pointer
 sta src_ptr
 lda replay_pointer+1
 sta src_ptr+1
 ldy #23
load_actor_packet:
 lda (src_ptr),y
 sta actors,y
 dey
 bpl load_actor_packet
 iny
 ldy #24
 lda (src_ptr),y
 clc
 adc replay_deadline
 sta replay_deadline
 jsr mc_prepare
 jsr mc_commit
demo_presented:
 inc demo_frame
 bne advance_replay
 inc demo_frame+1
advance_replay:
 clc
 lda replay_pointer
 adc #25
 sta replay_pointer
 bcc replay_no_carry
 inc replay_pointer+1
replay_no_carry:
 lda replay_remaining
 bne replay_dec_low
 dec replay_remaining+1
replay_dec_low:
 dec replay_remaining
 lda replay_remaining
 ora replay_remaining+1
 bne demo_ready
 jsr reset_replay
 jmp demo_ready
reset_replay:
 lda #<replay_data
 sta replay_pointer
 lda #>replay_data
 sta replay_pointer+1
 lda #<REPLAY_FRAMES
 sta replay_remaining
 lda #>REPLAY_FRAMES
 sta replay_remaining+1
 rts
replay_irq:
 lda $9124
 inc replay_tick
 pla
 tay
 pla
 tax
 pla
 rti

mc_init:
 ; Load the permanent VIC glyphs from the same row tables used when preparing
 ; hidden work characters. X stays the glyph code throughout each copy.
 ldx #0
init_characters:
 lda glyph_lo,x
 sta dst_ptr
 lda glyph_hi,x
 sta dst_ptr+1
 ldy #7
.repeat 8,N
 lda background_row7-N*147,x
 sta (dst_ptr),y
 dey
.endrepeat
 inx
 cpx #147
 bcc init_characters
 ldx #0
init_pages:
 lda background_map,x
 sta $1800,x
 lda background_map+256,x
 sta $1900,x
 lda background_colors,x
 sta $9400,x
 lda background_colors+256,x
 sta $9500,x
 lda #$ff
 sta cell_work,x
 sta cell_work+256,x
 cpx #55
 bcs init_no_tail
 sta cell_work+512,x
 lda background_map+512,x
 sta $1a00,x
 lda background_colors+512,x
 sta $9600,x
init_no_tail:
 inx
 bne init_pages
 lda #0
 sta mc_pending
 sta mc_status
 sta mc_old_count
 sta mc_new_count
 sta demo_frame
 sta demo_frame+1
 lda #147
 sta mc_new_base
 jmp select_banks

select_banks:
 lda mc_new_base
 ; Update the publisher's copy of the bank constant at the same boundary.
 sta publish_bank+1
 cmp #147
 bne new_bank_b
 lda #<cells_a_lo
 sta new_lo
 lda #>cells_a_lo
 sta new_lo+1
 lda #<cells_a_hi
 sta new_hi
 lda #>cells_a_hi
 sta new_hi+1
 lda #<colors_a
 sta new_color
 lda #>colors_a
 sta new_color+1
 lda #<cells_b_lo
 sta old_lo
 lda #>cells_b_lo
 sta old_lo+1
 lda #<cells_b_hi
 sta old_hi
 lda #>cells_b_hi
 sta old_hi+1
 rts
new_bank_b:
 lda #<cells_b_lo
 sta new_lo
 lda #>cells_b_lo
 sta new_lo+1
 lda #<cells_b_hi
 sta new_hi
 lda #>cells_b_hi
 sta new_hi+1
 lda #<colors_b
 sta new_color
 lda #>colors_b
 sta new_color+1
 lda #<cells_a_lo
 sta old_lo
 lda #>cells_a_lo
 sta old_lo+1
 lda #<cells_a_hi
 sta old_hi
 lda #>cells_a_hi
 sta old_hi+1
 rts

mc_prepare:
 lda mc_pending
 beq prepare_clean
 jsr mc_abort
prepare_clean:
 lda #0
 sta mc_status
 sta mc_new_count
 sta actor_index
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
 sta actor_has_accent
 lda pose_lo,y
 sta load_row_id+1
 lda pose_hi,y
 sta load_row_id+2
 lda actors,x
 and #3
 sta actor_shift
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
 ldy actor_shift
 lda phase_offsets,y
 clc
 adc load_row_id+1
 sta load_row_id+1
 bcc shifts_ready
 inc load_row_id+2
shifts_ready:
 ; Each band uses destination Y for the source-row lookup too. Bias the
 ; source base by the actor's Y once, then add the hardware band's origin.
 sec
 lda load_row_id+1
 sbc actor_y
 sta load_source_low+1
 lda load_row_id+2
 sbc #0
 sta load_source_high+1
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
 ; Clipping and the selected column painter stay constant for this actor.
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
 lda draw_lo,x
 sta row_blit+1
 lda draw_hi,x
 sta row_blit+2
 lda resolve_lo,x
 sta resolve_band_cells+1
 lda resolve_hi,x
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
 lda mc_status
 beq band_ready
 jmp prepare_failed
band_ready:
 clc
load_source_low:
 lda #0
 adc band_top
 sta load_row_id+1
load_source_high:
 lda #0
 adc #0
 sta load_row_id+2
 lda pixel_y
 and #7
 tay
band_row:
load_row_id:
 ldx $ffff,y
row_blit:
 jmp draw_0
row_colors:
 lda color_pending
 beq row_advance
 and row_accent,x
 beq row_advance
 ; The source-row ID is no longer needed. X selects a colour-write path,
 ; then the destination colour slots; Y remains the glyph scanline.
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
 jmp prepare_actor
prepare_done:
 lda #1
 sta mc_pending
mc_prepare_end:
 rts
prepare_failed:
 lda #1
 sta mc_status
 jsr clear_work_map
 lda #0
 sta mc_pending
 rts

; Band loops keep Y as the glyph scanline and X as the pre-shifted row ID.
.macro DRAW PTR,DAT,MASK
 lda (PTR),y
 and MASK,x
 ora DAT,x
 sta (PTR),y
.endmacro
draw_0:
 jmp row_colors
draw_1:
 DRAW left_ptr,row_data0,row_mask0
 jmp row_colors
draw_2:
 DRAW middle_ptr,row_data1,row_mask1
 jmp row_colors
draw_3:
 DRAW left_ptr,row_data0,row_mask0
 DRAW middle_ptr,row_data1,row_mask1
 jmp row_colors
draw_4:
 DRAW right_ptr,row_data2,row_mask2
 jmp row_colors
draw_5:
 DRAW left_ptr,row_data0,row_mask0
 DRAW right_ptr,row_data2,row_mask2
 jmp row_colors
draw_6:
 DRAW middle_ptr,row_data1,row_mask1
 DRAW right_ptr,row_data2,row_mask2
 jmp row_colors
draw_7:
 DRAW left_ptr,row_data0,row_mask0
 DRAW middle_ptr,row_data1,row_mask1
 DRAW right_ptr,row_data2,row_mask2
 jmp row_colors

; The two colour banks are contiguous, so all seven combinations share fixed
; absolute-X stores. Common two-column and single-column updates come first.
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

; Resolve the clipped columns once per band. Advance the cell index directly;
; all actors still share one map so overlaps use a single working character.
resolve_row:
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
 jsr resolve_cells_0
 bcc resolve_cells_ready
 lda #1
 sta mc_status
 rts
resolve_cells_ready:
 lda #0
 ldx actor_has_accent
 beq resolve_colors
 lda valid_columns
resolve_colors:
 sta color_pending
 rts

.macro RESOLVE_CELL PTR,INDEX
 .local fits
 jsr get_work_cell
 bcc fits
 rts
fits:
 lda current_code
 sec
 sbc #147
 sta INDEX
 lda dst_ptr
 sta PTR
 lda dst_ptr+1
 sta PTR+1
.endmacro
.macro NEXT_CELL
 .local no_carry
 inc cell_low
 bne no_carry
 inc cell_high
no_carry:
.endmacro
resolve_cells_0:
 clc
 rts
resolve_cells_1:
 RESOLVE_CELL left_ptr,left_index
 clc
 rts
resolve_cells_2:
 NEXT_CELL
 RESOLVE_CELL middle_ptr,middle_index
 clc
 rts
resolve_cells_3:
 RESOLVE_CELL left_ptr,left_index
 NEXT_CELL
 RESOLVE_CELL middle_ptr,middle_index
 clc
 rts
resolve_cells_4:
 NEXT_CELL
 NEXT_CELL
 RESOLVE_CELL right_ptr,right_index
 clc
 rts
resolve_cells_5:
 RESOLVE_CELL left_ptr,left_index
 NEXT_CELL
 NEXT_CELL
 RESOLVE_CELL right_ptr,right_index
 clc
 rts
resolve_cells_6:
 NEXT_CELL
 RESOLVE_CELL middle_ptr,middle_index
 NEXT_CELL
 RESOLVE_CELL right_ptr,right_index
 clc
 rts
resolve_cells_7:
 RESOLVE_CELL left_ptr,left_index
 NEXT_CELL
 RESOLVE_CELL middle_ptr,middle_index
 NEXT_CELL
 RESOLVE_CELL right_ptr,right_index
 clc
 rts

; Inline the small address helpers on the preparation path. The publication
; and abort paths retain the shared map helper to limit code growth.
.macro CELL_MAP_POINTER
 lda cell_high
 clc
 adc #>cell_work
 sta map_ptr+1
.endmacro
.macro GLYPH_DESTINATION
 ; Both callers already have the character code in A.
 tax
 lda glyph_lo,x
 sta dst_ptr
 lda glyph_hi,x
 sta dst_ptr+1
.endmacro
get_work_cell:
 CELL_MAP_POINTER
 ldy #0
 lda (map_ptr),y
 cmp #$ff
 beq allocate_cell
 sta current_code
 GLYPH_DESTINATION
 clc
 rts
allocate_cell:
 lda mc_new_count
 cmp #54
 bcc allocation_fits
 sec
 rts
allocation_fits:
 tay
 lda cell_low
 sta (new_lo),y
 lda cell_high
 sta (new_hi),y
 lda #14
 sta (new_color),y
 lda mc_new_count
 clc
allocate_code:
 adc #147
 sta current_code
 ldy #0
 sta (map_ptr),y
 inc mc_new_count
 GLYPH_DESTINATION
 clc
 lda cell_low
 adc #<background_map
 sta src_ptr
 lda cell_high
 adc #>background_map
 sta src_ptr+1
 ldy #0
 lda (src_ptr),y
 tax
 ldy #7
.repeat 8,N
 lda background_row7-N*147,x
 sta (dst_ptr),y
 dey
.endrepeat
 clc
 rts

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

; Keep these lookup bytes off the executed path while placing the publisher's
; common cached-page branch within a page, without adding padding.
draw_lo: .lobytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
draw_hi: .hibytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
.assert >draw_lo = >(draw_lo+7), lderror, "Drawing lookup must stay within a page"
.assert >draw_hi = >(draw_hi+7), lderror, "Drawing lookup must stay within a page"
mc_publish:
 lda #0
 sta list_index
restore_vacated:
 ldy list_index
 cpy mc_old_count
 bcs publish_start
 lda (old_lo),y
 sta cell_low
 lda (old_hi),y
 sta cell_high
 jsr make_map_ptr
 ldy #0
 lda (map_ptr),y
 cmp #$ff
 bne restore_skip
 clc
 lda cell_low
 adc #<background_map
 sta src_ptr
 lda cell_high
 adc #>background_map
 sta src_ptr+1
 jsr make_screen_ptr
 lda (src_ptr),y
 sta (screen_ptr),y
 lda #14
 sta (color_ptr),y
restore_skip:
 inc list_index
 jmp restore_vacated
publish_start:
 lda #0
 sta list_index
publish_cell:
 ldy list_index
 cpy mc_new_count
 bcs mc_commit_end
 lda (new_lo),y
 tax
 lda (new_hi),y
 ; Consecutive cells usually share a matrix/colour/map page. The patched
 ; stores remain valid until this high byte changes, including across frames.
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
.assert >(publish_page+4) = >publish_page_ready, lderror, "Cached publication branch must stay within a page"
 lda (new_color),y
publish_color:
 sta $9400,x
 lda list_index
 clc
publish_bank:
 adc #147
publish_code:
 sta $1800,x
 lda #$ff
publish_clear:
 sta cell_work,x
 inc list_index
 jmp publish_cell
mc_commit_end:
 rts

make_screen_ptr:
 lda cell_low
 sta screen_ptr
 sta color_ptr
 lda cell_high
 clc
 adc #$18
 sta screen_ptr+1
 clc
 adc #$7c
 sta color_ptr+1
 ldy #0
 rts

mc_abort:
 jsr clear_work_map
 lda #0
 sta mc_pending
 rts
clear_work_map:
 lda #0
 sta list_index
clear_map_cell:
 ldy list_index
 cpy mc_new_count
 bcs clear_map_done
 lda (new_lo),y
 sta cell_low
 lda (new_hi),y
 sta cell_high
 jsr make_map_ptr
 ldy #0
 lda #$ff
 sta (map_ptr),y
 inc list_index
 jmp clear_map_cell
clear_map_done:
 rts

column_bits: .byte 1,2,4
phase_offsets: .byte 0,14,28,42
resolve_lo: .lobytes resolve_cells_0,resolve_cells_1,resolve_cells_2,resolve_cells_3,resolve_cells_4,resolve_cells_5,resolve_cells_6,resolve_cells_7
resolve_hi: .hibytes resolve_cells_0,resolve_cells_1,resolve_cells_2,resolve_cells_3,resolve_cells_4,resolve_cells_5,resolve_cells_6,resolve_cells_7
row_cell_lo:
.repeat 27,N
 .byte <(N*21)
.endrepeat
row_cell_hi:
.repeat 27,N
 .byte >(N*21)
.endrepeat

.segment "DATA"
; Eight 147-byte row planes: the same 1,176 bytes as the permanent charset.
background_rows: .incbin "background-rows.bin"
background_row7 = background_rows+7*147
background_map: .incbin "background-map.bin"
background_colors: .incbin "background-colors.bin"
pose_data: .incbin "pose-rows.bin"
pose_lo:
.repeat POSE_COUNT,N
 .byte <(pose_data+N*56)
.endrepeat
pose_hi:
.repeat POSE_COUNT,N
 .byte >(pose_data+N*56)
.endrepeat
pose_has_accent: .incbin "pose-accents.bin"
glyph_lo:
.repeat 256,N
 .byte <($1000+N*8)
.endrepeat
glyph_hi:
.repeat 256,N
 .byte >($1000+N*8)
.endrepeat
row_data0: .incbin "row-records.bin",0,ROW_RECORDS
row_data1: .incbin "row-records.bin",ROW_RECORDS,ROW_RECORDS
row_data2: .incbin "row-records.bin",ROW_RECORDS*2,ROW_RECORDS
row_mask0: .incbin "row-records.bin",ROW_RECORDS*3,ROW_RECORDS
row_mask1: .incbin "row-records.bin",ROW_RECORDS*4,ROW_RECORDS
row_mask2: .incbin "row-records.bin",ROW_RECORDS*5,ROW_RECORDS
row_accent: .incbin "row-records.bin",ROW_RECORDS*6,ROW_RECORDS
replay_data: .incbin "replay.bin"
