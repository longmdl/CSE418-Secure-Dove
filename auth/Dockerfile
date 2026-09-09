FROM python:3.8

ENV HOME /root
WORKDIR /root

COPY ./requirements.txt ./requirements.txt
COPY ./server.py ./server.py
COPY ./auth_server.py ./auth_server.py
COPY ./public ./public
COPY ./util ./util
COPY ./auth ./auth
COPY ./controller/ ./controller/
COPY ./service/ ./service/
COPY ./repository ./repository
COPY ./keys/jwt_private.pem ./keys/jwt_private.pem

#RUN apt-get update && apt-get install -y ffmpeg
RUN pip3 install -r requirements.txt

EXPOSE 8080

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.2.1/wait /wait
RUN chmod +x /wait


CMD /wait && python3 -u auth_server.py
