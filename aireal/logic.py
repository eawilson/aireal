import pdb
from collections import defaultdict

from flask import session, request















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
    
    
    

