"""Base system.

Revision ID: cbddd0e7fb6a
Revises: 
Create Date: 2021-04-02 13:08:20.958975

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cbddd0e7fb6a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('groups',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_groups')),
    sa.UniqueConstraint('name', name=op.f('uq_groups_name'))
    )
    op.create_table('materials',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_materials'))
    )
    op.create_table('pipelines',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('script', sa.String(), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pipelines')),
    sa.UniqueConstraint('name', name=op.f('uq_pipelines_name'))
    )
    op.create_table('sequencings',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('platform', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('completion_datetime', sa.String(), nullable=False),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sequencings')),
    sa.UniqueConstraint('name', name=op.f('uq_sequencings_name'))
    )
    op.create_table('sites',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sites')),
    sa.UniqueConstraint('name', name=op.f('uq_sites_name'))
    )
    op.create_index(op.f('ix_sites_deleted'), 'sites', ['deleted'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('forename', sa.String(), nullable=False),
    sa.Column('surname', sa.String(), nullable=False),
    sa.Column('last_session', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('restricted', sa.Boolean(name='Bool'), nullable=True),
    sa.Column('totp_secret', sa.String(), nullable=True),
    sa.Column('password', sa.String(), nullable=True),
    sa.Column('reset_datetime', sa.String(), nullable=True),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('analyses',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('pipeline_id', sa.Integer(), nullable=True),
    sa.Column('sequencing_id', sa.Integer(), nullable=True),
    sa.Column('application', sa.String(), nullable=True),
    sa.Column('version', sa.String(), nullable=True),
    sa.Column('command_line', sa.String(), nullable=False),
    sa.Column('log', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], name=op.f('fk_analyses_pipeline_id_pipelines')),
    sa.ForeignKeyConstraint(['sequencing_id'], ['sequencings.id'], name=op.f('fk_analyses_sequencing_id_sequencings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_analyses'))
    )
    op.create_table('logs',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('tablename', sa.String(), nullable=False),
    sa.Column('row_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('details', sa.String(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('datetime', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_logs_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_logs'))
    )
    op.create_index(op.f('ix_logs_row_id'), 'logs', ['row_id'], unique=False)
    op.create_index(op.f('ix_logs_tablename'), 'logs', ['tablename'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.Column('subject_attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('collection_attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('pipeline_id', sa.Integer(), nullable=True),
    sa.Column('default_pipeline_options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], name=op.f('fk_projects_pipeline_id_pipelines')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    sa.UniqueConstraint('name', name=op.f('uq_projects_name')),
    sa.UniqueConstraint('name', name=op.f('uq_projects_name'))
    )
    op.create_index(op.f('ix_projects_deleted'), 'projects', ['deleted'], unique=False)
    op.create_table('users_groups',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_users_groups_group_id_groups')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_users_groups_user_id_users')),
    sa.UniqueConstraint('user_id', 'group_id', name=op.f('uq_users_groups_user_id'))
    )
    op.create_table('users_sites',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_users_sites_site_id_sites')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_users_sites_user_id_users')),
    sa.UniqueConstraint('user_id', 'site_id', name=op.f('uq_users_sites_user_id'))
    )
    op.create_table('subjects',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_subjects_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subjects')),
    sa.UniqueConstraint('project_id', 'name', name=op.f('uq_subjects_project_id'))
    )
    op.create_table('users_projects',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_users_projects_project_id_projects')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_users_projects_user_id_users')),
    sa.UniqueConstraint('user_id', 'project_id', name=op.f('uq_users_projects_user_id'))
    )
    op.create_table('collections',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('collection_datetime', sa.DateTime(timezone=True), nullable=True),
    sa.Column('received_datetime', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_collections_subject_id_subjects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_collections'))
    )
    op.create_table('files',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('collection_id', sa.Integer(), nullable=False),
    sa.Column('analysis_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('extension', sa.String(), nullable=False),
    sa.Column('creation_datetime', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], name=op.f('fk_files_analysis_id_analyses')),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], name=op.f('fk_files_collection_id_collections')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_files')),
    sa.UniqueConstraint('name', name=op.f('uq_files_name'))
    )
    op.create_table('samples',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('collection_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('material_id', sa.Integer(), nullable=False),
    sa.Column('creation_datetime', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], name=op.f('fk_samples_collection_id_collections')),
    sa.ForeignKeyConstraint(['material_id'], ['materials.id'], name=op.f('fk_samples_material_id_materials')),
    sa.ForeignKeyConstraint(['parent_id'], ['subjects.id'], name=op.f('fk_samples_parent_id_subjects')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_samples_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_samples'))
    )
    op.create_table('slides',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('collection_id', sa.Integer(), nullable=True),
    sa.Column('directory_name', sa.String(), nullable=False),
    sa.Column('user_directory_timestamp', sa.String(), nullable=False),
    sa.Column('created_datetime', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attr', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], name=op.f('fk_slides_collection_id_collections')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_slides_project_id_projects')),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_slides_site_id_sites')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_slides_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_slides')),
    sa.UniqueConstraint('name', name=op.f('uq_slides_name')),
    sa.UniqueConstraint('user_directory_timestamp', name=op.f('uq_slides_user_directory_timestamp'))
    )
    op.create_table('diskfiles',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('aws_bucket', sa.String(), nullable=False),
    sa.Column('aws_key', sa.String(), nullable=False),
    sa.Column('storage_class', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('deleted', sa.Boolean(name='bool'), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['files.id'], name=op.f('fk_diskfiles_file_id_files')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_diskfiles'))
    )
    op.create_table('files_analyses',
    sa.Column('file_id', sa.Integer(), nullable=False),
    sa.Column('analysis_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], name=op.f('fk_files_analyses_analysis_id_analyses')),
    sa.ForeignKeyConstraint(['file_id'], ['files.id'], name=op.f('fk_files_analyses_file_id_files')),
    sa.UniqueConstraint('file_id', 'analysis_id', name=op.f('uq_files_analyses_file_id'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('files_analyses')
    op.drop_table('diskfiles')
    op.drop_table('slides')
    op.drop_table('samples')
    op.drop_table('files')
    op.drop_table('collections')
    op.drop_table('users_projects')
    op.drop_table('subjects')
    op.drop_table('users_sites')
    op.drop_table('users_groups')
    op.drop_index(op.f('ix_projects_deleted'), table_name='projects')
    op.drop_table('projects')
    op.drop_index(op.f('ix_logs_tablename'), table_name='logs')
    op.drop_index(op.f('ix_logs_row_id'), table_name='logs')
    op.drop_table('logs')
    op.drop_table('analyses')
    op.drop_table('users')
    op.drop_index(op.f('ix_sites_deleted'), table_name='sites')
    op.drop_table('sites')
    op.drop_table('sequencings')
    op.drop_table('pipelines')
    op.drop_table('materials')
    op.drop_table('groups')
    # ### end Alembic commands ###
