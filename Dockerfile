FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN find /app -type f -name '*.sh' -exec sed -i 's/\r$//' {} + \
	&& chmod +x /app/entrypoint.sh
EXPOSE 5000
ENTRYPOINT ["/app/entrypoint.sh"]
