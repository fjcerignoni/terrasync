FROM postgis/postgis:16-3.5

ARG PG_PARQUET_VERSION=0.3.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        curl \
        git \
        libclang-dev \
        libssl-dev \
        pkg-config \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

ENV CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:$PATH

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain stable --profile minimal \
    && cargo install --locked cargo-pgrx --version 0.12.5 \
    && cargo pgrx init --pg16 /usr/lib/postgresql/16/bin/pg_config

RUN git clone --depth 1 --branch v${PG_PARQUET_VERSION} \
        https://github.com/CrunchyData/pg_parquet.git /tmp/pg_parquet \
    && cd /tmp/pg_parquet \
    && cargo pgrx install --release --pg-config /usr/lib/postgresql/16/bin/pg_config \
    && rm -rf /tmp/pg_parquet ${CARGO_HOME}/registry ${CARGO_HOME}/git

RUN apt-get purge -y --auto-remove \
        build-essential \
        clang \
        curl \
        git \
        libclang-dev \
        libssl-dev \
        pkg-config \
        postgresql-server-dev-16 \
    && rm -rf ${CARGO_HOME} ${RUSTUP_HOME}

COPY init/10-extensions.sql /docker-entrypoint-initdb.d/10-extensions.sql
COPY postgresql.conf /etc/postgresql/postgresql.conf

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
