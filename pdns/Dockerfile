FROM powerdns/pdns-auth-49

# Install psql client to check schema readiness
USER root
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

COPY pdns.conf /etc/powerdns/pdns.conf
COPY gpgsql.conf.j2 /etc/powerdns/templates.d/gpgsql.conf.j2
COPY wait-for-schema.sh /usr/local/bin/wait-for-schema.sh

ENTRYPOINT ["/usr/local/bin/wait-for-schema.sh"]
CMD ["/usr/local/sbin/pdns_server-startup"]
