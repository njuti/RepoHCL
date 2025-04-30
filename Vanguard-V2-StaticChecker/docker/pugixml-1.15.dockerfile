FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=pugixml-1.15

RUN wget https://github.com/zeux/pugixml/releases/download/v1.15/pugixml-1.15.zip && \
    unzip pugixml-1.15.zip && \
    rm pugixml-1.15.zip && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc` && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
