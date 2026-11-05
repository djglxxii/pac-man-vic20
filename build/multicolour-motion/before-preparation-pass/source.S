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
cell: .res 2
raw_lo: .res 1

.segment "STATE"
cells_a_lo: .res 54
cells_a_hi: .res 54
colors_a: .res 54
cells_b_lo: .res 54
cells_b_hi: .res 54
colors_b: .res 54
.export actors,mc_status,mc_pending,mc_new_count,mc_old_count,mc_new_base
actors: .res 24                 ; Six records, painter priority: x,y,pose,accent.
mc_status: .res 1
mc_pending: .res 1
mc_new_count: .res 1
mc_old_count: .res 1
mc_new_base: .res 1
actor_index: .res 1
actor_col: .res 1
actor_y: .res 1
actor_shift: .res 1
actor_columns: .res 1
actor_accent: .res 1
actor_has_accent: .res 1
source_row: .res 1
pixel_y: .res 1
last_band: .res 1
current_band: .res 1
row_offset: .res 1
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

.segment "CODE"
.export entry,loader_start,mc_init,mc_prepare,mc_prepare_end,mc_commit,mc_commit_end,mc_publish,mc_abort,demo_ready,demo_presented
.export resolve_row,get_work_cell,clear_work_map
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
 sta demo_frame
 sta demo_frame+1
 lda #147
 sta mc_new_base
 jmp select_banks

select_banks:
 lda mc_new_base
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
 sta actor_accent
 ldy actor_shift
 lda phase_offsets,y
 clc
 adc load_row_id+1
 sta load_row_id+1
 bcc shifts_ready
 inc load_row_id+2
shifts_ready:
 lda #$ff
 sta last_band
 lda #13
 sta source_row
 clc
 adc actor_y
 sta pixel_y
prepare_row:
 lda pixel_y
 cmp #16
 bcs row_not_above
 jmp row_advance
row_not_above:
 cmp #208
 bcc row_inside
 jmp row_advance
row_inside:
 and #7
 sta row_offset
 lda pixel_y
 lsr
 lsr
 lsr
 sta current_band
 cmp last_band
 beq row_ready
 sta last_band
 jsr resolve_row
 lda mc_status
 beq row_ready
 jmp prepare_failed
row_ready:
 ldy source_row
load_row_id:
 lda $ffff,y
 tax
 ldy row_offset
row_blit:
 jmp draw_0
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
row_colors:
 lda color_pending
 beq row_advance
 and row_accent,x
 beq row_advance
 sta source_accent
 eor color_pending
 sta color_pending
.macro PAINT_COLOR INDEX,BIT
 .local no_color
 lda source_accent
 and #BIT
 beq no_color
 ldy INDEX
 lda actor_accent
 sta (new_color),y
no_color:
.endmacro
 PAINT_COLOR left_index,1
 PAINT_COLOR middle_index,2
 PAINT_COLOR right_index,4
row_advance:
 dec pixel_y
 dec source_row
 bmi next_actor
 jmp prepare_row
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

; Resolve up to three columns once per hardware row, sharing cells across actors.
resolve_row:
 lda #0
 sta valid_columns
 sta column_index
resolve_column:
 lda actor_col
 clc
 adc column_index
 bmi resolve_next
 cmp #21
 bcs resolve_next
 sta raw_lo
 ldx current_band
 lda row_cell_lo,x
 clc
 adc raw_lo
 sta cell
 lda row_cell_hi,x
 adc #0
 sta cell+1
 jsr get_work_cell
 bcc resolve_cell_ok
 rts
resolve_cell_ok:
 lda current_code
 sec
 sbc mc_new_base
 ldx column_index
 sta left_index,x
 cpx #0
 beq resolve_left
 cpx #1
 beq resolve_middle
 lda dst_ptr
 sta right_ptr
 lda dst_ptr+1
 sta right_ptr+1
 jmp resolve_mark
resolve_left:
 lda dst_ptr
 sta left_ptr
 lda dst_ptr+1
 sta left_ptr+1
 jmp resolve_mark
resolve_middle:
 lda dst_ptr
 sta middle_ptr
 lda dst_ptr+1
 sta middle_ptr+1
resolve_mark:
 ldx column_index
 lda valid_columns
 ora column_bits,x
 sta valid_columns
resolve_next:
 inc column_index
 lda column_index
 cmp actor_columns
 bcc resolve_column
 lda #0
 ldx actor_has_accent
 beq resolve_colors
 lda valid_columns
resolve_colors:
 sta color_pending
 ldx valid_columns
 lda draw_lo,x
 sta row_blit+1
 lda draw_hi,x
 sta row_blit+2
 rts

get_work_cell:
 jsr make_map_ptr
 ldy #0
 lda (map_ptr),y
 cmp #$ff
 beq allocate_cell
 sta current_code
 jsr code_to_destination
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
 lda cell
 sta (new_lo),y
 lda cell+1
 sta (new_hi),y
 lda #14
 sta (new_color),y
 lda mc_new_count
 clc
 adc mc_new_base
 sta current_code
 ldy #0
 sta (map_ptr),y
 inc mc_new_count
 jsr code_to_destination
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
 lda #0
 sta mc_pending
 lda mc_new_base
 eor #$5a
 sta mc_new_base
 jmp select_banks
mc_publish:
 lda #0
 sta list_index
restore_vacated:
 ldy list_index
 cpy mc_old_count
 bcs publish_start
 lda (old_lo),y
 sta cell
 lda (old_hi),y
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
publish_cell:
 ldy list_index
 cpy mc_new_count
 bcs mc_commit_end
 lda (new_lo),y
 tax
 lda (new_hi),y
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
 lda (new_color),y
publish_color:
 sta $9400,x
 lda list_index
 clc
 adc mc_new_base
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
 sta cell
 lda (new_hi),y
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
phase_offsets: .byte 0,14,28,42
draw_lo: .lobytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
draw_hi: .hibytes draw_0,draw_1,draw_2,draw_3,draw_4,draw_5,draw_6,draw_7
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
