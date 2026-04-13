# 使用 Python 3.10 作為基底
FROM python:3.10-slim

# 1. 安裝系統級別的依賴 (這是讓 Manim 不會報錯的關鍵)
# 包含 ffmpeg, cairo, pango 以及基本的 LaTeX 環境
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libcairo2-dev \
    libpango1.0-dev \
    texlive \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-latex-recommended \
    texlive-science \
    tipa \
    && rm -rf /var/lib/apt/lists/*

# 2. 設定工作目錄
WORKDIR /app

# 3. 複製套件清單並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 把你所有的程式碼 (src, scripts, config) 複製進容器
COPY . .

# 5. 設定 PYTHONPATH，讓 Python 找得到 src 裡的模組
ENV PYTHONPATH=/app

# 6. 啟動 FastAPI 伺服器 (假設你的 FastAPI 實例在 src/server.py 且命名為 app)
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
