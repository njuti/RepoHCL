FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=zlib-1.3.1

RUN wget https://github.com/madler/zlib/archive/refs/tags/v1.3.1.zip && \
    unzip v1.3.1.zip && \
    rm v1.3.1.zip && \
    cp -r ${ROOT} origin

#WORKDIR /root/resource/${ROOT}
#
#RUN ./configure && \
#    bear make -j`nproc` && \
#    python3 ~/vanguard/benchmark/genastcmd.py && \
#    chmod +x buildast.sh && \
#    ./buildast.sh | tee buildast.log
#
#WORKDIR /root/output
#RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
#    rm -rf ~/resource/${ROOT}
