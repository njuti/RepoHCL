FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=opentelemetry-1.20.0

RUN wget https://github.com/open-telemetry/opentelemetry-cpp/archive/refs/tags/v1.20.0.zip && \
    unzip v1.20.0.zip && \
    mv opentelemetry-cpp-1.20.0 ${ROOT} && \
    rm v1.20.0.zip && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DBUILD_TESTING=0 -DWITH_BENCHMARK=0 . && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log \

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}
