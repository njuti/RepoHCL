FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=zstd-1.4.7

RUN wget https://github.com/facebook/zstd/archive/refs/tags/v1.4.7.zip && unzip v1.4.7.zip && rm v1.4.7.zip

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc`
RUN cp ~/vanguard/benchmark/genastcmd.py .
RUN python3 genastcmd.py
RUN chmod +x buildast.sh
RUN ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt
