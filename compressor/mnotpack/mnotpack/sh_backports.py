
PARAMLIST = 'param-list'
DICT = 'dictionary'
ITEM = 'item'
LIST = 'list'

backportmap = {
  b':status':                          ITEM,
  b'accept':                           PARAMLIST,
  b'accept-encoding':                  PARAMLIST,
  b'accept-language':                  PARAMLIST,
  b'alt-svc':                          PARAMLIST,
  b'content-type':                     PARAMLIST,
  b'forwarded':                        PARAMLIST,
  b'te':                               PARAMLIST,
  b'cache-control':                    DICT,
  b'pragma':                           DICT,
  b'surrogate-control':                DICT,
  b'prefer':                           DICT,
  b'preference-applied':               DICT,
  b'digest':                           DICT,
  b'age':                              ITEM,
  b'content-length':                   ITEM,
  b'access-control-max-age':           ITEM,
  b'alt-used':                         ITEM,
  b'host':                             ITEM,
  b'content-encoding':                 ITEM,
  b'expect':                           ITEM,
  b'origin':                           ITEM,
  b'access-control-allow-credentials': ITEM,
  b'access-control-request-method':    ITEM,
  b'x-content-type-options':           ITEM,
  b'access-control-allow-origin':      ITEM,
  b'accept-patch':                     LIST,
  b'accept-ranges':                    LIST,
  b'allow':                            LIST,
  b'alpn':                             LIST,
  b'content-language':                 LIST,
  b'transfer-encoding':                LIST,
  b'vary':                             LIST,
  b'trailer':                          LIST,
  b'access-control-allow-headers':     LIST,
  b'access-control-allow-methods':     LIST,
  b'access-control-request-headers':   LIST
}

import http.cookies
def parse_cookie(value):
    cookies = http.cookies.SimpleCookie()
    cookies.load(value)
    cookies = {c:cookies[c].value for c in cookies}
    return cookies

import calendar
from email.utils import parsedate as lib_parsedate
def parse_date(value):
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        raise ValueError
    if date_tuple[0] < 100:
        if date_tuple[0] > 68:
            date_tuple = (date_tuple[0]+1900,) + date_tuple[1:] # type: ignore
        else:
            date_tuple = (date_tuple[0]+2000,) + date_tuple[1:] # type: ignore
    return calendar.timegm(date_tuple)

backport_funcs = {
  b'cookie': parse_cookie,
  b'date': parse_date,
  b'last-modified': parse_date,
  b'expires': parse_date
}