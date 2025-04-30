FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=jemalloc-5.3.0

RUN wget https://github.com/jemalloc/jemalloc/releases/download/5.3.0/jemalloc-5.3.0.tar.bz2 && tar -xvf jemalloc-5.3.0.tar.bz2 && rm jemalloc-5.3.0.tar.bz2 && cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN ./configure
RUN bear make -j`nproc`
RUN cp ~/vanguard/benchmark/genastcmd.py .
RUN python3 genastcmd.py
RUN chmod +x buildast.sh
RUN ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt
