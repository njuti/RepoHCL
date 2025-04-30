FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=mbedtls-3.6.3

WORKDIR /root/resource

RUN wget https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-3.6.3/mbedtls-3.6.3.tar.bz2 && \
    tar -xvf mbedtls-3.6.3.tar.bz2 && \
    rm mbedtls-3.6.3.tar.bz2 && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc` && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log \

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
