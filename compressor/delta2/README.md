
Delta2 Compressor
=================


Parameters
----------

* max_byte_size: the maximum number of key and value characters that the compressor is allowed to buffer.
* max_entries: the maximum number of slots in the LRU.
* hg_adjust: when set, entries of the current header-group are reinserted into the LRU. This is intended to ensure that these values stay alive in the LRU for longer and also intended to casue the indices which refer to these values to be bunched together.
* implict_hg_add: when set, items being added via sclone or skvsto have their indices automatically inserted into the current header-group.
* small_index: when set, causes the index size (on the wire) to become one byte, down from two bytes.  This indirectly causes the maximum number of items in the LRU to drop to ~200 elements (though smaller values are still honored if set via max_entries, above).
* refcnt_vals: when set, value strings are refcounted. This only matters when/if hg_adjust is enabled.
* only_etoggles: when set, the compressor is forced to make explicit backreferences to everything, and thus acts similarly to the headerdiff encoder.
* varint_encoding: when set, indices are encoded as variable-length integers. For values <= 15, 4 bits will be used. For values >15 and <= 255, 12 bits will be used. For values >255 and <= 16535, 28 bits will be used, and for values >16535, 60 bits will be used. For this to be effective, obviously, the expectation is that most integer values are quite small.
# idx_from_end: when set, indices are encoded as distance-from-the-newest element. In conjunection with varint_encoding, this should yield a space savings on the wire.


