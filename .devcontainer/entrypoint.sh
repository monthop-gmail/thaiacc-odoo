#!/bin/bash
set -e

echo "=== ThaiACC Odoo Entrypoint ==="

# THAIACC_PROFILE selects what this stack boots as:
#   official  — Odoo 20 official-only baseline: no OCA aggregation, install
#               the official l10n_th chart. The E20-001 baseline profile.
#   aggregate — full gitaggregate flow (OCA deps + thaiacc meta-package),
#               kept for when the OCA 20.0 branches / our fork bridges are
#               aggregated. The fail-loud aggregation protections only
#               apply here.
THAIACC_PROFILE="${THAIACC_PROFILE:-official}"
echo "Profile: $THAIACC_PROFILE"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
export PGPASSWORD=odoo
until pg_isready -h db -U odoo -q; do
    sleep 1
done
echo "PostgreSQL is ready!"

cd /workspace

if [ "$THAIACC_PROFILE" = "aggregate" ]; then
    # Pull OCA dependencies if not already present
    AGGREGATE_FAILED=""
    if [ ! -d "/workspace/l10n-thailand" ]; then
        echo "Pulling OCA dependencies with gitaggregate..."
        gitaggregate -c repos.yml -j 4 || AGGREGATE_FAILED=1
    else
        echo "OCA dependencies already present."
    fi

    # A failed aggregate leaves repos mid-merge with conflict markers in the source.
    # Odoo would only notice much later, as a SyntaxError deep in the module loader,
    # and the check above would then skip re-aggregating forever because the broken
    # directory exists. So verify the result here and say what actually went wrong.
    UNMERGED=""
    for dir in /workspace/*/; do
        [ -d "$dir.git" ] || continue
        if [ -n "$(git -C "$dir" ls-files --unmerged 2>/dev/null)" ]; then
            UNMERGED="$UNMERGED $(basename "$dir")"
        fi
    done

    if [ -n "$AGGREGATE_FAILED" ] || [ -n "$UNMERGED" ]; then
        echo "" >&2
        echo "!!! OCA dependency aggregation is incomplete." >&2
        if [ -n "$UNMERGED" ]; then
            echo "    Repos left mid-merge:$UNMERGED" >&2
            echo "    Fix repos.yml or the branches it merges, then re-run:" >&2
            echo "      cd /workspace && rm -rf$UNMERGED && gitaggregate -c repos.yml -j 4" >&2
        else
            echo "    gitaggregate exited non-zero — see the log above." >&2
        fi
        echo "    Refusing to start Odoo: it would fail later with a confusing error." >&2
        exit 1
    fi

    # Build the addons path from whatever gitaggregate actually produced, rather than
    # from a hardcoded list. The old list silently drifted out of sync when
    # ./tier-validation was added to repos.yml: the modules were cloned, but Odoo
    # never saw them, and installing l10n_th_tier_department failed with
    # "depends on module base_tier_validation_formula ... not available in your system".
    # /workspace goes last so this repo's own modules keep the lowest priority.
    ADDONS_PATH="/usr/lib/python3/dist-packages/odoo/addons"
    for dir in /workspace/*/; do
        [ -d "$dir.git" ] || continue
        ADDONS_PATH="$ADDONS_PATH,${dir%/}"
    done
    ADDONS_PATH="$ADDONS_PATH,/workspace"
else
    # Official-only baseline: core Odoo + this repo's own modules. No OCA
    # aggregation, so a fresh install never waits on upstream migrations.
    ADDONS_PATH="/usr/lib/python3/dist-packages/odoo/addons,/workspace"
    INIT_MODULE="l10n_th"
fi

echo "Addons path: $ADDONS_PATH"

if [ "$THAIACC_PROFILE" = "aggregate" ]; then
    INIT_MODULE="thaiacc"
fi

# Create database if not exists
DB_EXISTS=$(psql -h db -U odoo -tAc "SELECT 1 FROM pg_database WHERE datname='thaiacc'" 2>/dev/null || echo "0")
if [ "$DB_EXISTS" != "1" ]; then
    echo "Creating database 'thaiacc'..."
    createdb -h db -U odoo thaiacc
fi

# Install the profile's entry module if missing (official profile: the core
# Thai chart; aggregate profile: the full thaiacc meta-package).
MODULE_INSTALLED=$(psql -h db -U odoo -d thaiacc -tAc \
    "SELECT 1 FROM ir_module_module WHERE name='$INIT_MODULE' AND state='installed'" 2>/dev/null || echo "0")
if [ "$MODULE_INSTALLED" != "1" ]; then
    echo "Module $INIT_MODULE not installed. Installing with demo data..."
    exec odoo -d thaiacc \
        --db_host=db --db_user=odoo --db_password=odoo \
        --http-interface=0.0.0.0 \
        --addons-path="$ADDONS_PATH" \
        --init="$INIT_MODULE" \
        --without-demo=False
fi

echo "Database 'thaiacc' ready, module $INIT_MODULE installed. Starting Odoo..."
exec odoo -d thaiacc \
    --db_host=db --db_user=odoo --db_password=odoo \
    --http-interface=0.0.0.0 \
    --addons-path="$ADDONS_PATH" \
    --max-cron-threads=0
