-- Reference DDL generated from apps/api/app/models.py; runtime models are the source of truth.

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
	PRIMARY KEY (id),
	UNIQUE (platform, source_id, is_demo)
);

CREATE INDEX ix_ads_is_demo ON ads (is_demo);

CREATE INDEX ix_ads_advertiser ON ads (advertiser);

CREATE INDEX ix_ads_platform ON ads (platform);

CREATE INDEX ix_ads_landing_domain ON ads (landing_domain);

CREATE INDEX ix_ads_country ON ads (country);

CREATE TABLE creatives (
	id SERIAL NOT NULL,
	ad_id INTEGER NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	content JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (ad_id, fingerprint),
	FOREIGN KEY(ad_id) REFERENCES ads (id) ON DELETE CASCADE
);

CREATE INDEX ix_creatives_ad_id ON creatives (ad_id);

CREATE TABLE observations (
	id SERIAL NOT NULL,
	ad_id INTEGER NOT NULL,
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	source_url VARCHAR(2000) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (ad_id, observed_at),
	FOREIGN KEY(ad_id) REFERENCES ads (id) ON DELETE CASCADE
);

CREATE INDEX ix_observations_ad_id ON observations (ad_id);
