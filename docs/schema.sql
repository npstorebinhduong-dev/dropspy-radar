-- v0.2 PostgreSQL schema reference generated from metadata.
-- Apply apps/api/migrations with Alembic; do not run this reference on existing data.


CREATE TABLE sources (
	id VARCHAR(60) NOT NULL,
	name VARCHAR(100) NOT NULL,
	kind VARCHAR(40) NOT NULL,
	corpus_types JSON NOT NULL,
	countries JSON NOT NULL,
	supported_filters JSON NOT NULL,
	approval_status VARCHAR(40) NOT NULL,
	rights_reference VARCHAR(1000) NOT NULL,
	live_enabled BOOLEAN NOT NULL,
	import_enabled BOOLEAN NOT NULL,
	media_storage_allowed BOOLEAN NOT NULL,
	retention_days INTEGER,
	state VARCHAR(30) NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE TABLE advertisers (
	id SERIAL NOT NULL,
	source_id VARCHAR(60) NOT NULL,
	identity_key VARCHAR(200) NOT NULL,
	external_id VARCHAR(150),
	name VARCHAR(200) NOT NULL,
	identity_method VARCHAR(30) NOT NULL,
	is_demo BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_advertiser_identity UNIQUE (source_id, identity_key, is_demo),
	FOREIGN KEY(source_id) REFERENCES sources (id)
)

;

CREATE TABLE collection_queries (
	id VARCHAR(36) NOT NULL,
	source_id VARCHAR(60) NOT NULL,
	scope_hash VARCHAR(64) NOT NULL,
	parameters JSON NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_query_scope UNIQUE (source_id, scope_hash),
	FOREIGN KEY(source_id) REFERENCES sources (id)
)

;

CREATE TABLE ads (
	id SERIAL NOT NULL,
	source_id VARCHAR(200) NOT NULL,
	platform VARCHAR(30) NOT NULL,
	advertiser VARCHAR(200) NOT NULL,
	title VARCHAR(500) NOT NULL,
	country VARCHAR(2) NOT NULL,
	status VARCHAR(20) NOT NULL,
	landing_url VARCHAR(2000) NOT NULL,
	landing_domain VARCHAR(255) NOT NULL,
	source_url VARCHAR(2000) NOT NULL,
	first_seen TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_seen TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	is_demo BOOLEAN NOT NULL,
	saved BOOLEAN NOT NULL,
	registry_source_id VARCHAR(60),
	advertiser_ref_id INTEGER,
	external_id VARCHAR(150),
	corpus VARCHAR(40) DEFAULT 'unknown' NOT NULL,
	delivery_start TIMESTAMP WITHOUT TIME ZONE,
	delivery_end TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (platform, source_id, is_demo),
	FOREIGN KEY(registry_source_id) REFERENCES sources (id),
	FOREIGN KEY(advertiser_ref_id) REFERENCES advertisers (id)
)

;
CREATE INDEX ix_ads_advertiser ON ads (advertiser);
CREATE INDEX ix_ads_country ON ads (country);
CREATE INDEX ix_ads_is_demo ON ads (is_demo);
CREATE INDEX ix_ads_landing_domain ON ads (landing_domain);
CREATE INDEX ix_ads_platform ON ads (platform);
CREATE INDEX ix_ads_registry_source_id ON ads (registry_source_id);

CREATE TABLE collection_runs (
	id VARCHAR(36) NOT NULL,
	query_id VARCHAR(36) NOT NULL,
	source_id VARCHAR(60) NOT NULL,
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	completeness VARCHAR(20) NOT NULL,
	status VARCHAR(30) NOT NULL,
	record_count INTEGER NOT NULL,
	is_demo BOOLEAN NOT NULL,
	note VARCHAR(500) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(query_id) REFERENCES collection_queries (id),
	FOREIGN KEY(source_id) REFERENCES sources (id)
)

;

CREATE TABLE ad_provenance (
	ad_id INTEGER NOT NULL,
	source_id VARCHAR(80) NOT NULL,
	external_id VARCHAR(100) NOT NULL,
	rights_reference VARCHAR(500) NOT NULL,
	imported_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	details JSON NOT NULL,
	PRIMARY KEY (ad_id),
	FOREIGN KEY(ad_id) REFERENCES ads (id) ON DELETE CASCADE
)

;

CREATE TABLE creatives (
	id SERIAL NOT NULL,
	ad_id INTEGER NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	content JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (ad_id, fingerprint),
	FOREIGN KEY(ad_id) REFERENCES ads (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_creatives_ad_id ON creatives (ad_id);

CREATE TABLE import_jobs (
	id VARCHAR(36) NOT NULL,
	idempotency_key VARCHAR(64) NOT NULL,
	source_id VARCHAR(60) NOT NULL,
	dataset_id VARCHAR(60) NOT NULL,
	filename VARCHAR(200) NOT NULL,
	file_sha256 VARCHAR(64) NOT NULL,
	file_format VARCHAR(10) NOT NULL,
	data_label VARCHAR(10) NOT NULL,
	corpus VARCHAR(40) NOT NULL,
	rights_reference VARCHAR(1000) NOT NULL,
	mapping JSON NOT NULL,
	raw_rows JSON NOT NULL,
	normalized_rows JSON NOT NULL,
	errors JSON NOT NULL,
	total_rows INTEGER NOT NULL,
	error_count INTEGER NOT NULL,
	processed INTEGER NOT NULL,
	cursor INTEGER NOT NULL,
	status VARCHAR(30) NOT NULL,
	completeness VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	lease_until TIMESTAMP WITHOUT TIME ZONE,
	run_id VARCHAR(36),
	PRIMARY KEY (id),
	UNIQUE (idempotency_key),
	FOREIGN KEY(source_id) REFERENCES sources (id),
	FOREIGN KEY(run_id) REFERENCES collection_runs (id)
)

;
CREATE INDEX ix_import_jobs_status ON import_jobs (status);

CREATE TABLE observations (
	id SERIAL NOT NULL,
	ad_id INTEGER NOT NULL,
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	source_url VARCHAR(2000) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (ad_id, observed_at),
	FOREIGN KEY(ad_id) REFERENCES ads (id) ON DELETE CASCADE
)

;
CREATE INDEX ix_observations_ad_id ON observations (ad_id);

CREATE TABLE raw_evidence (
	id SERIAL NOT NULL,
	job_id VARCHAR(36) NOT NULL,
	run_id VARCHAR(36) NOT NULL,
	ad_id INTEGER NOT NULL,
	observation_id INTEGER NOT NULL,
	row_number INTEGER NOT NULL,
	source_id VARCHAR(60) NOT NULL,
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	source_url VARCHAR(2000),
	raw_sha256 VARCHAR(64) NOT NULL,
	raw_data JSON NOT NULL,
	normalized_data JSON NOT NULL,
	rights_reference VARCHAR(1000) NOT NULL,
	retention_until TIMESTAMP WITHOUT TIME ZONE,
	is_demo BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_evidence_row UNIQUE (job_id, row_number),
	FOREIGN KEY(job_id) REFERENCES import_jobs (id),
	FOREIGN KEY(run_id) REFERENCES collection_runs (id),
	FOREIGN KEY(ad_id) REFERENCES ads (id),
	FOREIGN KEY(observation_id) REFERENCES observations (id),
	FOREIGN KEY(source_id) REFERENCES sources (id)
)

;
CREATE INDEX ix_raw_evidence_ad_id ON raw_evidence (ad_id);
CREATE INDEX ix_raw_evidence_job_id ON raw_evidence (job_id);
