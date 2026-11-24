#!/bin/bash
# Generate a lab CA and a server certificate for DoT/DoH (first start only),
# then run Unbound in the foreground.
set -e
C=/certs
mkdir -p "$C"
if [ ! -s "$C/server.pem" ]; then
  echo "[unbound] generating lab CA and server certificate in $C"
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout "$C/ca.key" -out "$C/ca.pem" -days 825 -subj "/CN=DNS Lab CA" 2>/dev/null
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -keyout "$C/server.key" -out "$C/server.csr" -subj "/CN=resolver.lab" 2>/dev/null
  cat > "$C/ext.cnf" <<EOF
subjectAltName=DNS:resolver.lab,IP:10.10.4.10
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=serverAuth
EOF
  openssl x509 -req -in "$C/server.csr" -CA "$C/ca.pem" -CAkey "$C/ca.key" \
    -CAcreateserial -out "$C/server.pem" -days 825 -extfile "$C/ext.cnf" 2>/dev/null
fi
unbound -V | head -n 3
unbound-checkconf /etc/unbound-lab/unbound.conf
exec unbound -d -c /etc/unbound-lab/unbound.conf
