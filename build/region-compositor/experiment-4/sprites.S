/* Native compositor frontend. The arcade buffers remain in arcade units.
   Six 36-byte underlays retain the original sprite priority and restore order. */
.section .work,"aw",@nobits
.global under
under: .zero 216
.section .sprite_cache,"aw",@nobits
cache_x: .zero 14
cache_y: .zero 14
cache_attr: .zero 14
cache_pal: .zero 14
new_x: .zero 14
new_y: .zero 14
cache_dirty: .zero 14
.global sprite_compose
.set sprite_compose,cache_dirty+1
.set compose_candidate,cache_dirty+3
/* Index zero is unused by the six even actor slots. A bit covers two
   hardware colour rows, so the seven visible bands fit in one byte. */
.set dirty_bands,cache_x
.section .zp.bss,"aw",@nobits
v_actor: .zero 1
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
.section .text.sprites,"ax",@progbits
.global video_refresh,video_frame_begin,video_frame_end,video_batch_begin,video_batch_end
/* Full rebuilds are progressive. Remove actors once, then keep their underlays
   invalid until the background converges. Only completion counts as a frame. */
video_refresh:
 lda rebuild_phase
 beq video_frame_begin
 jsr video_background
 lda full_dirty
 bne video_batch_end
 jsr video_sprites
 jmp video_frame_end
video_frame_begin:
 jsr video_update_begin
video_batch_begin:
 jsr video_background
 lda full_dirty
 bne video_batch_end
 jsr video_update_end
video_frame_end:
 rts
video_batch_end:
 rts
.global video_restore,video_sprites,video_update_begin,video_update_end
video_restore:
 jsr sprite_force_all
 jmp restore_start
video_update_begin:
 jsr sprite_mark
restore_start:
 lda #2
 sta v_off
 ldx #180
restore_actor:
 stx v_actor
 ldy v_off
 lda cache_dirty,y
 beq restore_advance
 bmi restore_advance
 lda under+3,x
 beq restore_advance
 jsr sprite_restore_actor
restore_advance:
 inc v_off
 inc v_off
 txa
 sec
 sbc #36
 tax
 bcc restore_done
 jmp restore_actor
restore_done:
 rts
sprite_restore_actor:
 lda under,x
 sta v_addr
 lda under+1,x
 sta v_addr+1
 txa
 clc
 adc #<(under+8)
 sta v_save
 lda #>(under+8)
 adc #0
 sta v_save+1
 lda under+5,x
 sta v_flags
 jsr bitmap_erase
 ldx v_actor
 jsr sprite_restore_colors
 lda #0
 sta under+3,x
 rts
sprite_restore_colors:
 ldy under+2,x
 lda v_flags
 and #1
 beq restore_no_left
 lda under+32,x
 sta $9600,y
restore_no_left:
 lda v_flags
 and #2
 beq restore_no_right
 iny
 lda under+33,x
 sta $9600,y
 dey
restore_no_right:
 lda under+7,x
 cmp #5
 bcc restore_colors_done
 tya
 clc
 adc #14
 tay
 lda v_flags
 and #1
 beq restore_no_lower_left
 lda under+34,x
 sta $9600,y
restore_no_lower_left:
 lda v_flags
 and #2
 beq restore_colors_done
 iny
 lda under+35,x
 sta $9600,y
restore_colors_done:
 rts

video_sprites:
 jsr sprite_mark
 jsr sprite_force_all
video_update_end:
 lda maze_flash
 beq sprite_flash_done
 jsr bitmap_maze_flash
 lda #0
 sta maze_flash
sprite_flash_done:
 lda #0
 sta v_actor
 lda #12
 sta v_off
sprite_actor:
 ldx v_off
 lda cache_dirty,x
 bne sprite_changed
 jmp sprite_advance
sprite_changed:
 lda $0c21,x
 and #31
 bne sprite_visible
 jmp sprite_advance
sprite_visible:
 sta v_pal
 lda $0c20,x
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
 ldx v_col
 bmi sprite_left_address
 lda column_lo,x
 clc
 adc v_sy
 sta v_addr
 lda column_hi,x
 adc #0
 jmp sprite_address_ready
sprite_left_address:
 lda #$20
 clc
 adc v_sy
 sta v_addr
 lda #$0f
 adc #0
sprite_address_ready:
 sta v_addr+1
 lda v_pal
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
 /* Source offset = frame * 12, added to the normal or eyes-only atlas. */
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
 ldx v_actor
 lda v_addr
 sta under,x
 lda v_addr+1
 sta under+1,x
 lda v_cell
 sta under+2,x
 lda #1
 sta under+3,x
 lda v_flags
 sta under+5,x
 lda v_sy
 and #15
 sta under+7,x
 /* Save the cell colors before writing this actor. */
 ldy v_off
 lda cache_dirty,y
 sta sprite_compose
 bmi sprite_colors_saved
 ldy v_cell
 lda $9600,y
 sta under+32,x
 iny
 lda $9600,y
 sta under+33,x
 lda under+7,x
 cmp #5
 bcc sprite_colors_saved
 tya
 clc
 adc #13
 tay
 lda $9600,y
 sta under+34,x
 iny
 lda $9600,y
 sta under+35,x
sprite_colors_saved:
 txa
 clc
 adc #<(under+8)
 sta v_save
 lda #>(under+8)
 adc #0
 sta v_save+1
 lda v_sx
 and #7
 sta v_shift
 lda v_attr
 and #3
 sta v_flip
 lda v_code
 cmp #28
 bcc sprite_generic_draw
 cmp #30
 bcc sprite_fright_shift
 cmp #32
 bcc sprite_generic_draw
 cmp #38
 bcs sprite_generic_draw
 lda v_code
 and #1
 asl
 asl
 asl
 ora v_shift
 jmp sprite_shift_ready
sprite_fright_shift:
 lda v_code
 and #1
 asl
 asl
 asl
 ora v_shift
 ora #16
sprite_shift_ready:
 tax
 lda v_pal
 cmp #25
 beq sprite_generic_draw
 lda v_flags
 cmp #3
 bne sprite_generic_draw
 jsr bitmap_draw_ghost
 jmp sprite_drawn
sprite_generic_draw:
 jsr bitmap_draw
sprite_drawn:
 ldx v_actor
 lda sprite_compose
 bpl sprite_colors_restored
 jsr sprite_restore_colors
sprite_colors_restored:
 ldy v_off
 lda #1
 sta cache_dirty,y
 ldy v_cell
 lda v_flags
 and #1
 beq sprite_no_left_color
 lda v_color
 sta $9600,y
sprite_no_left_color:
 lda v_flags
 and #2
 beq sprite_no_right_color
 /* An aligned mask has no pixels in the right-hand cell. */
 lda v_shift
 beq sprite_no_right_color
 iny
 lda v_color
 sta $9600,y
 dey
sprite_no_right_color:
 lda under+7,x
 cmp #5
 bcc sprite_advance
 tya
 clc
 adc #14
 tay
 lda v_flags
 and #1
 beq sprite_no_lower_left_color
 lda v_color
 sta $9600,y
sprite_no_lower_left_color:
 lda v_flags
 and #2
 beq sprite_advance
 lda v_shift
 beq sprite_advance
 iny
 lda v_color
 sta $9600,y
sprite_advance:
 ldy v_off
 lda cache_dirty,y
 bpl sprite_advanced
 /* A newly invisible mask must still remove its deferred old image. */
 ldx v_actor
 jsr sprite_restore_actor
sprite_advanced:
 lda v_actor
 clc
 adc #36
 sta v_actor
 dec v_off
 dec v_off
 beq sprites_done
 jmp sprite_actor
sprites_done:
 rts

/* A cell color can affect both scanline columns and two character rows.
   Propagate changes through overlapping old/new footprints before restoring. */
sprite_mark:
 lda #0
 sta v_actor
 sta dirty_bands
 sta compose_candidate
 lda full_dirty
 ora maze_flash
 bne mark_no_background
 lda dirty_count
 beq mark_no_background
 jsr sprite_background_bands
mark_no_background:
 ldx #12
mark_actor:
 lda #239
 cpx #5
 bcs mark_x_origin
 lda #238
mark_x_origin:
 sec
 sbc $0c30,x
 bcs mark_positive_x
 sec
 ror
 jmp mark_x_ready
mark_positive_x:
 lsr
mark_x_ready:
 sta new_x,x
 lda $0c31,x
 sta v_sy
 lsr
 lsr
 clc
 adc #204
 sec
 sbc v_sy
 sta new_y,x
 lda full_dirty
 ora maze_flash
 bne mark_dirty
 lda $0c20,x
 cmp cache_attr,x
 bne mark_dirty
 lda $0c21,x
 and #31
 cmp cache_pal,x
 bne mark_dirty
 lda new_x,x
 cmp cache_x,x
 bne mark_dirty
 lda new_y,x
 cmp cache_y,x
 bne mark_dirty
 /* HUD/dot writes elsewhere must not erase an otherwise unchanged actor.
    A conservative row test also covers colour-cell sharing. */
 lda dirty_count
 beq mark_underlay
 jsr sprite_background_overlap
 bne mark_dirty
mark_underlay:
 /* An explicit restore can have erased a still-current cached actor. */
 ldy v_actor
 lda under+3,y
 bne mark_clean
 lda cache_pal,x
 beq mark_clean
 lda new_x,x
 cmp #112
 bcc mark_dirty
 cmp #249
 bcs mark_dirty
mark_clean:
 lda #0
 beq mark_store
mark_dirty:
 lda #1
 sta cache_dirty,x
 /* An isolated update can compose directly from its retained underlay.
    The bitmap row and columns must stay valid. */
 lda compose_candidate
 bne mark_next_slot
 lda new_y,x
 cmp cache_y,x
 bne mark_next_slot
 lda new_x,x
 eor cache_x,x
 and #$f8
 bne mark_next_slot
 lda $0c21,x
 and #31
 beq mark_next_slot
 lda full_dirty
 ora maze_flash
 bne mark_next_slot
 lda dirty_count
 beq mark_compose_background
 jsr sprite_background_overlap
 bne mark_next_slot
mark_compose_background:
 ldy v_actor
 lda under+3,y
 beq mark_next_slot
 stx compose_candidate
 lda #$81
mark_store:
 sta cache_dirty,x
mark_next_slot:
 lda v_actor
 clc
 adc #36
 sta v_actor
 dex
 dex
 beq mark_propagate
 jmp mark_actor
mark_propagate:
 lda #0
 sta v_temp
 ldx #12
mark_candidate:
 lda cache_dirty,x
 cmp #1
 beq mark_next_candidate
 stx v_off
 lda $0c21,x
 and #31
 beq mark_next_candidate
 ldy #12
mark_other:
 cpy v_off
 beq mark_next_other
 lda cache_dirty,y
 beq mark_next_other
 lda new_x,x
 sec
 sbc cache_x,y
 clc
 adc #15
 cmp #31
 bcs mark_new_footprint
 lda new_y,x
 sec
 sbc cache_y,y
 clc
 adc #31
 cmp #63
 bcc mark_overlap
mark_new_footprint:
 lda new_x,x
 sec
 sbc new_x,y
 clc
 adc #15
 cmp #31
 bcs mark_next_other
 lda new_y,x
 sec
 sbc new_y,y
 clc
 adc #31
 cmp #63
 bcs mark_next_other
mark_overlap:
 lda #1
 sta cache_dirty,x
 sta v_temp
 bne mark_next_candidate
mark_next_other:
 dey
 dey
 bne mark_other
mark_next_candidate:
 dex
 dex
 bne mark_candidate
 lda v_temp
 bne mark_propagate
 ldx #12
mark_commit:
 lda new_x,x
 sta cache_x,x
 lda new_y,x
 sta cache_y,x
 lda $0c20,x
 sta cache_attr,x
 lda $0c21,x
 and #31
 sta cache_pal,x
 dex
 dex
 bne mark_commit
 rts
/* Build the dirty tile bands once, while all actors are still visible.
   The arcade's side columns map to the top/bottom HUD. */
sprite_background_bands:
 lda dirty_count
 asl
 tax
background_band_tile:
 dex
 dex
 stx v_off
 lda dirty_queue+1,x
 asl
 asl
 asl
 sta v_sy
 lda dirty_queue,x
 lsr
 lsr
 lsr
 lsr
 lsr
 ora v_sy
 cmp #2
 bcc background_overlap_bottom
 cmp #30
 bcs background_overlap_top
 lda dirty_queue,x
 and #31
 clc
 adc #2
 jmp background_overlap_y
background_overlap_bottom:
 clc
 adc #34
 bne background_overlap_y
background_overlap_top:
 sec
 sbc #30
background_overlap_y:
 asl
 sta v_sy
 asl
 clc
 adc v_sy
 sta v_sx
 lsr
 lsr
 lsr
 lsr
 lsr
 tay
 lda bit_masks,y
 sta v_sy
 lda v_sx
 and #31
 cmp #27
 bcc background_band_single
 lda v_sy
 asl
 ora v_sy
 sta v_sy
background_band_single:
 lda v_sy
 ora dirty_bands
 sta dirty_bands
 ldx v_off
 bne background_band_tile
 rts
/* X is the actor slot. Pixel spans imply all of their shared colour rows
   because band boundaries coincide with hardware cell boundaries. */
sprite_background_overlap:
 lda new_y,x
 lsr
 lsr
 lsr
 lsr
 lsr
 tay
 lda bit_masks,y
 sta v_sx
 lda new_y,x
 and #31
 cmp #21
 bcc background_overlap_done
 lda v_sx
 asl
 ora v_sx
 sta v_sx
background_overlap_done:
 lda v_sx
 and dirty_bands
 rts
sprite_force_all:
 ldx #12
 lda #1
force_actor:
 sta cache_dirty,x
 dex
 dex
 bne force_actor
 rts
