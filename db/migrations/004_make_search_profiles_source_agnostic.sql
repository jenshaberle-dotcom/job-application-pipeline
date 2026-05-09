ALTER TABLE search_profiles
ALTER COLUMN search_term DROP NOT NULL;

ALTER TABLE search_profiles
ALTER COLUMN search_location DROP NOT NULL;

ALTER TABLE search_profiles
ALTER COLUMN search_radius_km DROP NOT NULL;

ALTER TABLE search_profiles
ALTER COLUMN offer_type DROP NOT NULL;
