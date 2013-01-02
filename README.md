
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

    ./compare_compressors.py -t my.har

This will create two TSV files, req.tsv and res.tsv, that can then be
displayed by the display_tsv.html file. See [an
example](http://http2.github.com/compression-test/).


Adding New Compression Algorithms
---------------------------------

If you wish to implement a new codec, there are two easy approaches.

1) Develop it in Python. New modules should be subdirectories of 
'compressor', and should inherit from BaseProcessor there.

2) Develop it in another language, and use the 'fork' module to execute
it in a separate process. See 'sample_exec_codec.py' for an example of this; 
it can be run like this:

    ./compare_compressors.py -c fork="sample_exec_codec.py" file.har



NOTE WELL
=========

Any submission to the [IETF](http://www.ietf.org/) intended by the Contributor
for publication as all or part of an IETF Internet-Draft or RFC and any
statement made within the context of an IETF activity is considered an "IETF
Contribution". Such statements include oral statements in IETF sessions, as
well as written and electronic communications made at any time or place, which
are addressed to:

 * The IETF plenary session
 * The IESG, or any member thereof on behalf of the IESG
 * Any IETF mailing list, including the IETF list itself, any working group 
   or design team list, or any other list functioning under IETF auspices
 * Any IETF working group or portion thereof
 * Any Birds of a Feather (BOF) session
 * The IAB or any member thereof on behalf of the IAB
 * The RFC Editor or the Internet-Drafts function
 * All IETF Contributions are subject to the rules of 
   [RFC 5378](http://tools.ietf.org/html/rfc5378) and 
   [RFC 3979](http://tools.ietf.org/html/rfc3979) 
   (updated by [RFC 4879](http://tools.ietf.org/html/rfc4879)).

Statements made outside of an IETF session, mailing list or other function,
that are clearly not intended to be input to an IETF activity, group or
function, are not IETF Contributions in the context of this notice.

Please consult [RFC 5378](http://tools.ietf.org/html/rfc5378) and [RFC 
3979](http://tools.ietf.org/html/rfc3979) for details.

A participant in any IETF activity is deemed to accept all IETF rules of
process, as documented in Best Current Practices RFCs and IESG Statements.

A participant in any IETF activity acknowledges that written, audio and video
records of meetings may be made and may be available to the public.
