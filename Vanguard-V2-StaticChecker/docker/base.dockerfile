FROM ubuntu:20.04

RUN sed -i 's@archive.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@security.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list

# 设置默认时区，后面按照依赖包安装时会用到
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo "Asia/Shanghai" > /etc/timezone

RUN apt update && apt install -y build-essential llvm-9-dev ninja-build clang-9 libclang-9-dev zlib1g-dev wget bear python3-dev python-dev unzip

# 安装新版cmake
RUN wget https://github.com/Kitware/CMake/releases/download/v3.31.0/cmake-3.31.0-linux-x86_64.sh -q -O /tmp/cmake-install.sh \
    && chmod u+x /tmp/cmake-install.sh \
    && mkdir /opt/cmake-3.31.0 \
    && /tmp/cmake-install.sh --skip-license --prefix=/opt/cmake-3.31.0 \
    && rm /tmp/cmake-install.sh \
    && ln -s /opt/cmake-3.31.0/bin/* /usr/local/bin

WORKDIR /root/vanguard

COPY . .

RUN mkdir cmake-build-debug

WORKDIR /root/vanguard/cmake-build-debug

RUN cmake -G Ninja -DLLVM_PREFIX=/lib/llvm-9 ..

RUN ninja