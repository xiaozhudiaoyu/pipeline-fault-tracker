set -u
wget -q -O - http://127.0.0.1/ | head -c 120
echo
wget -q -O - http://127.0.0.1/api/health
echo
