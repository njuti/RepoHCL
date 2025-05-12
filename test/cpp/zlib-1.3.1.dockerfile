FROM applerodite/repohcl-base

WORKDIR /root/resource

ENV ROOT=zlib-1.3.1

RUN wget https://github.com/madler/zlib/archive/refs/tags/v1.3.1.zip && \
    unzip v1.3.1.zip && \
    rm v1.3.1.zip

WORKDIR /root/

ADD metrics/parse.sc /root/metrics/parse.sc

RUN mkdir -p /root/resource/${ROOT} && \
    mkdir -p /root/output/${ROOT} && \
    joern --script metrics/parse.sc --param path=/root/resource/${ROOT} --param output=/root/output/${ROOT} && \
    ctags -R --languages=C,C++ --c-kinds=p -f /root/output/${ROOT}/tags /root/resource/${ROOT}

WORKDIR /root
CMD ["python3", "main.py", "resource/${ROOT}", "--lang", "cpp"]