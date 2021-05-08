


CREATE TABLE IF NOT EXISTS pathologysite (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
    deleted BOOLEAN DEFAULT FALSE NOT NULL, 
	CONSTRAINT pk_pathologysite PRIMARY KEY (id), 
	CONSTRAINT uq_pathologysite_name UNIQUE (name)
    );



CREATE TABLE IF NOT EXISTS slide (
	id INTEGER GENERATED ALWAYS AS IDENTITY, 
	name VARCHAR NOT NULL, 
	project_id INTEGER, 
    directory_name VARCHAR NOT NULL, 
    user_directory_timestamp VARCHAR NOT NULL, 
    created_datetime TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
    users_id INTEGER NOT NULL, 
    pathologysite_id INTEGER, 
    clinical_details VARCHAR DEFAULT '' NOT NULL, 
    status VARCHAR NOT NULL, 
    deleted BOOLEAN DEFAULT FALSE NOT NULL, 
	CONSTRAINT pk_slide PRIMARY KEY (id), 
	CONSTRAINT uq_slide_name UNIQUE (name), 
	CONSTRAINT fk_slide_project_id_project FOREIGN KEY(project_id) REFERENCES project (id),
	CONSTRAINT uq_slide_user_directory_timestamp UNIQUE (user_directory_timestamp), 
	CONSTRAINT fk_slide_users_id_users FOREIGN KEY(users_id) REFERENCES users (id), 
	CONSTRAINT fk_slide_pathologysite_id_pathologysite FOREIGN KEY(pathologysite_id) REFERENCES pathologysite (id)
    );


