#!/usr/bin/env bash
# Install + test ThaiACC modules on Odoo 20.
# Usage: DEMO=1 bash test/run_install_test.sh [module ...]
#   DEMO=1 loads demo data (needed by tests using demo records).
# Default modules: l10n_th_base_sequence l10n_th_promptpay
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

MODULES="${*:-l10n_th_base_sequence l10n_th_promptpay}"
ADDONS_DIR="${ADDONS_DIR:-$REPO_DIR}"
TAGS=$(printf "/%s," $MODULES); TAGS=${TAGS%,}
DB=thaiacc20

docker network create thaiacc20net 2>/dev/null || true
docker rm -f thaiacc20-db 2>/dev/null || true
docker volume rm thaiacc20-pgdata 2>/dev/null || true

docker run -d --name thaiacc20-db --network thaiacc20net --network-alias db \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres \
  -v thaiacc20-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
echo "waiting for postgres..."
until docker exec thaiacc20-db pg_isready -U odoo -q; do sleep 1; done

# Odoo 20 validates -i/-u names against the ir_module_module table, which on
# a virgin db only knows base — so the module names get "ignored". Boot in
# two steps: 1) init base, 2) install the target modules with tests.
docker exec thaiacc20-db dropdb --if-exists -U odoo "$DB"
docker exec thaiacc20-db createdb -U odoo "$DB"

DEMO_FLAG=""
if [ "${DEMO:-0}" = "1" ]; then
    # Odoo 20.0: demo is enabled with --with-demo (store_true). The old
    # '--without-demo=False' idiom parses as a truthy string and SILENTLY
    # disables demo data.
    DEMO_FLAG="--with-demo"
fi

echo "=== step 1: init base ==="
docker run --rm --network thaiacc20net -v "$ADDONS_DIR:/mnt/extra-addons:ro" \
  --entrypoint /usr/bin/odoo thaiacc-test:20 \
  -d "$DB" --db_host=db --db_user=odoo --db_password=odoo \
  --stop-after-init --max-cron-threads=0 -i base $DEMO_FLAG

echo "=== installing + testing: $MODULES ==="
docker run --rm --network thaiacc20net -v "$ADDONS_DIR:/mnt/extra-addons:ro" \
  --entrypoint /usr/bin/odoo thaiacc-test:20 \
  -d "$DB" --db_host=db --db_user=odoo --db_password=odoo \
  -i "$(echo $MODULES | tr ' ' ',')" $DEMO_FLAG \
  --test-enable --test-tags "$TAGS" \
  --stop-after-init --max-cron-threads=0
echo "=== install+test exit code: $? ==="
