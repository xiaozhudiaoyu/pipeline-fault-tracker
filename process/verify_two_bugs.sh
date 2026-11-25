#!/usr/bin/env bash
set -u
C=pipeline-fault-tracker-postgres-1
Q() { docker exec -i "$C" psql -U pft -d pft_probe -v ON_ERROR_STOP=0 -q "$@" 2>&1; }

echo "=== main stack untouched: real db still at head ==="
docker exec -i "$C" psql -U pft -d pft -Atc "SELECT version_num FROM alembic_version;"

echo "=== scratch db (isolated from pft) ==="
docker exec -i "$C" psql -U pft -d pft -qc "DROP DATABASE IF EXISTS pft_probe;" >/dev/null
docker exec -i "$C" psql -U pft -d pft -qc "CREATE DATABASE pft_probe;" && echo "created pft_probe"

echo
echo "### BUG1: add Enum column WITHOUT CREATE TYPE  (alone) ###"
Q -c "CREATE TABLE pf (id serial PRIMARY KEY);"
echo "-- no faultpriority type exists yet:"
Q -c "SELECT typname FROM pg_type WHERE typname='faultpriority';"
echo "-- attempt the ORIGINAL migration statement:"
Q -c "ALTER TABLE pf ADD COLUMN priority faultpriority DEFAULT 'normal' NOT NULL;" | head -n 2
echo "-- now apply the FIX (create type first), same statement:"
Q -c "CREATE TYPE faultpriority AS ENUM ('normal','urgent');"
Q -c "ALTER TABLE pf ADD COLUMN priority faultpriority DEFAULT 'normal' NOT NULL;" | head -n 2
Q -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='pf' AND column_name='priority';"

echo
echo "### BUG2: boolean column with DEFAULT 1 (integer)  (alone) ###"
echo "-- ORIGINAL migration statement:"
Q -c "CREATE TABLE u (id serial PRIMARY KEY, is_active BOOLEAN DEFAULT 1 NOT NULL);" | head -n 2
echo "-- FIX (DEFAULT true):"
Q -c "CREATE TABLE u2 (id serial PRIMARY KEY, is_active BOOLEAN DEFAULT true NOT NULL);" | head -n 2
Q -c "SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name='u2' AND column_name='is_active';"

echo
echo "=== cleanup scratch db ==="
docker exec -i "$C" psql -U pft -d pft -qc "DROP DATABASE pft_probe;" && echo "dropped pft_probe"
