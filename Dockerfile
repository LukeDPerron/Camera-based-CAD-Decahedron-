FROM node:24-bookworm-slim

# Install Codex and required dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git python3 python3-pip build-essential bubblewrap procps \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex \
    && groupadd --gid 10001 llmsandbox \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash llmsandbox \
    && mkdir -p /workspace /home/llmsandbox/.codex \
    && chown -R 10001:10001 /workspace /home/llmsandbox

USER 10001:10001
ENV HOME=/home/llmsandbox
WORKDIR /workspace
CMD ["codex"]