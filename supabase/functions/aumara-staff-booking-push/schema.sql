-- Additive, service-role-only storage. No guest names, contacts or payment data.
begin;
create table if not exists public.aumara_staff_push_config (
  id integer primary key check (id=1),
  vapid_public text not null,
  vapid_private text not null,
  webhook_secret text not null,
  active_from timestamptz not null default now()
);
create table if not exists public.aumara_staff_push_devices (
  device_id text primary key,
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  lease_until timestamptz not null,
  last_test_at timestamptz
);
create table if not exists public.aumara_staff_booking_events (
  booking_id bigint primary key,
  property_id integer not null check (property_id=324882),
  room_id integer not null check (room_id in (674465,674466)),
  arrival date not null,
  departure date not null check (departure>arrival),
  guests integer not null check (guests between 1 and 24),
  booked_at timestamptz not null,
  status text not null check (status in ('new','confirmed')),
  received_at timestamptz not null default now()
);
create table if not exists public.aumara_staff_push_outbox (
  booking_id bigint not null references public.aumara_staff_booking_events on delete cascade,
  device_id text not null references public.aumara_staff_push_devices on delete cascade,
  state text not null default 'pending' check (state in ('pending','sending','sent','failed')),
  attempts integer not null default 0,
  lease_id uuid,
  lease_until timestamptz,
  next_attempt_at timestamptz not null default now(),
  sent_at timestamptz,
  primary key (booking_id,device_id)
);
alter table public.aumara_staff_push_config enable row level security;
alter table public.aumara_staff_push_devices enable row level security;
alter table public.aumara_staff_booking_events enable row level security;
alter table public.aumara_staff_push_outbox enable row level security;
revoke all on public.aumara_staff_push_config,public.aumara_staff_push_devices,public.aumara_staff_booking_events,public.aumara_staff_push_outbox from public,anon,authenticated;
grant select,insert,update,delete on public.aumara_staff_push_config,public.aumara_staff_push_devices,public.aumara_staff_booking_events,public.aumara_staff_push_outbox to service_role;
create or replace function public.aumara_staff_push_ingest(p_event jsonb)
returns boolean language plpgsql security invoker set search_path=public as $$
declare inserted bigint;
begin
  insert into aumara_staff_booking_events(booking_id,property_id,room_id,arrival,departure,guests,booked_at,status)
  select (p_event->>'booking_id')::bigint,(p_event->>'property_id')::int,(p_event->>'room_id')::int,
         (p_event->>'arrival')::date,(p_event->>'departure')::date,(p_event->>'guests')::int,
         (p_event->>'booked_at')::timestamptz,p_event->>'status'
  on conflict (booking_id) do nothing returning booking_id into inserted;
  if inserted is null then return false; end if;
  insert into aumara_staff_push_outbox(booking_id,device_id)
  select inserted,device_id from aumara_staff_push_devices where lease_until>now()
  on conflict do nothing;
  return true;
end; $$;
create or replace function public.aumara_staff_push_claim(p_booking bigint,p_lease uuid)
returns setof jsonb language sql security invoker set search_path=public as $$
  with picked as (
    select o.booking_id,o.device_id
    from aumara_staff_push_outbox o
    join aumara_staff_push_devices d using(device_id)
    where o.booking_id=p_booking and d.lease_until>now() and o.attempts<6
      and ((o.state='pending' and o.next_attempt_at<=now()) or (o.state='sending' and o.lease_until<=now()))
    order by o.device_id limit 20 for update of o skip locked
  ), claimed as (
    update aumara_staff_push_outbox o set state='sending',attempts=o.attempts+1,
      lease_id=p_lease,lease_until=now()+interval '60 seconds'
    from picked p where o.booking_id=p.booking_id and o.device_id=p.device_id returning o.*
  )
  select jsonb_build_object('booking_id',c.booking_id,'device_id',c.device_id,'attempts',c.attempts,
    'endpoint',d.endpoint,'p256dh',d.p256dh,'auth',d.auth)
  from claimed c join aumara_staff_push_devices d using(device_id);
$$;
revoke all on function public.aumara_staff_push_ingest(jsonb),public.aumara_staff_push_claim(bigint,uuid) from public,anon,authenticated;
grant execute on function public.aumara_staff_push_ingest(jsonb),public.aumara_staff_push_claim(bigint,uuid) to service_role;
commit;
