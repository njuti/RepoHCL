FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=md5

RUN wget https://github.com/talent518/md5/archive/refs/heads/master.zip && \
    unzip master.zip && \
    rm master.zip && \
    mv md5-master ${ROOT}

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc` && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
