FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=lz4-1.10.0

RUN wget https://github.com/lz4/lz4/archive/refs/tags/v1.10.0.zip && \
    unzip v1.10.0.zip && \
    rm v1.10.0.zip && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc` && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
