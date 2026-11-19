# Инструменты увеличения иконок (тест «Режима max retina»): xBRZ и Real-ESRGAN (CPU).
#   docker build -t sprutio-upscale stand/tools/upscale
#   docker run --rm -v "$PWD":/w -w /w sprutio-upscale python stand/tools/upscale/upscale_icons.py
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends g++ curl git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir spandrel pillow numpy \
 && pip install --no-cache-dir git+https://github.com/ioistired/xbrz.py.git
# (xbrz.py с PyPI собирается без xbrz.h — ставим из git с сабмодулями)
# модели Real-ESRGAN: общая x2 и «аниме» x4 (лучше на рисованных картинках с плоскими заливками)
RUN mkdir -p /models \
 && curl -fsSL -o /models/RealESRGAN_x2plus.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth \
 && curl -fsSL -o /models/RealESRGAN_x4plus_anime_6B.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
