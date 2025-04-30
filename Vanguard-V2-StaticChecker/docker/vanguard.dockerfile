FROM cg

WORKDIR /root

ENV CC=clang-9
ENV CXX=clang++-9

ENV ROOT=vanguard

RUN cp -r /root/vanguard /root/resource/${ROOT} && cp -r /root/vanguard /root/resource/origin

WORKDIR /root/resource/${ROOT}

RUN cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1 . && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output

RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
