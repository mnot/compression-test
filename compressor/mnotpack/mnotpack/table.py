# -*- coding: utf-8 -*-
# flake8: noqa
from collections import deque
import logging

from .exceptions import InvalidTableIndex

log = logging.getLogger(__name__)


def table_entry_size(value):
    """
    Calculates the size of a single entry

    This size is mostly irrelevant to us and defined
    specifically to accommodate memory management for
    lower level implementations. The 32 extra bytes are
    considered the "maximum" overhead that would be
    required to represent each entry in the table.

    See RFC7541 Section 4.1
    """
    return 16 + len(value)


class HeaderTable(object):
    """
    Implements the combined static and dynamic header table

    The name and value arguments for all the functions
    should ONLY be byte strings (b'') however this is not
    strictly enforced in the interface.

    See RFC7541 Section 2.3
    """
    #: Default maximum size of the dynamic table. See
    #:  RFC7540 Section 6.5.2.
    DEFAULT_SIZE = 4096

    #: Constant list of static headers. See RFC7541 Section
    #:  2.3.1 and Appendix A
    STATIC_TABLE = (
        b':authority'                 ,  # noqa
        b':method'                    ,  # noqa
        b':method'                    ,  # noqa
        b':path'                      ,  # noqa
        b':path'                      ,  # noqa
        b':scheme'                    ,  # noqa
        b':scheme'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b':status'                    ,  # noqa
        b'accept-charset'             ,  # noqa
        b'accept-encoding'            ,  # noqa
        b'accept-language'            ,  # noqa
        b'accept-ranges'              ,  # noqa
        b'accept'                     ,  # noqa
        b'access-control-allow-origin',  # noqa
        b'age'                        ,  # noqa
        b'allow'                      ,  # noqa
        b'authorization'              ,  # noqa
        b'cache-control'              ,  # noqa
        b'content-disposition'        ,  # noqa
        b'content-encoding'           ,  # noqa
        b'content-language'           ,  # noqa
        b'content-length'             ,  # noqa
        b'content-location'           ,  # noqa
        b'content-range'              ,  # noqa
        b'content-type'               ,  # noqa
        b'cookie'                     ,  # noqa
        b'date'                       ,  # noqa
        b'etag'                       ,  # noqa
        b'expect'                     ,  # noqa
        b'expires'                    ,  # noqa
        b'from'                       ,  # noqa
        b'host'                       ,  # noqa
        b'if-match'                   ,  # noqa
        b'if-modified-since'          ,  # noqa
        b'if-none-match'              ,  # noqa
        b'if-range'                   ,  # noqa
        b'if-unmodified-since'        ,  # noqa
        b'last-modified'              ,  # noqa
        b'link'                       ,  # noqa
        b'location'                   ,  # noqa
        b'max-forwards'               ,  # noqa
        b'proxy-authenticate'         ,  # noqa
        b'proxy-authorization'        ,  # noqa
        b'range'                      ,  # noqa
        b'referer'                    ,  # noqa
        b'refresh'                    ,  # noqa
        b'retry-after'                ,  # noqa
        b'server'                     ,  # noqa
        b'set-cookie'                 ,  # noqa
        b'strict-transport-security'  ,  # noqa
        b'transfer-encoding'          ,  # noqa
        b'user-agent'                 ,  # noqa
        b'vary'                       ,  # noqa
        b'via'                        ,  # noqa
        b'www-authenticate'           ,  # noqa
        b'GET',
        b'POST',
        b'/',
        b'/index.html',
        b'http',
        b'https',
        b'200',
        b'204',
        b'206',
        b'304',
        b'400',
        b'404',
        b'500',
        b'gzip, deflate'
    )  # noqa

    STATIC_TABLE_LENGTH = len(STATIC_TABLE)

    def __init__(self):
        self._maxsize = HeaderTable.DEFAULT_SIZE
        self._current_size = 0
        self.resized = False
        self.dynamic_entries = deque()

    def get_by_index(self, index):
        """
        Returns the entry specified by index

        Note that the table is 1-based ie an index of 0 is
        invalid.  This is due to the fact that a zero value
        index signals that a completely unindexed header
        follows.

        The entry will either be from the static table or
        the dynamic table depending on the value of index.
        """
        original_index = index
        index -= 1
        if 0 <= index:
            if index < HeaderTable.STATIC_TABLE_LENGTH:
                return HeaderTable.STATIC_TABLE[index]

            index -= HeaderTable.STATIC_TABLE_LENGTH
            if index < len(self.dynamic_entries):
                return self.dynamic_entries[index]

        raise InvalidTableIndex("Invalid table index %d" % original_index)

    def __repr__(self):
        return "HeaderTable(%d, %s, %r)" % (
            self._maxsize,
            self.resized,
            self.dynamic_entries
        )

    def add(self, value):
        """
        Adds a new entry to the table

        We reduce the table size if the entry will make the
        table size greater than maxsize.
        """
        # We just clear the table if the entry is too big
        size = table_entry_size(value)
        if size > self._maxsize:
            self.dynamic_entries.clear()
            self._current_size = 0
        else:
            # Add new entry
            self.dynamic_entries.appendleft(value)
            self._current_size += size
            self._shrink()

    def search(self, value):
        """
        Searches the table for the entry specified by name
        and value

        Returns one of the following:
            - ``None``, no match at all
            - ``(index, value)`` for perfect matches.
        """

        index = HeaderTable.STATIC_TABLE_MAPPING.get(value)
        if index:
            return index, value
        else:
            offset = HeaderTable.STATIC_TABLE_LENGTH + 1
            for (i, v) in enumerate(self.dynamic_entries):
                if v == value:
                    return i + offset, v
            return None

    @property
    def maxsize(self):
        return self._maxsize

    @maxsize.setter
    def maxsize(self, newmax):
        newmax = int(newmax)
        log.debug("Resizing header table to %d from %d", newmax, self._maxsize)
        oldmax = self._maxsize
        self._maxsize = newmax
        self.resized = (newmax != oldmax)
        if newmax <= 0:
            self.dynamic_entries.clear()
            self._current_size = 0
        elif oldmax > newmax:
            self._shrink()

    def _shrink(self):
        """
        Shrinks the dynamic table to be at or below maxsize
        """
        cursize = self._current_size
        while cursize > self._maxsize:
            value = self.dynamic_entries.pop()
            cursize -= table_entry_size(value)
            log.debug("Evicting %s from the header table", value)
        self._current_size = cursize


def _build_static_table_mapping():
    """
    static_table_mapping used for hash searching.
    """
    return {v: i for i, v in enumerate(HeaderTable.STATIC_TABLE)}


HeaderTable.STATIC_TABLE_MAPPING = _build_static_table_mapping()
