from pathlib import Path
import sqlite3, os, shutil, datetime

src=Path(os.environ.get("EBL_DB_PATH","ebl.db"))
if not src.exists():
    raise SystemExit(f"Database not found: {src}")
outdir=Path(os.environ.get("EBL_BACKUP_DIR","backups"))
outdir.mkdir(parents=True,exist_ok=True)
stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
dst=outdir/f"ebl_genesis_{stamp}.db"
c=sqlite3.connect(src)
b=sqlite3.connect(dst)
c.backup(b)
b.close();c.close()
print(dst)
