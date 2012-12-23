
HTTP Header Compression Tests
=============================

Usage
-----

The test can be run like this:

    ./compare_compressors.py [options] list-of-har-files

See [the HAR specification](http://www.softwareishard.com/blog/har-12-spec/), 
and our [collected sample HAR files](https://github.com/http2/http_samples).

The most important option is -c, which specifies what compressors to run.
Current codecs include:

* http1_gzip - gzip compression of HTTP1.x headers
* spdy3 - SPDY 3's gzip-based compression
* delta - draft-rpeon-httpbis-header-compression implementation
* fork - fork a process; see below

Interpreting Text Results
-------------------------

Results will look something like:

    732 req messages processed
                      compressed | ratio min   max   std
    req       fork       195,386 | 1.00  1.00  1.00  0.00
    req      http1       195,386 | 1.00  1.00  1.00  0.00
    req http1_gzip        20,801 | 0.11  0.02  0.60  0.08
    req      spdy3        27,238 | 0.14  0.04  0.71  0.08

    732 res messages processed
                      compressed | ratio min   max   std
    res       fork       161,029 | 1.00  1.00  1.00  0.00
    res      http1       161,029 | 1.00  1.00  1.00  0.00
    res http1_gzip        35,187 | 0.22  0.02  0.61  0.07
    res      spdy3        41,468 | 0.26  0.04  0.67  0.08

The 'compressed' column shows how many bytes the compression algorithm
outputs; 'ratio' shows the ratio to the baseline (http1, by default), and the
'min', 'max' and 'std; columns show the minimum, maximum and standard
deviations of the ratios, respectively.


Showing Message Graphs
----------------------

When the "-t" option is used, TSV output is created. E.g.,

    ./compare_compressors.py -t req my.har > req.tsv
    ./compare_compressors.py -t res my.har > res.tsv

This will create two TSV files that can then be displayed by the 
display_tsv.html file.


Adding New Compression Algorithms
---------------------------------

If you wish to implement a new codec, there are two easy approaches.

1) Develop it in Python. New modules should be subdirectories of 
'compressor'. 

2) Develop it in another language, and use the 'fork' module to execute
it in a separate process. See 'sample_exec_codec.py' for an example of this; 
it can be run like this:

    ./compare_compressors.py -c fork="sample_exec_codec.py" file.har


