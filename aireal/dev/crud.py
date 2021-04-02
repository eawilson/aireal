import pdb
from collections import OrderedDict, defaultdict
from inspect import signature

from sqlalchemy import select, join, or_, and_
from sqlalchemy.exc import IntegrityError


from flask import redirect, url_for, request, Blueprint, current_app, session
from werkzeug.exceptions import Conflict, Forbidden, BadRequest

from .utils import url_fwrd, url_back, tablerow, navbar, abort, engine, login_required, surname_forename, render_page, unique_violation_or_reraise
from .forms import ReorderForm
from . import logic
from .models import metadata
from .i18n import _

__all__ = ("list_view", "reorder_view", "upsert_view", "crud_route", "app")



class MergedColumn(object):
    def __repr__(self):
        return "MergedColumn({})".format(repr(self._vals))
    
    def __init__(self, val):
        self._vals = [val]

    def __str__(self):
        return ", ".join(str(val) for val in self._vals)

    def merge(self, val):
        if val not in self._vals:
            self._vals.append(val)



class MemoryDict(OrderedDict):
    def __missing__(self, key):
        self[key] = ""
        return ""



def make_join(primary_table, foreign_table, reverse=False):
    for column in primary_table.c:
        if column.foreign_keys:
            foreign_column = tuple(column.foreign_keys)[0].column
            if foreign_column.table == foreign_table:
                table = foreign_table if not reverse else primary_table
                return (table, column == foreign_column)



def make_joins(tables):
    if len(tables) == 1:
        return tables[0]
    primary_table = tables[0]
    m2m_tables = []
    joinplans = []
    for foreign_table in tables[1:]:
        joinplan = make_join(primary_table, foreign_table) or \
                   make_join(foreign_table, primary_table, reverse=True)
        if joinplan:
            joinplans += [joinplan]
        else:
            m2m_tables += [foreign_table]

    for foreign_table in m2m_tables:
        for linking_table in primary_table.metadata.sorted_tables:
            if linking_table not in tables:
                joinplan = [make_join(linking_table, primary_table, reverse=True), make_join(linking_table, foreign_table)]
                if None not in joinplan:
                    joinplans += joinplan
                    break
    selectable = join(primary_table, *joinplans[0], isouter=True)
    for joinplan in joinplans[1:]:
        selectable = selectable.join(*joinplan, isouter=True)
    return selectable                



def list_view(*table_definition, title=None, toplevel=False):#, **filters):
    """ table_definition consists of a list of tuples. Each tuple has three
        eleents (name, stupidtable datatype, contents).
    """
    head, fields = zip(*table_definition)
    memory = MemoryDict()
    for column in fields:
        if hasattr(column, "__call__"):
            column(memory)
        else:
            memory[column]
    columns = list(memory.keys())
    tables = list(OrderedDict((column.table, None) for column
                              in columns).keys())
    primary_table = tables[0]
    columns += [primary_table.c.id]
    if "deleted" in primary_table.c:
        columns += [primary_table.c.deleted]
    upsert_endpoint = "admin.{}_upsert".format(primary_table.name)
    reorder_endpoint = "admin.{}_reorder".format(primary_table.name)

    order = []
    for table in tables:
        if "order" in table.c:
            order += [table.c.order]
        elif "surname" in table.c and "forename" in table.c:
            order += [table.c.surname, table.c.forename]
        elif "name" in table.c:
            order += [table.c.name]
    
    sql = select(columns).select_from(make_joins(tables)).order_by(*order)
    
    buttons = {}
    if "deleted" in primary_table.c:
        args = dict(request.args)
        show = args.pop("show", False)
        if show:
            buttons["info"] = (_("Hide Deleted"), url_for(request.endpoint, **request.view_args, **args))
        else:
            sql = sql.where(primary_table.c.deleted == False)
            buttons["info"] = (_("Show Deleted"), url_for(request.endpoint, show="True", **request.view_args, **args))
            
    #if filters:
        #where_clauses = [getattr(primary_table.c, key) == val for key, val
                         #in filters.items()]
        #sql = sql.where(*where_clauses)
    
    if upsert_endpoint in current_app.view_functions:
        clickable = True
    else:
        href = None
    body = OrderedDict()
    with engine.connect() as conn:
        for row in conn.execute(sql):
            columns = []
            for column in fields:
                val = column(row) if hasattr(column, "__call__") else row[column]
                columns += [val]
                
            if row["id"] in body:
                if not isinstance(body[row["id"]][0][0], MergedColumn):
                    body[row["id"]] = ([MergedColumn(col) for col in body[row["id"]][0]], body[row["id"]][1])
                for prevcol, newcol in zip(body[row["id"]][0], columns):
                    prevcol.merge(newcol)
            else:
                if clickable:
                    href = url_fwrd(upsert_endpoint, row_id=row["id"])
                deleted = row["deleted"] if "deleted" in row else False
                body[row["id"]] = tablerow(*columns,
                                           deleted=deleted,
                                           href=href)
    
    if upsert_endpoint in current_app.view_functions:
        function = current_app.view_functions[upsert_endpoint]
        if list(signature(function).parameters.items())[0][1].default is None:
            buttons["new"] = ("", url_fwrd(upsert_endpoint))
    
    if not toplevel:
        buttons["back"] = (_("Back"), url_back())
    #if reorder_endpoint in current_app.view_functions:
        #buttons += [("Reorder", {"href": url_fwrd(reorder_endpoint), "class": "float-right"})]
    return render_page("table.html",
                       title=title or primary_table.name.title(),
                       table={"head": head, "body": body.values()},
                       buttons=buttons)







def reorder_view(primary_table):
    columns = [primary_table.c.name]
    sql = select(columns)
    if "deleted" in primary_table.c:
        sql = sql.where(primary_table.c.deleted == False)
    sql = sql.order_by(primary_table.c.order)

    with engine.begin() as conn:
        items = [row[0] for row in conn.execute(sql)]
        form = ReorderForm(request.form)
        
        if request.method == "POST" and form.validate():
            for index, name in enumerate(form.order.data.split(",")[:-1]):
                logic.admin_update(primary_table,
                                   where=(primary_table.c.name == name),
                                   values={"order": index},
                                   conn=conn)
            return redirect(url_back())
                
    buttons = [(_("Save"), {"submit": url_for(request.endpoint)}),
               (_("Back"), {"href": url_back()})]
    title = _("Reorder {}").format(primary_table.name.title())
    return  render_page("reorder.html",
                            title=title,
                            items=items,
                            form=form,
                            buttons=buttons,
                            active="Tables")



def upsert_view(row_id, primary_table, FormClass):
    with engine.begin() as conn:
        form = FormClass()
        choices = {}
        columns = [primary_table.c[name] for name in form.keys() if name in primary_table.c]
        columns += [primary_table.c.id]
        if "deleted" in primary_table.c:
            columns += [primary_table.c.deleted]

        if row_id is not None:
            sql = select(columns).where(primary_table.c.id == row_id)
            old_data = dict(conn.execute(sql).first() or abort(BadRequest))
        else:
            old_data = {}
            
        for name, field in form.items():
            if hasattr(field, "choices"):

                # Many to one relationship
                if name in primary_table.c:
                    column = primary_table.c[name]
                    foreign_table = tuple(column.foreign_keys)[0].column.table
                    sql = select([foreign_table.c.id, foreign_table.c.name]). \
                            order_by(foreign_table.c.name)
                    if "deleted" in foreign_table.c:
                        where = (foreign_table.c.deleted == False)
                        if row_id is not None:
                            where = or_(where, foreign_table.c.id == old_data[name])
                        sql = sql.where(where)
                    rows = [tuple(row) for row in conn.execute(sql)]
                
                # Many to many relationship
                else:
                    foreign_table = metadata.tables[name]
                    m2mtable, primary, secondary = logic._linking_table(primary_table, foreign_table)
                    sql = select([foreign_table.c.id, foreign_table.c.name, primary]). \
                            select_from(join(foreign_table, m2mtable, and_(foreign_table.c.id == secondary, primary == row_id), isouter=True)). \
                            order_by(foreign_table.c.name)
                    if "deleted" in foreign_table.c:
                        where = (foreign_table.c.deleted == False)
                        if row_id is not None:
                            where = or_(where, primary_col == row_id)
                        sql = sql.where(where)
                    rows = [tuple(row) for row in conn.execute(sql)]
                    if row_id is not None:
                        old_data[name] = [row[0] for row in rows if row[2]]
                   
                choices[name] = field.choices = [tuple(row)[:2] for row in conn.execute(sql)]
 
        form.fill(request.form if request.method == "POST" else old_data)

        if request.method == "POST" and form.validate():
            new_data = form.data
            action = request.args.get("action", "") if "deleted" in primary_table.c else ""
            if action == "Delete":
                new_data["deleted"] = True
            elif action == "Restore":
                new_data["deleted"] = False
            
            try:
                row_id = logic.crud(conn, primary_table, new_data, old_data, **choices)
            except IntegrityError as e:
                form[unique_violation_or_reraise(e)].errors = _("Must be unique.")
            else:
                return redirect(url_back())

    title = _("Edit") if row_id is not None else _("New")
    buttons = {"submit": (_("Save"), url_for(request.endpoint, row_id=row_id)),
               "back": (_("Cancel"), url_back())}
    if row_id is not None and "deleted" in primary_table.c:
        action = _("Restore") if old_data["deleted"] else _("Delete")
        url = url_for(request.endpoint, row_id=row_id, action=action)
        buttons["danger"] = (action, url)
    if row_id is not None:
        url = url_fwrd(".editlog", tablename=primary_table.name, row_id=row_id)
        buttons["info"] = (_("History"), url)
    return render_page("form.html", form=form, buttons=buttons, title=title)



