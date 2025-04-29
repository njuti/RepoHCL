FROM cg

ENV CC=clang-9
ENV CXX=clang++-9

WORKDIR /root/resource

RUN apt update && apt install -y libboost-all-dev

ENV ROOT=cereal

# TODO: v1.3.2在c++11的支持上存在问题，无法编译
# RUN wget https://github.com/USCiLab/cereal/archive/refs/tags/v1.3.2.zip && unzip v1.3.2.zip && mv cereal-1.3.2 ${ROOT} && rm v1.3.2.zip

RUN wget https://github.com/USCiLab/cereal/archive/refs/heads/master.zip && unzip master.zip && mv cereal-master ${ROOT} && rm master.zip

WORKDIR /root/resource/${ROOT}

RUN cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1  .

RUN cp ~/vanguard/benchmark/genastcmd.py .
RUN python3 genastcmd.py
RUN chmod +x buildast.sh
RUN ./buildast.sh | tee buildast.log

WORKDIR /root/output
RUN ~/vanguard/cmake-build-debug/tools/CallGraphGen/cge ~/resource/${ROOT}/astList.txt

