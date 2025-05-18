FROM applerodite/repohcl-base

WORKDIR /root/resource

ENV ROOT=cjson-1.7.18

RUN wget https://github.com/DaveGamble/cJSON/archive/refs/tags/v1.7.18.zip && \
    unzip v1.7.18.zip && \
    mv cJSON-1.7.18 cjson-1.7.18 && \
    rm v1.7.18.zip

WORKDIR /root/

ADD metrics/parse.sc /root/metrics/parse.sc

RUN mkdir -p /root/resource/${ROOT} && \
    mkdir -p /root/output/${ROOT} && \
    joern --script metrics/parse.sc --param path=/root/resource/${ROOT} --param output=/root/output/${ROOT} && \
    ctags -R --languages=C,C++ --c-kinds=p -f /root/output/${ROOT}/tags /root/resource/${ROOT}

WORKDIR /root
CMD ["python3", "main.py", "resource/${ROOT}", "--lang", "cpp"]