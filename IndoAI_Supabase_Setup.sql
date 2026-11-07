-- Indo AI cloud state table: music collections, approved facts, and encrypted DLM snapshots
-- Run once in Supabase Dashboard > SQL Editor > New query.
create table if not exists public.indo_user_state (
    user_id text not null,
    state_type text not null,
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    constraint indo_user_state_pkey primary key (user_id, state_type),
    constraint indo_user_state_user_id_sha256 check (length(user_id) = 64),
    constraint indo_user_state_type_check check (state_type in ('music_library', 'personal_memory', 'dynamic_memory_v1'))
);

-- Upgrade existing v18.10.2/v18.10.3 state tables with the encrypted DLM snapshot type.
alter table public.indo_user_state drop constraint if exists indo_user_state_type_check;
alter table public.indo_user_state add constraint indo_user_state_type_check
    check (state_type in ('music_library', 'personal_memory', 'dynamic_memory_v1'));

alter table public.indo_user_state enable row level security;
revoke all on table public.indo_user_state from anon, authenticated;
grant all on table public.indo_user_state to service_role;

-- No anon/authenticated policies are intentionally created. Indo calls this
-- table only from its Python backend using the Supabase secret key.

-- dynamic_memory_v1 contains a Fernet-encrypted whole-account DLM snapshot.
-- Keep INDO_SESSION_SECRET stable across Render deploys: it is used to derive
-- the DLM encryption key. Losing/changing it makes old encrypted DLM snapshots unreadable.
