CREATE EXTENSION IF NOT EXISTS btree_gist;



CREATE TABLE version (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    version VARCHAR NOT NULL, -- all applied versions are stored, the current is the most recent
    datetime TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp NOT NULL,
    CONSTRAINT pk_version PRIMARY KEY (id),
    CONSTRAINT uq_version_name UNIQUE (version)
    );



CREATE TABLE users (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
    name VARCHAR GENERATED ALWAYS AS (LEFT(forename, 1) || '.' || surname) STORED, 
    fullname VARCHAR GENERATED ALWAYS AS (surname || ', ' || forename) STORED, 
    email VARCHAR NOT NULL, 
    forename VARCHAR NOT NULL,
    surname VARCHAR NOT NULL, 
    last_session JSONB DEFAULT '{}'::jsonb NOT NULL, 
    last_login_datetime TIMESTAMP WITH TIME ZONE,
    totp_secret VARCHAR, 
    password VARCHAR, 
    reset_datetime VARCHAR, 
    deleted BOOLEAN DEFAULT false NOT NULL, 
    CONSTRAINT pk_user PRIMARY KEY (id), 
    CONSTRAINT uq_user_email UNIQUE (email)
    );



CREATE TABLE role (
    name VARCHAR, -- not null as primary key
    CONSTRAINT pk_role PRIMARY KEY (name)
    );



CREATE TABLE role_users (
    users_id INTEGER NOT NULL,
    name VARCHAR NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (users_id, name), 
    CONSTRAINT fk_users_role_users_id_users FOREIGN KEY (users_id) REFERENCES users (id), 
    CONSTRAINT fk_users_role_role_role FOREIGN KEY (name) REFERENCES role (name)
    );
CREATE INDEX ix_role_users_name ON role_users (name);



CREATE TABLE editrecord (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
    tablename VARCHAR NOT NULL, 
    row_id INTEGER NOT NULL, 
    action VARCHAR NOT NULL, 
    details JSONB DEFAULT '{}'::jsonb NOT NULL, 
    users_id INTEGER, 
    ip_address INET, 
    edit_datetime TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp NOT NULL, 
    CONSTRAINT pk_editrecord PRIMARY KEY (id), 
    CONSTRAINT fk_editrecord_users_id_user FOREIGN KEY (users_id) REFERENCES users (id)
    );
CREATE INDEX ix_editrecord_tablename ON editrecord (tablename);
CREATE INDEX ix_editrecord_row_id ON editrecord (row_id);



CREATE TABLE auditaction (
    name VARCHAR, -- not null as primary key
    CONSTRAINT pk_auditaction PRIMARY KEY (name)
    );



CREATE TABLE audittarget (
    name VARCHAR, -- not null as primary key
    CONSTRAINT pk_audittarget PRIMARY KEY (name)
    );



CREATE TABLE audittrail (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    action VARCHAR NOT NULL, -- verb, past tense eg Created, Edited, Deleted, Restored, Imported
    target VARCHAR NOT NULL, -- noun, uniquely identifies affected object type eg User, Location, Sample
    name VARCHAR NOT NULL, -- identifies affected object at the time the action occured
    keyvals JSONB DEFAULT '{}'::jsonb NOT NULL, --
    format_string VARCHAR NOT NULL DEFAULT '',
    users_id INTEGER,
    ip_address INET,
    datetime TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp NOT NULL,
    CONSTRAINT pk_audittrail PRIMARY KEY (id),
    CONSTRAINT fk_audittrail_action_auditaction FOREIGN KEY (action) REFERENCES auditaction (name),
    CONSTRAINT fk_audittrail_target_audittarget FOREIGN KEY (target) REFERENCES audittarget (name),
    CONSTRAINT fk_audittrail_users_id_users FOREIGN KEY (users_id) REFERENCES users (id)
    );
CREATE INDEX ix_audittrail_action ON audittrail (action);
CREATE INDEX ix_audittrail_target ON audittrail (target);
CREATE INDEX ix_audittrail_users_id ON audittrail (users_id);



CREATE TABLE auditlink (
    audittrail_id INTEGER NOT NULL,
    tablename VARCHAR NOT NULL,
    row_id INTEGER NOT NULL,
    CONSTRAINT pk_auditlink PRIMARY KEY (tablename, row_id, audittrail_id),
    CONSTRAINT fk_auditlink_audittrail_id_audittrail FOREIGN KEY (audittrail_id) REFERENCES audittrail (id)
    );
CREATE INDEX ix_auditlink_audittrail ON auditlink (audittrail_id);



CREATE TABLE project (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    name VARCHAR NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    deleted BOOLEAN DEFAULT false NOT NULL,
    fastq_s3_path VARCHAR, -- ???????????????????????????? should this be not null
    fastq_command_line VARCHAR, -- ???????????????????????????? should this be not null

--    subject_attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
--    collection_attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
--    pipeline_id INTEGER, 
--    default_pipeline_options JSONB DEFAULT '{}'::jsonb NOT NULL, 
--    CONSTRAINT fk_project_pipeline_id_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipeline (id)
    CONSTRAINT pk_project PRIMARY KEY (id), 
    CONSTRAINT uq_project_name UNIQUE (name)
    );



CREATE TABLE project_users (
    users_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    CONSTRAINT uq_user_project_users_id UNIQUE (users_id, project_id),
    CONSTRAINT fk_user_project_users_id_user FOREIGN KEY (users_id) REFERENCES users (id),
    CONSTRAINT fk_user_project_project_id_project FOREIGN KEY (project_id) REFERENCES project (id)
    );



CREATE TABLE identifierdatatype (
    name VARCHAR, -- not null as primary key
    CONSTRAINT pk_datatype PRIMARY KEY (name)
    );



CREATE TABLE identifiertype (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    name VARCHAR NOT NULL,
    datatype VARCHAR NOT NULL,
    uniq BOOLEAN NOT NULL,
    deleted BOOLEAN DEFAULT false NOT NULL,
    CONSTRAINT pk_identifiertype PRIMARY KEY (id), 
    CONSTRAINT uq_identifiertype_name UNIQUE (name),
    CONSTRAINT fk_identifiertype_datatype_identifierdatatype FOREIGN KEY (datatype) REFERENCES identifierdatatype (name)
    );



CREATE TABLE project_identifiertype (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    project_id INTEGER NOT NULL,
    identifiertype_id INTEGER NOT NULL,
    regex VARCHAR NOT NULL,
    required BOOLEAN NOT NULL,
    deleted BOOLEAN DEFAULT false NOT NULL,
    CONSTRAINT pk_project_identifiertype PRIMARY KEY (id), 
    CONSTRAINT uq_project_identifiertype_project_id_identifiertype_id UNIQUE (project_id, identifiertype_id),
    CONSTRAINT fk_project_identifiertype_project_id_project FOREIGN KEY (project_id) REFERENCES project (id),
    CONSTRAINT fk_project_identifiertype_identifiertype_id_identifiertype FOREIGN KEY (identifiertype_id) REFERENCES identifiertype (id)
    );



CREATE TABLE subject (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    identifiers JSONB DEFAULT '{}'::jsonb NOT NULL,
    invalid_identifiers BOOLEAN NOT NULL,
    name VARCHAR NOT NULL, -- project specific identifier chosen from identifiers, for display purposes only
    project_id INTEGER NOT NULL,
    attr JSONB DEFAULT '{}'::jsonb NOT NULL,
    deleted BOOLEAN DEFAULT false NOT NULL,
    CONSTRAINT pk_subject PRIMARY KEY (id),
    CONSTRAINT uq_subject_project_id UNIQUE (project_id, name),
    CONSTRAINT fk_subject_project_id_project FOREIGN KEY (project_id) REFERENCES project (id)
    );



CREATE TABLE collection (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    subject_id INTEGER, 
    collection_datetime TIMESTAMP WITH TIME ZONE, 
    received_datetime TIMESTAMP WITH TIME ZONE, 
    attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
    deleted BOOLEAN DEFAULT false NOT NULL, 
    CONSTRAINT pk_collection PRIMARY KEY (id), 
    CONSTRAINT fk_collection_subject_id_subject FOREIGN KEY (subject_id) REFERENCES subject (id)
    );



CREATE TABLE material (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    name VARCHAR NOT NULL,
    primary BOOLEAN NOT NULL,
    CONSTRAINT pk_material PRIMARY KEY (id),
    CONSTRAINT uq_material_name UNIQUE (name)
    );
    


CREATE TABLE sample (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY,
    collection_id INTEGER NOT NULL,
    parent_id INTEGER,
    project_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    creation_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    --location_id INTEGER NOT NULL,
    
    attr JSONB DEFAULT '{}'::jsonb NOT NULL,
    deleted BOOLEAN DEFAULT false NOT NULL,
    CONSTRAINT pk_sample PRIMARY KEY (id),
    CONSTRAINT fk_sample_collection_id_collection FOREIGN KEY (collection_id) REFERENCES collection (id),
    CONSTRAINT fk_sample_parent_id_sample FOREIGN KEY (parent_id) REFERENCES sample (id),
    CONSTRAINT fk_sample_project_id_project FOREIGN KEY (project_id) REFERENCES project (id),
    CONSTRAINT fk_sample_material_id_material FOREIGN KEY (material_id) REFERENCES material (id)
    --CONSTRAINT fk_sample_location_id_location FOREIGN KEY (location_id) REFERENCES location (id)
    );



INSERT INTO version (version) VALUES ('1.1.0-alpha1');
INSERT INTO users (email, forename, surname) VALUES ('someone@example.com', 'Admin', 'Admin');
INSERT INTO role (name) VALUES ('Admin');
INSERT INTO role_users (users_id, name) SELECT users.id, 'Admin' FROM users WHERE users.email = 'someone@example.com';

INSERT INTO identifierdatatype (name) VALUES ('String');
INSERT INTO identifierdatatype (name) VALUES ('Date of Birth');
INSERT INTO identifierdatatype (name) VALUES ('NHS Number');

INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Surname', 'String', false);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Forename', 'String', false);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Date of Birth', 'Date of Birth', false);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Medical Record Number', 'String', true);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('NHS Number', 'NHS Number', true);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Study ID', 'String', true);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Screening ID', 'String', true);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Pre-screening ID', 'String', true);
INSERT INTO identifiertype (name, datatype, uniq) VALUES ('Initials', 'String', false);

INSERT INTO auditaction (name) VALUES ('Created');
INSERT INTO auditaction (name) VALUES ('Deleted');
INSERT INTO auditaction (name) VALUES ('Added');
INSERT INTO auditaction (name) VALUES ('Removed');
INSERT INTO auditaction (name) VALUES ('Restored');
INSERT INTO auditaction (name) VALUES ('Edited');
INSERT INTO auditaction (name) VALUES ('Imported');

INSERT INTO audittarget (name) VALUES ('User');
INSERT INTO audittarget (name) VALUES ('Project');
INSERT INTO audittarget (name) VALUES ('Project Identifiers');
INSERT INTO audittarget (name) VALUES ('Location Model');
INSERT INTO audittarget (name) VALUES ('Location');

INSERT INTO material (name, primary) ('Genomic DNA', false);
INSERT INTO material (name, primary) ('Cell Free DNA', false);
INSERT INTO material (name, primary) ('EDTA Blood', true);
INSERT INTO material (name, primary) ('Streck Blood', true);
INSERT INTO material (name, primary) ('Roche Blood', true);
INSERT INTO material (name, primary) ('SST Blood', true);
INSERT INTO material (name, primary) ('Stool', true);
INSERT INTO material (name, primary) ('Urine', true);
-- INSERT INTO material (name, primary) ('Genomic DNA', );
-- INSERT INTO material (name, primary) ('Genomic DNA', );
-- INSERT INTO material (name, primary) ('Genomic DNA', );
-- INSERT INTO material (name, primary) ('Genomic DNA', );
-- INSERT INTO material (name, primary) ('Genomic DNA', );
-- INSERT INTO material (name, primary) ('Genomic DNA', );



-- 
-- 
-- 
-- CREATE TABLE pipeline (
--     id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
--     name VARCHAR NOT NULL, 
--     version VARCHAR NOT NULL, 
--     script VARCHAR NOT NULL, 
--     deleted BOOLEAN DEFAULT false NOT NULL, 
--     CONSTRAINT pk_pipeline PRIMARY KEY (id), 
--     CONSTRAINT uq_pipeline_name UNIQUE (name)
--     );
-- 
-- 
-- 
-- CREATE TABLE sequencing (
--     id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
--     name VARCHAR NOT NULL, 
--     platform VARCHAR NOT NULL, 
--     status VARCHAR NOT NULL, 
--     completion_datetime VARCHAR NOT NULL, 
--     attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
--     CONSTRAINT pk_sequencing PRIMARY KEY (id), 
--     CONSTRAINT uq_sequencing_name UNIQUE (name)
--     );
-- 
-- 
-- 
-- CREATE TABLE analysis (
--     id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
--     pipeline_id INTEGER, 
--     sequencing_id INTEGER, 
--     application VARCHAR, 
--     version VARCHAR NOT NULL, 
--     command_line VARCHAR NOT NULL, 
--     log VARCHAR NOT NULL, 
--     status VARCHAR NOT NULL, 
--     attr JSONB DEFAULT '{}'::jsonb NOT NULL, 
--     deleted BOOLEAN DEFAULT false NOT NULL, 
--     CONSTRAINT pk_analysis PRIMARY KEY (id), 
--     CONSTRAINT fk_analysis_pipeline_id_pipeline FOREIGN KEY (pipeline_id) REFERENCES pipeline (id), 
--     CONSTRAINT fk_analysis_sequencing_id_sequencing FOREIGN KEY (sequencing_id) REFERENCES sequencing (id)
--     );
-- 
-- 
-- 
-- CREATE TABLE file (
--     id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
--     name VARCHAR NOT NULL, 
--     collection_id INTEGER NOT NULL, 
--     analysis_id INTEGER, 
--     type VARCHAR NOT NULL, 
--     extension VARCHAR NOT NULL, 
--     creation_datetime TIMESTAMP WITH TIME ZONE NOT NULL, 
--     deleted BOOLEAN DEFAULT false NOT NULL, 
--     CONSTRAINT pk_file PRIMARY KEY (id), 
--     CONSTRAINT uq_file_name UNIQUE (name), 
--     CONSTRAINT fk_file_collection_id_collection FOREIGN KEY (collection_id) REFERENCES collection (id), 
--     CONSTRAINT fk_file_analysis_id_analysis FOREIGN KEY (analysis_id) REFERENCES analysis (id)
--     );
-- 
-- 
-- 
-- CREATE TABLE diskfile (
--     id INTEGER GENERATED BY DEFAULT AS IDENTITY, 
--     file_id INTEGER NOT NULL, 
--     size INTEGER NOT NULL, 
--     aws_bucket VARCHAR NOT NULL, 
--     aws_key VARCHAR NOT NULL, 
--     storage_class VARCHAR NOT NULL, 
--     status VARCHAR NOT NULL, 
--     deleted BOOLEAN DEFAULT false NOT NULL, 
--     CONSTRAINT pk_diskfile PRIMARY KEY (id), 
--     CONSTRAINT fk_diskfile_file_id_file FOREIGN KEY (file_id) REFERENCES file (id)
--     );
-- 
-- 
-- 
-- CREATE TABLE analysis_files (
--     file_id INTEGER NOT NULL, 
--     analysis_id INTEGER NOT NULL, 
--     CONSTRAINT uq_file_analysis_file_id UNIQUE (file_id, analysis_id), 
--     CONSTRAINT fk_file_analysis_file_id_file FOREIGN KEY (file_id) REFERENCES file (id), 
--     CONSTRAINT fk_file_analysis_analysis_id_analysis FOREIGN KEY (analysis_id) REFERENCES analysis (id)
--     );



