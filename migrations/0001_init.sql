-- The serving log. Every shortlist the platform shows is logged with its positions and whether it was
-- shuffled: that is what makes the next model trainable and the next evaluation unbiased (ADR 0002).
create table if not exists shortlist_log (
  id            bigserial primary key,
  served_at     timestamptz not null default now(),
  lot_id        bigint not null,
  policy        text not null,
  model_version text not null,
  randomised    boolean not null,
  firm_id       bigint not null,
  position      smallint not null check (position >= 0),
  score         double precision,
  p_bid         double precision,
  p_competitive double precision
);
create index if not exists shortlist_log_lot on shortlist_log (lot_id, served_at);

create table if not exists invitations (
  id              bigserial primary key,
  at              timestamptz not null default now(),
  lot_id          bigint not null,
  firm_id         bigint not null,
  invited_by      text not null,
  idempotency_key text not null,
  unique (idempotency_key, firm_id)
);
create index if not exists invitations_firm on invitations (firm_id, at);

-- append-only: a log that can be rewritten cannot be used to evaluate anything
create or replace function forbid_change() returns trigger language plpgsql as $$
begin
  raise exception '% is append-only', tg_table_name;
end $$;
drop trigger if exists shortlist_log_append_only on shortlist_log;
create trigger shortlist_log_append_only before update or delete on shortlist_log
  for each row execute function forbid_change();
drop trigger if exists invitations_append_only on invitations;
create trigger invitations_append_only before update or delete on invitations
  for each row execute function forbid_change();
