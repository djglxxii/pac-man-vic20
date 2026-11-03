/* Original-hires actor groups updated in a raster-safe window. Main thread
   only. A/X/Y and the existing v_* renderer temporaries are scratch. Group
   state survives calls to the original eraser/painter; the timer IRQ is intact.
   Coordinates cover whole 8x16 colour cells, old AND new footprints. */
.section .beam_state,"aw",@nobits
.global beam_state,beam_state_end,beam_frames,beam_protected,beam_fallback
.global beam_masks,beam_early,beam_ends,beam_tops,beam_budgets,beam_group
.global beam_mask
beam_state:
beam_left: .zero 6
beam_right: .zero 6
beam_top: .zero 6
beam_bottom: .zero 6
beam_masks: .zero 6
beam_early: .zero 6
beam_ends: .zero 6
beam_tops: .zero 6
beam_budgets: .zero 6
beam_pending: .zero 1
beam_count: .zero 1
beam_group: .zero 1
beam_mask: .zero 1
beam_l: .zero 1
beam_r: .zero 1
beam_t: .zero 1
beam_b: .zero 1
beam_budget: .zero 1
beam_changed: .zero 1
beam_index: .zero 1
beam_now: .zero 1
beam_frames: .zero 2
beam_protected: .zero 2
beam_fallback: .zero 2
beam_state_end:
.zeropage v_actor,v_off,v_sx,v_sy,v_temp

.section .text.beam,"ax",@progbits
.global beam_init,video_refresh,video_frame_begin,video_frame_end,video_batch_begin,video_batch_end
beam_init:
 lda #0
 ldx #(beam_state_end-beam_state-1)
beam_clear:
 sta beam_state,x
 dex
 bpl beam_clear
 rts

video_refresh:
 lda rebuild_phase
 beq video_frame_begin
 jsr video_background
 lda full_dirty
 beq beam_rebuild_ready
 rts
beam_rebuild_ready:
 jsr video_sprites
 jmp video_frame_end
video_frame_begin:
video_batch_begin:
 lda full_dirty
 ora maze_flash
 ora dirty_count
 beq beam_normal
 /* Background edits and global effects retain the original transaction. */
 jsr video_update_begin
 jsr video_background
 lda full_dirty
 beq beam_background_ready
 rts
beam_background_ready:
 jsr video_update_end
 jmp video_frame_end
beam_normal:
 jsr sprite_mark
 jsr beam_bounds
 jsr beam_groups
beam_choose:
 lda beam_count
 bne beam_choose_active
 jmp beam_complete
beam_choose_active:
 lda $9004
 sta beam_now
 ldx #5
beam_find_ready:
 lda beam_masks,x
 beq beam_next_choice
 lda beam_early,x
 cmp #255
 beq beam_ready
 cmp beam_ends,x
 bcs beam_safe_middle
 lda beam_now
 cmp beam_ends,x
 bcs beam_ready
 cmp beam_early,x
 bcc beam_ready
 bcs beam_next_choice
beam_safe_middle:
 lda beam_now
 cmp beam_ends,x
 bcc beam_next_choice
 cmp beam_early,x
 bcc beam_ready
beam_next_choice:
 dex
 bpl beam_find_ready
 jmp beam_choose
beam_ready:
 stx beam_group
 lda beam_masks,x
 sta beam_mask
 ldx #5
beam_select_flags:
 lda beam_mask
 and beam_bits,x
 ldy beam_slots,x
 sta cache_dirty,y
 dex
 bpl beam_select_flags
.global beam_group_begin,beam_group_end
beam_group_begin:
 jsr restore_start
 jsr video_update_end
beam_group_end:
 ldx beam_group
 lda beam_early,x
 cmp #255
 beq beam_ungated
 inc beam_protected
 bne beam_retire
 inc beam_protected+1
 jmp beam_retire
beam_ungated:
 inc beam_fallback
 bne beam_retire
 inc beam_fallback+1
beam_retire:
 lda #0
 sta beam_masks,x
 dec beam_count
 jmp beam_choose
beam_complete:
 inc beam_frames
 bne video_frame_end
 inc beam_frames+1
video_frame_end:
 rts
video_batch_end:
 rts
beam_slots: .byte 2,4,6,8,10,12
beam_records: .byte 180,144,108,72,36,0
beam_bits: .byte 1,2,4,8,16,32

/* Union an actor's old and new colour rectangles. An absent footprint has
   left=255. X is actor index, preserved by beam_add_bounds. */
.section .beam_code,"ax",@progbits
beam_bounds:
 lda #0
 sta beam_pending
 ldx #5
beam_bound_actor:
 stx beam_index
 lda #255
 sta beam_left,x
 sta beam_top,x
 lda #0
 sta beam_right,x
 sta beam_bottom,x
 sta beam_masks,x
 ldy beam_slots,x
 lda cache_dirty,y
 beq beam_bound_next
 lda $0c21,y
 and #31
 beq beam_bound_old
 lda new_x,y
 cmp #112
 bcc beam_bound_new
 cmp #249
 bcc beam_bound_old
beam_bound_new:
 sta v_sx
 lda new_y,y
 sta v_sy
 jsr beam_add_bounds
beam_bound_old:
 ldy beam_records,x
 lda under+3,y
 beq beam_bound_done
 lda under+4,y
 sta v_sx
 lda under+6,y
 sta v_sy
 jsr beam_add_bounds
beam_bound_done:
 lda beam_left,x
 cmp #255
 beq beam_bound_next
 lda beam_bits,x
 ora beam_pending
 sta beam_pending
beam_bound_next:
 dex
 bpl beam_bound_actor
 rts
beam_add_bounds:
 lda v_sx
 cmp #128
 bcc beam_positive
 lda #0
 beq beam_column
beam_positive:
 lsr
 lsr
 lsr
beam_column:
 cmp beam_left,x
 bcs beam_right_bound
 sta beam_left,x
beam_right_bound:
 ldy v_sx
 bmi beam_right_clipped
 clc
 adc #1
 cmp #14
 bcc beam_right_ready
 lda #13
 bne beam_right_ready
beam_right_clipped:
 lda #0
beam_right_ready:
 cmp beam_right,x
 bcc beam_top_bound
 sta beam_right,x
beam_top_bound:
 lda v_sy
 lsr
 lsr
 lsr
 lsr
 cmp beam_top,x
 bcs beam_bottom_bound
 sta beam_top,x
beam_bottom_bound:
 lda v_sy
 clc
 adc #11
 lsr
 lsr
 lsr
 lsr
 cmp beam_bottom,x
 bcc beam_bounds_return
 sta beam_bottom,x
beam_bounds_return:
 rts

/* Form independent groups, conservatively merging intersecting union boxes.
   Keep original reverse-erase/forward-paint priority inside every group. */
.section .text.beam,"ax",@progbits
beam_groups:
 lda #0
 sta beam_count
beam_new_group:
 lda beam_pending
 bne beam_new_group_active
 rts
beam_new_group_active:
 lda #255
 sta beam_l
 sta beam_t
 lda #0
 sta beam_r
 sta beam_b
 sta beam_mask
 lda #8
 sta beam_budget
beam_group_scan:
 lda #0
 sta beam_changed
 ldx #5
beam_group_candidate:
 lda beam_bits,x
 and beam_pending
 beq beam_group_next
 lda beam_mask
 beq beam_join
 lda beam_left,x
 cmp beam_r
 bcc beam_test_right
 beq beam_test_right
 bne beam_group_next
beam_test_right:
 lda beam_l
 cmp beam_right,x
 bcc beam_test_top
 beq beam_test_top
 bne beam_group_next
beam_test_top:
 lda beam_top,x
 cmp beam_b
 bcc beam_test_bottom
 beq beam_test_bottom
 bne beam_group_next
beam_test_bottom:
 lda beam_t
 cmp beam_bottom,x
 bcc beam_join
 bne beam_group_next
beam_join:
 lda beam_bits,x
 eor beam_pending
 sta beam_pending
 lda beam_bits,x
 ora beam_mask
 sta beam_mask
 lda #1
 sta beam_changed
 lda beam_budget
 clc
 adc #20
 sta beam_budget
 lda beam_left,x
 cmp beam_l
 bcs beam_join_right
 sta beam_l
beam_join_right:
 lda beam_right,x
 cmp beam_r
 bcc beam_join_top
 sta beam_r
beam_join_top:
 lda beam_top,x
 cmp beam_t
 bcs beam_join_bottom
 sta beam_t
beam_join_bottom:
 lda beam_bottom,x
 cmp beam_b
 bcc beam_group_next
 sta beam_b
beam_group_next:
 dex
 bmi beam_group_scanned
 jmp beam_group_candidate
beam_group_scanned:
 lda beam_changed
 beq beam_group_finish
 jmp beam_group_scan
beam_group_finish:
 ldx beam_count
 lda beam_mask
 sta beam_masks,x
 lda beam_budget
 sta beam_budgets,x
 lda beam_t
 asl
 asl
 asl
 clc
 adc #16
 sta beam_tops,x
 lda beam_b
 asl
 asl
 asl
 clc
 adc #25
 sta beam_ends,x
 sec
 sbc beam_tops,x
 clc
 adc beam_budget
 cmp #131
 bcs beam_group_too_large
 lda beam_tops,x
 sec
 sbc beam_budget
 bcs beam_early_ready
 adc #131
beam_early_ready:
 sta beam_early,x
 jmp beam_group_saved
beam_group_too_large:
 lda #255
 sta beam_early,x
beam_group_saved:
 inc beam_count
 jmp beam_new_group
beam_groups_done:
 rts
