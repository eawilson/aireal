import pdb
from collections import defaultdict

from flask import session, request




def update_table(table, old_data, new_data, primary_keys, conn):
    """Performs modification of rows in target database table to facilitate a one to many relationship.

    Args:
        table (Table): Table object to be updated.
        old_data (list): Existing rows, list of dicts
        new_data (list): New rows, list of dicts
        primary_keys (list): Keys to uniquely identify each row, does not have to be the true primary key
        conn (Connection): Sqlalchemy connection.
        
    Returns:
        None
        
    Raises:
        KeyError if coding error and primary_keys not present in any row
        Database errors
    """
    inserts = []
    updates = []
    deletes = {tuple(row.pop(key) for key in primary_keys): row for row in old_data}
    for row in new_data:
        unmodified_row = row.copy()
        identifiers = tuple(row.pop(key) for key in primary_keys)
        try:
            if deletes.pop(identifiers) != row:
                updates += [([getattr(table.c, key) == val for key, val in zip(primary_keys, identifiers)], row)]
        except KeyError:
            inserts += [unmodified_row]
    
    for identifiers, values in updates:
        conn.execute(table.update().where(and_(*identifiers)).values(**values))
        
    if inserts:
        conn.execute(table.insert(), inserts)

    for identifiers in deletes:
        conn.execute(table.delete().where(and_(*[getattr(table.c, key) == val for key, val in zip(primary_keys, identifiers)])))



def update_o2m(table, old_data, new_data, primary_key, selected_key, default_data, conn, return_pks=False, update=True):
    """Performs modification of rows in target database table to facilitate a one to many relationship.

    Args:
        table (Table): Table object to be updated.
        old_data (dict): Rows currently in the database, is only required to contain selected_key and primary_key, all others are ignored.
        new_data (dict): New rows, required to contain seleceted_ky, all contained columns will be updated.
        primary_key (str): Name of key in old_data that maps to table.id.
        selected_key (str): Name of the key in both old_data and new_data that uniquely identifies the row.
        default_data (dict): additional value pairs to be set during inserts.
        conn (Connection): Sqlalchemy connection.
        return_pks (bool): If True then return pks of all inserted and updated rows, a bulk insert is used instead of multiple separate inserts if False.
        update (bool): If False then only perform insertions and deletions and do not update entries that already exist in the database.
        
    Returns:
        list: List of pks of all inserted and updated rows, will only be accurate if return_pks=True is passed in Args.
        
    Raises:
        KeyError: Will only raise an exception if the input data is corrupt eg missing primary or selected keys, this would be a coding error and should never happen.
    """
    pks = []
    old_selected_keys = {row[selected_key]: row for row in old_data}
    updates = []
    inserts = []
    for row in new_data:
        sk = row[selected_key]
        try:
            old_row = old_selected_keys.pop(sk)
            update_vals = {k: v for k, v in row.items() if v != old_row.get(k, None)}
            updates += [(old_row[primary_key], update_vals)]
        except KeyError:
            inserts += [{**default_data, **row}]
    
    if update:
        for pk, values in updates:
            conn.execute(table.update().where(table.c.id == pk).values(**values, **default_data))
            pks += [pk]
        
    if inserts:
        if return_pks:
            pks += [conn.execute(table.insert().values(**values)).inserted_primary_key[0] for values in inserts]
        else:
            conn.execute(table.insert().values(inserts))
    if old_selected_keys:
        conn.execute(table.delete().where(table.c.id.in_([row[primary_key] for row in old_selected_keys.values()])))
    return pks



def upsert(table, unique_data, other_data, conn):
    """Performs an insert of unique_data+other_data into table, if this violates a unique constraint then an update of other_data will be performed instead.

    Args:
        table (Table): Table object to be updated.
        unique_data (dict): Data that could potentially violate a unique constraint in table.
        other_data (dict): Data that could not violate a unique constraint in table.
        conn (Connection): Sqlalchemy connection.
        
    Returns:
        None.
        
    Raises:
        Should not raise any exceptions.
    """
    for row in unique_data:
        trans = conn.begin_nested()
        try:
            conn.execute(table.insert().values(**row, **other_data))
            trans.commit()
        except IntegrityError:
            trans.rollback()
            if other_data:
                conn.execute(table.update().where(and_(*[getattr(table.c, key) == val for key, val in row.items()])).values(**other_data))



#def m2m(primary_id, table, primary_column, linking_column, old_linking_ids, new_linking_ids, conn):
    #old = set(old_linking_ids)
    #new = set(new_linking_ids)
    #to_insert = new - old
    #to_delete = old - new
    #if to_insert:
        #conn.execute(table.insert().values([{primary_column.name: primary_id, linking_column.name: item_id} for item_id in to_insert]))
    #if to_delete:
        #conn.execute(table.delete().where(and_(primary_column == primary_id, linking_column.in_(to_delete))))



##def m2m(table, new_data, old_data, conn):
    ##to_insert = [data for data in new_data if data not in old_data]
    ##if to_insert:
        ##conn.execute(table.insert().values(to_insert))

    ##to_delete = [data for data in old_data if data not in new_data]
    ##if to_delete:
        ##if len(to_delete) > 1:
            ##common_data = {}
            ##for k, v in old_data[0].items():
                ##if all(data[k] == v for data in old_data[1:]):
                    ##common_data[k] = v
            ##if len(common_data) == len(old_data[0]) - 1:
                ##for k in old_data.keys():
                    ##if k not in common_data:
                        ##break
                ##where_clauses = [getattr(table.c, k).in_([data[k] for data in old_data])]
                ##for k, v in common_data.items():
                    ##where_clauses += [getattr(table.c, k) == v]
                ##conn.execute(table.delete().where(*where_clauses))
                ##return
        
        ##for data in to_delete:
            ##conn.execute(table.delete().where(and_(*[getattr(table.c, k) == v
                                                     ##for k, v in data.items()])))

























#def edit_m2m(table, row_id, m2mtable, values, old_values, choices, conn):
    #new_ids = set(values)
    #old_ids = set(old_values)
    #to_ins = new_ids - old_ids
    #to_del = old_ids - new_ids
    #if not (to_ins or to_del):
        #return
    
    #if len(m2mtable.c) != 2:
        #raise RuntimeError(f"{m2mtable.name} is not a valid linking table.")
    #for col in m2mtable.c:
        #foreign = tuple(col.foreign_keys)[0].column.table
        #if foreign == table:
            #primary = col
        #else:
            #secondary = col
            #other = foreign
    #names = dict(choice[:2] for choice in choices)
    
    #if to_ins:
        #data = [{primary.name: row_id, secondary.name: sec_id}
                #for sec_id in to_ins]
        #conn.execute(m2mtable.insert(), data)
        #items = ", ".join(names[sec_id] for sec_id in to_ins)
        #details = {other.name: items}
        #crudrecord(table.name, row_id, "Added", details, conn)
    
    #if to_del:
        #sql = m2mtable.delete().where(and_(primary == row_id,
                                           #secondary.in_(to_del)))
        #conn.execute(sql)
        #items = ", ".join(names[sec_id] for sec_id in to_del)
        #details = {other.name: items}
        #crudrecord(table.name, row_id, "Removed", details, conn)



#def admin_edit(table, row_id, values, old_values, conn, calculated_values={}):
    #values = {k: v for k, v in values.items() if not isinstance(v, list)}
    #if row_id is None:
        #sql = table.insert().values(**values, **calculated_values)
        #row_id = conn.execute(sql).inserted_primary_key[0]
        #action = "Created"
    #else:
        #sql = table.update(). \
                #where(table.c.id == row_id). \
                #values(**values, **calculated_values)
        #conn.execute(sql)
        #action = "Edited"

    #deleted = values.pop("deleted", None)
    #changed_values = {k: v for k, v 
                      #in values.items() 
                      #if v != old_values.get(k, None)}
    #if changed_values:
        #crudrecord(table.name, row_id, action, changed_values, conn)
    #if deleted is not None:
        #action = "Deleted" if deleted else "Restored"
        #crudrecord(table.name, row_id, action, {}, conn)
    #return row_id











def krud(cur, table, new, old={}, logable_columns=(), **choices):
    changed = {}
    for k, v in new.items():
        if not isinstance(v, list) and v != old.get(k, None):
            changed[k] = v
    
    if "id" in old:
        action = "Edited"
        row_id = old["id"]
        if changed:
            assignments = ", ".join(f"{k} = %({k})s" for k in changed.keys())
            sql = f"UPDATE {table} SET {assignments} WHERE id = {row_id};"
            cur.execute(sql, changed)
    else:
        keys = sorted(changed.keys())
        columns = ", ".join(keys)
        values = ", ".join(f"%({k})s" for k in keys)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING id;"
        cur.execute(sql, changed)
        row_id = cur.fetchone()[0]
        action = "Created"

    deleted = changed.pop("deleted", None)
    details = {}
    for k, v in changed.items():
        if k in loggable.get(table, ()):
            if isinstance(v, dict):
                old_attr = old[k]
                for attr_k, attr_v in v.items():
                    if not attr_v.statswith("_") and attr_v != old_attr.get(attr_k, None):
                        details[attr_k] = attr_v
            else:
                for option in choices.get(k, ()):
                    if option[0] == v:
                        if k.endswith("_id"):
                            k = k[:-3]
                        v = option[1]
                        break
                details[k] = v
    if action == "Created" or details:
        crudrecord(cur, table=table, row_id=row_id, action=action, details=details)
    
    for k, v in new.items():
        if isinstance(v, list):
            new_ids = set(v)
            old_ids = set(old.get(k, ()))
            to_ins = sorted(new_ids - old_ids)
            to_del = sorted(old_ids - new_ids)
            link_table, col1, col2 = joins[table][k]
            names = dict(choices[k])
            
            if to_ins:
                sql = f"INSERT INTO {link_table} ({col1}, {col2}) VALUES (%({col1})s, %({col2})s);"
                data = [{col1: row_id, col2: sec_id} for sec_id in to_ins]
                cur.executemany(sql, data)
                items = ", ".join(names[sec_id] for sec_id in to_ins)
                crudrecord(cur, table=table, row_id=row_id, action="Added", details={k: items})
            
            if to_del:
                sql = f"DELETE FROM {link_table} WHERE {col1} = %({col1})s AND {col2} = %({col2})s;"
                data = [{col1: row_id, col2: sec_id} for sec_id in to_del]
                cur.executemany(sql, data)
                items = ", ".join(names[sec_id] for sec_id in to_del)
                crudrecord(cur, table=table, row_id=row_id, action="Removed", details={k: items})
        
    if deleted is not None:
        action = "Deleted" if deleted else "Restored"
        crudrecord(cur, table=table, row_id=row_id, action=action)
    return row_id
    _("Created")
    _("Edited")
    _("Added")
    _("Removed")
    _("Deleted")
    _("Restored")




def crudrecord(cur, **data):
    details = data.get("details", {})
    data["details"] = "\t".join(f"{k}={v}" for k, v in sorted(details.items()))
    data["user_id"] = session.get("id", None)
    
    sql = "INSERT INTO crudrecord (tablename, row_id, action, details, user_id) VALUES" \
          " (%(table)s, %(row_id)s, %(action)s, %(details)s, %(user_id)s)"
    cur.execute(sql, data)













def record_edit(cur, tablename, new, old={}, labels={}, **choices):
    details = {}
    edited = {}
    addedremoved = defaultdict(dict)
    for k, v in list(new.items()):
        if isinstance(v, list):
            new_ids = set(v)
            old_ids = set(old.get(k, ()))
            addedremoved[k]["Added"] = sorted(new_ids - old_ids)
            addedremoved[k]["Removed"] = sorted(old_ids - new_ids)
        
        elif isinstance(v, dict):
            edited[k] = v
            for k1, v1 in set(v.items()) - set(old.get(k, {}).items()):
                details[labels.get(k)] = v
        
        elif v != old.get(k, None):
            edited[k] = v
            for option in choices.get(k, ()):
                if option[0] == v:
                    details[labels.get(k)] = option[1]
                    break
            else:
                details[labels.get(k)] = v

    # No matching label therefore not user entered therefore don't record
    details.pop(None, None)
    
    keys = sorted(edited.keys())
    if "id" in old:
        action = "Edited"
        row_id = old["id"]
        if edited:
            updates = ", ".join(f"{k} = %({k})s" for k in keys)
            sql = f"UPDATE {tablename} SET {updates} WHERE id = {row_id};"
            cur.execute(sql, edited)
    else:
        action = "Created"
        columns = ", ".join(keys)
        values = ", ".join(f"%({k})s" for k in keys)
        sql = f"INSERT INTO {tablename} ({columns}) VALUES ({values}) RETURNING id;"
        cur.execute(sql, edited)
        row_id = cur.fetchone()[0]
    
    
    log_sql = """INSERT INTO editrecord (tablename, row_id, action, details, users_id, ip_address)
                 VALUES (%(tablename)s, %(row_id)s, %(action)s, %(details)s, %(users_id)s, %(ip_address)s);"""
    log_data = {"tablename": tablename,
                "row_id": row_id,
                "users_id": session.get("id", None),
                "ip_address": request.remote_addr}
    
    if action == "Created" or details:
        cur.execute(log_sql, {"action": action, "details": details, **log_data})
    
    for foreigntable, actions in addedremoved.items():
        for action, keys in actions.items():
            if keys:
                linktable = "_".join(sorted((tablename, foreigntable)))
                values = [{"local": row_id, "foreign": key} for key in keys]
                foreignkey = f"{foreigntable}_id" if isinstance(keys[0], int) else "name"
                if action == "Added":
                    sql = f"INSERT INTO {linktable} ({tablename}_id, {foreignkey}) VALUES (%(local)s, %(foreign)s);"
                else:
                    sql = f"DELETE FROM {linktable} WHERE {tablename}_id = %(local)s AND {foreignkey} = %(foreign)s;"
                cur.executemany(sql, values)
                details = {labels[foreigntable]: [option[1] for option in choices[foreigntable] if option[0] in keys]}
                cur.execute(log_sql, {"action": action, "details": details, **log_data})
            
    if "deleted" in edited:
        action = "Deleted" if deleted else "Restored"
        cur.execute(log_sql, {"action": action, "details": None, **log_data})
    return row_id
    _("Created")
    _("Edited")
    _("Added")
    _("Removed")
    _("Deleted")
    _("Restored")






def record_form(cur, tablename, action, row_id, form, old={}):
    edited = {}
    added = defaultdict(list)
    removed = defaultdict(list)
    
    for fieldname, field in form.items():
        try:
            data = field.data
        except AttributeError:
            continue
        
        if data != old.get(fieldname):
            label = field._label.unlocalised
            if isinstance(data, list):
                new_ids = set(data)
                old_ids = set(old.get(fieldname, ()))
                add_ids = new_ids - old_ids
                del_ids = old_ids - new_ids
                for choice in field.choices:
                    if choice[0] in add_ids:
                        added[label].append(getattr(choice[1], "unlocalised", choice[1]))
                    elif choice[0] in del_ids:
                        removed[label].append(getattr(choice[1], "unlocalised", choice[1]))
            
            else:
                for choice in getattr(field, "choices", ()):
                    if choice[0] == data:
                        data = getattr(choice[1], "unlocalised", choice[1])
                        break
                edited[label] = data

    deleted = edited.pop("deleted", None)
    
    sql = """INSERT INTO editrecord (tablename, row_id, action, details, users_id, ip_address)
             VALUES (%(tablename)s, %(row_id)s, %(action)s, %(details)s, %(users_id)s, %(ip_address)s);"""
    values = {"tablename": tablename,
              "row_id": row_id,
              "users_id": session.get("id", None),
              "ip_address": request.remote_addr}
    
    if edited:
        cur.execute(sql, {"action": action, "details": edited, **values})
    
    if added:
        cur.execute(sql, {"action": "Added", "details": added, **values})
    
    if removed:
        cur.execute(sql, {"action": "Removed", "details": removed, **values})
    
    if deleted is not None:
        cur.execute(sql, {"action": "Deleted" if deleted else "Restored", **values})
    
    return row_id
    _("Created")
    _("Edited")
    _("Added")
    _("Removed")
    _("Deleted")
    _("Restored")



def perform_edit(cur, tablename, new, old={}, form=None):
    edited = {}
    added = {}
    removed = {}
    
    for k, v in new.items():
        if isinstance(v, list):
            new_ids = set(v)
            old_ids = set(old.get(k, ()))
            added[k] = sorted(new_ids - old_ids)
            removed[k] = sorted(old_ids - new_ids)
        
        elif v != old.get(k):
            edited[k] = v
    
    keys = edited.keys()
    if "id" in old:
        action = "Edited"
        row_id = old["id"]
        if edited:
            updates = ", ".join(f"{k} = %({k})s" for k in keys)
            sql = f"UPDATE {tablename} SET {updates} WHERE id = {row_id};"
            cur.execute(sql, edited)
    else:
        action = "Created"
        columns = ", ".join(keys)
        values = ", ".join(f"%({k})s" for k in keys)
        sql = f"INSERT INTO {tablename} ({columns}) VALUES ({values}) RETURNING id;"
        cur.execute(sql, edited)
        row_id = cur.fetchone()[0]
    
    for foreignname, keys in added.items():
        if keys:
            linktable = "_".join(sorted((tablename, foreignname)))
            foreignkey = f"{foreignname}_id" if isinstance(keys[0], int) else "name"
            values = [{"local": row_id, "foreign": k} for k in keys]
            sql = f"INSERT INTO {linktable} ({tablename}_id, {foreignkey}) VALUES (%(local)s, %(foreign)s);"
            cur.executemany(sql, values)
        
    for foreignname, keys in removed.items():
        if keys:
            linktable = "_".join(sorted((tablename, foreignname)))
            foreignkey = f"{foreignname}_id" if isinstance(keys[0], int) else "name"
            values = [{"local": row_id, "foreign": k} for k in keys]
            sql = f"DELETE FROM {linktable} WHERE {tablename}_id = %(local)s AND {foreignkey} = %(foreign)s;"
            cur.executemany(sql, values)
    
    if form:
        record_form(cur, tablename, action, row_id, form, old)
    return row_id



def perform_delete(cur, tablename, row_id, pk="id"):
    sql = f"UPDATE {tablename} SET deleted = true WHERE deleted = false AND {pk} = %(row_id)s;"
    cur.execute(sql, {"row_id": row_id})
    if cur.rowcount:
        sql = """INSERT INTO editrecord (tablename, row_id, action, users_id, ip_address)
                 VALUES (%(tablename)s, %(row_id)s, %(action)s, %(users_id)s, %(ip_address)s);"""
        cur.execute(sql, {"tablename": tablename,
                          "row_id": row_id,
                          "action": "Deleted",
                          "users_id": session.get("id", None),
                          "ip_address": request.remote_addr})
    
    
    
def perform_restore(cur, tablename, row_id, pk="id"):
    sql = f"UPDATE {tablename} SET deleted = false WHERE deleted = true AND {pk} = %(row_id)s;"
    cur.execute(sql, {"row_id": row_id})
    if cur.rowcount:
        sql = """INSERT INTO editrecord (tablename, row_id, action, users_id, ip_address)
                 VALUES (%(tablename)s, %(row_id)s, %(action)s, %(users_id)s, %(ip_address)s);"""
        cur.execute(sql, {"tablename": tablename,
                          "row_id": row_id,
                          "action": "Restored",
                          "users_id": session.get("id", None),
                          "ip_address": request.remote_addr})
    
    
    

