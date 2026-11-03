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
#if defined(GHOST_SHADOW) || defined(BEAM_FOLLOW)
.global cache_dirty
#endif
#ifdef BEAM_FOLLOW
.global new_x,new_y,sprite_mark,restore_start,v_sx,v_sy
#endif
/* Index zero is unused by the six even actor slots. A bit covers two
   hardware colour rows, so the seven visible bands fit in one byte. */
.set dirty_bands,cache_x
#ifdef ACTOR_COMMIT
/* Odd cache slots are unused by the six even arcade actor slots. Bounds
   include old/new byte columns and whole colour rows, with inclusive ends. */
.set group_left,cache_x+1
.set group_right,cache_y+1
.set group_top,cache_attr+1
.set group_bottom,cache_pal+1
#endif
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
#ifdef ACTOR_COMMIT
group_select: .zero 1
group_single: .zero 1
#endif
.section .text.sprites,"ax",@progbits
.global video_refresh,video_frame_begin,video_frame_end,video_batch_begin,video_batch_end
/* Full rebuilds are progressive. Remove actors once, then keep their underlays
   invalid until the background converges. Only completion counts as a frame. */
#ifndef BEAM_FOLLOW
video_refresh:
 lda rebuild_phase
 beq video_frame_begin
 jsr video_background
 lda full_dirty
 bne video_batch_end
 jsr video_sprites
 jmp video_frame_end
video_frame_begin:
#ifdef ACTOR_COMMIT
 lda full_dirty
 ora maze_flash
 bne commit_legacy
 lda #0
 sta group_select
 sta group_single
 jsr sprite_mark
 jsr sprite_groups
 lda dirty_count
 beq commit_next
 /* Every actor affected by queued tiles belongs to this first transaction.
    Independent components stay visible while the background is painted. */
 jsr restore_start
 jsr video_background
 jsr video_update_end
commit_next:
 ldx #2
commit_find:
 lda cache_dirty,x
 bmi commit_group
 inx
 inx
 cpx #14
 bne commit_find
 jmp video_frame_end
commit_group:
 and #63
 sta group_select
 sec
 sbc #1
 and group_select
 bne commit_cluster
 /* A singleton enters each actor kernel directly, avoiding six-slot scans. */
 stx v_off
 txa
 lsr
 tay
 lda actor_records-1,y
 tax
 lda #1
 sta group_single
 jsr restore_actor
 jsr sprite_actor
 lda #0
 sta group_single
 jmp commit_next
commit_cluster:
 jsr restore_start
 jsr video_update_end
 jmp commit_next
commit_legacy:
#endif
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
#endif
.global video_restore,video_sprites,video_update_begin,video_update_end
video_restore:
#ifdef GHOST_SHADOW
 jsr shadow_end
#endif
 jsr sprite_force_all
 jmp restore_start
video_update_begin:
#ifdef ACTOR_COMMIT
 lda #0
 sta group_single
 lda #255
 sta group_select
#endif
 jsr sprite_mark
#ifdef GHOST_SHADOW
 jsr shadow_begin
#endif
restore_start:
 lda #2
 sta v_off
 ldx #180
restore_actor:
 stx v_actor
 ldy v_off
 lda cache_dirty,y
#ifdef ACTOR_COMMIT
 and group_select
#endif
 beq restore_advance
 lda under+3,x
 beq restore_advance
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
 bcc restore_clear
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
 beq restore_clear
 iny
 lda under+35,x
 sta $9600,y
restore_clear:
 lda #0
 sta under+3,x
restore_advance:
#ifdef ACTOR_COMMIT
 lda group_single
 bne restore_done
#endif
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
#ifdef ACTOR_COMMIT
 and group_select
#endif
 bne sprite_changed
 jmp sprite_advance
sprite_changed:
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
#ifdef BEAM_FOLLOW
 lda v_sx
 sta under+4,x
 lda v_sy
 sta under+6,x
#endif
#ifdef ACTOR_COMMIT
 lda v_col
 clc
 adc #1
 sta under+4,x
 lda v_sy
 lsr
 lsr
 lsr
 lsr
 sta under+6,x
#endif
 lda v_flags
 sta under+5,x
 lda v_sy
 and #15
 sta under+7,x
 /* Save the cell colors before writing this actor. */
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
#ifdef ACTOR_COMMIT
 lda group_single
 beq sprite_advance_all
 ldx v_off
 lda #0
 sta cache_dirty,x
 rts
sprite_advance_all:
#endif
 lda v_actor
 clc
 adc #36
 sta v_actor
 dec v_off
 dec v_off
 beq sprites_done
 jmp sprite_actor
sprites_done:
#ifdef ACTOR_COMMIT
 ldx #12
commit_clear:
 lda cache_dirty,x
 and group_select
 beq commit_clear_next
 lda #0
 sta cache_dirty,x
commit_clear_next:
 dex
 dex
 bne commit_clear
#endif
#ifdef GHOST_SHADOW
 jsr shadow_end
#endif
 rts

/* A cell color can affect both scanline columns and two character rows.
   Propagate changes through overlapping old/new footprints before restoring. */
sprite_mark:
 jsr score_expand
 lda #0
 sta v_actor
 sta dirty_bands
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
mark_store:
 sta cache_dirty,x
 lda v_actor
 clc
 adc #36
 sta v_actor
 dex
 dex
 beq mark_propagate
 jmp mark_actor
mark_propagate:
#ifdef ACTOR_COMMIT
 /* The component pass supplies propagation on the transaction path. */
 lda group_select
 beq mark_commit_start
#endif
 lda #0
 sta v_temp
 ldx #12
mark_candidate:
 lda cache_dirty,x
 bne mark_next_candidate
 lda $0c21,x
 and #31
 beq mark_next_candidate
 ldy #12
mark_other:
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
mark_commit_start:
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
 jmp score_unexpand
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
#ifdef ACTOR_COMMIT
 lda #0
 sta group_single
 lda #255
 sta group_select
#endif
 ldx #12
 lda #1
force_actor:
 sta cache_dirty,x
 dex
 dex
 bne force_actor
 rts

#ifdef ACTOR_COMMIT
.section .text.sprites,"ax",@progbits
actor_records: .byte 180,144,108,72,36,0
/* Main-thread only. A/X/Y and v_* scratch are clobbered. cache_dirty becomes
   a component mask: bits 0..5 actors, bit 6 background, bit 7 needs repaint.
   Disjoint components can be restored and repainted in either order. */
sprite_groups:
 lda #0
 sta v_actor
 ldx #12
group_actor:
 lda cache_dirty,x
 beq group_clean
 lda #128
group_clean:
 sta v_temp
 txa
 lsr
 tay
 lda bit_masks-1,y
 ora v_temp
 sta cache_dirty,x
 lda #255
 sta group_left,x
 sta group_top,x
 lda #0
 sta group_right,x
 sta group_bottom,x
 lda $0c21,x
 and #31
 beq group_old
 lda new_x,x
 cmp #112
 bcc group_new
 cmp #249
 bcc group_old
group_new:
 cmp #128
 bcs group_new_left
 lsr
 lsr
 lsr
 clc
 adc #1
 bne group_new_column
group_new_left:
 lda #0
group_new_column:
 sta group_left,x
 clc
 adc #1
 sta group_right,x
 lda new_y,x
 lsr
 lsr
 lsr
 lsr
 sta group_top,x
 lda new_y,x
 clc
 adc #11
 lsr
 lsr
 lsr
 lsr
 sta group_bottom,x
group_old:
 ldy v_actor
 lda under+3,y
 beq group_band
 lda under+4,y
 cmp group_left,x
 bcs group_old_right
 sta group_left,x
group_old_right:
 clc
 adc #1
 cmp group_right,x
 bcc group_old_row
 sta group_right,x
group_old_row:
 lda under+6,y
 cmp group_top,x
 bcs group_old_bottom
 sta group_top,x
group_old_bottom:
 lda under+7,y
 cmp #5
 lda under+6,y
 adc #0
 cmp group_bottom,x
 bcc group_band
 sta group_bottom,x
group_band:
 lda group_top,x
 cmp #255
 beq group_advance
 lsr
 tay
 lda bit_masks,y
 sta v_temp
 lda group_bottom,x
 lsr
 tay
 /* (1 << (last band + 1)) - (1 << first band), including both ends. */
 lda bit_masks+1,y
 sec
 sbc v_temp
 and dirty_bands
 beq group_advance
 lda cache_dirty,x
 ora #64
 sta cache_dirty,x
group_advance:
 lda v_actor
 clc
 adc #36
 sta v_actor
 dex
 dex
 beq group_pairs
 jmp group_actor
group_pairs:
 /* Visit each pair once; merging rewrites every member's component mask. */
 ldx #12
group_pair_actor:
 txa
 tay
group_pair:
 dey
 dey
 beq group_pair_next
 lda cache_dirty,x
 cmp cache_dirty,y
 beq group_pair
 lda group_right,x
 cmp group_left,y
 bcc group_pair
 lda group_right,y
 cmp group_left,x
 bcc group_pair
 lda group_bottom,x
 cmp group_top,y
 bcc group_pair
 lda group_bottom,y
 cmp group_top,x
 bcc group_pair
 lda cache_dirty,x
 ora cache_dirty,y
 sta v_temp
 stx v_actor
 sty v_off
 ldx #12
group_merge:
 lda cache_dirty,x
 and v_temp
 and #63
 beq group_merge_next
 lda v_temp
 sta cache_dirty,x
group_merge_next:
 dex
 dex
 bne group_merge
 ldx v_actor
 ldy v_off
 jmp group_pair
group_pair_next:
 dex
 dex
 cpx #2
 bne group_pair_actor
 lda #0
 sta group_select
 ldx #12
group_background:
 lda cache_dirty,x
 and #64
 beq group_background_next
 lda cache_dirty,x
 and #63
 ora group_select
 sta group_select
group_background_next:
 dex
 dex
 bne group_background
 rts

#endif
