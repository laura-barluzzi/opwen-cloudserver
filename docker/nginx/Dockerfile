FROM nginx:stable

RUN apt-get -qq update \
  && apt-get -qq install -y \
    curl \
    apache2-utils \
  && curl -fsSL https://git.io/get-mo -o /usr/local/bin/mo \
  && chmod +x /usr/local/bin/mo \
  && rm -rf /var/lib/apt/lists/*

ADD docker/nginx/static /static
ADD docker/nginx/nginx.conf.mu /app/frontend.conf.mu
ADD docker/nginx/run-nginx.sh /app/run-nginx.sh

RUN rm /etc/nginx/conf.d/default.conf

ENV DNS_RESOLVER=""
ENV HOSTNAME_EMAIL_RECEIVE="SET_ME"
ENV HOSTNAME_CLIENT_WRITE="SET_ME"
ENV HOSTNAME_CLIENT_READ="SET_ME"
ENV HOSTNAME_CLIENT_REGISTER="SET_ME"
ENV REGISTRATION_USERNAME="SET_ME"
ENV REGISTRATION_PASSWORD="SET_ME"

ADD docker/nginx/healthcheck.sh /app/healthcheck.sh
HEALTHCHECK --interval=89s --timeout=17s CMD /app/healthcheck.sh
CMD ["/app/run-nginx.sh"]
