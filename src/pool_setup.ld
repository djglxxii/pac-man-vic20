/* Two pointer bits store the class in the optional sprite descriptors. */
/* Retain the independent packed class data for the real-display observer. */
EXTERN(arcade_sprite_class)
ASSERT((arcade_sprites & 3) == 0, "Sprite descriptors require four-byte artwork alignment")
ASSERT(pool_sprite_descriptors_end - pool_sprite_descriptors == 128, "Sprite descriptors must cover all 64 frames")
