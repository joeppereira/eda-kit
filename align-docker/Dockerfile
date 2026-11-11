# ALIGN (analog layout auto place-and-route) in a container.
# ALIGN is source-only C++/CMake and targets Linux + Python <=3.12, so it can't be
# installed natively on this macOS/py3.14 host — run it here instead.
#
# Build:  docker build -t align .
# Run:    docker run --rm -v "$PWD/work:/work" align \
#             schematic2layout.py /work/<design> -p /ALIGN-public/pdks/Asap7_PDK
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential cmake ninja-build \
      python3.10 python3.10-venv python3-pip \
      libboost-all-dev lp-solve liblpsolve55-dev \
      ca-certificates && rm -rf /var/lib/apt/lists/*

RUN python3.10 -m pip install --upgrade pip setuptools wheel

# ALIGN + its ASAP7 PDK (predictive 7nm FinFET; same node as our 7nm model).
RUN git clone --depth 1 https://github.com/ALIGN-analoglayout/ALIGN-public.git /ALIGN-public
WORKDIR /ALIGN-public
RUN pip install -e .           # builds the C++ placement engine
RUN git clone --depth 1 https://github.com/ALIGN-analoglayout/ALIGN-pdk-asap7.git pdks/Asap7_PDK || true

ENV ALIGN_HOME=/ALIGN-public
WORKDIR /work
CMD ["bash"]
