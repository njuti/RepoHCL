FROM applerodite/repohcl-base

WORKDIR /root/resource


ENV ROOT=libxml2-2.9.9

RUN wget https://download.gnome.org/sources/libxml2/2.9/libxml2-2.9.9.tar.xz && \
    tar xvf libxml2-2.9.9.tar.xz && \
    rm libxml2-2.9.9.tar.xz

WORKDIR /root/

ADD metrics/parse.sc /root/metrics/parse.sc

RUN mkdir -p /root/resource/${ROOT} && \
    mkdir -p /root/output/${ROOT} && \
    joern --script metrics/parse.sc --param path=/root/resource/${ROOT} --param output=/root/output/${ROOT} && \
    ctags -R --languages=C,C++ --c-kinds=p -f /root/output/${ROOT}/tags /root/resource/${ROOT}

WORKDIR /root
CMD ["python3", "main.py", "resource/${ROOT}", "--lang", "cpp"]