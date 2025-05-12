FROM applerodite/repohcl-base

WORKDIR /root/

ENV VIRTUAL_ENV=/root/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ADD requirements.txt .

RUN python3.12 -m venv $VIRTUAL_ENV && \
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple && \
    pip install -r requirements.txt

ENV HF_ENDPOINT=https://hf-mirror.com

COPY . .

EXPOSE 31000

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "31000"]