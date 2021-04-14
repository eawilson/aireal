


CREATE TABLE IF NOT EXISTS pathology_sites (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
    deleted BOOLEAN DEFAULT FALSE NOT NULL, 
	CONSTRAINT pk_pathology_sites PRIMARY KEY (id), 
	CONSTRAINT uq_pathology_sites_name UNIQUE (name)
    );



CREATE TABLE IF NOT EXISTS slides (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	project_id INTEGER NOT NULL, 
    directory_name VARCHAR NOT NULL, 
    user_directory_timestamp VARCHAR NOT NULL, 
    created_datetime TIMESTAMP WITH TIME ZONE NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
    user_id INTEGER NOT NULL, 
    pathology_site_id INTEGER NOT NULL, 
    status VARCHAR NOT NULL, 
    deleted BOOLEAN DEFAULT FALSE NOT NULL, 
	CONSTRAINT pk_slides PRIMARY KEY (id), 
	CONSTRAINT uq_slides_name UNIQUE (name), 
	CONSTRAINT fk_slides_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (id),
	CONSTRAINT uq_slides_user_directory_timestamp UNIQUE (user_directory_timestamp), 
	CONSTRAINT fk_slides_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT fk_slides_pathology_site_id_pathology_sites FOREIGN KEY(pathology_site_id) REFERENCES pathology_sites (id)
    );


