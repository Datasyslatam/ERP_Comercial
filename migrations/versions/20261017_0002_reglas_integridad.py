"""Reglas de integridad en base de datos (defensa en profundidad además de la capa de servicios).

- Asientos contabilizados balanceados (trigger de restricción diferido al commit).
- Asientos contabilizados inmutables: solo se permite marcar 'posted' -> 'reversed'.
- No se contabiliza en periodos cerrados.
- Movimientos de inventario y bitácora de auditoría: solo inserción.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UP = r"""
create or replace function erp_check_entry_balanced() returns trigger language plpgsql as $$
declare
    v_entry bigint;
    v_status text;
    v_debit numeric;
    v_credit numeric;
    v_lines int;
begin
    v_entry := coalesce(new.entry_id, old.entry_id);
    select status into v_status from journal_entries where id = v_entry;
    if v_status is null or v_status = 'draft' then
        return null;
    end if;
    select coalesce(sum(debit), 0), coalesce(sum(credit), 0), count(*) into v_debit, v_credit, v_lines
      from journal_lines where entry_id = v_entry;
    if v_debit <> v_credit or v_lines < 2 then
        raise exception 'Asiento % desbalanceado (debito %, credito %)', v_entry, v_debit, v_credit
            using errcode = '23514';
    end if;
    return null;
end $$;

create constraint trigger trg_journal_lines_balanced
    after insert or update or delete on journal_lines
    deferrable initially deferred
    for each row execute function erp_check_entry_balanced();

create or replace function erp_journal_lines_immutable() returns trigger language plpgsql as $$
declare v_status text;
begin
    select status into v_status from journal_entries where id = old.entry_id;
    if v_status in ('posted', 'reversed') then
        raise exception 'Las lineas de un asiento contabilizado no se modifican ni eliminan' using errcode = '55000';
    end if;
    return case when tg_op = 'DELETE' then old else new end;
end $$;

create trigger trg_journal_lines_immutable
    before update or delete on journal_lines
    for each row execute function erp_journal_lines_immutable();

create or replace function erp_journal_entries_guard() returns trigger language plpgsql as $$
declare v_period_status text;
begin
    if tg_op = 'DELETE' then
        if old.status <> 'draft' then
            raise exception 'Un asiento contabilizado no puede eliminarse; utilice un reverso' using errcode = '55000';
        end if;
        return old;
    end if;
    if tg_op = 'UPDATE' and old.status <> 'draft' then
        if not (old.status = 'posted' and new.status = 'reversed'
                and new.entry_date = old.entry_date and new.total_debit = old.total_debit
                and new.total_credit = old.total_credit and new.period_id = old.period_id) then
            raise exception 'Asiento contabilizado inmutable (solo se permite marcarlo como reversado)'
                using errcode = '55000';
        end if;
        return new;
    end if;
    if new.status = 'posted' then
        select status into v_period_status from fiscal_periods where id = new.period_id;
        if v_period_status is distinct from 'open' then
            raise exception 'El periodo contable esta cerrado' using errcode = '55000';
        end if;
    end if;
    return new;
end $$;

create trigger trg_journal_entries_guard
    before insert or update or delete on journal_entries
    for each row execute function erp_journal_entries_guard();

create or replace function erp_append_only() returns trigger language plpgsql as $$
begin
    raise exception 'La tabla % es de solo insercion', tg_table_name using errcode = '55000';
end $$;

create trigger trg_stock_moves_append_only
    before update or delete on stock_moves
    for each row execute function erp_append_only();

create trigger trg_audit_log_append_only
    before update or delete on audit_log
    for each row execute function erp_append_only();
"""

DOWN = r"""
drop trigger if exists trg_audit_log_append_only on audit_log;
drop trigger if exists trg_stock_moves_append_only on stock_moves;
drop trigger if exists trg_journal_entries_guard on journal_entries;
drop trigger if exists trg_journal_lines_immutable on journal_lines;
drop trigger if exists trg_journal_lines_balanced on journal_lines;
drop function if exists erp_append_only();
drop function if exists erp_journal_entries_guard();
drop function if exists erp_journal_lines_immutable();
drop function if exists erp_check_entry_balanced();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
