for f in ../http_samples/**/*.har
do
  echo "Processing $f..."
  ./headerstats.py "$f" > counts/$(basename $f).txt
done
echo "Done!"
