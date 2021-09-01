FROM python:3.9-alpine

WORKDIR /usr/src/app

COPY LICENSE gcp_ddns.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python", "./gcp_ddns.py" ]
CMD [ "/ddns/config.yaml" ]
