Two random buckets

Headers are randomly placed into one of two buckets 
and compressed independently of one another using
randomly selection compression levels.
  
Compression window size is random. Rather than
compressing one fixed size chunk of data, two
variable sized chunks of data are compressed.
  
(There are a finite number of possible window 
sizes)
  
Redundancy in the message will be random within a 
fixed number of possible permutations. The number 
of permutations is determinate on the number of 
headers encoded and the specific values of those
headers. 
  
With CRIME, a critical step is determining the 
compression ratio.. len(compress(input+secret)).
Using random selection across two compression
buckets, even if the attacker controls what data
is going into the bucket, they cannot determine
which bucket their input goes into and compression
ratio varies for each bucket based on what goes 
into it.
  
It's not foolproof, obviously.. an attacker would 
just need to run the guess scenario a sufficient 
number of times and determine the guess that has 
the lowest average compression.. precisely how many 
times depends on the length of the secret and how 
randomized it is.
  
Within the SPDY frame, we cannot hide the length
of the compressed header blocks, so that is still
visible to attackers, but the length will vary 
randomly within a given range with identical input.
  
len(encrypt(compress(input+public+secret))) yields
random lengths within a finite range across multiple 
requests, even with identical input. This does not 
prevent leakage, but it makes it more difficult.
  
CRIME algorithm:
  
  "Make a guess, ask browser to send a request with path
  as guess. Observe length of the request that was sent.
  Correct guess is when length is different than usual.."
  
The randomization short circuits this algorithm, to 
some degree, by causing length to become variable 
within a set range of permutations.
  
This approach makes it a bit more difficult to do a 
CRIME attack but certainly not impossible.
