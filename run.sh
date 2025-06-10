git pull
docker stop euclid-close-formatter || true
docker rm euclid-close-formatter || true
docker rmi euclid-close-formatter || true
docker build -t euclid-close-formatter .
docker run -d -p 3000:8501 --name euclid-close-formatter euclid-close-formatter
