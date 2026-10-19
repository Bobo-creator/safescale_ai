-- hazard-taxonomy: normalized hazard categories per recall, plus standards violations.
-- `safescale classify` recomputes both tables in full; rows carry the TAXONOMY_VERSION that wrote
-- them. The category seed must match pipeline/src/safescale/taxonomy/categories.py (tested).

create table hazard_categories (
  code        text primary key,
  label       text not null,
  description text not null,
  sort_order  int  not null unique
);

insert into hazard_categories (code, label, description, sort_order) values
  ('fire_overheating', 'Fire / overheating', 'Fire, flames, ignition, explosion, overheating, melting or smoking.', 1),
  ('burn', 'Burn', 'Burns or scalds from hot surfaces, liquids, flames or chemicals.', 2),
  ('electrical_shock', 'Electrical shock', 'Electric shock or electrocution.', 3),
  ('choking', 'Choking', 'Choking or aspiration: small parts, or objects lodged in the throat or airway.', 4),
  ('suffocation_strangulation', 'Suffocation / strangulation', 'Suffocation, asphyxia, strangulation or entanglement (e.g. cords, bedding).', 5),
  ('laceration', 'Laceration', 'Cuts or punctures from sharp edges or points.', 6),
  ('fall', 'Fall / tip-over', 'A person falls, or a product tips over or collapses onto or under someone.', 7),
  ('entrapment', 'Entrapment / crush', 'Entrapment, pinching, crushing or amputation (e.g. fingers, head, body).', 8),
  ('poisoning', 'Poisoning / toxic exposure', 'Poisoning, lead, harmful chemicals, ingestion, carbon monoxide or illness.', 9),
  ('crash_loss_of_control', 'Crash / loss of control', 'Vehicle or ride-on crash or loss of control (e.g. brakes, steering, throttle).', 10),
  ('drowning', 'Drowning', 'Drowning.', 11),
  ('other', 'Other / unspecified injury', 'A hazard none of the other categories describes, or only a generic injury risk.', 12);

create table recall_hazards (
  recall_id        bigint not null references recalls (recall_id) on delete cascade,
  category         text   not null references hazard_categories (code),
  evidence         text   not null check (evidence <> ''),
  source           text   not null check (source in ('hazard', 'title', 'description')),
  taxonomy_version int    not null,
  primary key (recall_id, category)
);

create index recall_hazards_category on recall_hazards (category);

create table recall_standard_violations (
  id               bigint generated always as identity primary key,
  recall_id        bigint not null references recalls (recall_id) on delete cascade,
  standard         text,                    -- null: the text names no specific standard
  evidence         text   not null check (evidence <> ''),
  source           text   not null check (source in ('hazard', 'title', 'description')),
  taxonomy_version int    not null
);

create index recall_standard_violations_recall on recall_standard_violations (recall_id);

alter table hazard_categories          enable row level security;
alter table recall_hazards             enable row level security;
alter table recall_standard_violations enable row level security;
