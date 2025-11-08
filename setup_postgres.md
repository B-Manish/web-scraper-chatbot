# PostgreSQL with pgvector Setup Guide

This guide will help you set up PostgreSQL with the pgvector extension for use with Agno.

## Option 1: Docker Setup (Recommended - Easiest)

This is the quickest way to get PostgreSQL with pgvector running.

### Step 1: Run PostgreSQL with pgvector using Docker

```bash
docker run -d \
  --name agno-postgres \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e POSTGRES_DB=ai \
  -p 5532:5432 \
  pgvector/pgvector:pg16
```

This will:
- Create a PostgreSQL 16 container with pgvector pre-installed
- Set username: `ai`, password: `ai`, database: `ai`
- Expose port 5532 (matching the default in your code)

### Step 2: Verify it's running

```bash
docker ps | grep agno-postgres
```

### Step 3: Test the connection

```bash
docker exec -it agno-postgres psql -U ai -d ai -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

If this runs without errors, you're all set!

### Stop/Start the container

```bash
# Stop
docker stop agno-postgres

# Start
docker start agno-postgres

# Remove (if needed)
docker rm -f agno-postgres
```

---

## Option 2: Manual Installation

### Step 1: Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**macOS (using Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**CentOS/RHEL:**
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
```

### Step 2: Install pgvector Extension

**Ubuntu/Debian:**
```bash
sudo apt install postgresql-16-pgvector
# Or for PostgreSQL 15: sudo apt install postgresql-15-pgvector
```

**macOS (using Homebrew):**
```bash
brew install pgvector
```

**From Source:**
```bash
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Step 3: Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL prompt, run:
CREATE USER ai WITH PASSWORD 'ai';
CREATE DATABASE ai OWNER ai;
\c ai
CREATE EXTENSION vector;
\q
```

### Step 4: Configure PostgreSQL (if needed)

Edit PostgreSQL config to allow connections:

```bash
# Find your pg_hba.conf location
sudo -u postgres psql -c "SHOW hba_file;"

# Edit the file (usually /etc/postgresql/16/main/pg_hba.conf)
# Add this line for local connections:
# local   all             all                                     md5
# host    all             all             127.0.0.1/32            md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

---

## Option 3: Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: agno-postgres
    environment:
      POSTGRES_USER: ai
      POSTGRES_PASSWORD: ai
      POSTGRES_DB: ai
    ports:
      - "5532:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Then run:
```bash
docker-compose up -d
```

---

## Verify Your Setup

Test the connection with Python:

```python
import psycopg

try:
    conn = psycopg.connect(
        "postgresql://ai:ai@localhost:5532/ai"
    )
    cursor = conn.cursor()
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
    version = cursor.fetchone()
    print(f"✓ pgvector extension installed: {version[0]}")
    conn.close()
    print("✓ Database connection successful!")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

Or using psql:
```bash
psql -h localhost -p 5532 -U ai -d ai -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

---

## Update Connection String (if needed)

If you use different credentials or port, update the `db_url` in `poc_agno.py`:

```python
vector_db = PgVector(
    table_name="website_documents",
    db_url="postgresql+psycopg://YOUR_USER:YOUR_PASSWORD@localhost:YOUR_PORT/YOUR_DB",
)
```

Connection string format: `postgresql+psycopg://username:password@host:port/database`

---

## Troubleshooting

### Connection refused
- Check if PostgreSQL is running: `docker ps` or `sudo systemctl status postgresql`
- Verify port is correct (default: 5532 for Docker, 5432 for local)

### Authentication failed
- Verify username and password match
- Check `pg_hba.conf` configuration

### Extension not found
- Make sure pgvector is installed: `sudo apt install postgresql-16-pgvector`
- Create extension: `CREATE EXTENSION vector;`

### Port already in use
- Change the port in Docker: `-p 5533:5432` and update `db_url` accordingly

