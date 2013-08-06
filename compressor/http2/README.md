HTTP/2.0 Codec
==============

Specification
-------------
This codec is an implementation of the HTTP/2.0 header compression at:
https://datatracker.ietf.org/doc/draft-ietf-httpbis-header-compression/

Contents
--------
The codec comprises both an encoder and a decoder. It has a few options.

### Maximum buffer size

The buffer_size option allows to specify the maximum size of the header table.
The default value is 4096 bytes.

Example usage: 

	./compare_compressors.py -c "http2=buffer_size=8192" file.har
