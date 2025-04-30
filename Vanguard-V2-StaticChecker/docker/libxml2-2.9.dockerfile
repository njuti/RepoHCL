FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=libxml2-2.9.9

RUN wget https://download.gnome.org/sources/libxml2/2.9/libxml2-2.9.9.tar.xz && \
    tar xvf libxml2-2.9.9.tar.xz && \
    rm libxml2-2.9.9.tar.xz && \
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
