FROM nginx:1.19-alpine

RUN rm /etc/nginx/conf.d/default.conf

RUN mkdir log

COPY ./nginx.conf /etc/nginx/templates/nginx.conf.template

# COPY ./start.sh ./

# RUN chmod 755 ./start.sh

# CMD ["./start.sh"]