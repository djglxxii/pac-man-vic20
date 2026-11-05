; Isolated VIC-I character compositor. No game logic or arcade clock changes.
; Background codes 0..146; 108 persistent working characters 147..254.
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
src_ptr: .res 2
dst_ptr: .res 2
new_codes: .res 2
old_codes: .res 2
new_overlaps: .res 2
old_overlaps: .res 2
screen_ptr: .res 2
color_ptr: .res 2
left_ptr: .res 2
middle_ptr: .res 2
right_ptr: .res 2
cell: .res 2
raw_lo: .res 1

.segment "STATE"
.export actors,mc_status,mc_pending,mc_new_count,mc_old_count,mc_bank
.export mc_reused_count,dirty_mask
actors: .res 24                 ; Six records, painter priority: x,y,pose,accent.
committed_actors: .res 24
prepared_actors: .res 24
mc_status: .res 1
mc_pending: .res 1
mc_new_count: .res 1
mc_old_count: .res 1
mc_bank: .res 1                 ; Selects metadata, not character slots.
mc_reused_count: .res 1
dirty_mask: .res 1
actor_bit: .res 1
free_count: .res 1
current_work_index: .res 1
closure_changed: .res 1
new_overlap_count: .res 1
old_overlap_count: .res 1
actor_index: .res 1
actor_col: .res 1
actor_y: .res 1
actor_shift: .res 1
actor_columns: .res 1
actor_accent: .res 1
actor_has_accent: .res 1
pixel_y: .res 1
current_band: .res 1
row_offset: .res 1
sprite_bottom: .res 1
band_top: .res 1
band_bottom: .res 1
band_end: .res 1
source_bias: .res 2
valid_columns: .res 1
color_pending: .res 1
source_accent: .res 1
left_index: .res 1
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
codes_a: .res 54
codes_b: .res 54
slot_cell_lo: .res 108
slot_cell_hi: .res 108
slot_color: .res 108
slot_owners: .res 108
overlaps_a: .res 54
overlaps_b: .res 54
free_slots: .res 108

.segment "CODE"
.export entry,loader_start,mc_init,mc_prepare,mc_prepare_end,mc_commit,mc_commit_end,mc_publish,mc_abort,demo_ready,demo_presented
.export resolve_row,get_work_cell,clear_work_map
.export analyse_changes,retain_cells,free_count,free_slots
.export actor_col,current_band
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
 ldx #0
init_pages:
.repeat 4,N
 lda background_charset+N*256,x
 sta $1000+N*256,x
.endrepeat
 cpx #152
 bcs init_no_char_tail
 lda background_charset+1024,x
 sta $1400,x
init_no_char_tail:
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
 sta mc_bank
 sta old_overlap_count
 sta demo_frame
 sta demo_frame+1
 ldx #107
init_slots:
 txa
 sta free_slots,x
 dex
 bpl init_slots
 lda #108
 sta free_count
 lda #$ff
 ldx #23
init_committed:
 sta committed_actors,x
 dex
 bpl init_committed
 jmp select_banks

.macro SELECT_POINTER PTR,ADDRESS
 lda #<ADDRESS
 sta PTR
 lda #>ADDRESS
 sta PTR+1
.endmacro
select_banks:
 lda mc_bank
 bne new_bank_b
 SELECT_POINTER new_codes,codes_a
 SELECT_POINTER new_overlaps,overlaps_a
 SELECT_POINTER old_codes,codes_b
 SELECT_POINTER old_overlaps,overlaps_b
 rts
new_bank_b:
 SELECT_POINTER new_codes,codes_b
 SELECT_POINTER new_overlaps,overlaps_b
 SELECT_POINTER old_codes,codes_a
 SELECT_POINTER old_overlaps,overlaps_a
 rts

; Snapshot inputs before preparing. Dirty groups include every unchanged actor
; sharing cells with the old/new footprint of a dirty actor, transitively.
analyse_changes:
 lda #0
 sta dirty_mask
 ldx #23
compare_actor_bytes:
 lda actors,x
 sta prepared_actors,x
 cmp committed_actors,x
 beq actor_byte_same
 lda dirty_mask
 ora actor_bits,x
 sta dirty_mask
actor_byte_same:
 dex
 bpl compare_actor_bytes
 lda dirty_mask
 beq analysis_initial_done
 ; Hidden actors cannot contribute cells. Treat them as dirty so a frame
 ; where every visible actor changes can take the full-redraw fast path.
 ldx #0
ignore_hidden_actors:
 lda prepared_actors+2,x
 cmp #$ff
 bne hidden_actor_next
 lda dirty_mask
 ora actor_bits,x
 sta dirty_mask
hidden_actor_next:
 txa
 clc
 adc #4
 tax
 cpx #24
 bcc ignore_hidden_actors
 lda dirty_mask
 cmp #63
 bne analysis_build_bounds
analysis_initial_done:
 clc
 rts
analysis_build_bounds:
closure_pass:
 lda #0
 sta closure_changed
 ; Only cells shared by multiple actors can propagate old dependencies.
 ldy #0
closure_old_cell:
 cpy old_overlap_count
 bcs closure_new_cells
 lda (old_overlaps),y
 and dirty_mask
 beq closure_old_next
 lda (old_overlaps),y
 ora dirty_mask
 cmp dirty_mask
 beq closure_old_next
 sta dirty_mask
 inc closure_changed
closure_old_next:
 iny
 bne closure_old_cell
closure_new_cells:
 lda dirty_mask
 cmp #63
 beq analysis_done
 ldy #0
closure_candidate:
 lda actor_bits,y
 and dirty_mask
 bne closure_next_candidate
 lda prepared_actors+2,y
 cmp #$ff
 beq closure_next_candidate
 ldx #0
closure_test:
 lda actor_bits,x
 and dirty_mask
 beq closure_next_test
 lda prepared_actors+2,x
 cmp #$ff
 beq closure_next_test
 ; Sharing any cell requires origins within eight horizontal pixels and
 ; twenty scanlines. This conservative test avoids constructing rectangles.
 lda prepared_actors,x
 sec
 sbc prepared_actors,y
 clc
 adc #8
 cmp #17
 bcs closure_next_test
 lda prepared_actors+1,x
 sec
 sbc prepared_actors+1,y
 clc
 adc #20
 cmp #41
 bcs closure_next_test
 lda actor_bits,y
 ora dirty_mask
 sta dirty_mask
 lda #1
 sta closure_changed
 bne closure_next_candidate
closure_next_test:
 txa
 clc
 adc #4
 tax
 cpx #24
 bcc closure_test
closure_next_candidate:
 tya
 clc
 adc #4
 tay
 cpy #24
 bcc closure_candidate
 lda dirty_mask
 cmp #63
 beq analysis_done
 lda closure_changed
 beq analysis_done
 jmp closure_pass
analysis_done:
 clc
 rts

retain_cells:
 lda dirty_mask
 cmp #63
 beq retain_done
 lda #0
 sta list_index
retain_cell:
 ldy list_index
 cpy mc_old_count
 bcs retain_done
 lda (old_codes),y
 tax
 lda slot_owners,x
 and dirty_mask
 bne retain_next
 stx current_work_index
 lda slot_cell_lo,x
 sta cell
 lda slot_cell_hi,x
 sta cell+1
 ; Shared cells carry their dependency into the next image.
 lda slot_owners,x
 sta source_accent
 sec
 sbc #1
 and source_accent
 beq retained_single_owner
 lda source_accent
 jsr record_overlap
retained_single_owner:
 txa
 ldy mc_new_count
 sta (new_codes),y
 jsr make_map_ptr
 ldy #0
 lda current_work_index
 ora #$80
 sta (map_ptr),y
 inc mc_new_count
 inc mc_reused_count
retain_next:
 inc list_index
 jmp retain_cell
retain_done:
 rts

mc_prepare:
 lda mc_pending
 beq prepare_clean
 jsr mc_abort
prepare_clean:
 lda #0
 sta mc_status
 sta mc_new_count
 sta mc_reused_count
 sta new_overlap_count
 jsr analyse_changes
 bcc changes_valid
 jmp prepare_failed
changes_valid:
 jsr retain_cells
 lda #0
 sta actor_index
prepare_actor:
 ldx actor_index
 lda actor_bits,x
 sta actor_bit
 and dirty_mask
 bne actor_dirty
 jmp next_actor
actor_dirty:
 lda prepared_actors+2,x
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
 lda prepared_actors,x
 and #3
 sta actor_shift
 cmp #3
 lda #2
 adc #0
 sta actor_columns
 lda prepared_actors,x
 cmp #$80
 ror
 cmp #$80
 ror
 sta actor_col
 lda prepared_actors+1,x
 sta actor_y
 lda prepared_actors+3,x
 and #7
 ora #8
 sta actor_accent
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
 sta source_bias
 lda load_row_id+2
 sbc #0
 sta source_bias+1
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
 sta band_end
 jsr resolve_row
 lda mc_status
 beq band_ready
 jmp prepare_failed
band_ready:
 clc
 lda source_bias
 adc band_top
 sta load_row_id+1
 lda source_bias+1
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
 sta source_accent
 eor color_pending
 sta color_pending
 sty row_offset
.macro PAINT_COLOR INDEX,BIT
 .local no_color
 lda source_accent
 and #BIT
 beq no_color
 ldy INDEX
 lda actor_accent
 sta slot_color,y
no_color:
.endmacro
 PAINT_COLOR left_index,1
 PAINT_COLOR middle_index,2
 PAINT_COLOR right_index,4
 ldy row_offset
row_advance:
 iny
 cpy band_end
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

; Resolve the clipped columns once per band. Advance the cell index directly;
; all actors still share one map so overlaps use a single working character.
resolve_row:
 ldx current_band
 lda row_cell_lo,x
 clc
 adc actor_col
 sta cell
 lda row_cell_hi,x
 adc #0
 ldx actor_col
 bpl resolve_positive_column
 sec
 sbc #1
resolve_positive_column:
 sta cell+1
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
 lda current_work_index
 sta INDEX
 lda dst_ptr
 sta PTR
 lda dst_ptr+1
 sta PTR+1
.endmacro
.macro NEXT_CELL
 .local no_carry
 inc cell
 bne no_carry
 inc cell+1
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

get_work_cell:
 jsr make_map_ptr
 ldy #0
 lda (map_ptr),y
 cmp #$ff
 beq allocate_cell
 ; Retained map entries have bit 7 set. Never return a live glyph for drawing.
 bpl existing_prepared_cell
 sec
 rts
existing_prepared_cell:
 sta current_work_index
 tax
 lda slot_owners,x
 ora actor_bit
 sta slot_owners,x
 jsr record_overlap
 jmp slot_to_destination
allocate_cell:
 lda mc_new_count
 cmp #54
 bcc allocation_fits
 sec
 rts
allocation_fits:
 ldx free_count
 bne free_slot_found
 sec
 rts
free_slot_found:
 dex
 stx free_count
 lda free_slots,x
 tax
 stx current_work_index
 lda cell
 sta slot_cell_lo,x
 lda cell+1
 sta slot_cell_hi,x
 lda #14
 sta slot_color,x
 lda actor_bit
 sta slot_owners,x
 txa
 ldy mc_new_count
 sta (new_codes),y
 ldy #0
 sta (map_ptr),y
 inc mc_new_count
 jsr slot_to_destination
 clc
 lda cell
 adc #<background_map
 sta src_ptr
 lda cell+1
 adc #>background_map
 sta src_ptr+1
 ldy #0
 lda (src_ptr),y
 tax
 lda glyph_lo,x
 sta src_ptr
 lda glyph_hi,x
 sta src_ptr+1
 ldy #7
.repeat 8
 lda (src_ptr),y
 sta (dst_ptr),y
 dey
.endrepeat
 clc
 rts
slot_to_destination:
 lda current_work_index
 clc
 adc #147
 sta current_code
 jsr code_to_destination
 clc
 rts

record_overlap:
 ldy new_overlap_count
 sta (new_overlaps),y
 inc new_overlap_count
 ldy current_work_index
 rts

make_map_ptr:
 lda cell
 sta map_ptr
 lda cell+1
 clc
 adc #>cell_work
 sta map_ptr+1
 rts
code_to_destination:
 ldx current_code
 lda glyph_lo,x
 sta dst_ptr
 lda glyph_hi,x
 sta dst_ptr+1
 rts

mc_commit:
 lda mc_pending
 bne commit_ready
 rts
commit_ready:
 jsr mc_publish
 lda mc_new_count
 sta mc_old_count
 lda new_overlap_count
 sta old_overlap_count
 lda #0
 sta mc_pending
 ldx #23
commit_inputs:
 lda prepared_actors,x
 sta committed_actors,x
 dex
 bpl commit_inputs
 lda mc_bank
 eor #1
 sta mc_bank
 jmp select_banks
mc_publish:
 lda #0
 sta list_index
restore_vacated:
 ldy list_index
 cpy mc_old_count
 bcs publish_start
 lda (old_codes),y
 tax
 lda slot_owners,x
 and dirty_mask
 beq restore_skip
 txa
 ldx free_count
 sta free_slots,x
 inc free_count
 tax
 lda slot_cell_lo,x
 sta cell
 lda slot_cell_hi,x
 sta cell+1
 jsr make_map_ptr
 ldy #0
 lda (map_ptr),y
 cmp #$ff
 bne restore_skip
 clc
 lda cell
 adc #<background_map
 sta src_ptr
 lda cell+1
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
clear_retained:
 ldy list_index
 cpy mc_reused_count
 bcs publish_cell
 lda (new_codes),y
 tay
 lda slot_cell_lo,y
 tax
 lda slot_cell_hi,y
 clc
 adc #>cell_work
 sta retained_clear+2
 lda #$ff
retained_clear:
 sta cell_work,x
 inc list_index
 jmp clear_retained
publish_cell:
 ldy list_index
 cpy mc_new_count
 bcs mc_commit_end
 lda (new_codes),y
 tay
 lda slot_cell_lo,y
 tax
 lda slot_cell_hi,y
 clc
 adc #$18
 sta publish_code+2
 clc
 adc #$7c
 sta publish_color+2
 lda slot_cell_hi,y
 clc
 adc #>cell_work
 sta publish_clear+2
 lda slot_color,y
publish_color:
 sta $9400,x
 tya
 clc
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
 lda cell
 sta screen_ptr
 sta color_ptr
 lda cell+1
 clc
 adc #$18
 sta screen_ptr+1
 clc
 adc #$7c
 sta color_ptr+1
 ldy #0
 rts

mc_abort:
 lda mc_pending
 beq abort_done
 jsr clear_work_map
 lda #0
 sta mc_pending
abort_done:
 rts
clear_work_map:
 lda #0
 sta list_index
clear_map_cell:
 ldy list_index
 cpy mc_new_count
 bcs clear_map_done
 lda (new_codes),y
 tax
 cpy mc_reused_count
 bcc release_retained
 txa
 ldx free_count
 sta free_slots,x
 inc free_count
 tax
release_retained:
 lda slot_cell_lo,x
 sta cell
 lda slot_cell_hi,x
 sta cell+1
 jsr make_map_ptr
 ldy #0
 lda #$ff
 sta (map_ptr),y
 inc list_index
 jmp clear_map_cell
clear_map_done:
 rts

column_bits: .byte 1,2,4
actor_bits: .byte 1,1,1,1,2,2,2,2,4,4,4,4,8,8,8,8,16,16,16,16,32,32,32,32
phase_offsets: .byte 0,14,28,42
draw_lo: .lobytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
draw_hi: .hibytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
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
background_charset: .incbin "background-charset.bin"
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
