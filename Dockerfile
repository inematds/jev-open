# Serviço em CPU (amd64 ou arm64). Sem torch: só onnxruntime + tokenizers.
# Os pesos NÃO entram na imagem: monte os pacotes em /pacotes (um diretório por tarefa).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JEV_PACOTES=/pacotes JEV_THREADS=2
RUN pip install --no-cache-dir "onnxruntime==1.30.0" "tokenizers==0.22.2" "pyyaml" "numpy"
WORKDIR /app
COPY serve/ serve/
COPY tasks/ tasks/
EXPOSE 8080
USER nobody
ENTRYPOINT ["python", "-m", "serve.api", "--porta", "8080"]
CMD ["--tarefas", "advocacia-atendimento", "clinica-triagem"]
