# One image for every node (routers, BIND servers, Unbound, client).
# Each service in docker-compose.yml picks its role through its command.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        bind9 bind9-utils bind9-dnsutils \
        unbound openssl ca-certificates \
        iproute2 iputils-ping traceroute procps \
        tcpdump tshark \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Pinned Python packages: dnspython (DoT/DoH client and parser cross-check),
# httpx + h2 (HTTP/2 for DoH), pandas + matplotlib (analysis and graphs).
RUN pip3 install --no-cache-dir --break-system-packages \
        dnspython==2.6.1 httpx==0.27.2 h2==4.1.0 \
        pandas==2.2.3 matplotlib==3.9.2

COPY entrypoints/ /opt/lab/
# Strip Windows line endings in case the repo was checked out with CRLF.
RUN sed -i 's/\r$//' /opt/lab/*.sh && chmod +x /opt/lab/*.sh
