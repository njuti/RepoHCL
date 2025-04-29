FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=lz4-1.10.0

RUN wget https://github.com/lz4/lz4/archive/refs/tags/v1.10.0.zip && unzip v1.10.0.zip && rm v1.10.0.zip

WORKDIR /root/resource/${ROOT}

RUN bear make -j`nproc`
RUN cp ~/vanguard/benchmark/genastcmd.py .
RUN python3 genastcmd.py
RUN chmod +x buildast.sh
RUN ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt
