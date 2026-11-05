.section .sprite_cache,"aw",@nobits
.global cache_x,cache_y,cache_attr,cache_pal
cache_x: .zero 14
cache_y: .zero 14
cache_attr: .zero 14
cache_pal: .zero 14
.set new_x,cache_x
.set new_y,cache_y
.section .zp.bss,"aw",@nobits
.global v_cell,v_color,v_sy
v_actor: .zero 1
.set pool_next_low,v_actor
v_off: .zero 1
v_sx: .zero 1
v_sy: .zero 1
v_col: .zero 1
v_cell: .zero 1
v_color: .zero 1
v_pal: .zero 1
v_code: .zero 1
v_attr: .zero 1
v_base: .zero 2
v_temp: .zero 1
.zeropage v_addr,v_right,v_save,v_saved_right,v_data,v_shift,v_flip,v_hi,v_lo,v_row
.zeropage v_flags,full_dirty
.section .text.pool,"ax",@progbits
.global pool_actors,pool_reuse_guard,pool_draw
pool_reuse_guard:
 ldx #13
pool_guard_loop:
 dex
 bne pool_guard_loop
 rts
pool_actors:
 jsr score_expand
 ldx #12
pool_capture:
 lda #239
 cpx #5
 bcs pool_x_origin
 lda #238
pool_x_origin:
 sec
 sbc $0c30,x
 bcs pool_positive_x
 sec
 ror
 jmp pool_x_ready
pool_positive_x:
 lsr
pool_x_ready:
 sta cache_x,x
 lda $0c31,x
 sta v_sy
 lsr
 lsr
 clc
 adc #204
 sec
 sbc v_sy
 sta cache_y,x
 lda $0c20,x
 sta cache_attr,x
 lda $0c21,x
 and #31
 sta cache_pal,x
 dex
 dex
 bne pool_capture
 jsr score_unexpand
 lda #12
 sta v_off
sprite_actor:
 ldx v_off
 lda cache_pal,x
 and #31
 bne sprite_visible
 jmp sprite_advance
sprite_visible:
 sta v_pal
 lda cache_attr,x
 sta v_attr
 lsr
 lsr
 sta v_code
 lda new_x,x
 cmp #112
 bcc sprite_inside
 cmp #249
 bcs sprite_inside
 jmp sprite_advance
sprite_inside:
 sta v_sx
 lda new_y,x
 sta v_sy
 ldx #255
 lda v_sx
 bmi sprite_column_ready
 lsr
 lsr
 lsr
 tax
sprite_column_ready:
 stx v_col
 lda #3
 cpx #255
 bne sprite_not_left_edge
 lda #2
sprite_not_left_edge:
 cpx #13
 bne sprite_flags_ready
 lda #1
sprite_flags_ready:
 sta v_flags
 lda v_sy
 lsr
 lsr
 lsr
 lsr
 tax
 lda row_times_14,x
 clc
 adc v_col
 sta v_cell
 lda v_pal
 cmp #31
 beq sprite_score_right
sprite_check_eyes:
 cmp #25
 bne sprite_regular
 lda v_code
 sec
 sbc #32
 cmp #8
 bcs sprite_regular
 sta v_temp
 lda #<arcade_eyes
 sta v_base
 lda #>arcade_eyes
 sta v_base+1
 lda #1
 jmp sprite_class_ready
sprite_score_right:
 lda v_code
 sec
 sbc #40
 cmp #4
 bcc sprite_score_frame
 lda v_pal
 jmp sprite_check_eyes
sprite_score_frame:
 sta v_temp
 lda #<arcade_score_right
 sta v_base
 lda #>arcade_score_right
 sta v_base+1
 lda #24
 sta v_pal
 lda #1
 jmp sprite_class_ready
sprite_regular:
 lda v_code
 sta v_temp
 and #3
 asl
 tay
 lda v_code
 lsr
 lsr
 tax
 lda arcade_sprite_class,x
 cpy #0
 beq sprite_class_shifted
sprite_class_shift:
 lsr
 dey
 bne sprite_class_shift
sprite_class_shifted:
 and #3
 pha
 lda #<arcade_sprites
 sta v_base
 lda #>arcade_sprites
 sta v_base+1
 pla
sprite_class_ready:
 sta v_color
 lda v_pal
 asl
 asl
 ora v_color
 tax
 lda arcade_colors,x
 bne sprite_has_color
 jmp sprite_advance
sprite_has_color:
 sta v_color
 lda v_temp
 asl
 clc
 adc v_temp
 sta v_data
 lda #0
 sta v_data+1
 asl v_data
 rol v_data+1
 asl v_data
 rol v_data+1
 lda v_data
 clc
 adc v_base
 sta v_data
 lda v_data+1
 adc v_base+1
 sta v_data+1
 lda v_sx
 and #7
 sta v_shift
 lda v_attr
 and #3
 sta v_flip
 jsr pool_setup
 lda v_flags
 cmp #3
 bne pool_generic
 lda v_pal
 cmp #25
 beq pool_generic
 lda v_code
 sec
 sbc #32
 cmp #6
 bcs pool_generic
 and #1
 asl
 asl
 asl
 ora v_shift
 asl
 tax
 jsr pool_draw_ghost
 jmp sprite_advance
pool_generic:
 jsr pool_draw
sprite_advance:
 dec v_off
 dec v_off
 beq pool_actors_done
 jmp sprite_actor
pool_actors_done:
 rts
pool_draw:
 lda v_data
 sta pool_fetch+1
 lda v_data+1
 sta pool_fetch+2
 lda v_shift
 asl
 tax
 lda pool_shifts,x
 sta pool_mirror+1
 sta pool_reverse_done+1
 lda pool_shifts+1,x
 sta pool_mirror+2
 sta pool_reverse_done+2
 lda v_flip
 and #2
 beq pool_mirror_ready
 lda #<pool_reverse
 sta pool_mirror+1
 lda #>pool_reverse
 sta pool_mirror+2
pool_mirror_ready:
 ldx #0
 ldy #12
 lda #$e8
 lsr v_flip
 bcc pool_source_ready
 ldx #11
 ldy #255
 lda #$ca
pool_source_ready:
 sta pool_step
 sty pool_row_end+1
 lda v_sy
 and #15
 tay
pool_row:
pool_fetch:
 lda $ffff,x
 beq pool_step
pool_mirror:
 jmp pool_shift_0
pool_merge_low:
 ora (v_right),y
 sta (v_right),y
 lda v_hi
 ora (v_addr),y
 sta (v_addr),y
pool_step:
 inx
pool_row_end:
 cpx #12
 beq pool_draw_done
 iny
 cpy #16
 bne pool_row
 lda v_save
 sta v_addr
 lda v_save+1
 sta v_addr+1
 lda v_saved_right
 sta v_right
 lda v_saved_right+1
 sta v_right+1
 ldy #0
 beq pool_row
pool_draw_done:
 rts
pool_merge_high:
 ora (v_addr),y
 sta (v_addr),y
 lda v_lo
 ora (v_right),y
 sta (v_right),y
 jmp pool_step
pool_reverse:
 sty v_row
 tay
 lda bit_reverse,y
 ldy v_row
pool_reverse_done:
 jmp pool_shift_0
pool_shift_0:
 ora (v_addr),y
 sta (v_addr),y
 jmp pool_step
pool_shift_1:
 sta v_hi
 lda #0
 lsr v_hi
 ror
 jmp pool_merge_low
pool_shift_2:
 sta v_hi
 lda #0
 lsr v_hi
 ror
 lsr v_hi
 ror
 jmp pool_merge_low
pool_shift_3:
 sta v_hi
 lda #0
 lsr v_hi
 ror
 lsr v_hi
 ror
 lsr v_hi
 ror
 jmp pool_merge_low
pool_shift_4:
 sta v_hi
 asl
 asl
 asl
 asl
 sta v_lo
 lda v_hi
 lsr
 lsr
 lsr
 lsr
 jmp pool_merge_high
pool_left_3:
 sta v_lo
 lsr
 lsr
 lsr
 lsr
 lsr
 sta v_hi
 lda v_lo
 asl
 asl
 asl
 jmp pool_merge_low
pool_left_2:
 sta v_lo
 lda #0
 asl v_lo
 rol
 asl v_lo
 rol
 jmp pool_merge_high
pool_left_1:
 sta v_lo
 lda #0
 asl v_lo
 rol
 jmp pool_merge_high
pool_shifts:
.word pool_shift_0,pool_shift_1,pool_shift_2,pool_shift_3
.word pool_shift_4,pool_left_3,pool_left_2,pool_left_1
.global pool_setup,video_restore,video_sprites,video_update_begin,video_update_end
pool_cell:
 sta v_col
 tay
 lda $96c4,y
 and #14
 cmp pool_epoch
 bne pool_allocate
 lda $96c4,y
 and #1
 asl
 asl
 asl
 asl
 sta v_temp
 lda $94c4,y
 and #15
 ora v_temp
 clc
 adc pool_start
 tax
 jsr pool_pointer
 jmp pool_colour
pool_allocate:
 ldy pool_bank
 lda pool_count,y
 cmp #24
 bcc pool_space
 lda #1
 sta pool_failed
 lda #$f0
 sta v_base
 lda #$1f
 sta v_base+1
 rts
pool_space:
 clc
 adc pool_start
 tax
 lda pool_count,y
 clc
 adc #1
 sta pool_count,y
 lda v_col
 sta pool_cells,x
 tay
 txa
 sec
 sbc pool_start
 pha
 and #15
 sta $94c4,y
 pla
 lsr
 lsr
 lsr
 lsr
 ora pool_epoch
 sta $96c4,y
 lda pool_next_low
 sta v_base
 clc
 adc #16
 sta pool_next_low
 lda pool_code_end
 sta v_base+1
 adc #0
 sta pool_code_end
 ldy v_col
 lda home_codes,y
 sta v_hi
 and #$f0
 sta v_lo
 lda v_hi
 and #15
 ora #$10
 sta v_hi
 ldy #0
pool_copy:
.rept 15
 lda (v_lo),y
 sta (v_base),y
 iny
.endr
 lda (v_lo),y
 sta (v_base),y
 jmp pool_colour
pool_colour:
 lda v_color
 sta pool_colours,x
 rts
pool_pointer:
 txa
 clc
 adc #196
 pha
 asl
 asl
 asl
 asl
 sta v_base
 pla
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta v_base+1
 rts
pool_setup:
 lda #$f0
 sta v_addr
 sta v_right
 sta v_save
 sta v_saved_right
 lda #$1f
 sta v_addr+1
 sta v_right+1
 sta v_save+1
 sta v_saved_right+1
 lda v_flags
 and #1
 beq pool_setup_right
 lda v_cell
 jsr pool_cell
 lda v_base
 sta v_addr
 lda v_base+1
 sta v_addr+1
 lda v_sy
 and #15
 cmp #5
 bcc pool_setup_right
 lda v_cell
 clc
 adc #14
 jsr pool_cell
 lda v_base
 sta v_save
 lda v_base+1
 sta v_save+1
pool_setup_right:
 lda v_flags
 and #2
 beq pool_setup_done
 lda v_shift
 beq pool_setup_done
 lda v_cell
 clc
 adc #1
 jsr pool_cell
 lda v_base
 sta v_right
 lda v_base+1
 sta v_right+1
 lda v_sy
 and #15
 cmp #5
 bcc pool_setup_done
 lda v_cell
 clc
 adc #15
 jsr pool_cell
 lda v_base
 sta v_saved_right
 lda v_base+1
 sta v_saved_right+1
pool_setup_done:
 rts
video_restore:
 jsr pool_bank_start
 sta pool_start
 ldx pool_bank
 clc
 adc pool_count,x
 sta pool_limit
 lda #0
 sta pool_count,x
 ldx pool_start
pool_restore_next:
 cpx pool_limit
 beq pool_restore_done
 ldy pool_cells,x
 jsr pool_home
 inx
 bne pool_restore_next
pool_restore_done:
 rts
pool_home:
 lda home_codes,y
.global pool_unpack_home
pool_unpack_home:
 asl
 adc #$80
 rol
 asl
 adc #$80
 rol
 sta $0200,y
 lda $9400,y
 sta $9600,y
 rts
pool_bank_start:
 lda pool_bank
 beq pool_bank_zero
 lda #24
pool_bank_zero:
 rts
video_sprites:
 jsr video_update_begin
 jmp video_update_end
video_update_begin:
 jsr pool_reuse_guard
 lda pool_epoch
 clc
 adc #2
 cmp #16
 bcc pool_epoch_ready
 lda #0
 ldx #196
pool_clear_map:
 dex
 sta $96c4,x
 bne pool_clear_map
 lda #2
pool_epoch_ready:
 sta pool_epoch
 lda pool_bank
 eor #1
 sta pool_bank
 tax
 lda #0
 sta pool_count,x
 sta pool_failed
 jsr pool_bank_start
 sta pool_start
 txa
 lsr
 lda #$80
 ror
 sta pool_next_low
 txa
 adc #$1c
 sta pool_code_end
 rts
video_update_end:
 lda maze_flash
 beq pool_no_flash
 jsr bitmap_maze_flash
 lda #0
 sta maze_flash
pool_no_flash:
 jsr pool_actors
 lda pool_failed
 beq pool_publish
 lda pool_bank
 eor #1
 sta pool_bank
 rts
.global pool_publish,pool_published
pool_publish:
 ldy pool_bank
 lda pool_count,y
 clc
 adc pool_start
 sta pool_limit
 clc
 adc #196
 sta pool_code_end
 lda pool_start
 clc
 adc #196
 sta pool_code_base
 ldx pool_start
pool_publish_next:
 cpx pool_limit
 beq pool_settle
 ldy pool_cells,x
 txa
 clc
 adc #196
 sta $0200,y
 lda pool_colours,x
 sta $9600,y
 inx
 bne pool_publish_next
pool_settle:
 lda pool_bank
 eor #1
 tay
 lda pool_start
 eor #24
 tax
 clc
 adc pool_count,y
 sta pool_limit
pool_settle_next:
 cpx pool_limit
 beq pool_published
 ldy pool_cells,x
 lda $0200,y
 cmp pool_code_base
 bcc pool_settle_home
 cmp pool_code_end
 bcc pool_settle_skip
pool_settle_home:
 jsr pool_home
pool_settle_skip:
 inx
 bne pool_settle_next
pool_published:
 rts
pool_draw_ghost:
 lda pool_ghost_sources,x
 sta pool_ghost_left+1
 clc
 adc #10
 sta pool_ghost_right+1
 lda pool_ghost_sources+1,x
 sta pool_ghost_left+2
 adc #0
 sta pool_ghost_right+2
 ldx #0
 lda #$e8
 lsr v_flip
 bcc pool_ghost_forward
 ldx #9
 lda #$ca
pool_ghost_forward:
 sta pool_ghost_step
 lda v_sy
 and #15
 tay
 lda #10
 sta v_temp
pool_ghost_row:
 iny
 cpy #16
 bne pool_ghost_inside
 lda v_save
 sta v_addr
 lda v_save+1
 sta v_addr+1
 lda v_saved_right
 sta v_right
 lda v_saved_right+1
 sta v_right+1
 ldy #0
pool_ghost_inside:
 lda (v_addr),y
pool_ghost_left:
 ora $ffff,x
 sta (v_addr),y
 lda (v_right),y
pool_ghost_right:
 ora $ffff,x
 sta (v_right),y
pool_ghost_step:
 inx
 dec v_temp
 bne pool_ghost_row
 rts
pool_ghost_sources:
.set k,0
.rept 16
 .word arcade_ghost_shifted+k*20
.set k,k+1
.endr
