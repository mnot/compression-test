
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
