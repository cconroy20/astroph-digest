"""Extract the Zotero library (regular items only) to data/library_zotero.json.

Reads a copy of zotero.sqlite (+WAL) so it is safe while Zotero is open.
"""
import json, os, re, shutil, sqlite3, tempfile

ZDIR = os.path.expanduser("~/software/Zotero")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "library_zotero.json")

tmp = tempfile.mkdtemp()
for suf in ("", "-wal"):
    src = os.path.join(ZDIR, "zotero.sqlite" + suf)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(tmp, "z.sqlite" + suf))
db = sqlite3.connect(os.path.join(tmp, "z.sqlite"))
q = lambda sql, *a: db.execute(sql, a).fetchall()

trashed = {r[0] for r in q("select itemID from deletedItems")}
items = q("""select i.itemID, i.key, t.typeName, i.dateAdded from items i join itemTypes t using(itemTypeID)
             where t.typeName not in ('attachment','note','annotation')""")

fields = {}
for iid, fname, val in q("""select d.itemID, f.fieldName, v.value from itemData d
                            join fields f using(fieldID) join itemDataValues v using(valueID)"""):
    fields.setdefault(iid, {})[fname] = val

creators = {}
for iid, last, first, ctype, order in q("""select ic.itemID, c.lastName, c.firstName, ct.creatorType, ic.orderIndex
        from itemCreators ic join creators c using(creatorID) join creatorTypes ct using(creatorTypeID)
        order by ic.itemID, ic.orderIndex"""):
    creators.setdefault(iid, []).append({"last": last, "first": first, "type": ctype})

colls = {cid: (name, parent) for cid, name, parent in q("select collectionID, collectionName, parentCollectionID from collections")}
def cpath(cid):
    name, parent = colls[cid]
    return cpath(parent) + "/" + name if parent else name
itemcolls = {}
for iid, cid in q("select itemID, collectionID from collectionItems"):
    itemcolls.setdefault(iid, []).append(cpath(cid))

tags = {}
for iid, name in q("select it.itemID, t.name from itemTags it join tags t using(tagID)"):
    tags.setdefault(iid, []).append(name)

out = []
for iid, key, typ, added in items:
    if iid in trashed:
        continue
    f = fields.get(iid, {})
    out.append({
        "key": key, "type": typ, "dateAdded": added,
        "title": f.get("title", ""), "abstract": f.get("abstractNote", ""),
        "date": f.get("date", ""), "doi": f.get("DOI", ""), "url": f.get("url", ""),
        "extra": f.get("extra", ""), "journal": f.get("publicationTitle", ""),
        "archiveID": f.get("archiveID", ""),
        "authors": creators.get(iid, []),
        "collections": sorted(itemcolls.get(iid, [])),
        "tags": [t for t in tags.get(iid, []) if not t.startswith("zotfix:")],
    })
json.dump(out, open(OUT, "w"), indent=1)
print(len(out), "items ->", os.path.abspath(OUT))
print("no collection:", sum(1 for o in out if not o["collections"]))
shutil.rmtree(tmp)
