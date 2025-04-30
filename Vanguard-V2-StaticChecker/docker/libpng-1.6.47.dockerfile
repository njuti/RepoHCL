FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=libpng-1.6.47

RUN wget https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.47.zip && \
    unzip v1.6.47.zip && \
    rm v1.6.47.zip && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN ./configure && \
    bear -j`nproc` make && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}