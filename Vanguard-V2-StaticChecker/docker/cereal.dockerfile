FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

ENV ROOT=cereal

# TODO: v1.3.2在c++11的支持上存在问题，无法编译
# RUN wget https://github.com/USCiLab/cereal/archive/refs/tags/v1.3.2.zip && unzip v1.3.2.zip && mv cereal-1.3.2 ${ROOT} && rm v1.3.2.zip

RUN wget https://github.com/USCiLab/cereal/archive/refs/heads/master.zip && \
    unzip master.zip && \
    mv cereal-master ${ROOT} && \
    rm master.zip && \
    cp -r ${ROOT} origin

WORKDIR /root/resource/${ROOT}

RUN cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1 . && \
    python3 ~/vanguard/benchmark/genastcmd.py && \
    chmod +x buildast.sh && \
    ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt && \
    rm -rf ~/resource/${ROOT}