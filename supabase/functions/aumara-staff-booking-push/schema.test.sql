-- Run only against an ephemeral test database.
insert into public.aumara_staff_push_devices(device_id,endpoint,p256dh,auth,lease_until)
values ('synthetic-active','https://fcm.googleapis.com/test-active','test','test',now()+interval '1 day'),
       ('synthetic-expired','https://fcm.googleapis.com/test-expired','test','test',now()-interval '1 day');
do $$
declare event jsonb:='{"booking_id":12345,"property_id":324882,"room_id":674465,"arrival":"2030-01-02","departure":"2030-01-03","guests":2,"booked_at":"2026-11-27T12:01:00Z","status":"confirmed"}';
begin
  if not public.aumara_staff_push_ingest(event) then raise exception 'first ingest failed'; end if;
  if public.aumara_staff_push_ingest(event) then raise exception 'duplicate event created'; end if;
  if (select count(*) from public.aumara_staff_push_outbox)<>1 then raise exception 'duplicate or expired device included'; end if;
  if (select count(*) from public.aumara_staff_push_claim(12345,'00000000-0000-0000-0000-000000000001'))<>1 then raise exception 'claim failed'; end if;
  if (select count(*) from public.aumara_staff_push_claim(12345,'00000000-0000-0000-0000-000000000002'))<>0 then raise exception 'double claim'; end if;
  if has_table_privilege('anon','public.aumara_staff_push_devices','select') then raise exception 'anonymous subscription access'; end if;
  if has_table_privilege('authenticated','public.aumara_staff_push_config','select') then raise exception 'private config exposed'; end if;
  if has_function_privilege('authenticated','public.aumara_staff_push_ingest(jsonb)','execute') then raise exception 'ingestion RPC exposed'; end if;
end $$;
