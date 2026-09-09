#!/bin/bash
openssl req -x509 -newkey rsa:4096 -keyout ./nginx/private.key -out ./nginx/cert.pem -days 365 -sha256 -nodes -subj "/C=US"
openssl genrsa -out ./keys/jwt_private.pem 2048
openssl rsa -in ./keys/jwt_private.pem -pubout -out keys/jwt_public.pem