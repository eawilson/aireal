


CREATE TABLE IF NOT EXISTS groups (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	CONSTRAINT pk_groups PRIMARY KEY (id), 
	CONSTRAINT uq_groups_name UNIQUE (name)
    );



CREATE TABLE IF NOT EXISTS materials (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	CONSTRAINT pk_materials PRIMARY KEY (id)
    );



CREATE TABLE IF NOT EXISTS pipelines (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	version VARCHAR NOT NULL, 
	script VARCHAR NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_pipelines PRIMARY KEY (id), 
	CONSTRAINT uq_pipelines_name UNIQUE (name)
    );



CREATE TABLE IF NOT EXISTS sequencings (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	platform VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	completion_datetime VARCHAR NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	CONSTRAINT pk_sequencings PRIMARY KEY (id), 
	CONSTRAINT uq_sequencings_name UNIQUE (name)
    );



CREATE TABLE IF NOT EXISTS users (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	email VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	forename VARCHAR NOT NULL, 
	surname VARCHAR NOT NULL, 
	last_session JSONB DEFAULT '{}'::jsonb NOT NULL, 
	restricted BOOLEAN, 
	totp_secret VARCHAR, 
	password VARCHAR, 
	reset_datetime VARCHAR, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT uq_users_email UNIQUE (email)
    );



CREATE TABLE IF NOT EXISTS analyses (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	pipeline_id INTEGER, 
	sequencing_id INTEGER, 
	application VARCHAR, 
	version VARCHAR NOT NULL, 
	command_line VARCHAR NOT NULL, 
	log VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_analyses PRIMARY KEY (id), 
	CONSTRAINT fk_analyses_pipeline_id_pipelines FOREIGN KEY(pipeline_id) REFERENCES pipelines (id), 
	CONSTRAINT fk_analyses_sequencing_id_sequencings FOREIGN KEY(sequencing_id) REFERENCES sequencings (id)
    );



CREATE TABLE IF NOT EXISTS locationtypes (
	name VARCHAR NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_locationtypes PRIMARY KEY (name)
    );



CREATE TABLE IF NOT EXISTS locationmodels (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	locationtype VARCHAR NOT NULL, 
	movable BOOLEAN NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_locationmodels PRIMARY KEY (id), 
	CONSTRAINT uq_locationmodels_name UNIQUE (name), 
	CONSTRAINT fk_locationmodels_locationtype_locationtypes FOREIGN KEY(locationtype) REFERENCES locationtypes (name)
    );



CREATE TABLE IF NOT EXISTS locationtypes_locationtypes (
	parent VARCHAR NOT NULL, 
	child VARCHAR NOT NULL, 
	CONSTRAINT uq_locationtypes_locationtypes_parent UNIQUE (parent, child), 
	CONSTRAINT fk_locationtypes_locationtypes_parent_locationtypes FOREIGN KEY(parent) REFERENCES locationtypes (name), 
	CONSTRAINT fk_locationtypes_locationtypes_child_locationtypes FOREIGN KEY(child) REFERENCES locationtypes (name)
    );



CREATE TABLE IF NOT EXISTS logs (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	tablename VARCHAR NOT NULL, 
	row_id INTEGER NOT NULL, 
	action VARCHAR NOT NULL, 
	details VARCHAR NOT NULL, 
	user_id INTEGER, 
	ip_address VARCHAR DEFAULT '' NOT NULL, 
	datetime TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_logs PRIMARY KEY (id), 
	CONSTRAINT fk_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
    );



CREATE TABLE IF NOT EXISTS projects (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	subject_attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	collection_attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	pipeline_id INTEGER, 
	default_pipeline_options JSONB DEFAULT '{}'::jsonb NOT NULL, 
	CONSTRAINT pk_projects PRIMARY KEY (id), 
	CONSTRAINT uq_projects_name UNIQUE (name), 
	CONSTRAINT uq_projects_name UNIQUE (name), 
	CONSTRAINT fk_projects_pipeline_id_pipelines FOREIGN KEY(pipeline_id) REFERENCES pipelines (id)
    );



CREATE TABLE IF NOT EXISTS users_groups (
	user_id INTEGER NOT NULL, 
	group_id INTEGER NOT NULL, 
	CONSTRAINT uq_users_groups_user_id UNIQUE (user_id, group_id), 
	CONSTRAINT fk_users_groups_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT fk_users_groups_group_id_groups FOREIGN KEY(group_id) REFERENCES groups (id)
    );



CREATE TABLE IF NOT EXISTS locations (
	id INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1), 
	name VARCHAR NOT NULL, 
	barcode VARCHAR, 
	locationmodel_id INTEGER NOT NULL, 
	parent_id INTEGER NOT NULL, 
	site_id INTEGER NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_locations PRIMARY KEY (id), 
	CONSTRAINT uq_locations_name UNIQUE (name, site_id), 
	CONSTRAINT uq_locations_barcode UNIQUE (barcode, site_id), 
	CONSTRAINT fk_locations_locationmodel_id_locationmodels FOREIGN KEY(locationmodel_id) REFERENCES locationmodels (id), 
	CONSTRAINT fk_locations_parent_id_locations FOREIGN KEY(parent_id) REFERENCES locations (id), 
	CONSTRAINT fk_locations_site_id_locations FOREIGN KEY(site_id) REFERENCES locations (id)
    );



CREATE TABLE IF NOT EXISTS subjects (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	project_id INTEGER NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_subjects PRIMARY KEY (id), 
	CONSTRAINT uq_subjects_project_id UNIQUE (project_id, name), 
	CONSTRAINT fk_subjects_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
    );



CREATE TABLE IF NOT EXISTS users_projects (
	user_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	CONSTRAINT uq_users_projects_user_id UNIQUE (user_id, project_id), 
	CONSTRAINT fk_users_projects_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT fk_users_projects_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id)
)   ;



CREATE TABLE IF NOT EXISTS collections (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	subject_id INTEGER, 
	collection_datetime TIMESTAMP WITH TIME ZONE, 
	received_datetime TIMESTAMP WITH TIME ZONE, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_collections PRIMARY KEY (id), 
	CONSTRAINT fk_collections_subject_id_subjects FOREIGN KEY(subject_id) REFERENCES subjects (id)
    );



CREATE TABLE IF NOT EXISTS users_locations (
	user_id INTEGER NOT NULL, 
	location_id INTEGER NOT NULL, 
	CONSTRAINT uq_users_locations_user_id UNIQUE (user_id, location_id), 
	CONSTRAINT fk_users_locations_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT fk_users_locations_location_id_locations FOREIGN KEY(location_id) REFERENCES locations (id)
    );



CREATE TABLE IF NOT EXISTS files (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	collection_id INTEGER NOT NULL, 
	analysis_id INTEGER, 
	type VARCHAR NOT NULL, 
	extension VARCHAR NOT NULL, 
	creation_datetime TIMESTAMP WITH TIME ZONE NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_files PRIMARY KEY (id), 
	CONSTRAINT uq_files_name UNIQUE (name), 
	CONSTRAINT fk_files_collection_id_collections FOREIGN KEY(collection_id) REFERENCES collections (id), 
	CONSTRAINT fk_files_analysis_id_analyses FOREIGN KEY(analysis_id) REFERENCES analyses (id)
    );



CREATE TABLE IF NOT EXISTS samples (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	collection_id INTEGER NOT NULL, 
	parent_id INTEGER, 
	project_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	creation_datetime TIMESTAMP WITH TIME ZONE NOT NULL, 
	position VARCHAR NOT NULL, 
	location INTEGER, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_samples PRIMARY KEY (id), 
	CONSTRAINT fk_samples_collection_id_collections FOREIGN KEY(collection_id) REFERENCES collections (id), 
	CONSTRAINT fk_samples_parent_id_samples FOREIGN KEY(parent_id) REFERENCES samples (id), 
	CONSTRAINT fk_samples_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id), 
	CONSTRAINT fk_samples_material_id_materials FOREIGN KEY(material_id) REFERENCES materials (id), 
	CONSTRAINT fk_samples_location_locations FOREIGN KEY(location) REFERENCES locations (id)
    );



CREATE TABLE IF NOT EXISTS diskfiles (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	file_id INTEGER NOT NULL, 
	size INTEGER NOT NULL, 
	aws_bucket VARCHAR NOT NULL, 
	aws_key VARCHAR NOT NULL, 
	storage_class VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	deleted BOOLEAN DEFAULT false NOT NULL, 
	CONSTRAINT pk_diskfiles PRIMARY KEY (id), 
	CONSTRAINT fk_diskfiles_file_id_files FOREIGN KEY(file_id) REFERENCES files (id)
    );



CREATE TABLE IF NOT EXISTS files_analyses (
	file_id INTEGER NOT NULL, 
	analysis_id INTEGER NOT NULL, 
	CONSTRAINT uq_files_analyses_file_id UNIQUE (file_id, analysis_id), 
	CONSTRAINT fk_files_analyses_file_id_files FOREIGN KEY(file_id) REFERENCES files (id), 
	CONSTRAINT fk_files_analyses_analysis_id_analyses FOREIGN KEY(analysis_id) REFERENCES analyses (id)
    );



