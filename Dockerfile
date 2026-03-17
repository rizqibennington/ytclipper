FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg nodejs ca-certificates \
  && if [ -e /usr/bin/nodejs ] && [ ! -e /usr/bin/node ]; then ln -s /usr/bin/nodejs /usr/bin/node; fi \
  && nodejs --version \
  && node --version \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV HOST=0.0.0.0
ENV PORT=5000
ENV DEBUG=0
ENV YTCLIPPER_ROOT_PATH=/apps/ytclip
ENV HOME=/data
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

EXPOSE 5000

CMD ["python", "run.py"]
